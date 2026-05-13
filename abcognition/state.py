# SPDX-License-Identifier: Apache-2.0
"""
BasinState and related data structures.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List
import numpy as np


@dataclass
class BasinState:
    """
    Represents the state of an attractor basin.
    """
    name: str
    pattern: np.ndarray
    energy: float = 0.0
    activation: float = 0.0
    stability: float = 0.0
    metadata: Dict = field(default_factory=dict)
    
    # Hebbian strength tracking
    strength: float = 0.0
    activation_count: int = 0
    activation_history: List[str] = field(default_factory=list)

    # Optional canalization metrics
    canalization: Any = None

    # Marginal distribution memory
    marginal_distribution: Dict[str, float] = field(default_factory=dict)
    observation_count: int = 0
    density_update_timestamp: str = ""


def update_marginal_distribution(basin: BasinState, observation_type: str, weight: float = 1.0) -> None:
    """
    Update marginal distribution p(o) for an observation type.
    """
    old_total = basin.observation_count

    if old_total > 0 and basin.marginal_distribution:
        for k in list(basin.marginal_distribution.keys()):
            basin.marginal_distribution[k] *= old_total

    basin.marginal_distribution[observation_type] = (
        basin.marginal_distribution.get(observation_type, 0.0) + weight
    )
    basin.observation_count = old_total + weight

    total = sum(basin.marginal_distribution.values())
    if total > 0.0:
        for k in basin.marginal_distribution:
            basin.marginal_distribution[k] /= total

    if len(basin.marginal_distribution) > 100:
        min_key = min(basin.marginal_distribution, key=basin.marginal_distribution.get)
        del basin.marginal_distribution[min_key]
        total = sum(basin.marginal_distribution.values())
        if total > 0.0:
            for k in basin.marginal_distribution:
                basin.marginal_distribution[k] /= total

    from datetime import datetime
    basin.density_update_timestamp = datetime.utcnow().isoformat()
