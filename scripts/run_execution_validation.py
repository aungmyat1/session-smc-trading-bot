#!/usr/bin/env python3
"""Run the execution validation suite from a JSON payload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from execution_validation import ExecutionValidationSuite, load_validation_rules
from execution_validation.tests.test_broker_rules import assess_broker_rules


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run execution validation suite")
    parser.add_argument("--payload", help="JSON file with signals/orders/fills/events")
    parser.add_argument("--strategy", default="ST-A2")
    parser.add_argument("--period", default="2023-2026")
    parser.add_argument("--rules", help="Validation rules YAML")
    args = parser.parse_args()

    payload = _load_json(args.payload)
    rules = load_validation_rules(args.rules)
    suite = ExecutionValidationSuite(rules=rules)
    report = suite.run(
        strategy=args.strategy,
        period=args.period,
        signals=payload.get("signals", []),
        orders=payload.get("orders", []),
        fills=payload.get("fills", []),
        execution_events=payload.get("execution_events", []),
        risk_samples=payload.get("risk_samples", []),
        broker_rule_samples=payload.get("broker_rule_samples", []),
        recovery_snapshot=payload.get("recovery_snapshot", {}),
        recovery_expected_open_positions=int(payload.get("recovery_expected_open_positions", 0)),
        backtest_pf=float(payload.get("backtest_pf", 1.0)),
        virtual_pf=float(payload.get("virtual_pf", 1.0)),
    )
    print(report.to_json())
    return 0 if report.status == "READY FOR DEMO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
