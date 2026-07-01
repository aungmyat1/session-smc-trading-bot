from __future__ import annotations

from execution.governance_guard import StrategyExecutionGuard


def test_governance_guard_warns_in_shadow_for_unapproved_strategy(tmp_path):
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "strategy_catalog.yaml").write_text(
        """
current_strategy: null
strategies:
  ShadowStrat:
    status: shadow
    approved: false
    version: "0.1"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    guard = StrategyExecutionGuard(root=tmp_path)

    result = guard.evaluate("ShadowStrat", environment="shadow")

    assert result.allowed is True
    assert result.reason_code == "WARN_SHADOW_GOVERNANCE_INCOMPLETE"


def test_governance_guard_blocks_demo_without_approval(tmp_path):
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "strategy_catalog.yaml").write_text(
        """
current_strategy: null
strategies:
  DemoStrat:
    status: shadow
    approved: false
    version: "0.2"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    guard = StrategyExecutionGuard(root=tmp_path)

    result = guard.evaluate("DemoStrat", environment="demo")

    assert result.allowed is False
    assert result.reason_code == "DEPLOYMENT_NOT_APPROVED"
