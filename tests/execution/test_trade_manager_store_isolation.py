"""
Regression coverage for the 2026-07-06 "58 non-terminal ExecutionRecords"
incident (docs/systems/system2/DASHBOARD_READINESS.md §13).

Root cause: TradeManager.__init__ defaults execution_store to
ExecutionStateStore(".") — CWD-relative — when no store is injected.
tests/test_demo_execution_safety.py and tests/execution/test_trade_manager.py
constructed TradeManager without an explicit store, so every pytest run
(invoked from the repo root) silently wrote simulated ExecutionRecord JSON
files into the *real* data/execution/ directory the live dashboard reads —
376 accumulated over the project's history, 58 non-terminal, all
SIM-prefixed (zero real trades). Not a state-machine bug; abandoned,
unisolated test fixtures.

Fix: both call sites now inject ExecutionStateStore(tmp_path). This file
locks in two things: the dangerous default's actual behavior (so a future
change to it is deliberate, not accidental), and a repo-wide static check
that no *other* test file repeats the same mistake.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from unittest.mock import MagicMock

from execution.trade_manager import TradeManager

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TESTS_DIR = _REPO_ROOT / "tests"
# Marker the static checker below looks for, on the same source line, to
# allowlist a deliberate exception without hardcoding a fragile line number.
_ALLOW_MARKER = "store-isolation-allow"


def test_trade_manager_default_store_is_cwd_relative(tmp_path, monkeypatch):
    """Documents the actual (fragile) default so a future change to it is a
    deliberate decision, not a silent behavior change. Real callers
    (scripts/run_st_a2_demo.py) never rely on this default — they always
    inject an explicit ExecutionStateStore — so this default only matters
    for callers (like tests) that forget to."""
    monkeypatch.chdir(tmp_path)

    manager = TradeManager(MagicMock())  # store-isolation-allow: chdir'd to tmp_path above

    assert manager._store.root == Path(".")
    assert manager._store.store_root == Path(".") / "data" / "execution"


def test_no_test_constructs_trademanager_without_an_explicit_store():
    """Static, repo-wide guard: every `TradeManager(...)` call under tests/
    must pass execution_store= explicitly. Prevents a new test file from
    reintroducing the exact pollution bug this file is named after — a
    per-test isolation fix alone doesn't stop the *next* test file from
    making the same mistake, but this check does."""
    violations: list[str] = []
    call_pattern = re.compile(r"TradeManager\s*\(")

    for path in _TESTS_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if not call_pattern.search(text):
            continue
        lines = text.splitlines()
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name != "TradeManager":
                continue
            has_store_kwarg = any(kw.arg == "execution_store" for kw in node.keywords)
            has_store_star = any(kw.arg is None for kw in node.keywords)  # **kwargs spread
            source_line = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
            if not has_store_kwarg and not has_store_star and _ALLOW_MARKER not in source_line:
                violations.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}")

    assert not violations, (
        "TradeManager() constructed without execution_store= in tests/ — this will silently "
        "write simulated execution records into the real data/execution/ directory the live "
        "dashboard reads (see docs/systems/system2/DASHBOARD_READINESS.md §13). "
        f"Pass execution_store=ExecutionStateStore(tmp_path) at: {violations}"
    )
