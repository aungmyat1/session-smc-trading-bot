from __future__ import annotations

from execution.risk_manager import RiskManager
from execution.trade_logger import TradeLogger
from tests.test_ops01_safety import BASE_CONFIG


def test_build_recovery_summary_reflects_loaded_state_and_journal(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "execution.risk_manager.STATE_FILE", tmp_path / "bot_state.json"
    )

    risk = RiskManager(BASE_CONFIG)
    risk._state.daily_loss_r = 1.25
    risk._state.weekly_loss_r = 2.50
    risk._state.consecutive_losses = 2
    risk._state.halted = True
    risk._state.halt_reason = "MAX_DAILY_LOSS"
    risk._save_state()

    log_file = tmp_path / "trades.jsonl"
    journal = TradeLogger(log_file)
    journal.signal_created(
        "EURUSD",
        "london",
        "long",
        1.08,
        1.07,
        1.10,
        10.0,
        signal_ts="2026-06-27T08:00:00Z",
    )
    journal.order_submitted(
        "EURUSD", "london", "long", 0.01, 1.07, 1.10, 0.01, 10_000.0, 1.0
    )
    journal.order_filled("EURUSD", "O1", 1.08, 0.01, 1.07, 1.10)
    journal.position_closed("EURUSD", "P1", 1.5, "TP")
    journal.error("EURUSD", "boom", "scan")

    from bot import _build_recovery_summary, _load_seen_signals

    seen = _load_seen_signals(journal, ["EURUSD"])
    summary = _build_recovery_summary(journal, risk, seen)

    assert "recovered_signals=1" in summary
    assert "signals=1" in summary
    assert "closes=1" in summary
    assert "halted=True" in summary
    assert "MAX_DAILY_LOSS" in summary
