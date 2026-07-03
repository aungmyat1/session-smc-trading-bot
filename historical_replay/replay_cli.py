from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from historical_replay.market_data_loader import load_m1_candles
from historical_replay.replay_engine import ReplayEngine
from historical_replay.replay_report import write_replay_report
from shared.configuration.symbols import enabled_symbols
from shared.serialization import append_jsonl
from production.engine import (
    AllowAllRiskGate,
    CanonicalExecutionPipeline,
    ExecutionIntent,
    ReplayExecutionAdapter,
    RuntimeAuthority,
    RuntimeContext,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic no-signal replay audit")
    parser.add_argument("data")
    parser.add_argument("--pair", required=True, choices=enabled_symbols("research"))
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--output", default="reports/replay")
    parser.add_argument("--strategy-package", required=True)
    parser.add_argument("--strategy-id")
    args = parser.parse_args()
    candles = load_m1_candles(args.data, start=args.start, end=args.end)
    authority = RuntimeAuthority(
        root=Path.cwd(),
        package_path=args.strategy_package,
        verifying_public_key=os.environ.get("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", ""),
        expected_strategy_id=args.strategy_id,
    )
    output = Path(args.output)
    replay_result = None

    def pipeline_factory(_context: RuntimeContext) -> CanonicalExecutionPipeline:
        return CanonicalExecutionPipeline(
            mode="replay",
            risk_gate=AllowAllRiskGate(),
            adapter=ReplayExecutionAdapter(),
            event_sink=lambda event: append_jsonl(output / "execution-events.jsonl", event.to_dict()),
        )

    async def workload(pipeline: CanonicalExecutionPipeline) -> None:
        nonlocal replay_result
        replay_result = ReplayEngine(args.pair, candles, lambda _: None).run()
        for index, event in enumerate(replay_result.events):
            signal = event.signal
            await pipeline.submit(
                ExecutionIntent(
                    intent_id=f"{replay_result.run_id}:{index}",
                    strategy_id=args.strategy_id or "replay-audit",
                    symbol=args.pair,
                    side=str(signal.get("side", signal.get("direction", "none"))),
                    quantity=float(signal.get("quantity", signal.get("lots", 0.0))),
                    metadata={"replay_timestamp": event.timestamp, "signal": signal},
                )
            )

    asyncio.run(authority.run_pipeline(pipeline_factory, workload))
    assert replay_result is not None
    json_path, _ = write_replay_report(replay_result, args.output)
    print(f"replay_run_id={replay_result.run_id} report={json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
