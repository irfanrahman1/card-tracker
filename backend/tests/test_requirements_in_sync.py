"""Vercel installs from the root requirements.txt; everything else uses
backend/requirements.txt. They must list the same packages."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def packages(path: Path) -> set[str]:
    lines = (line.strip() for line in path.read_text().splitlines())
    return {line for line in lines if line and not line.startswith("#")}


def test_root_and_backend_requirements_match():
    assert packages(ROOT / "requirements.txt") == packages(ROOT / "backend" / "requirements.txt")
