from __future__ import annotations

from pathlib import Path


def test_fastapi_and_uvicorn_are_declared_runtime_dependencies():
    requirements = Path("requirements.in").read_text(encoding="utf-8")
    assert "fastapi>=" in requirements
    assert "uvicorn>=" in requirements
