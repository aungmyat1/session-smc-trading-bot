from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from datetime import date
from pathlib import Path
from uuid import uuid4

from replay.replay_config import ReplayConfig, parse_timestamp
from replay.replay_session import ReplaySession
from research_db.readiness import check_database


def _run(args: argparse.Namespace) -> int:
    if not args.allow_incomplete_data:
        readiness = check_database(
            [args.symbol],
            date.fromisoformat(args.start[:10]),
            date.fromisoformat(args.end[:10]),
        )
        if readiness["status"] != "READY":
            print(json.dumps({"status": "NOT_READY", "readiness": readiness}))
            return 2
    config = ReplayConfig(
        run_id=args.run_id or f"replay-{uuid4().hex[:12]}", symbol=args.symbol, timeframe=args.timeframe,
        start_time=parse_timestamp(args.start), end_time=parse_timestamp(args.end), data_path=Path(args.data),
        strategy_package_path=Path(args.strategy_package), output_dir=Path(args.output_dir),
    )
    result = ReplaySession(config).run()
    print(json.dumps({"run_id": config.run_id, "status": result.status, "hash": result.deterministic_replay_hash, "output": str(config.run_dir)}))
    return 0 if result.status == "pass" else 1


def _self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="svos-replay-") as directory:
        root = Path(directory)
        data = root / "sample.csv"
        data.write_text(
            "symbol,timestamp,open,high,low,close,volume,timeframe,source\n"
            "EURUSD,2024-01-01T00:00:00Z,1.10,1.11,1.09,1.105,100,M1,self-test\n"
            "EURUSD,2024-01-01T00:01:00Z,1.105,1.12,1.10,1.115,120,M1,self-test\n",
            encoding="utf-8",
        )
        package = root / "example.package.json"
        package.write_text("{}\n", encoding="utf-8")
        config = ReplayConfig(
            run_id="self-test", symbol="EURUSD", timeframe="M1",
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc), end_time=datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
            data_path=data, strategy_package_path=package, output_dir=root / "artifacts" / "replay",
        )
        result = ReplaySession(config).run()
        required = [config.run_dir / "events.jsonl", config.run_dir / "summary.json", config.run_dir / "replay_report.md"]
        if result.status != "pass" or result.candles_replayed != 2 or not all(path.exists() for path in required):
            print("self-test failed")
            return 1
        print(f"self-test passed hash={result.deterministic_replay_hash}")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic SVOS System 1 historical replay")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test", help="run a broker-free replay using temporary candle data")
    run = commands.add_parser("run", help="replay historical candles")
    run.add_argument("--symbol", required=True)
    run.add_argument("--timeframe", required=True)
    run.add_argument("--from", dest="start", required=True)
    run.add_argument("--to", dest="end", required=True)
    run.add_argument("--data", required=True)
    run.add_argument("--strategy-package", required=True)
    run.add_argument("--run-id")
    run.add_argument("--output-dir", default="artifacts/replay")
    run.add_argument(
        "--allow-incomplete-data",
        action="store_true",
        help="research-only override; run despite a NOT_READY canonical database gate",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return _self_test() if args.command == "self-test" else _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
