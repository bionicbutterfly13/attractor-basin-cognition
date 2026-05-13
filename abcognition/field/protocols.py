# SPDX-License-Identifier: Apache-2.0
"""
Protocols for BasinFieldEngine dependency injection.
"""

from typing import Protocol, Any, Dict, List


class FieldEventPublisher(Protocol):
    """Fires system events for resonance clusters."""
    async def publish_resonance_event(self, resonant_basins: List[str], step_count: int) -> None: ...


class FieldPersistenceProvider(Protocol):
    """Handles persistence of periodic field snapshots."""
    async def record_field_snapshot(self, state_dict: Dict[str, Any]) -> None: ...


class AdaptiveTemperatureProvider(Protocol):
    """Provides Boltzmann probabilities for cross-basin coupling."""
    def boltzmann_probability(self, delta_energy: float) -> float: ...
    def adapt_temperature(self, accepted: bool) -> None: ...
