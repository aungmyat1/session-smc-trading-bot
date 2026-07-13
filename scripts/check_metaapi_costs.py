#!/usr/bin/env python3
"""Read-only MetaAPI spread/cost sampler for demo accounts."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from execution.mt5_connector import MT5Connector, resolve_metaapi_account_id
from execution.vantage_demo_executor import VantageDemoExecutor as MetaApiDemoExecutor
from strategy.session_liquidity.session_builder import classify_session

REPORT_PATH = _ROOT / "reports" / "metaapi_cost_check.json"
MISMATCH_REPORT_PATH = _ROOT / "reports" / "metaapi_cost_check.BROKER_IDENTITY_MISMATCH.json"
BROKER_SYMBOL_MAPPING_PATH = _ROOT / "config" / "broker_symbol_mapping.yaml"

try:
    import yaml
except ImportError:  # pragma: no cover - project runtime includes PyYAML
    yaml = None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p / 100
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)


def ceil_to(value: float, increment: float) -> float:
    return math.ceil(round(value / increment, 8)) * increment


def stats(values: list[float], commission_pips: float) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "avg_spread_pips": None,
            "median_spread_pips": None,
            "p95_spread_pips": None,
            "max_spread_pips": None,
            "recommended_standard_cost_pips": None,
            "recommended_stress2x_cost_pips": None,
        }
    p95 = percentile(values, 95) or 0.0
    standard = ceil_to(p95 + commission_pips, 0.05)
    return {
        "n": len(values),
        "avg_spread_pips": round(statistics.mean(values), 4),
        "median_spread_pips": round(statistics.median(values), 4),
        "p95_spread_pips": round(p95, 4),
        "max_spread_pips": round(max(values), 4),
        "recommended_standard_cost_pips": round(standard, 4),
        "recommended_stress2x_cost_pips": round(standard * 2, 4),
    }


def normalize_broker_name(value: str) -> str:
    normalized = value.lower().replace("-", "_")
    return "vt_markets" if normalized in {"vtmarkets", "vt_markets"} else normalized


def preserve_broker_identity_mismatch() -> None:
    if not REPORT_PATH.exists():
        return
    try:
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    broker = normalize_broker_name(str(report.get("broker", "")))
    if broker != "vantage":
        return
    redact_account_metadata(report)
    report["broker_identity_status"] = "BROKER_IDENTITY_MISMATCH"
    report["corrected_broker"] = "vt_markets"
    report["preservation_note"] = (
        "Raw observations preserved; report regenerated with VT Markets demo provenance."
    )
    MISMATCH_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MISMATCH_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    REPORT_PATH.with_suffix(".pre-broker-correction.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )


def redact_account_metadata(report: dict[str, Any]) -> None:
    account = report.get("account")
    if isinstance(account, dict):
        account["account_id"] = "[REDACTED]"


def load_symbol_mapping() -> dict[str, Any]:
    if yaml is None or not BROKER_SYMBOL_MAPPING_PATH.exists():
        return {}
    payload = yaml.safe_load(BROKER_SYMBOL_MAPPING_PATH.read_text(encoding="utf-8"))
    return payload or {}


def write_symbol_mapping(payload: dict[str, Any]) -> None:
    if yaml is None:
        return
    BROKER_SYMBOL_MAPPING_PATH.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def spec_value(spec: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in spec:
            return spec[name]
    return None


def gold_candidate_symbols(symbols: list[str]) -> list[str]:
    candidates: list[str] = []
    for symbol in symbols:
        upper = symbol.upper()
        if "XAU" in upper or "GOLD" in upper:
            candidates.append(symbol)
    return candidates


def non_trading_spec(spec: dict[str, Any], description: str) -> bool:
    text = description.upper()
    if "NOT FOR TRADING" in text or "CONVERSION" in text:
        return True
    trade_mode = str(spec_value(spec, "tradeMode", "trade_mode") or "").lower()
    return trade_mode in {"disabled", "closeonly", "close_only"}


async def resolve_broker_symbols(executor: MetaApiDemoExecutor, canonical_symbols: list[str]) -> dict[str, dict[str, Any]]:
    available_symbols = await executor.get_symbols()
    resolved: dict[str, dict[str, Any]] = {}

    for canonical in canonical_symbols:
        if canonical != "XAUUSD":
            resolved[canonical] = {
                "canonical_symbol": canonical,
                "broker_symbol": canonical if canonical in available_symbols else None,
                "source": "metaapi_get_symbols_exact_match",
                "specification": None,
            }
            continue

        matches: list[dict[str, Any]] = []
        for broker_symbol in gold_candidate_symbols(available_symbols):
            try:
                spec = await executor.get_symbol_specification(broker_symbol)
            except Exception:
                continue
            base = str(spec_value(spec, "baseCurrency", "base_currency") or "").upper()
            quote = str(
                spec_value(spec, "quoteCurrency", "quote_currency", "profitCurrency", "profit_currency") or ""
            ).upper()
            description = str(spec_value(spec, "description", "path") or "")
            if non_trading_spec(spec, description):
                continue
            if base == "XAU" or "GOLD" in description.upper() or "XAU" in broker_symbol.upper():
                matches.append(
                    {
                        "canonical_symbol": canonical,
                        "broker_symbol": broker_symbol,
                        "source": "metaapi_symbol_specification",
                        "base_currency": base or None,
                        "quote_or_profit_currency": quote or None,
                        "description": description or None,
                        "specification": spec,
                    }
                )

        usd_matches = [
            item for item in matches
            if item.get("quote_or_profit_currency") == "USD" or "USD" in item["broker_symbol"].upper()
        ]
        selected = usd_matches[0] if len(usd_matches) == 1 else (matches[0] if len(matches) == 1 else None)
        resolved[canonical] = selected or {
            "canonical_symbol": canonical,
            "broker_symbol": None,
            "source": "metaapi_symbol_specification_unresolved",
            "candidate_count": len(matches),
            "candidates": [
                {
                    "broker_symbol": item["broker_symbol"],
                    "base_currency": item.get("base_currency"),
                    "quote_or_profit_currency": item.get("quote_or_profit_currency"),
                    "description": item.get("description"),
                }
                for item in matches
            ],
            "specification": None,
        }
    return resolved


def update_mapping_file(resolved: dict[str, dict[str, Any]]) -> None:
    payload = load_symbol_mapping() or {
        "version": 1,
        "provider": "metaapi",
        "brokers": {},
    }
    broker_payload = payload.setdefault("brokers", {}).setdefault(
        "vt_markets",
        {"account_environment": "demo", "symbols": {}},
    )
    broker_payload["account_environment"] = "demo"
    symbols_payload = broker_payload.setdefault("symbols", {})
    for canonical, item in resolved.items():
        broker_symbol = item.get("broker_symbol")
        if not broker_symbol:
            continue
        entry = {
            "broker_symbol": broker_symbol,
            "source": item.get("source", "metaapi_get_symbols"),
        }
        if item.get("base_currency"):
            entry["base_currency"] = item["base_currency"]
        if item.get("quote_or_profit_currency"):
            entry["quote_or_profit_currency"] = item["quote_or_profit_currency"]
        symbols_payload[canonical] = entry
    write_symbol_mapping(payload)


def account_metadata(connector: MT5Connector, account_info: dict[str, Any]) -> dict[str, Any]:
    account = connector._account
    data = getattr(account, "_data", {}) if account is not None else {}
    if not isinstance(data, dict):
        data = {}
    return {
        "account_id": "[REDACTED]",
        "account_env_key": connector._account_env_key,
        "currency": account_info["currency"],
        "equity": account_info["equity"],
        "state": getattr(account, "state", data.get("state", "")),
        "server": getattr(account, "server", data.get("server", "")),
        "type": data.get("type", ""),
        "region": data.get("region", ""),
    }


async def run(args: argparse.Namespace) -> int:
    if os.getenv("LIVE_TRADING", "false").strip().lower() in {"true", "1", "yes"}:
        print("FAIL: LIVE_TRADING must remain false for this check")
        return 2

    if args.account_url:
        account_id = resolve_metaapi_account_id(args.account_url)
        if account_id == args.account_url:
            print("FAIL: --account-url must be a MetaAPI setup URL containing an account UUID")
            return 2
        if args.broker == "vtmarkets":
            os.environ["VTMARKETS_DEMO_METAAPI_ID"] = account_id
        else:
            os.environ["VANTAGE_DEMO_METAAPI_ID"] = account_id

    broker = normalize_broker_name(args.broker)
    connector = MT5Connector(mode="demo", broker=args.broker)
    executor = MetaApiDemoExecutor(connector)
    samples: dict[str, list[float]] = defaultdict(list)
    raw_samples: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    started_at = datetime.now(timezone.utc)
    session = classify_session(started_at) or "off"

    try:
        await connector.connect()
        account = await executor.get_account_info()
        preserve_broker_identity_mismatch()
        resolved_symbols = await resolve_broker_symbols(executor, args.symbols)
        update_mapping_file(resolved_symbols)
        for idx in range(args.samples):
            sampled_at = datetime.now(timezone.utc)
            session = classify_session(sampled_at) or "off"
            for symbol in args.symbols:
                try:
                    broker_symbol = resolved_symbols.get(symbol, {}).get("broker_symbol")
                    if not broker_symbol:
                        raise RuntimeError(f"{symbol} broker symbol unresolved from MetaAPI specifications")
                    price = await executor.get_price(broker_symbol, canonical_symbol=symbol)
                    spread = float(price["spread_pips"])
                    samples[symbol].append(spread)
                    raw_samples.append(
                        {
                            "time_utc": sampled_at.isoformat(),
                            "symbol": symbol,
                            "broker_symbol": broker_symbol,
                            "session": session,
                            "bid": price["bid"],
                            "ask": price["ask"],
                            "spread_pips": spread,
                        }
                    )
                except Exception as exc:
                    errors.append(
                        {
                            "time_utc": sampled_at.isoformat(),
                            "symbol": symbol,
                            "error": str(exc) or exc.__class__.__name__,
                        }
                    )
            if idx < args.samples - 1:
                await asyncio.sleep(args.interval)

        generated_at = datetime.now(timezone.utc).isoformat()
        symbols = {
            symbol: stats(samples[symbol], args.commission_pips)
            for symbol in args.symbols
        }
        report = {
            "generated_at": generated_at,
            "provider": "metaapi",
            "broker": broker,
            "account_environment": "demo",
            "profile_candidate": "vtmarkets_demo_measured" if broker == "vt_markets" else f"{broker}_demo_measured",
            "mode": "demo",
            "session": session,
            "commission_pips_added": args.commission_pips,
            "account": account_metadata(connector, account),
            "broker_symbol_mapping": {
                symbol: {
                    key: value for key, value in item.items()
                    if key != "specification"
                }
                for symbol, item in resolved_symbols.items()
            },
            "symbols": symbols,
            "raw_samples": raw_samples,
            "errors": errors,
            "promotion_status": (
                "SNAPSHOT_ONLY_NOT_FOR_BACKTEST_PROFILE"
                if session == "off" or args.samples < args.min_qualifying_samples
                else "CANDIDATE_NEEDS_MULTI_SESSION_REVIEW"
            ),
            "evidence_status": "DEMO_ACCOUNT_EVIDENCE_ONLY",
            "notes": [
                "Read-only check: no orders were placed.",
                "Do not replace config/costs.json from a short/off-session snapshot.",
                "Qualified cost profiles require killzone samples across London and New York sessions.",
                "Demo-account costs must not be described as VT Markets live-account costs.",
                "VT Markets measurements must not be written into vantage_measured.",
            ],
        }
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

        print("PASS: MetaAPI demo cost snapshot captured")
        print(f"broker={broker} session={session} account_equity={account['equity']:.2f} {account['currency']}")
        for symbol, data in symbols.items():
            broker_symbol = resolved_symbols.get(symbol, {}).get("broker_symbol")
            print(
                f"{symbol}({broker_symbol or 'unresolved'}): n={data['n']} avg={data['avg_spread_pips']}p "
                f"p95={data['p95_spread_pips']}p max={data['max_spread_pips']}p "
                f"std_cost={data['recommended_standard_cost_pips']}p "
                f"stress2x={data['recommended_stress2x_cost_pips']}p"
            )
        if errors:
            print(f"warnings={len(errors)} symbol sample errors; see report")
        print(f"report={REPORT_PATH.relative_to(_ROOT)}")
        return 0
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        print(f"FAIL: MetaAPI demo cost check failed: {detail}")
        return 1
    finally:
        await connector.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker", choices=["vantage", "vtmarkets"], default="vtmarkets")
    parser.add_argument("--account-url", default=None)
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD", "XAUUSD"])
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--commission-pips", type=float, default=0.0)
    parser.add_argument("--min-qualifying-samples", type=int, default=100)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
