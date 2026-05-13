# SPDX-License-Identifier: Apache-2.0

import pytest

from abcognition.field import BasinFieldEngine


@pytest.mark.asyncio
async def test_field_step_registers_and_scores_basins() -> None:
    engine = BasinFieldEngine(["experiential-basin"], oscillator_dim=16)

    state = await engine.step({
        "experiential-basin": 0.7,
        "procedural-basin": 0.2,
    })

    assert "experiential-basin" in state.influence
    assert "procedural-basin" in state.influence
    assert state.influence["experiential-basin"] > state.influence["procedural-basin"]
    assert ("experiential-basin", "procedural-basin") in engine.get_coupling_matrix()
