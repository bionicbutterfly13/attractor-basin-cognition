# SPDX-License-Identifier: Apache-2.0
import hashlib
import logging
import datetime as _dt
from typing import Dict, List, Optional, Any
import numpy as np

from elume.basins.hopfield import HopfieldNetwork, ConvergenceResult
from .state import BasinState
from .protocols import BasinCacheProvider, SharedModuleRegistry, EventPublisher

logger = logging.getLogger(__name__)


class CoreAttractorService:
    """
    Pure mathematical core for attractor basin operations.
    Dependencies (caching, events, module registry, field engine) are injected.
    """

    HEBBIAN_INCREMENT: float = 0.2

    def __init__(
        self,
        n_units: int = 128,
        basin_cache: Optional[BasinCacheProvider] = None,
        shared_module_registry: Optional[SharedModuleRegistry] = None,
        event_publisher: Optional[EventPublisher] = None,
        field_engine: Any = None,  # Will type properly when field is extracted
    ):
        self.n_units = n_units
        self.network = HopfieldNetwork(n_units)
        self.basins: Dict[str, BasinState] = {}

        self.basin_cache = basin_cache
        self.shared_module_registry = shared_module_registry
        self.event_publisher = event_publisher
        self.field_engine = field_engine

    def _basin_to_cache_dict(self, basin: BasinState) -> Dict[str, Any]:
        return {
            "name": basin.name,
            "energy": float(basin.energy),
            "activation": float(basin.activation),
            "stability": float(basin.stability),
            "metadata": basin.metadata,
            "pattern": basin.pattern.tolist() if basin.pattern is not None else None,
            "strength": float(basin.strength),
            "activation_count": basin.activation_count,
            "activation_history": basin.activation_history,
        }

    def _write_cache(self, basin: BasinState) -> None:
        if self.basin_cache is None:
            return
        payload = self._basin_to_cache_dict(basin)
        ok = self.basin_cache.set_basin(basin.name, payload)
        if not ok:
            logger.warning("Basin cache write failed for '%s'; continuing without cache.", basin.name)

    def _invalidate_cache(self, name: str) -> None:
        if self.basin_cache is None:
            return
        ok = self.basin_cache.invalidate_basin(name)
        if not ok:
            logger.warning("Basin cache invalidation failed for '%s'; cache may be stale.", name)

    def _content_to_pattern(self, content: str) -> np.ndarray:
        content_hash = hashlib.sha256(content.encode()).digest()
        pattern_bytes = bytearray()
        seed = content_hash
        while len(pattern_bytes) < self.n_units:
            seed = hashlib.sha256(seed).digest()
            pattern_bytes.extend(seed)

        pattern = np.array([
            1 if b & (1 << (i % 8)) else -1
            for i, b in enumerate(pattern_bytes[:self.n_units])
        ], dtype=float)

        return pattern

    async def create_basin(self, name: str, seed_content: str, metadata: Optional[Dict] = None) -> BasinState:
        pattern = self._content_to_pattern(seed_content)
        self.network.store_pattern(pattern)
        energy = self.network.compute_energy(pattern)

        basin = BasinState(
            name=name,
            pattern=pattern,
            energy=energy,
            activation=1.0,
            stability=1.0,
            metadata=metadata or {"seed_content": seed_content[:100]}
        )

        self.basins[name] = basin
        if self.field_engine:
            self.field_engine.register_basin(name)
            
        logger.info(f"Created basin '{name}' with energy {energy:.3f}")
        self._write_cache(basin)

        if self.event_publisher:
            try:
                await self.event_publisher.emit_basin_changed(
                    basin_name=basin.name,
                    source_id="attractor_basin_service",
                    activation_strength=float(basin.activation),
                )
            except Exception:
                pass 

        return basin

    async def morph_basin(self, name: str, push_back: bool = False, strength: float = 1.0) -> Optional[BasinState]:
        basin = self.basins.get(name)
        if not basin:
            logger.warning(f"Basin '{name}' not found for morphing")
            return None

        if push_back:
            self.network.push_pattern(basin.pattern, strength)
            if self.field_engine:
                self.field_engine.remove_basin(name)
            logger.info(f"Pushed back attractor basin '{name}' with strength {strength}")
            self._invalidate_cache(name)
        else:
            self.network.store_pattern(basin.pattern, int(strength))
            if self.field_engine:
                self.field_engine.register_basin(name)
            logger.info(f"Strengthened attractor basin '{name}' with degree {int(strength)}")

        basin.energy = self.network.compute_energy(basin.pattern)
        basin.stability = self.compute_basin_stability(basin)

        if not push_back:
            self._write_cache(basin)

        return basin

    async def find_nearest_basin(self, query_content: str, max_iterations: int = 50) -> Optional[ConvergenceResult]:
        if not self.basins:
            logger.warning("No basins stored")
            return None

        query_pattern = self._content_to_pattern(query_content)
        result = self.network.run_until_convergence(query_pattern, max_iterations)
        return result

    def compute_basin_stability(self, basin: BasinState) -> float:
        if basin.pattern is None:
            return 0.0

        n_tests = 10
        noise_levels = np.linspace(0.05, 0.5, n_tests)
        successes = 0

        for noise in noise_levels:
            n_flip = int(noise * self.n_units)
            test_pattern = basin.pattern.copy()
            flip_indices = np.random.choice(self.n_units, n_flip, replace=False)
            test_pattern[flip_indices] *= -1

            result = self.network.run_until_convergence(test_pattern, max_iterations=30)

            if np.array_equal(result.final_state, basin.pattern) or np.array_equal(result.final_state, -basin.pattern):
                successes += 1

        return successes / n_tests

    def get_basin_by_name(self, name: str) -> Optional[BasinState]:
        if self.basin_cache is not None:
            cached = self.basin_cache.get_basin(name)
            if cached is not None:
                return self._cache_dict_to_basin(cached)
        return self.basins.get(name)

    def _cache_dict_to_basin(self, data: Dict[str, Any]) -> BasinState:
        pattern = data.get("pattern")
        if pattern is not None:
            pattern = np.array(pattern)
        return BasinState(
            name=data.get("name", ""),
            pattern=pattern,
            energy=float(data.get("energy", 0.0)),
            activation=float(data.get("activation", 0.0)),
            stability=float(data.get("stability", 0.0)),
            metadata=data.get("metadata", {}),
            strength=float(data.get("strength", 0.0)),
            activation_count=int(data.get("activation_count", 0)),
            activation_history=data.get("activation_history", []),
        )

    def list_basins(self) -> List[str]:
        return list(self.basins.keys())

    async def strengthen_basin(self, name: str) -> Optional[BasinState]:
        basin = self.basins.get(name)
        if basin is None:
            return None

        basin.strength += self.HEBBIAN_INCREMENT
        basin.activation_count += 1
        ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
        basin.activation_history.append(ts)

        self.network.store_pattern(basin.pattern, degree=1)
        basin.energy = self.network.compute_energy(basin.pattern)
        basin.stability = self.compute_basin_stability(basin)

        self._write_cache(basin)

        if self.shared_module_registry is not None:
            for module in self.shared_module_registry.get_modules_for_basin(name):
                try:
                    self.shared_module_registry.update_module(module.name, name, success=True, eps=0.05)
                except KeyError:
                    pass

        return basin

    def get_shared_modules_for_basin(self, basin_name: str) -> list:
        if self.shared_module_registry is None:
            return []
        return self.shared_module_registry.get_modules_for_basin(basin_name)

    def get_basins_by_strength(self) -> List[BasinState]:
        return sorted(self.basins.values(), key=lambda b: b.strength, reverse=True)
