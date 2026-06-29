"""Architecture gates for exclusive lifecycle mutation authority."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEGACY_MUTATORS = {
    "promote_strategy_stage",
    "set_current_strategy",
    "update_strategy_manifest",
}


def _active_python_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(part in {"archive", ".venv", "__pycache__"} for part in relative.parts):
            continue
        files.append(path)
    return files


def test_no_legacy_catalog_mutation_callers() -> None:
    violations: list[str] = []
    for path in _active_python_files():
        relative = path.relative_to(ROOT)
        if relative == Path("core/strategy_registry.py") or relative.parts[0] == "tests":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in LEGACY_MUTATORS:
                violations.append(f"{relative}:{node.lineno}: {node.id}")
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and node.attr in LEGACY_MUTATORS:
                violations.append(f"{relative}:{node.lineno}: {node.attr}")
    assert not violations, "Legacy lifecycle mutation bypasses remain:\n" + "\n".join(violations)


def test_lifecycle_code_does_not_write_catalog_projection() -> None:
    callers: list[str] = []
    for path in _active_python_files():
        relative = path.relative_to(ROOT)
        if relative == Path("core/strategy_registry.py") or relative.parts[0] == "tests":
            continue
        if "_update_strategy_projection" in path.read_text(encoding="utf-8"):
            callers.append(str(relative))
    assert not callers, f"Compatibility projection writer used by active code: {callers}"


def test_catalog_has_no_active_or_approved_strategy() -> None:
    import yaml

    catalog = yaml.safe_load((ROOT / "config/strategy_catalog.yaml").read_text(encoding="utf-8"))
    assert catalog.get("current_strategy") is None
    violations = [
        name
        for name, spec in (catalog.get("strategies") or {}).items()
        if spec.get("approved", False) or spec.get("current", False)
    ]
    assert not violations, f"Strategies active or approved during construction: {violations}"
