from __future__ import annotations

from pathlib import Path


def test_requirements_are_pinned_with_exact_versions() -> None:
    requirements_path = Path("requirements.txt")
    lines = requirements_path.read_text(encoding="utf-8").splitlines()

    package_lines = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("-r")
    ]

    assert package_lines, "requirements.txt should contain at least one package"
    assert all("==" in line for line in package_lines), "requirements.txt must pin exact versions with =="
