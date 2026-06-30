"""Unit tests for P1-4: strategy-generic backtest dispatch in payload_builder."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from core.strategy_registry import get_backtest_script
from research.svos import payload_builder
from research.svos.payload_builder import _no_backtest_summary

# ── get_backtest_script registry lookup ──────────────────────────────────────


def test_get_backtest_script_sta2_returns_path() -> None:
    result = get_backtest_script("ST-A2")
    assert result is not None
    assert isinstance(result, Path)
    assert result.name == "backtest_session_liquidity.py"


def test_get_backtest_script_sta2_path_resolves_to_scripts_dir() -> None:
    result = get_backtest_script("ST-A2")
    assert result is not None
    assert result.parent.name == "scripts"


def test_get_backtest_script_unknown_strategy_returns_none() -> None:
    assert get_backtest_script("DOES-NOT-EXIST") is None


def test_get_backtest_script_london_breakout_returns_none() -> None:
    assert get_backtest_script("LondonBreakout") is None


def test_get_backtest_script_ny_momentum_returns_none() -> None:
    assert get_backtest_script("NYMomentum") is None


# ── _no_backtest_summary stub ─────────────────────────────────────────────────


def test_no_backtest_summary_any_pass_false() -> None:
    stub = _no_backtest_summary("LondonBreakout")
    assert stub["any_pass"] is False


def test_no_backtest_summary_contains_required_keys() -> None:
    stub = _no_backtest_summary("LondonBreakout")
    assert "best_result" in stub
    assert "std_metrics" in stub["best_result"]
    metrics = stub["best_result"]["std_metrics"]
    for key in ("trade_count", "avg_r", "max_dd", "net_pf", "win_rate", "total_net_r"):
        assert key in metrics


def test_no_backtest_summary_run_id_contains_strategy() -> None:
    stub = _no_backtest_summary("MyStrat")
    assert "MyStrat" in stub["run_id"]


# ── build_svos_payload_bundle dispatches per strategy ────────────────────────


def test_build_svos_payload_bundle_no_script_strategy(tmp_path, monkeypatch) -> None:
    """LondonBreakout has no backtest_script → uses _no_backtest_summary (no subprocess)."""
    monkeypatch.setattr(payload_builder, "load_m15", lambda *a, **kw: [])
    monkeypatch.setattr(payload_builder, "load_h4", lambda *a, **kw: [])

    subprocess_called = []

    original_run = subprocess.run

    def spy_run(cmd, **kwargs):
        if len(cmd) > 1 and "backtest_session_liquidity.py" in str(cmd[1]):
            subprocess_called.append(list(cmd))
        return original_run(cmd, **kwargs)

    monkeypatch.setattr(payload_builder.subprocess, "run", spy_run)

    async def fake_execution_validation(*args, **kwargs):
        return None

    monkeypatch.setattr(
        payload_builder, "run_replay_validation_from_candles", fake_execution_validation
    )

    bundle = payload_builder.build_svos_payload_bundle(
        strategy="LondonBreakout",
        symbols=["EURUSD"],
        output_dir=tmp_path,
    )

    assert (
        subprocess_called == []
    ), "backtest script subprocess.run was unexpectedly called"
    assert bundle.backtest["completed_successfully"] is False
    assert bundle.backtest["trade_count"] == 0


def test_build_svos_payload_bundle_sta2_calls_subprocess(tmp_path, monkeypatch) -> None:
    """ST-A2 has a backtest_script → subprocess.run is invoked with the right script."""
    monkeypatch.setattr(payload_builder, "load_m15", lambda *a, **kw: [])
    monkeypatch.setattr(payload_builder, "load_h4", lambda *a, **kw: [])

    captured_cmd: list[list[str]] = []

    def fake_run(cmd, check, capture_output, text):
        captured_cmd.append(list(cmd))
        json_out = Path(cmd[cmd.index("--json-out") + 1])
        json_out.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "run_id": "st-a2-run",
            "any_pass": True,
            "best_rr": 5.0,
            "best_result": {
                "trades": 120,
                "std_metrics": {
                    "trade_count": 120,
                    "avg_r": 0.12,
                    "max_dd": 4.5,
                    "net_pf": 1.30,
                    "win_rate": 0.35,
                    "total_net_r": 12.0,
                },
            },
        }
        json_out.write_text(json.dumps(summary), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(payload_builder.subprocess, "run", fake_run)

    async def fake_execution_validation(*args, **kwargs):
        return None

    monkeypatch.setattr(
        payload_builder, "run_replay_validation_from_candles", fake_execution_validation
    )

    payload_builder.build_svos_payload_bundle(
        strategy="ST-A2",
        symbols=["EURUSD"],
        output_dir=tmp_path,
    )

    assert len(captured_cmd) == 1, "expected exactly one subprocess call"
    script_arg = captured_cmd[0][1]
    assert "backtest_session_liquidity.py" in script_arg
