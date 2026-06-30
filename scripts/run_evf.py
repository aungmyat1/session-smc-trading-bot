#!/usr/bin/env python3
"""Run the Execution Validation Framework from a JSON payload."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from execution_simulator.replay_engine.event_stream import \
    MarketEvent  # noqa: E402
from execution_validation import (ExecutionValidationSuite,  # noqa: E402
                                  load_validation_rules)


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _parse_market_event(
    value: dict | MarketEvent | None, symbol: str
) -> MarketEvent | None:
    if value is None or isinstance(value, MarketEvent):
        return value
    timestamp = value.get("timestamp") or value.get("time")
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if not isinstance(timestamp, datetime):
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return MarketEvent(
        timestamp=timestamp,
        symbol=str(value.get("symbol", symbol)),
        bid=float(value["bid"]),
        ask=float(value["ask"]),
        volume=float(value.get("volume", 0.0)),
    )


def _normalize_samples(samples: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for sample in samples:
        item = dict(sample)
        market_event = _parse_market_event(
            item.get("market_event"), str(item.get("symbol", ""))
        )
        if market_event is not None:
            item["market_event"] = market_event
        normalized.append(item)
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Execution Validation Framework"
    )
    parser.add_argument("--payload", help="JSON file with signals/orders/fills/events")
    parser.add_argument("--strategy", default="ST-A2")
    parser.add_argument("--period", default="2023-2026")
    parser.add_argument("--rules", help="Validation rules YAML")
    parser.add_argument("--report-dir", default="execution_validation/reports")
    args = parser.parse_args()

    payload = _load_json(args.payload)
    rules = load_validation_rules(args.rules)
    suite = ExecutionValidationSuite(rules=rules, report_dir=args.report_dir)
    risk_samples = _normalize_samples(payload.get("risk_samples", []))
    broker_rule_samples = _normalize_samples(payload.get("broker_rule_samples", []))
    report = suite.run(
        strategy=args.strategy,
        period=args.period,
        signals=payload.get("signals", []),
        orders=payload.get("orders", []),
        fills=payload.get("fills", []),
        execution_events=payload.get("execution_events", []),
        risk_samples=risk_samples,
        broker_rule_samples=broker_rule_samples,
        recovery_snapshot=payload.get("recovery_snapshot", {}),
        recovery_expected_open_positions=int(
            payload.get("recovery_expected_open_positions", 0)
        ),
        backtest_pf=float(payload.get("backtest_pf", 1.0)),
        virtual_pf=float(payload.get("virtual_pf", 1.0)),
    )
    print(report.to_json())
    return 0 if report.status == "READY FOR DEMO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
