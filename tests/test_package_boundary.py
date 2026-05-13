# SPDX-License-Identifier: Apache-2.0
from pathlib import Path


def test_package_does_not_import_host_code() -> None:
    package_root = Path(__file__).resolve().parents[1] / "abcognition"
    forbidden = (
        "from api.",
        "import api.",
        "api.models",
        "api.services",
    )

    offenders: list[str] = []
    for path in package_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text:
                offenders.append(f"{path.relative_to(package_root.parent)} contains {marker!r}")

    assert offenders == []


def test_import_name_is_abcognition() -> None:
    import abcognition

    assert abcognition.CoreAttractorService.__name__ == "CoreAttractorService"
