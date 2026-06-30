"""Tests for the manifest-driven research queue."""

import json
from pathlib import Path

from research.research_queue import (
    ResearchJob,
    ResearchStep,
    load_research_queue,
    run_research_job,
    run_research_queue,
)


def test_load_research_queue_reads_jobs(tmp_path):
    queue = tmp_path / "queue.yaml"
    queue.write_text(
        """
jobs:
  - job_id: J1
    strategy: ST-A2
    symbol: EURUSD
    steps:
      - name: replay
        command: ["python3", "scripts/historical_replay.py"]
      - name: report
""".strip(),
        encoding="utf-8",
    )
    jobs = load_research_queue(queue)
    assert len(jobs) == 1
    assert jobs[0].job_id == "J1"
    assert jobs[0].steps[0].name == "replay"


def test_run_research_job_dry_run_writes_report(tmp_path):
    job = load_research_queue(Path("config/research_queue.yaml"))[0]
    result = run_research_job(job, output_dir=tmp_path, dry_run=True)
    assert result.status == "passed"
    report_path = tmp_path / job.job_id / "report.md"
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "Research Job Report" in report
    assert job.strategy in report


def test_run_research_queue_handles_missing_file(tmp_path):
    results = run_research_queue(
        path=tmp_path / "missing.yaml", output_dir=tmp_path, dry_run=True
    )
    assert results == []


def test_run_research_job_executes_validation_pipeline(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(
        Path("config/strategy_catalog.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    replay_payload = {
        "completed_successfully": True,
        "trades": [
            {
                "trade_id": "T1",
                "timestamp": "2026-06-01T08:00:00Z",
                "side": "long",
                "entry_price": 1.1,
                "stop_loss": 1.095,
                "take_profit": 1.11,
                "position_size": 0.1,
                "required_features": ["sweep", "bias"],
            }
        ],
        "state_transitions": [
            ["IDLE", "SETUP"],
            ["SETUP", "CONFIRMED"],
            ["CONFIRMED", "ORDER_PLACED"],
            ["ORDER_PLACED", "FILLED"],
            ["FILLED", "CLOSED"],
        ],
        "required_features": ["sweep", "bias"],
        "available_features": ["sweep", "bias"],
    }
    backtest_payload = {
        "completed_successfully": True,
        "trade_count": 120,
        "expectancy": 0.12,
        "max_drawdown": 4.5,
        "profit_factor": 1.25,
        "metrics": {
            "trade_count": 120,
            "expectancy": 0.12,
            "max_drawdown": 4.5,
            "profit_factor": 1.25,
            "win_rate": 0.35,
            "net_return": 12.0,
        },
    }

    job = ResearchJob(
        job_id="integration-validation-flow",
        strategy="ST-A2",
        steps=[
            ResearchStep(
                name="write_replay",
                command=[
                    "python3",
                    "-c",
                    (
                        "import os; from pathlib import Path; "
                        "Path(os.environ['JOB_DIR'], 'replay.json').write_text("
                        f"{json.dumps(replay_payload)!r}, encoding='utf-8')"
                    ),
                ],
            ),
            ResearchStep(
                name="replay_validation",
                command=[
                    "python3",
                    "scripts/run_validation_gate.py",
                    "--mode",
                    "replay",
                    "--strategy",
                    "ST-A2",
                    "--replay-json",
                    "${JOB_DIR}/replay.json",
                    "--stage",
                    "replay",
                    "--outdir",
                    "${JOB_DIR}/validation",
                    "--registry",
                    str(catalog_copy),
                ],
            ),
            ResearchStep(
                name="write_backtest",
                command=[
                    "python3",
                    "-c",
                    (
                        "import os; from pathlib import Path; "
                        "Path(os.environ['JOB_DIR'], 'backtest_5y.json').write_text("
                        f"{json.dumps(backtest_payload)!r}, encoding='utf-8')"
                    ),
                ],
            ),
            ResearchStep(
                name="backtest_validation",
                command=[
                    "python3",
                    "scripts/run_validation_gate.py",
                    "--mode",
                    "backtest",
                    "--strategy",
                    "ST-A2",
                    "--backtest-json",
                    "${JOB_DIR}/backtest_5y.json",
                    "--latest-json",
                    "${JOB_DIR}/backtest_5y.json",
                    "--stage",
                    "backtest",
                    "--outdir",
                    "${JOB_DIR}/validation",
                    "--registry",
                    str(catalog_copy),
                ],
            ),
        ],
    )

    result = run_research_job(job, output_dir=tmp_path)
    assert result.status == "passed"
    assert [step.returncode for step in result.steps] == [0, 0, 0, 0]
    assert (tmp_path / job.job_id / "replay.json").exists()
    assert (tmp_path / job.job_id / "backtest_5y.json").exists()
    assert get_strategy_status(catalog_copy, "ST-A2") == "DEFERRED_REVALIDATION"
    assert list((tmp_path / job.job_id / "validation").rglob("validation.md"))


def get_strategy_status(catalog_path: Path, strategy: str) -> str:
    from core.strategy_registry import get_strategy_manifest

    return str(get_strategy_manifest(strategy, catalog_path).get("status", ""))
