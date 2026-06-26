"""Tests for the manifest-driven research queue."""

from pathlib import Path

from research.research_queue import load_research_queue, run_research_job, run_research_queue


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
    results = run_research_queue(path=tmp_path / "missing.yaml", output_dir=tmp_path, dry_run=True)
    assert results == []
