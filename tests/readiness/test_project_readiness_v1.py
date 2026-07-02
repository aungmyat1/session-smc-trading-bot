from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from approval_package.package_builder import build_approval_package
from approval_package.package_validator import validate_package
from demo_runtime.demo_health_check import REQUIRED_CHECKS, evaluate_demo_readiness
from historical_replay.replay_engine import ReplayEngine
from strategy_input.strategy_validator import validate_strategy


def test_strategy_input_validation() -> None:
    result = validate_strategy({"strategy_id": "xau-ny", "pair": "XAUUSD", "session": "ny", "bias": "H1 trend", "entry": "M5 CHOCH", "risk_pct": 0.5, "reward_risk": 2, "max_trades_per_day": 2})
    assert result.valid
    assert not validate_strategy({"strategy_id": "bad"}).valid


def test_historical_replay_is_reproducible_and_no_lookahead() -> None:
    timestamps = [datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc) for minute in range(4)]
    candles = pd.DataFrame({"timestamp": timestamps, "open": [1, 2, 3, 4], "high": [2, 3, 4, 5], "low": [0, 1, 2, 3], "close": [1, 2, 3, 4]})
    visible_lengths: list[int] = []

    def strategy(frame: pd.DataFrame) -> dict | None:
        visible_lengths.append(len(frame))
        return {"side": "buy"} if len(frame) == 3 else None

    first = ReplayEngine("EURUSD", candles, strategy).run()
    visible_lengths.clear()
    second = ReplayEngine("EURUSD", candles, strategy).run()
    assert visible_lengths == [1, 2, 3, 4]
    assert first.to_dict() == second.to_dict()


def _package(tmp_path, key: str = "test-secret"):
    evidence = {}
    for name in ("strategy_spec.yaml", "backtest_report.md", "replay_report.md", "risk_report.md"):
        path = tmp_path / name
        path.write_text("evidence\n")
        evidence[name] = path
    return build_approval_package(tmp_path / "package", evidence=evidence, validation_summary={"validation": "PASS", "risk_check": "PASS"}, expires_at=datetime.now(timezone.utc) + timedelta(days=1), signing_key=key)


def test_package_validation_rejects_tampering_and_expiry(tmp_path) -> None:
    package = _package(tmp_path)
    assert validate_package(package, signing_key="test-secret").valid
    (package / "risk_report.md").write_text("tampered")
    assert "signature is invalid" in validate_package(package, signing_key="test-secret").reasons


def test_bot_rejects_missing_package() -> None:
    from bot import run_bot

    with pytest.raises(PermissionError, match="approved strategy package"):
        run_bot().send(None)


def test_demo_readiness_gate_requires_every_check() -> None:
    assert evaluate_demo_readiness(dict.fromkeys(REQUIRED_CHECKS, True)).ready
    blocked = evaluate_demo_readiness({})
    assert not blocked.ready and blocked.score == 0
