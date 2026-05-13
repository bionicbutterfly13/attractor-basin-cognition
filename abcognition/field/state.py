# SPDX-License-Identifier: Apache-2.0
"""Basin field models for LinOSS-inspired oscillatory dynamics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from pydantic import BaseModel, Field


class FieldState(BaseModel):
    influence: Dict[str, float]
    coupling: Dict[str, float]
    resonance: Dict[str, float]
    persistence_profile: Dict[str, str]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    basin_names: List[str]
