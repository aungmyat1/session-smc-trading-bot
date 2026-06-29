"""
Phase A — Architecture gate: lifecycle mutation authority.

The canonical lifecycle is svos/lifecycle/manager.py.
No module outside the allowed set may call promote_strategy_stage or
write directly to the strategy catalog.

This test RECORDS the current known bypass callers. Any new caller added
outside this set will fail CI immediately (it shows up in grep but is not
in KNOWN_BYPASS_CALLERS). Once a caller is migrated to the svos/ boundary,
remove it from this set — that tightens the gate over time.

Do NOT add new entries to KNOWN_BYPASS_CALLERS. Fix the caller instead.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Files that are allowed to call promote_strategy_stage or update_strategy_manifest
# because they ARE the lifecycle authority or they own the legacy adapter.
ALLOWED_MUTATION_CALLERS = {
    # Definition site — not a caller.
    "core/strategy_registry.py",
    # New authority — the only legitimate caller path.
    "svos/registry/service.py",
    "svos/orchestration/service.py",
    "svos/deployment/service.py",
    "svos/api/service.py",
}

# Legacy bypass callers that existed before Phase A.
# These are KNOWN VIOLATIONS that must be migrated to the svos/ boundary.
# Do not add new entries here. Remove entries as you migrate each caller.
KNOWN_BYPASS_CALLERS = {
    "research/validation/engine.py",
    "research/svos/engine.py",
    "scripts/run_current_strategy_svos.py",
    "scripts/run_current_strategy_validation.py",
    "scripts/run_svos_sample.py",
    "scripts/generate_reports.py",
}

# Callers in test code are allowed to import for testing purposes.
ALLOWED_TEST_CALLERS = {
    # This file references the symbol as a string in documentation/sets.
    "tests/architecture/test_lifecycle_authority.py",
    "tests/core/test_registry.py",
    "tests/research_engine/test_svos.py",
    "tests/research_engine/test_svos_payload_builder.py",
    "tests/svos/test_platform.py",
    "tests/test_dashboard_app.py",
    "tests/test_generate_reports.py",
    "tests/test_research_queue.py",
    "tests/test_svos_sample.py",
    "tests/test_validation_gate.py",
}

ALL_ALLOWED = ALLOWED_MUTATION_CALLERS | KNOWN_BYPASS_CALLERS | ALLOWED_TEST_CALLERS


def _find_callers(symbol: str) -> set[str]:
    result = subprocess.run(
        ["grep", "-r", "--include=*.py", "-l", symbol, str(ROOT)],
        capture_output=True,
        text=True,
    )
    paths = set()
    for line in result.stdout.splitlines():
        p = Path(line)
        try:
            rel = p.relative_to(ROOT)
        except ValueError:
            continue
        parts = rel.parts
        # Skip caches, archives, and bytecode
        if any(part in ("__pycache__", "archive", ".venv") for part in parts):
            continue
        paths.add(str(rel))
    return paths


def test_no_new_promote_strategy_stage_callers():
    """Any file calling promote_strategy_stage must be in the allowed set."""
    callers = _find_callers("promote_strategy_stage")
    unexpected = callers - ALL_ALLOWED
    assert not unexpected, (
        "New caller(s) of promote_strategy_stage found outside the allowed set.\n"
        "Migrate to svos/ lifecycle boundary instead of adding to KNOWN_BYPASS_CALLERS:\n"
        + "\n".join(f"  {c}" for c in sorted(unexpected))
    )


def test_known_bypass_callers_still_exist():
    """Each entry in KNOWN_BYPASS_CALLERS must still exist as a file.

    If a file has been removed or migrated, remove it from KNOWN_BYPASS_CALLERS
    so the set does not silently grow stale.
    """
    for rel in KNOWN_BYPASS_CALLERS:
        assert (ROOT / rel).exists(), (
            f"{rel} is in KNOWN_BYPASS_CALLERS but no longer exists. "
            "Remove it from the set — the migration may be complete."
        )


def test_catalog_has_no_active_current_strategy():
    """Platform construction mode: no strategy should be set as current.

    current_strategy must be null until a strategy earns Production Approval
    through the full pipeline.
    """
    import yaml  # noqa: PLC0415

    catalog_path = ROOT / "config" / "strategy_catalog.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    current = catalog.get("current_strategy")
    assert current is None, (
        f"current_strategy is set to {current!r} but the platform is under construction. "
        "No strategy is approved. Set current_strategy: null in the catalog."
    )


def test_no_strategy_is_approved_in_catalog():
    """All strategies in the catalog must have approved: false during platform construction."""
    import yaml  # noqa: PLC0415

    catalog_path = ROOT / "config" / "strategy_catalog.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    violations = []
    for name, spec in (catalog.get("strategies") or {}).items():
        if spec.get("approved", False):
            violations.append(name)
    assert not violations, (
        "Strategies marked approved: true found, but no strategy has earned Production Approval. "
        "Set approved: false for: " + ", ".join(violations)
    )
