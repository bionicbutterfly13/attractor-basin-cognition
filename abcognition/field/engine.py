# SPDX-License-Identifier: Apache-2.0
"""LinOSS-inspired oscillator field engine for basin dynamics."""

from __future__ import annotations

import hashlib
import logging
import random
from typing import Dict, Iterable, Optional

import numpy as np

from .state import FieldState
from .protocols import FieldEventPublisher, FieldPersistenceProvider, AdaptiveTemperatureProvider

logger = logging.getLogger(__name__)


class BasinFieldEngine:
    """Lightweight LinOSS-style coupled oscillator field with parallel-scan recurrence core."""

    _FORCING_GAIN_MIN = 0.25
    _FORCING_GAIN_MAX = 4.0

    def __init__(
        self,
        basin_names: Optional[Iterable[str]] = None,
        oscillator_dim: int = 128,
        resonance_event_min_steps: int = 5,
        event_publisher: Optional[FieldEventPublisher] = None,
        persistence_provider: Optional[FieldPersistenceProvider] = None,
        adaptive_temp: Optional[AdaptiveTemperatureProvider] = None,
    ):
        self.basin_names = list(basin_names or ["experiential-basin", "conceptual-basin", "procedural-basin", "strategic-basin"])
        self.oscillator_dim = oscillator_dim
        self._index = {name: i for i, name in enumerate(self.basin_names)}
        n = len(self.basin_names)
        self._real = np.zeros((n, oscillator_dim), dtype=np.float32)
        self._imag = np.zeros((n, oscillator_dim), dtype=np.float32)
        self._forcing_gains = np.ones((n, oscillator_dim), dtype=np.float32)

        self._omega = np.linspace(0.15, 1.2, oscillator_dim, dtype=np.float32)
        self._damping = np.linspace(0.03, 0.30, oscillator_dim, dtype=np.float32)
        self._steps = np.full((oscillator_dim,), 0.2, dtype=np.float32)
        self._phase = np.zeros((n, oscillator_dim), dtype=np.float32)

        _a = np.exp(-self._damping * self._steps)
        self._rot_cos = (_a * np.cos(self._omega * self._steps)).astype(np.float32)
        self._rot_sin = (_a * np.sin(self._omega * self._steps)).astype(np.float32)

        _threshold = float(np.median(self._damping))
        self._damping_mode = "conservative" if float(self._damping.mean()) <= _threshold else "dissipative"
        self._snapshot_every = 10
        self._step_count = 0
        self._last_state: Optional[FieldState] = None

        self._resonance_event_min_steps = max(1, resonance_event_min_steps)
        self._last_resonance_event_step = -self._resonance_event_min_steps
        self._last_resonance_signature: tuple[str, ...] | None = None

        self.adaptive_temp = adaptive_temp
        self.event_publisher = event_publisher
        self.persistence_provider = persistence_provider

    def register_basin(self, basin_name: str) -> None:
        if basin_name in self._index:
            return
        self.basin_names.append(basin_name)
        self._index = {name: i for i, name in enumerate(self.basin_names)}
        self._real = np.vstack([self._real, np.zeros((1, self.oscillator_dim), dtype=np.float32)])
        self._imag = np.vstack([self._imag, np.zeros((1, self.oscillator_dim), dtype=np.float32)])
        self._forcing_gains = np.vstack([self._forcing_gains, np.ones((1, self.oscillator_dim), dtype=np.float32)])
        self._phase = np.vstack([self._phase, np.zeros((1, self.oscillator_dim), dtype=np.float32)])

    def remove_basin(self, basin_name: str) -> None:
        idx = self._index.get(basin_name)
        if idx is None:
            return
        keep = [i for i in range(len(self.basin_names)) if i != idx]
        self._real = self._real[keep, :]
        self._imag = self._imag[keep, :]
        self._forcing_gains = self._forcing_gains[keep, :]
        self._phase = self._phase[keep, :]
        self.basin_names = [self.basin_names[i] for i in keep]
        self._index = {name: i for i, name in enumerate(self.basin_names)}

    def apply_basin_forcing_adaptation(self, basin_name: str, delta: float, mask: np.ndarray | None = None) -> None:
        idx = self._index.get(basin_name)
        if idx is None:
            return
        if mask is None:
            self._forcing_gains[idx, :] = np.clip(
                self._forcing_gains[idx, :] + float(delta),
                self._FORCING_GAIN_MIN,
                self._FORCING_GAIN_MAX,
            )
            return
        if mask.shape[0] != self.oscillator_dim:
            return
        self._forcing_gains[idx, mask] = np.clip(
            self._forcing_gains[idx, mask] + float(delta),
            self._FORCING_GAIN_MIN,
            self._FORCING_GAIN_MAX,
        )

    @staticmethod
    def _parallel_scan_diag(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        if a.ndim == 1:
            a = a[:, None]
            b = b[:, None]
        cp = np.cumprod(a, axis=0)
        out = np.zeros_like(b)
        for t in range(b.shape[0]):
            weights = cp[t] / np.where(cp[: t + 1] == 0, 1.0, cp[: t + 1])
            out[t] = np.sum(b[: t + 1] * weights, axis=0)
        return out.squeeze(-1) if out.shape[1] == 1 else out

    async def step(self, basin_activations: Dict[str, float]) -> FieldState:
        n = len(self.basin_names)
        if n == 0:
            raise ValueError("BasinFieldEngine has no basins")

        u = np.zeros((n, self.oscillator_dim), dtype=np.float32)
        for basin_name, val in basin_activations.items():
            if basin_name not in self._index:
                self.register_basin(basin_name)
                n = len(self.basin_names)
                u = np.pad(u, ((0, 1), (0, 0)), mode="constant")
            idx = self._index[basin_name]
            u[idx, :] = float(max(0.0, val))
        u *= self._forcing_gains

        real_next = self._real * self._rot_cos - self._imag * self._rot_sin + 0.35 * u
        imag_next = self._imag * self._rot_cos + self._real * self._rot_sin + 0.10 * u

        if len(self.basin_names) > 1:
            mean_real = real_next.mean(axis=0, keepdims=True)
            mean_imag = imag_next.mean(axis=0, keepdims=True)
            coupled_real = 0.92 * real_next + 0.08 * mean_real
            coupled_imag = 0.92 * imag_next + 0.08 * mean_imag

            if self.adaptive_temp is not None:
                delta_energy = float(np.mean(
                    np.linalg.norm(coupled_real - real_next, axis=1)
                    + np.linalg.norm(coupled_imag - imag_next, axis=1)
                ))
                p_accept = self.adaptive_temp.boltzmann_probability(delta_energy)
                accepted = random.random() < p_accept
                self.adaptive_temp.adapt_temperature(accepted)
                if accepted:
                    real_next = coupled_real
                    imag_next = coupled_imag
            else:
                real_next = coupled_real
                imag_next = coupled_imag

        self._real = real_next.astype(np.float32)
        self._imag = imag_next.astype(np.float32)
        self._phase = np.arctan2(self._imag, self._real)
        self._step_count += 1

        _norms = np.linalg.norm(self._real, axis=1) / (self.oscillator_dim ** 0.5)
        influence = {name: float(_norms[i]) for i, name in enumerate(self.basin_names)}

        coupling: Dict[str, float] = {}
        resonance: Dict[str, float] = {}
        n_cur = len(self.basin_names)
        if n_cur > 1:
            _phase_diff = self._phase[:, None, :] - self._phase[None, :, :]
            _cos_matrix = (np.cos(_phase_diff).mean(axis=2) + 1.0) * 0.5
            _local_i0: list[float] = []
            for i, a_name in enumerate(self.basin_names):
                for j in range(i + 1, n_cur):
                    b_name = self.basin_names[j]
                    score = float(_cos_matrix[i, j])
                    coupling[f"{a_name}|{b_name}"] = score
                    if i == 0:
                        _local_i0.append(score)
                resonance[a_name] = float(np.mean(_local_i0)) if (i == 0 and _local_i0) else 1.0
        else:
            resonance = {name: 1.0 for name in self.basin_names}

        persistence = self.get_persistence_profile()
        state = FieldState(
            influence=influence,
            coupling=coupling,
            resonance=resonance,
            persistence_profile=persistence,
            basin_names=list(self.basin_names),
        )
        self._last_state = state

        resonant = sorted(k for k, v in resonance.items() if v >= 0.75)
        if len(resonant) >= 2 and self._should_emit_resonance_event(resonant):
            if self.event_publisher:
                await self.event_publisher.publish_resonance_event(resonant, self._step_count)

        if self._step_count % self._snapshot_every == 0:
            if self.persistence_provider:
                try:
                    await self.persistence_provider.record_field_snapshot(state.model_dump(mode="json"))
                except Exception as exc:
                    logger.warning("Field snapshot persistence failed at step %d: %s", self._step_count, exc, exc_info=True)

        return state

    def _should_emit_resonance_event(self, resonant: list[str]) -> bool:
        signature = tuple(resonant)
        step_delta = self._step_count - self._last_resonance_event_step
        should_emit = step_delta >= self._resonance_event_min_steps or signature != self._last_resonance_signature
        if should_emit:
            self._last_resonance_event_step = self._step_count
            self._last_resonance_signature = signature
        return should_emit

    def get_field_influence(self, basin_name: str) -> float:
        if self._last_state is None:
            return 0.0
        return float(self._last_state.influence.get(basin_name, 0.0))

    def apply_scaffold(self, biases: Dict[str, float]) -> None:
        for basin, bias in biases.items():
            if basin in self._index:
                idx = self._index[basin]
                self._real[idx, :] *= bias
                self._imag[idx, :] *= bias

    def get_coupling_matrix(self) -> Dict[tuple[str, str], float]:
        if self._last_state is None:
            return {}
        out: Dict[tuple[str, str], float] = {}
        for key, val in self._last_state.coupling.items():
            a, b = key.split("|", 1)
            out[(a, b)] = float(val)
        return out

    def get_resonance_map(self) -> Dict[str, float]:
        if self._last_state is None:
            return {name: 0.0 for name in self.basin_names}
        return dict(self._last_state.resonance)

    def get_persistence_profile(self) -> Dict[str, str]:
        mode = self._damping_mode
        profile = {}
        for name in self.basin_names:
            influence = self.get_field_influence(name)
            profile[name] = "conservative" if influence >= 0.5 and mode == "conservative" else "dissipative"
        return profile

    def export_state(self) -> dict:
        payload = {
            "basin_names": list(self.basin_names),
            "oscillator_dim": int(self.oscillator_dim),
            "real": self._real.tolist(),
            "imag": self._imag.tolist(),
            "forcing_gains": self._forcing_gains.tolist(),
            "omega": self._omega.tolist(),
            "damping": self._damping.tolist(),
            "steps": self._steps.tolist(),
            "step_count": self._step_count,
            "resonance_event_min_steps": self._resonance_event_min_steps,
            "last_resonance_event_step": self._last_resonance_event_step,
            "last_resonance_signature": list(self._last_resonance_signature or []),
        }
        digest = hashlib.sha256(str(payload["real"]).encode("utf-8")).hexdigest()
        payload["state_hash"] = digest
        return payload

    def load_state(self, payload: dict) -> None:
        self.basin_names = list(payload.get("basin_names", self.basin_names))
        self.oscillator_dim = int(payload.get("oscillator_dim", self.oscillator_dim))
        self._index = {name: i for i, name in enumerate(self.basin_names)}
        self._real = np.array(payload.get("real", self._real), dtype=np.float32)
        self._imag = np.array(payload.get("imag", self._imag), dtype=np.float32)
        self._forcing_gains = np.array(payload.get("forcing_gains", self._forcing_gains), dtype=np.float32)
        self._omega = np.array(payload.get("omega", self._omega), dtype=np.float32)
        self._damping = np.array(payload.get("damping", self._damping), dtype=np.float32)
        self._steps = np.array(payload.get("steps", self._steps), dtype=np.float32)
        self._phase = np.arctan2(self._imag, self._real)
        self._step_count = int(payload.get("step_count", self._step_count))
        self._resonance_event_min_steps = max(
            1, int(payload.get("resonance_event_min_steps", self._resonance_event_min_steps))
        )
        self._last_resonance_event_step = int(
            payload.get("last_resonance_event_step", self._last_resonance_event_step)
        )
        self._last_resonance_signature = tuple(payload.get("last_resonance_signature", [])) or None
