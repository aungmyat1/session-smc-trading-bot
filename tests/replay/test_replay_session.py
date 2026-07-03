import json
from datetime import datetime, timezone
from pathlib import Path

from replay.replay_config import ReplayConfig
from replay.replay_session import ReplaySession


def make_config(run_id: str, output: Path, data: Path, package: Path) -> ReplayConfig:
    return ReplayConfig(
        run_id=run_id, symbol="EURUSD", timeframe="M1",
        start_time=datetime(2024, 1, 1, tzinfo=timezone.utc), end_time=datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
        data_path=data, strategy_package_path=package, output_dir=output,
    )


def test_session_writes_all_evidence(sample_candles, strategy_package, tmp_path) -> None:
    config = make_config("evidence", tmp_path / "out", sample_candles, strategy_package)
    result = ReplaySession(config).run()
    assert result.status == "pass"
    assert result.candles_replayed == 2
    assert (config.run_dir / "events.jsonl").exists()
    assert (config.run_dir / "summary.json").exists()
    assert (config.run_dir / "replay_report.md").exists()
    summary = json.loads((config.run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["strategy_package_sha256"]
    assert "not connected" in summary["warnings"][0]


def test_same_input_produces_same_hash(sample_candles, strategy_package, tmp_path) -> None:
    first = ReplaySession(make_config("one", tmp_path / "out", sample_candles, strategy_package)).run()
    second = ReplaySession(make_config("two", tmp_path / "out", sample_candles, strategy_package)).run()
    assert first.deterministic_replay_hash == second.deterministic_replay_hash


def test_replay_package_has_no_execution_or_broker_imports() -> None:
    root = Path(__file__).parents[2] / "replay"
    forbidden = ("from execution", "import execution", "from production", "import production", "metaapi", "place_order")
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in root.glob("*.py"))
    assert not any(term in source for term in forbidden)
