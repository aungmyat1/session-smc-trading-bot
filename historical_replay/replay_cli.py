from __future__ import annotations

import argparse

from historical_replay.market_data_loader import load_m1_candles
from historical_replay.replay_engine import ReplayEngine
from historical_replay.replay_report import write_replay_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic no-signal replay audit")
    parser.add_argument("data")
    parser.add_argument("--pair", required=True, choices=["EURUSD", "GBPUSD", "XAUUSD"])
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--output", default="reports/replay")
    args = parser.parse_args()
    candles = load_m1_candles(args.data, start=args.start, end=args.end)
    result = ReplayEngine(args.pair, candles, lambda _: None).run()
    json_path, _ = write_replay_report(result, args.output)
    print(f"replay_run_id={result.run_id} report={json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
