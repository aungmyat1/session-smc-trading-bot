from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import scripts.run_current_strategy_svos as run_current_strategy_svos
from research.svos import payload_builder

UTC = timezone.utc


def _bar(
    t: datetime,
    high: float,
    low: float,
    open_: float | None = None,
    close: float | None = None,
) -> dict:
    mid = round((high + low) / 2, 6)
    return {
        "time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open": open_ if open_ is not None else mid,
        "high": high,
        "low": low,
        "close": close if close is not None else mid,
        "volume": 100.0,
    }


def _asian_bars() -> list[dict]:
    base = datetime(2024, 1, 14, 23, 0, tzinfo=UTC)
    return [_bar(base + timedelta(minutes=15 * i), 1.0750, 1.0700) for i in range(32)]


def _h4_bullish() -> list[dict]:
    highs = [1, 2, 5, 2, 1, 2, 3, 3, 2, 1, 8, 2, 1]
    lows = [0.5, 1, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]
    base = datetime(2024, 1, 12, 0, 0, tzinfo=UTC)
    return [
        _bar(base + timedelta(hours=4 * i), float(h), float(lo))
        for i, (h, lo) in enumerate(zip(highs, lows))
    ]


def _full_day() -> list[dict]:
    bars = _asian_bars()
    bars.append(
        _bar(datetime(2024, 1, 15, 7, 0, tzinfo=UTC), 1.0740, 1.0710, close=1.0730)
    )
    bars.append(
        _bar(
            datetime(2024, 1, 15, 7, 15, tzinfo=UTC),
            1.0748,
            1.0682,
            open_=1.0725,
            close=1.0720,
        )
    )
    bars.append(
        _bar(
            datetime(2024, 1, 15, 7, 30, tzinfo=UTC),
            1.0800,
            1.0695,
            open_=1.0700,
            close=1.0790,
        )
    )
    return bars


def test_build_svos_payload_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(
        payload_builder, "load_m15", lambda *args, **kwargs: _full_day()
    )
    monkeypatch.setattr(
        payload_builder, "load_h4", lambda *args, **kwargs: _h4_bullish()
    )

    summary = {
        "run_id": "run-1",
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

    def fake_run(cmd, check, capture_output, text):
        json_out = Path(cmd[cmd.index("--json-out") + 1])
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(summary), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(payload_builder.subprocess, "run", fake_run)

    class DummyReport:
        status = "READY FOR DEMO"

        def to_dict(self):
            return {
                "status": self.status,
                "readiness_status": "READY_FOR_DEMO",
                "final_score": 100,
                "broker_simulation_passed": True,
                "recovery_passed": True,
                "strategy_version_control_passed": True,
            }

    async def fake_execution_validation(*args, **kwargs):
        return DummyReport()

    monkeypatch.setattr(
        payload_builder, "run_replay_validation_from_candles", fake_execution_validation
    )

    bundle = payload_builder.build_svos_payload_bundle(
        strategy="ST-A2",
        symbols=["EURUSD"],
        output_dir=tmp_path,
    )

    assert bundle.replay["trades"]
    assert bundle.backtest["completed_successfully"] is True
    assert bundle.robustness["walk_forward_passed"] is True
    assert bundle.demo["synthetic"] is False
    assert bundle.demo["execution_validation_report"]["status"] == "READY FOR DEMO"
    assert (tmp_path / "svos_payload.json").exists()
    assert (tmp_path / "backtest" / "backtest_summary.json").exists()


def test_run_current_strategy_svos_auto_builds_payload(monkeypatch, tmp_path, capsys):
    recorded: dict[str, object] = {}

    class DummyRunner:
        def __init__(self, *args, **kwargs):
            recorded["runner_init"] = kwargs

        def run_pipeline(self, strategy_text, **kwargs):
            recorded["strategy_text"] = strategy_text
            recorded["run_kwargs"] = kwargs
            observer = kwargs.get("stage_observer")
            if observer is not None:
                from types import SimpleNamespace

                observer(
                    SimpleNamespace(
                        stage="audit",
                        phase=0,
                        status="PASS",
                        next_stage="enhancement",
                        can_promote=True,
                        fix_instructions=[],
                    ),
                    [
                        SimpleNamespace(
                            stage="audit",
                            phase=0,
                            status="PASS",
                            next_stage="enhancement",
                            can_promote=True,
                            fix_instructions=[],
                        )
                    ],
                    None,
                )

            class Result:
                overall_status = "PASS"
                promoted_stage = "demo"

            return Result()

    class DummyBundle:
        def to_dict(self):
            return {
                "replay": {"completed_successfully": True},
                "backtest": {"completed_successfully": True},
                "robustness": {"completed_successfully": True},
                "demo": {
                    "completed_successfully": True,
                    "synthetic": False,
                    "execution_validation_report": {
                        "status": "READY FOR DEMO",
                        "readiness_status": "READY_FOR_DEMO",
                        "final_score": 100,
                        "broker_simulation_passed": True,
                        "recovery_passed": True,
                        "strategy_version_control_passed": True,
                    },
                },
            }

    manifest = {"status": "demo"}
    updates: list[tuple[str, dict[str, object], Path]] = []

    monkeypatch.setattr(
        run_current_strategy_svos,
        "get_current_strategy_name",
        lambda *_args, **_kwargs: "ST-A2",
    )
    monkeypatch.setattr(
        run_current_strategy_svos,
        "get_strategy_manifest",
        lambda *_args, **_kwargs: manifest,
    )
    monkeypatch.setattr(
        run_current_strategy_svos,
        "get_strategy_spec_text",
        lambda *_args, **_kwargs: "Market: FX",
    )
    monkeypatch.setattr(
        run_current_strategy_svos,
        "load_validation_config",
        lambda *_args, **_kwargs: {"ok": True},
    )
    monkeypatch.setattr(
        run_current_strategy_svos,
        "build_svos_payload_bundle",
        lambda **_kwargs: DummyBundle(),
    )
    monkeypatch.setattr(run_current_strategy_svos, "SVOSRunner", DummyRunner)
    monkeypatch.setattr(
        run_current_strategy_svos.sys,
        "argv",
        [
            "run_current_strategy_svos.py",
            "--outdir",
            str(tmp_path / "reports"),
        ],
    )

    exit_code = run_current_strategy_svos.main()
    stderr = capsys.readouterr().err

    assert exit_code == 0
    assert recorded["run_kwargs"]["promote"] is False
    assert recorded["run_kwargs"]["virtual_demo"]["synthetic"] is False
    assert callable(recorded["run_kwargs"]["stage_observer"])
    assert "Virtual Demo Trading" in stderr or "virtual_demo" not in stderr
    assert "next action: proceed to enhancement" in stderr
    assert updates == []
