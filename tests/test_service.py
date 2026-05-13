# SPDX-License-Identifier: Apache-2.0

import pytest

from abcognition import CoreAttractorService


@pytest.mark.asyncio
async def test_create_and_strengthen_basin() -> None:
    service = CoreAttractorService(n_units=32)

    basin = await service.create_basin("procedural-basin", "repeatable action plan")
    strengthened = await service.strengthen_basin("procedural-basin")

    assert basin.name == "procedural-basin"
    assert strengthened is not None
    assert strengthened.strength > 0.0
    assert strengthened.activation_count == 1
