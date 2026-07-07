"""Architecture regression: execution/governance_guard.py must stay SVOS-free.

Sys2 Scope 2 decoupling removed the last production hot-path dependency on
svos.* from execution/governance_guard.py. This guards against regression.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD_PATH = ROOT / "execution" / "governance_guard.py"


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_governance_guard_has_no_svos_or_research_imports() -> None:
    modules = _imported_modules(GUARD_PATH)
    violations = [
        module
        for module in modules
        if module == "svos" or module.startswith("svos.") or module == "research" or module.startswith("research.")
    ]
    assert not violations, f"execution/governance_guard.py must not import SVOS/research modules: {violations}"


def test_governance_guard_source_has_no_svos_or_research_strings() -> None:
    text = GUARD_PATH.read_text(encoding="utf-8")
    assert "svos." not in text and "svos " not in text
    assert "research." not in text
