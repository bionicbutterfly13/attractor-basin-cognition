# SPDX-License-Identifier: Apache-2.0
"""
Host-neutral protocols for attractor-basin cognition.

These contracts keep the library independent from any application framework.
Host systems adapt their own objects into these shapes instead of the package
importing host models directly.
"""

from typing import Protocol, Any, Optional, Dict


class BasinImpulse(Protocol):
    """Smallest routable cognitive signal."""

    @property
    def activation_level(self) -> float: ...

    @property
    def dominant_basin(self) -> Optional[str]: ...


class PacketLike(Protocol):
    """Packet-scale signal with vector, precision, and coherence."""

    @property
    def content(self) -> str: ...

    @property
    def precision(self) -> float: ...

    @property
    def coherence(self) -> float: ...

    @property
    def metadata(self) -> Dict[str, Any]: ...


class ConceptFieldLike(Protocol):
    """Field-scale signal carrying basin-level convergence state."""

    @property
    def concepts(self) -> list[Any]: ...

    @property
    def dominant_basin(self) -> Optional[str]: ...

    @property
    def field_energy(self) -> float: ...


class BasinGraphLike(Protocol):
    """Graph-scale signal for mental model or basin relationship layers."""

    @property
    def constituent_basins(self) -> list[str]: ...

    @property
    def cohesion(self) -> float: ...

    @property
    def stability(self) -> float: ...


class BasinCacheProvider(Protocol):
    """Provides caching for basin data."""
    def get_basin(self, concept_id: str) -> Optional[Dict[str, Any]]: ...
    def set_basin(self, concept_id: str, basin_data: Dict[str, Any], ttl: Optional[int] = None) -> bool: ...
    def invalidate_basin(self, concept_id: str) -> bool: ...


class SharedModuleRegistry(Protocol):
    """Provides access to shared cognitive modules for state cross-pollination."""
    def get_modules_for_basin(self, basin_name: str) -> list[Any]: ...
    def update_module(self, module_name: str, basin_name: str, success: bool, eps: float = 0.05) -> None: ...


class EventPublisher(Protocol):
    """Fires lifecycle events for basins."""
    async def emit_basin_changed(
        self,
        basin_name: str,
        source_id: str,
        previous_basin: Optional[str] = None,
        activation_strength: Optional[float] = None,
        **extra: Any,
    ) -> None: ...
