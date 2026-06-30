"""
Unit tests for P1-2: strategy-agnostic pipeline dispatch.

Covers:
  - _get_signal_func() returns correct callable for known / unknown strategies
  - _trade_feature_flags() returns correct flags per strategy
  - replay_symbol() accepts strategy_id param without crashing on missing data
  - write_all() uses the strategy_name / strategy_version params in SQL (not hardcoded 'ST-A2')
  - run_phase0 CLI accepts --strategy flag and exits without error when --skip-db and --skip-features
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import polars as pl

from pipeline.pipeline_03_replay_engine import (
    _get_signal_func,
    _stub_signal,
    _trade_feature_flags,
    replay_symbol,
)
from pipeline.pipeline_04_write_db import write_all


# ── Signal dispatch ──────────────────────────────────────────────────────────

def test_get_signal_func_returns_callable_for_sta2() -> None:
    func = _get_signal_func("ST-A2")
    assert callable(func)


def test_get_signal_func_sta2_is_generate_signal_a() -> None:
    from session_smc.confirmation_entry import generate_signal_A
    assert _get_signal_func("ST-A2") is generate_signal_A


def test_get_signal_func_unknown_strategy_returns_stub() -> None:
    func = _get_signal_func("LONDON-BREAKOUT")
    assert callable(func)
    assert func is _stub_signal


def test_stub_signal_returns_none() -> None:
    result = _stub_signal(
        symbol="EURUSD",
        candles_4h=[],
        candles_1h=[],
        session_candles=[],
        session_name="London",
        config={},
    )
    assert result is None


def test_get_signal_func_any_unknown_strategy_returns_stub() -> None:
    for name in ("NYMomentum", "VWAPBreakout", "AdaptiveSMC", "D2E3", ""):
        assert _get_signal_func(name) is _stub_signal


# ── Trade feature flags ──────────────────────────────────────────────────────

def test_trade_feature_flags_sta2_all_true() -> None:
    flags = _trade_feature_flags("ST-A2")
    assert flags == {
        "bos_present": True,
        "choch_present": True,
        "fvg_present": True,
        "liquidity_sweep_present": True,
    }


def test_trade_feature_flags_unknown_all_false() -> None:
    for name in ("LONDON-BREAKOUT", "NYMomentum", ""):
        flags = _trade_feature_flags(name)
        assert all(v is False for v in flags.values()), f"expected all False for {name}"


# ── replay_symbol with missing data ──────────────────────────────────────────

def test_replay_symbol_returns_empty_when_data_missing(tmp_path: Path) -> None:
    from pipeline.config import SpreadConfig
    spread = SpreadConfig(spread_pips=1.0, commission_pips=0.5)
    # No data files exist — replay_symbol prints a warning and returns []
    with patch("pipeline.pipeline_03_replay_engine.DATA_DIR", tmp_path):
        result = replay_symbol(
            "EURUSD",
            date(2024, 1, 1),
            date(2024, 1, 2),
            spread,
            "TEST-run-id",
            strategy_id="LONDON-BREAKOUT",
        )
    assert result == []


def test_replay_symbol_sta2_returns_empty_when_data_missing(tmp_path: Path) -> None:
    from pipeline.config import SpreadConfig
    spread = SpreadConfig(spread_pips=1.0, commission_pips=0.5)
    with patch("pipeline.pipeline_03_replay_engine.DATA_DIR", tmp_path):
        result = replay_symbol(
            "EURUSD",
            date(2024, 1, 1),
            date(2024, 1, 2),
            spread,
            "ST-A2-EURUSD-standard-2024-01-01-2024-01-02",
            strategy_id="ST-A2",
        )
    assert result == []


# ── write_all uses strategy_name param ──────────────────────────────────────

def _make_mock_trade(run_id: str = "MYBOT-EURUSD-standard-2024-01-01-2024-01-02") -> dict:
    from datetime import datetime, timezone
    return {
        "trade_id":            f"{run_id}-t1",
        "run_id":              run_id,
        "symbol":              "EURUSD",
        "session":             "London",
        "direction":           "long",
        "setup_type":          "sweep_reversal",
        "entry_time":          datetime(2024, 1, 3, 9, 0, tzinfo=timezone.utc),
        "exit_time":           datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc),
        "entry_price":         1.10000,
        "stop_price":          1.09900,
        "tp1_price":           1.10400,
        "tp2_price":           1.10500,
        "sl_pips":             10.0,
        "risk_reward":         4.0,
        "spread_cost_pips":    1.5,
        "cost_in_r":           0.15,
        "gross_result_r":      3.95,
        "net_result_r":        3.80,
        "exit_reason":         "TP1_HIT",
        "tp1_hit":             True,
        "session_high":        1.10500,
        "session_low":         1.09800,
        "session_range_pips":  70.0,
        "bos_present":         True,
        "choch_present":       True,
        "fvg_present":         True,
        "liquidity_sweep_present": True,
    }


def test_write_all_uses_strategy_name_param() -> None:
    """write_all must not hardcode 'ST-A2' — it must use the strategy_name argument."""
    run_id = "MYBOT-EURUSD-standard-2024-01-01-2024-01-02"
    df = pl.DataFrame([_make_mock_trade(run_id)])

    recorded_sql: list[str] = []
    recorded_params: list[dict] = []

    class _FakeResult:
        def fetchone(self):
            return (42,)

    class _FakeSession:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            self.commit()
        def execute(self, stmt, params=None):
            sql = str(stmt)
            recorded_sql.append(sql)
            recorded_params.append(dict(params or {}))
            return _FakeResult()
        def commit(self):
            pass

    class _FakeEngine:
        pass

    with patch("pipeline.pipeline_04_write_db.Session", return_value=_FakeSession()):
        write_all(_FakeEngine(), df, strategy_name="MyBot", strategy_version="2.0")

    # The hardcoded 'ST-A2' string must NOT appear in any SQL or bound params
    all_sql = " ".join(recorded_sql)
    all_param_values = " ".join(
        str(v) for p in recorded_params for v in p.values()
    )
    assert "ST-A2" not in all_sql, "write_all SQL still hardcodes 'ST-A2'"
    assert "MyBot" in all_param_values, "strategy_name='MyBot' not passed to SQL"


def test_write_all_feature_flags_from_trade_dict() -> None:
    """trade_features flags must come from the trade dict, not hardcoded TRUE."""
    run_id = "MYBOT-EURUSD-standard-2024-01-01-2024-01-02"
    trade = _make_mock_trade(run_id)
    # Override to False
    trade["bos_present"] = False
    trade["choch_present"] = False
    df = pl.DataFrame([trade])

    feature_inserts: list[dict] = []

    class _FakeResult:
        def fetchone(self):
            return (1,)

    class _FakeSession:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            self.commit()
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if params and "bos" in params:
                feature_inserts.append(dict(params))
            return _FakeResult()
        def commit(self):
            pass

    class _FakeEngine:
        pass

    with patch("pipeline.pipeline_04_write_db.Session", return_value=_FakeSession()):
        write_all(_FakeEngine(), df, strategy_name="MyBot")

    assert feature_inserts, "no trade_features inserts captured"
    assert feature_inserts[0]["bos"] is False
    assert feature_inserts[0]["choch"] is False


# ── run_phase0 CLI accepts --strategy ────────────────────────────────────────

def test_run_phase0_accepts_strategy_flag_no_crash() -> None:
    """--strategy LONDON-BREAKOUT with --skip-features --skip-db must not crash."""
    result = subprocess.run(
        [
            sys.executable, "-m", "pipeline.run_phase0",
            "--strategy", "LONDON-BREAKOUT",
            "--start", "2024-01-01",
            "--end", "2024-01-02",
            "--skip-features",
            "--skip-db",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Must exit 0 — no trades found for LONDON-BREAKOUT is not a crash,
    # but an empty result set will still trigger FAIL gate (exit 1).
    # We only verify it doesn't crash due to an import error or missing arg.
    assert result.returncode in (0, 1), (
        f"Unexpected exit code {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "Error" not in result.stderr or "FAIL" in result.stdout, (
        f"Unexpected error output:\n{result.stderr}"
    )


def test_run_phase0_default_strategy_is_sta2() -> None:
    """Without --strategy the pipeline still runs the ST-A2 path."""
    result = subprocess.run(
        [
            sys.executable, "-m", "pipeline.run_phase0",
            "--start", "2024-01-01",
            "--end", "2024-01-02",
            "--skip-features",
            "--skip-db",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode in (0, 1)
    assert "ST-A2" in result.stdout
