from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline.strategy_validation_pipeline import StrategyValidationPipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate strategy specifications before replay."
    )
    parser.add_argument(
        "--spec", required=True, help="Path to a strategy specification markdown file"
    )
    parser.add_argument(
        "--outdir", default="reports/strategy_validation", help="Output directory"
    )
    args = parser.parse_args(argv)

    pipeline = StrategyValidationPipeline()
    report = pipeline.run_file(args.spec)
    spec_path = Path(args.spec)
    output_dir = Path(args.outdir) / report.strategy_name
    pipeline.write_report(report, output_dir)
    print(
        json.dumps(
            {
                "strategy": report.strategy_name,
                "source": str(spec_path),
                "overall_status": report.overall_status,
                "overall_score": report.overall_score,
                "readiness_decision": report.readiness_decision,
                "report_dir": str(output_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.readiness_decision == "READY_FOR_REPLAY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
