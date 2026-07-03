from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_canonical_entrypoints_delegate_to_runtime_pipeline_authority() -> None:
    portfolio = (ROOT / "scripts" / "run_portfolio.py").read_text(encoding="utf-8")
    replay = (ROOT / "historical_replay" / "replay_cli.py").read_text(encoding="utf-8")
    assert "authority.run_pipeline(" in portfolio
    assert "authority.run_pipeline(" in replay
    assert "CanonicalExecutionPipeline" in portfolio
    assert "CanonicalExecutionPipeline" in replay


def test_live_adapter_is_structurally_unavailable() -> None:
    pipeline = (ROOT / "production" / "engine" / "execution_pipeline.py").read_text(encoding="utf-8")
    assert 'LIVE = "live"' not in pipeline
    assert "LiveExecutionAdapter" not in pipeline
