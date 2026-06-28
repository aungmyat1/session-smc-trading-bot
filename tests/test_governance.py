"""
Smoke tests for governance lifecycle and registry.

Tests:
- LifecycleState transitions (happy path and disallowed)
- Evidence validation
- StrategyRegistry CRUD + persistence
"""

import tempfile
from pathlib import Path

import pytest

from session_smc.governance.lifecycle import (
    LifecycleState,
    LifecycleTransitionError,
    StrategyLifecycle,
)
from session_smc.governance.registry import StrategyRegistry, StrategyRegistryError


# ---------------------------------------------------------------------------
# LifecycleState transition tests
# ---------------------------------------------------------------------------


def test_happy_path_promotion():
    lc = StrategyLifecycle(strategy_id="TEST-1")
    assert lc.state == LifecycleState.RESEARCH_QUALIFIED

    lc.transition(
        LifecycleState.VERIFICATION_READY,
        evidence={
            "evidence_type": "backtest_report",
            "description": "PF_2x=1.025 n=169 PASS",
            "timestamp": "2026-06-21T10:00:00Z",
        },
        actor="backtest_runner",
    )
    assert lc.state == LifecycleState.VERIFICATION_READY
    assert len(lc.history) == 1
    assert lc.history[0].actor == "backtest_runner"


def test_disallowed_transition_raises():
    lc = StrategyLifecycle(strategy_id="TEST-2")
    with pytest.raises(LifecycleTransitionError):
        # Cannot jump from research_qualified to demo_live
        lc.transition(
            LifecycleState.DEMO_LIVE,
            evidence={"evidence_type": "demo_start_confirmation", "description": "", "timestamp": ""},
        )


def test_wrong_evidence_type_raises():
    lc = StrategyLifecycle(strategy_id="TEST-3")
    with pytest.raises(LifecycleTransitionError, match="evidence_type"):
        lc.transition(
            LifecycleState.VERIFICATION_READY,
            evidence={
                "evidence_type": "wrong_type",  # should be backtest_report
                "description": "...",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        )


def test_suspend_from_demo_live():
    lc = StrategyLifecycle(strategy_id="TEST-4")
    # Promote to demo_live via chain
    _promote_to(lc, LifecycleState.DEMO_LIVE)
    lc.transition(
        LifecycleState.SUSPENDED,
        evidence={
            "evidence_type": "suspension_reason",
            "description": "Drawdown limit hit",
            "timestamp": "2026-01-01T00:00:00Z",
        },
    )
    assert lc.state == LifecycleState.SUSPENDED


def test_serialisation_roundtrip():
    lc = StrategyLifecycle(strategy_id="TEST-5")
    lc.transition(
        LifecycleState.VERIFICATION_READY,
        evidence={
            "evidence_type": "backtest_report",
            "description": "PASS",
            "timestamp": "2026-06-21T10:00:00Z",
        },
    )
    d = lc.to_dict()
    lc2 = StrategyLifecycle.from_dict(d)
    assert lc2.strategy_id == "TEST-5"
    assert lc2.state == LifecycleState.VERIFICATION_READY
    assert len(lc2.history) == 1


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


def test_registry_register_and_get():
    with tempfile.TemporaryDirectory() as td:
        reg = StrategyRegistry(registry_path=Path(td) / "registry.json")
        reg.register("ST-TEST", meta={"pairs": ["EURUSD"]})
        assert reg.get_state("ST-TEST") == LifecycleState.RESEARCH_QUALIFIED


def test_registry_duplicate_raises():
    with tempfile.TemporaryDirectory() as td:
        reg = StrategyRegistry(registry_path=Path(td) / "registry.json")
        reg.register("ST-DUP")
        with pytest.raises(StrategyRegistryError):
            reg.register("ST-DUP")


def test_registry_promote():
    with tempfile.TemporaryDirectory() as td:
        reg = StrategyRegistry(registry_path=Path(td) / "registry.json")
        reg.register("ST-PROMO")
        reg.promote(
            "ST-PROMO",
            LifecycleState.VERIFICATION_READY,
            evidence={
                "evidence_type": "backtest_report",
                "description": "n=169 PF_2x=1.025 PASS",
                "timestamp": "2026-06-21T10:00:00Z",
            },
        )
        assert reg.get_state("ST-PROMO") == LifecycleState.VERIFICATION_READY


def test_registry_persists_and_reloads():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "registry.json"
        reg = StrategyRegistry(registry_path=path)
        reg.register("ST-PERSIST")
        assert path.exists()

        # Reload
        reg2 = StrategyRegistry(registry_path=path)
        assert "ST-PERSIST" in reg2.list_strategies()
        assert reg2.get_state("ST-PERSIST") == LifecycleState.RESEARCH_QUALIFIED


def test_registry_suspend():
    with tempfile.TemporaryDirectory() as td:
        reg = StrategyRegistry(registry_path=Path(td) / "registry.json")
        reg.register("ST-SUSP")
        _promote_to(reg.get_lifecycle("ST-SUSP"), LifecycleState.DEMO_LIVE)
        # Manually update registry state (simulate promotion)
        reg._strategies["ST-SUSP"].state = LifecycleState.DEMO_LIVE
        reg._persist()

        reg.suspend("ST-SUSP", reason="Test suspension")
        assert reg.get_state("ST-SUSP") == LifecycleState.SUSPENDED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EVIDENCE = {
    LifecycleState.VERIFICATION_READY: ("backtest_report", "PASS"),
    LifecycleState.EXECUTION_QUALIFIED: ("execution_qualification_report", "PASS"),
    LifecycleState.RISK_QUALIFIED: ("risk_qualification_report", "PASS"),
    LifecycleState.DEMO_APPROVED: ("demo_approval_sign_off", "Owner approved"),
    LifecycleState.DEMO_LIVE: ("demo_start_confirmation", "Demo started"),
}

_CHAIN = [
    LifecycleState.VERIFICATION_READY,
    LifecycleState.EXECUTION_QUALIFIED,
    LifecycleState.RISK_QUALIFIED,
    LifecycleState.DEMO_APPROVED,
    LifecycleState.DEMO_LIVE,
]


def _promote_to(lc: StrategyLifecycle, target: LifecycleState) -> None:
    """Promote lifecycle through the chain up to target state."""
    for state in _CHAIN:
        if lc.state == target:
            break
        ev_type, desc = _EVIDENCE[state]
        lc.transition(
            state,
            evidence={"evidence_type": ev_type, "description": desc, "timestamp": "2026-01-01T00:00:00Z"},
        )
        if state == target:
            break
