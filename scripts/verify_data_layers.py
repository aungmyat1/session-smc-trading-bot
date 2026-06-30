#!/usr/bin/env python3
"""Verify the layered research-data layout, schemas, and freshness."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"

DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]
DEFAULT_TIMEFRAMES = ["M1", "M5", "M15", "H1", "H4", "D1"]
REQUIRED_RAW_COLS = {"timestamp_ms", "ask", "bid", "ask_vol", "bid_vol"}
REQUIRED_NORMALIZED_COLS = {"timestamp_utc", "bid", "ask", "spread", "ask_vol", "bid_vol"}
REQUIRED_MARKET_SCHEMA_VARIANTS = [
    {
        "timestamp_utc",
        "symbol",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "real_volume",
        "spread_mean",
        "spread_max",
    },
    {
        "timestamp_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ask_open",
        "bid_open",
        "spread_avg",
        "spread_max",
        "tick_count",
    },
]


@dataclass
class LayerIssue:
    severity: str
    layer: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LayerResult:
    layer: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    issues: list[LayerIssue] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _mtime_utc(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _freshness_hours(path: Path) -> float | None:
    if not path.exists():
        return None
    delta = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return round(delta.total_seconds() / 3600.0, 2)


def _add_issue(results: list[LayerIssue], severity: str, layer: str, message: str, **details: Any) -> None:
    results.append(LayerIssue(severity=severity, layer=layer, message=message, details=details))


def _check_dir(layer: str, path: Path, issues: list[LayerIssue]) -> dict[str, Any]:
    exists = path.exists() and path.is_dir()
    if not exists:
        _add_issue(issues, "ERROR", layer, "missing directory", path=str(path))
    return {"path": str(path), "exists": exists, "mtime": _mtime_utc(path)}


def _check_parquet_schema(layer: str, path: Path, required_cols: set[str], issues: list[LayerIssue]) -> dict[str, Any]:
    if not path.exists():
        _add_issue(issues, "ERROR", layer, "missing parquet file", path=str(path))
        return {"path": str(path), "exists": False}

    try:
        schema = pq.read_schema(path)
        cols = set(schema.names)
    except Exception as exc:
        _add_issue(issues, "ERROR", layer, "unable to read parquet schema", path=str(path), error=str(exc))
        return {"path": str(path), "exists": True, "schema_ok": False}

    missing = sorted(required_cols - cols)
    if missing:
        _add_issue(issues, "ERROR", layer, "missing required parquet columns", path=str(path), missing=missing)
    return {
        "path": str(path),
        "exists": True,
        "schema_ok": not missing,
        "columns": sorted(cols),
        "mtime": _mtime_utc(path),
    }


def _check_market_schema(path: Path, issues: list[LayerIssue]) -> dict[str, Any]:
    if not path.exists():
        _add_issue(issues, "ERROR", "market", "missing parquet file", path=str(path))
        return {"path": str(path), "exists": False}

    try:
        schema = pq.read_schema(path)
        cols = set(schema.names)
    except Exception as exc:
        _add_issue(issues, "ERROR", "market", "unable to read parquet schema", path=str(path), error=str(exc))
        return {"path": str(path), "exists": True, "schema_ok": False}

    matched = any(required_cols.issubset(cols) for required_cols in REQUIRED_MARKET_SCHEMA_VARIANTS)
    if not matched:
        missing = [sorted(required_cols - cols) for required_cols in REQUIRED_MARKET_SCHEMA_VARIANTS]
        _add_issue(issues, "ERROR", "market", "missing required parquet columns", path=str(path), missing=missing)
    return {
        "path": str(path),
        "exists": True,
        "schema_ok": matched,
        "columns": sorted(cols),
        "mtime": _mtime_utc(path),
    }


def verify_layers(symbols: list[str], timeframes: list[str], max_age_hours: float) -> dict[str, Any]:
    issues: list[LayerIssue] = []
    results: list[LayerResult] = []

    layer_dirs = {
        "raw": DATA / "raw",
        "normalized": DATA / "normalized",
        "market": DATA / "market",
        "sessions": DATA / "sessions",
        "structure": DATA / "structure",
        "liquidity": DATA / "liquidity",
        "imbalances": DATA / "imbalances",
        "orderflow": DATA / "orderflow",
        "confluence": DATA / "confluence",
        "labels": DATA / "labels",
        "replay": DATA / "replay",
        "backtests": DATA / "backtests",
        "analytics": DATA / "analytics",
        "metadata": DATA / "metadata",
        "cache": DATA / "cache",
    }

    for layer, path in layer_dirs.items():
        details = _check_dir(layer, path, issues)
        results.append(LayerResult(layer=layer, status="PASS" if details.get("exists") else "FAIL", details=details))

    manifest_path = DATA / "layers_manifest.json"
    manifest = _read_json(manifest_path)
    if not manifest:
        _add_issue(issues, "ERROR", "metadata", "missing layers manifest", path=str(manifest_path))
    else:
        layers = manifest.get("layers", [])
        if not isinstance(layers, list) or not layers:
            _add_issue(issues, "ERROR", "metadata", "layers manifest has no layer entries", path=str(manifest_path))

    normalized_manifest_path = DATA / "normalized" / "metadata" / "dataset_manifest.json"
    normalized_manifest = _read_json(normalized_manifest_path)
    if not normalized_manifest:
        _add_issue(issues, "ERROR", "normalized", "missing normalized dataset manifest", path=str(normalized_manifest_path))
    else:
        raw_root = normalized_manifest.get("source_root")
        norm_root = normalized_manifest.get("normalized_root")
        if raw_root != "data/raw/dukascopy" or norm_root != "data/normalized":
            _add_issue(
                issues,
                "WARN",
                "normalized",
                "normalized manifest paths differ from expected values",
                source_root=raw_root,
                normalized_root=norm_root,
            )

    for symbol in symbols:
        raw_symbol_dir = DATA / "raw" / "dukascopy" / symbol
        raw_tick_files = sorted(raw_symbol_dir.rglob("ticks.parquet")) if raw_symbol_dir.exists() else []
        if not raw_tick_files:
            _add_issue(issues, "ERROR", "raw", "no raw tick parquet files found", symbol=symbol)
        else:
            raw_path = raw_tick_files[0]
            raw_details = _check_parquet_schema("raw", raw_path, REQUIRED_RAW_COLS, issues)
            if raw_details.get("exists") and raw_details.get("mtime"):
                age = _freshness_hours(raw_tick_files[-1])
                if age is not None and age > max_age_hours:
                    _add_issue(issues, "WARN", "raw", "raw ticks are stale", symbol=symbol, age_hours=age)

        norm_path = DATA / "normalized" / "tick" / symbol / "ticks.parquet"
        norm_details = _check_parquet_schema("normalized", norm_path, REQUIRED_NORMALIZED_COLS, issues)
        if norm_details.get("exists") and norm_details.get("mtime"):
            age = _freshness_hours(norm_path)
            if age is not None and age > max_age_hours:
                _add_issue(issues, "WARN", "normalized", "normalized parquet is stale", symbol=symbol, age_hours=age)

        for tf in timeframes:
            market_root = DATA / "market" / tf.lower() / symbol
            market_parts = sorted(market_root.glob("year=*/month=*/part-*.parquet")) if market_root.exists() else []
            proc_path = market_parts[0] if market_parts else DATA / "processed" / symbol / f"{tf}.parquet"
            proc_details = _check_market_schema(proc_path, issues)
            if market_parts:
                newest = max(market_parts, key=lambda path: path.stat().st_mtime)
                age = _freshness_hours(newest)
                if age is not None and age > max_age_hours:
                    _add_issue(issues, "WARN", "market", "market parquet is stale", symbol=symbol, timeframe=tf, age_hours=age)
            elif proc_details.get("exists") and proc_details.get("mtime"):
                age = _freshness_hours(proc_path)
                if age is not None and age > max_age_hours:
                    _add_issue(issues, "WARN", "market", "processed parquet is stale", symbol=symbol, timeframe=tf, age_hours=age)

    feature_db_path = ROOT / "research_db" / "feature_database.parquet"
    feature_duckdb_path = ROOT / "research_db" / "feature_database.duckdb"
    feature_exists = feature_db_path.exists() and feature_duckdb_path.exists()
    if not feature_exists:
        _add_issue(
            issues,
            "WARN",
            "analytics",
            "feature database outputs are incomplete",
            feature_database_parquet=str(feature_db_path),
            feature_database_duckdb=str(feature_duckdb_path),
        )
    else:
        age = _freshness_hours(feature_db_path)
        if age is not None and age > max_age_hours:
            _add_issue(issues, "WARN", "analytics", "feature database is stale", age_hours=age)

    status = "PASS" if not any(issue.severity == "ERROR" for issue in issues) else "FAIL"
    return {
        "generated_at": _now(),
        "status": status,
        "layers": [result.__dict__ for result in results],
        "issues": [issue.__dict__ for issue in issues],
        "symbols": symbols,
        "timeframes": timeframes,
        "max_age_hours": max_age_hours,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Data Layer Verification",
        "",
        f"- Generated: `{report.get('generated_at', '')}`",
        f"- Status: **{report.get('status', 'UNKNOWN')}**",
        f"- Symbols: `{', '.join(report.get('symbols', []))}`",
        f"- Timeframes: `{', '.join(report.get('timeframes', []))}`",
        f"- Max Age Hours: `{report.get('max_age_hours', '')}`",
        "",
        "## Layer Status",
        "",
        "| Layer | Status | Path |",
        "|---|---|---|",
    ]
    for layer in report.get("layers", []):
        details = layer.get("details", {}) if isinstance(layer, dict) else {}
        lines.append(
            f"| {layer.get('layer', '')} | {layer.get('status', '')} | {details.get('path', '')} |"
        )

    issues = report.get("issues", [])
    lines.extend(["", "## Issues", ""])
    if not issues:
        lines.append("No issues found.")
    else:
        lines.extend(["| Severity | Layer | Message | Details |", "|---|---|---|---|"])
        for issue in issues:
            details = issue.get("details", {}) if isinstance(issue, dict) else {}
            details_text = json.dumps(details, sort_keys=True, default=str).replace("|", "\\|")
            lines.append(
                f"| {issue.get('severity', '')} | {issue.get('layer', '')} | {issue.get('message', '')} | {details_text} |"
            )

    lines.extend(["", "## Summary", "", f"Result: **{report.get('status', 'UNKNOWN')}**"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the layered research-data layout")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--timeframes", nargs="+", default=DEFAULT_TIMEFRAMES)
    parser.add_argument("--max-age-hours", type=float, default=72.0, help="Warn when files are older than this")
    parser.add_argument("--report", default="reports/data_layer_verification.json")
    args = parser.parse_args()

    report = verify_layers(args.symbols, args.timeframes, args.max_age_hours)
    report_path = ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path = report_path.with_suffix(".md")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
