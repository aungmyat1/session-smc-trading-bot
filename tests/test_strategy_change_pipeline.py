"""Tests for the strategy change promotion pipeline manifest."""

from research.research_queue import load_research_queue, run_research_job


def test_strategy_change_pipeline_step_order():
    jobs = load_research_queue("config/strategy_change_pipeline.yaml")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_id == "ST-A2-change-flow"
    assert [step.name for step in job.steps] == [
        "unit_tests",
        "golden_dataset",
        "historical_replay_3m",
        "quick_backtest_1y",
        "full_backtest_5y",
        "walk_forward",
        "shadow",
        "demo",
        "live",
    ]


def test_strategy_change_pipeline_blocks_live_stage(tmp_path):
    job = load_research_queue("config/strategy_change_pipeline.yaml")[0]
    result = run_research_job(job, output_dir=tmp_path, dry_run=True)
    assert result.status == "blocked"
    assert result.steps[-1].name == "shadow"
    assert result.steps[-1].message.startswith("Shadow trading requires")
    assert job.steps[-1].name == "live"
