from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import scripts.generate_reports as generate_reports


UTC = timezone.utc


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _configure_tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for rel in ["logs", "data", "config", "reports", "docs"]:
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)

    _write(
        tmp_path / "config" / "strategy_catalog.yaml",
        """
current_strategy: ST-A2
strategies:
  ST-A2:
    status: walk_forward
    approved: true
    deployment_target: execution
    symbols: [EURUSD, GBPUSD]
    last_svos_status: FAIL
    last_svos_verification_ready: true
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "config" / "demo.yaml",
        """
execution:
  mode: demo
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "config" / "research_engine.yaml",
        """
analytics:
  duckdb_path: research.db
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "logs" / "st_a2_runner.log",
        "2026-06-28 11:59:00 INFO runner heartbeat ok\n",
    )
    _write(
        tmp_path / "logs" / "bot.log",
        "\n".join(
            [
                "2026-06-28 12:00:00 INFO bot [HEARTBEAT] connection_status=CONNECTED",
                "2026-06-28 12:01:00 INFO bot MetaAPI connected",
                "2026-06-28 12:02:00 ERROR bot sample error for testing",
            ]
        )
        + "\n",
    )
    _write(
        tmp_path / "logs" / "bot_state.json",
        json.dumps(
            {
                "trades_today": 2,
                "open_positions": 1,
                "daily_loss_pct": 0.0025,
                "consecutive_losses": 1,
                "halted": False,
                "halt_reason": "",
            }
        ),
    )
    _write(
        tmp_path / "logs" / "st_a2_demo_trades.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "record_type": "open",
                        "timestamp": "2026-06-28T10:00:00+00:00",
                        "symbol": "EURUSD",
                        "session": "london",
                        "strategy": "ST-A2",
                    }
                ),
                json.dumps(
                    {
                        "record_type": "close",
                        "timestamp": "2026-06-28T11:00:00+00:00",
                        "result_R": 1.5,
                    }
                ),
            ]
        )
        + "\n",
    )
    _write(
        tmp_path / "logs" / "trades.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "SIGNAL_CREATED",
                        "ts": "2026-06-28T10:00:00+00:00",
                        "symbol": "EURUSD",
                        "session": "london",
                    }
                ),
                json.dumps(
                    {
                        "event": "ORDER_SUBMITTED",
                        "ts": "2026-06-28T10:00:01+00:00",
                        "symbol": "EURUSD",
                    }
                ),
                json.dumps(
                    {
                        "event": "ORDER_FILLED",
                        "ts": "2026-06-28T10:00:02+00:00",
                        "symbol": "EURUSD",
                    }
                ),
                json.dumps(
                    {
                        "event": "POSITION_CLOSED",
                        "ts": "2026-06-28T11:00:00+00:00",
                        "symbol": "EURUSD",
                    }
                ),
                json.dumps(
                    {
                        "event": "ORDER_REJECTED",
                        "ts": "2026-06-28T11:10:00+00:00",
                        "symbol": "EURUSD",
                        "reason": "SPREAD_TOO_WIDE:2.1pip",
                    }
                ),
            ]
        )
        + "\n",
    )

    monkeypatch.setenv("DB_BACKEND", "duckdb")
    monkeypatch.setattr(generate_reports, "ROOT", tmp_path)
    monkeypatch.setattr(generate_reports, "TRADE_EVENT_LOG", tmp_path / "logs" / "trades.jsonl")
    monkeypatch.setattr(generate_reports, "BOT_LOG", tmp_path / "logs" / "bot.log")
    monkeypatch.setattr(generate_reports, "RUNNER_LOG", tmp_path / "logs" / "st_a2_runner.log")
    monkeypatch.setattr(generate_reports, "DEMO_JOURNALS", [tmp_path / "logs" / "st_a2_demo_trades.jsonl"])
    monkeypatch.setattr(generate_reports, "TRADE_DB", tmp_path / "data" / "trade_journal.db")
    monkeypatch.setattr(generate_reports, "BOT_STATE", tmp_path / "logs" / "bot_state.json")
    monkeypatch.setattr(generate_reports, "EXECUTION_DAILY", tmp_path / "logs" / "execution_summary_daily.json")
    monkeypatch.setattr(generate_reports, "EXECUTION_WEEKLY", tmp_path / "logs" / "execution_summary_weekly.json")
    monkeypatch.setattr(generate_reports, "CATALOG", tmp_path / "config" / "strategy_catalog.yaml")
    monkeypatch.setattr(generate_reports, "DEMO_CONFIG", tmp_path / "config" / "demo.yaml")
    monkeypatch.setattr(generate_reports, "VALIDATION_CONFIG", tmp_path / "config" / "validation.yaml")
    monkeypatch.setattr(generate_reports.health_check, "_ROOT", tmp_path)


def test_report_directories_exist():
    required = [
        Path("reports/daily"),
        Path("reports/weekly"),
        Path("reports/monthly"),
        Path("reports/strategy"),
        Path("reports/risk"),
        Path("reports/execution"),
        Path("reports/system_health"),
        Path("reports/incidents"),
        Path("reports/live_readiness"),
    ]
    for path in required:
        assert path.exists(), f"missing report directory: {path}"


def test_generate_daily_report_creates_markdown_with_required_sections(tmp_path, monkeypatch):
    _configure_tmp_repo(tmp_path, monkeypatch)
    ts = datetime(2026, 6, 28, 12, 30, tzinfo=UTC)

    path = generate_reports.generate_report("daily", root=tmp_path, generated_at=ts)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "# Daily Trading Report" in content
    assert "System mode" in content
    assert "Trades opened" in content
    assert "Trades closed" in content
    assert "Win rate" in content
    assert "Net R" in content
    assert "Profit factor" in content
    assert "Max drawdown" in content
    assert "Rejected signals" in content
    assert "Risk limit status" in content
    assert "Database status" in content
    assert "Broker status" in content
    assert "Critical incidents" in content
    assert "Final recommendation" in content


def test_generate_all_reports_creates_markdown_files(tmp_path, monkeypatch):
    _configure_tmp_repo(tmp_path, monkeypatch)
    ts = datetime(2026, 6, 28, 12, 30, tzinfo=UTC)

    artifacts = generate_reports.generate_many("all", root=tmp_path, generated_at=ts)

    assert len(artifacts) == 9
    assert all(artifact.path.exists() for artifact in artifacts)


def test_invalid_report_type_fails_cleanly():
    with pytest.raises(ValueError, match="Unsupported report type"):
        generate_reports.generate_report("not-a-real-report")


def test_report_generation_does_not_call_live_broker_checks(tmp_path, monkeypatch):
    _configure_tmp_repo(tmp_path, monkeypatch)
    ts = datetime(2026, 6, 28, 12, 30, tzinfo=UTC)

    def _forbidden(*args, **kwargs):
        raise AssertionError("live broker checks must not run during report generation")

    monkeypatch.setattr(generate_reports.health_check, "check_broker", _forbidden)
    monkeypatch.setattr(generate_reports.health_check, "check_data_feed", _forbidden)

    path = generate_reports.generate_report("system-health", root=tmp_path, generated_at=ts)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Database connection" in content
    assert "Broker/API connection" in content
