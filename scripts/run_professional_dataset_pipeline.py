#!/usr/bin/env python3
"""Build, validate, and package the 3-year professional dataset workflow.

Stage 1 runs on this VPS:
  - verify/download raw data
  - build processed Parquet timeframes
  - validate dataset quality
  - extract SMC features
  - optionally run first-pass VPS backtests

Stage 2 is prepared, not executed here:
  - create an MT5-server transfer package with processed candles, manifest,
    validation report, and config.

This script never places orders and never enables live trading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "professional_dataset.yaml"
REPORTS = ROOT / "reports"
ARTIFACTS = ROOT / "artifacts" / "mt5_dataset_exports"


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=check)


def _load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _month_range(start: str, end: str) -> list[tuple[int, int]]:
    sy, sm = (int(part) for part in start.split("-", 1))
    ey, em = (int(part) for part in end.split("-", 1))
    months: list[tuple[int, int]] = []
    year, month = sy, sm
    while (year, month) <= (ey, em):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _raw_path(symbol: str, year: int, month: int) -> Path:
    return ROOT / "data" / "raw" / "dukascopy" / symbol / str(year) / f"{month:02d}" / "ticks.parquet"


def _bitget_raw_path(symbol: str, start: str, end: str) -> Path:
    return ROOT / "data" / "raw" / "bitget" / symbol / "M5" / f"{start}_{end}.parquet"


def _processed_path(symbol: str, timeframe: str) -> Path:
    return ROOT / "data" / "processed" / symbol / f"{timeframe}.parquet"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parquet_rows(path: Path) -> int | None:
    try:
        import pyarrow.parquet as pq

        return pq.read_metadata(path).num_rows
    except Exception:
        return None


def _provider_for(config: dict[str, Any], symbol: str) -> dict[str, Any]:
    raw_sources = config.get("raw_sources") or {}
    source_config = raw_sources.get(symbol)
    if source_config:
        return source_config
    return {"provider": config.get("raw_source", "dukascopy")}


def _missing_raw(config: dict[str, Any], symbols: list[str], months: list[tuple[int, int]]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    start = config["window"]["start"]
    end = config["window"]["end"]
    for symbol in symbols:
        provider = _provider_for(config, symbol).get("provider", "dukascopy")
        if provider == "bitget_spot":
            if not _bitget_raw_path(symbol, start, end).exists():
                missing[symbol] = [f"{start}..{end}"]
            continue
        for year, month in months:
            path = _raw_path(symbol, year, month)
            if not path.exists():
                missing.setdefault(symbol, []).append(f"{year:04d}-{month:02d}")
    return missing


def _write_manifest(config: dict[str, Any], config_path: Path) -> Path:
    symbols = list(config["symbols"])
    timeframes = list(config["timeframes"])
    months = _month_range(config["window"]["start"], config["window"]["end"])
    files: list[dict[str, Any]] = []

    for symbol in symbols:
        provider = _provider_for(config, symbol).get("provider", "dukascopy")
        if provider == "bitget_spot":
            path = _bitget_raw_path(symbol, config["window"]["start"], config["window"]["end"])
            if path.exists():
                files.append(
                    {
                        "layer": "raw",
                        "source": "bitget_spot",
                        "symbol": symbol,
                        "timeframe": "M5",
                        "path": str(path.relative_to(ROOT)),
                        "bytes": path.stat().st_size,
                        "rows": _parquet_rows(path),
                        "sha256": _sha256(path),
                    }
                )
            continue
        for year, month in months:
            path = _raw_path(symbol, year, month)
            if path.exists():
                files.append(
                    {
                        "layer": "raw",
                        "symbol": symbol,
                        "month": f"{year:04d}-{month:02d}",
                        "path": str(path.relative_to(ROOT)),
                        "bytes": path.stat().st_size,
                        "rows": _parquet_rows(path),
                        "sha256": _sha256(path),
                    }
                )

    for symbol in symbols:
        for timeframe in timeframes:
            path = _processed_path(symbol, timeframe)
            if path.exists():
                files.append(
                    {
                        "layer": "processed",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "path": str(path.relative_to(ROOT)),
                        "bytes": path.stat().st_size,
                        "rows": _parquet_rows(path),
                        "sha256": _sha256(path),
                    }
                )

    manifest = {
        "schema_version": 1,
        "dataset": config.get("name", "professional_dataset"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path.relative_to(ROOT)),
        "sources": config.get("raw_sources") or config.get("raw_source"),
        "window": config.get("window"),
        "symbols": symbols,
        "timeframes": timeframes,
        "file_count": len(files),
        "files": files,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / "professional_dataset_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Manifest written: {out_path}")
    return out_path


def _export_mt5_package(config: dict[str, Any], manifest_path: Path) -> Path:
    dataset = config.get("name", "professional_dataset")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    package_path = ARTIFACTS / f"{dataset}_{stamp}.tar.gz"

    include_paths = [
        ROOT / "config" / "professional_dataset.yaml",
        manifest_path,
        ROOT / "reports" / "dataset_validation_report.md",
    ]
    for symbol in config["symbols"]:
        for timeframe in config["timeframes"]:
            include_paths.append(_processed_path(symbol, timeframe))

    with tarfile.open(package_path, "w:gz") as archive:
        for path in include_paths:
            if path.exists():
                archive.add(path, arcname=str(path.relative_to(ROOT)))

    print(f"MT5 export package written: {package_path}")
    return package_path


def _run_stage1_backtests(config: dict[str, Any]) -> None:
    out_dir = ROOT / "reports" / "stage1_backtests"
    out_dir.mkdir(parents=True, exist_ok=True)

    for item in config.get("stage1_vps", {}).get("backtests", []):
        script = ROOT / item["script"]
        if not script.exists():
            print(f"SKIP {item['id']}: missing {script}")
            continue

        if item["id"] == "st_a2_session_liquidity":
            _run(
                [
                    sys.executable,
                    str(script.relative_to(ROOT)),
                    "--costs-json",
                    "config/costs.json",
                    "--json-out",
                    str((out_dir / "st_a2_session_liquidity.json").relative_to(ROOT)),
                    "--trial-id",
                    "PROF-3Y-4PAIR-STAGE1-VPS-ST-A2",
                ],
                check=False,
            )
        elif item["id"] == "vwap_mean_reversion":
            symbols = [symbol for symbol in config["symbols"] if symbol in item.get("supported_symbols", [])]
            _run(
                [
                    sys.executable,
                    str(script.relative_to(ROOT)),
                    "--symbols",
                    *symbols,
                ],
                check=False,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run professional dataset and stage-1 backtest workflow")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG.relative_to(ROOT)))
    parser.add_argument("--download-missing", action="store_true", help="Download missing raw Dukascopy months")
    parser.add_argument("--workers", type=int, default=4, help="Downloader worker count")
    parser.add_argument("--timeout-seconds", type=float, default=120.0, help="Per-hour download timeout")
    parser.add_argument("--max-retries", type=int, default=10, help="Retries per hour before failing a month")
    parser.add_argument("--build", action="store_true", help="Build processed Parquet timeframes")
    parser.add_argument("--validate", action="store_true", help="Run dataset validator")
    parser.add_argument("--features", action="store_true", help="Extract SMC feature artifacts")
    parser.add_argument("--backtest", action="store_true", help="Run first-pass VPS backtests")
    parser.add_argument("--export-mt5", action="store_true", help="Create MT5-server transfer package")
    parser.add_argument("--all", action="store_true", help="Run download/build/validate/features/export")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config = _load_config(config_path)
    symbols = list(config["symbols"])
    timeframes = list(config["timeframes"])
    start = config["window"]["start"]
    end = config["window"]["end"]
    months = _month_range(start, end)

    do_download = args.download_missing or args.all
    do_build = args.build or args.all
    do_validate = args.validate or args.all
    do_features = args.features or args.all
    do_export = args.export_mt5 or args.all

    missing = _missing_raw(config, symbols, months)
    if missing:
        print("Missing raw months:")
        print(json.dumps(missing, indent=2, sort_keys=True))
        if do_download:
            for symbol, month_labels in missing.items():
                provider_config = _provider_for(config, symbol)
                provider = provider_config.get("provider", "dukascopy")
                print(f"Downloading {symbol}: {len(month_labels)} missing raw item(s) from {provider}")
                if provider == "bitget_spot":
                    _run(
                        [
                            sys.executable,
                            "scripts/download_bitget_candles.py",
                            "--symbol",
                            symbol,
                            "--source-symbol",
                            provider_config.get("source_symbol", "BTCUSDT"),
                            "--start",
                            start,
                            "--end",
                            end,
                            "--timeframes",
                            *timeframes,
                        ]
                    )
                else:
                    _run(
                        [
                            sys.executable,
                            "scripts/download_dukascopy.py",
                            "--symbols",
                            symbol,
                            "--start",
                            min(month_labels),
                            "--end",
                            max(month_labels),
                            "--workers",
                            str(args.workers),
                            "--timeout-seconds",
                            str(args.timeout_seconds),
                            "--max-retries",
                            str(args.max_retries),
                        ]
                    )
        else:
            print("Use --download-missing or --all to fetch missing raw months.")
    else:
        print("Raw coverage present for all configured symbols/months.")

    if do_build:
        dukascopy_symbols = [
            symbol for symbol in symbols if _provider_for(config, symbol).get("provider", "dukascopy") == "dukascopy"
        ]
        bitget_symbols = [
            symbol for symbol in symbols if _provider_for(config, symbol).get("provider") == "bitget_spot"
        ]
        for symbol in bitget_symbols:
            provider_config = _provider_for(config, symbol)
            _run(
                [
                    sys.executable,
                    "scripts/download_bitget_candles.py",
                    "--symbol",
                    symbol,
                    "--source-symbol",
                    provider_config.get("source_symbol", "BTCUSDT"),
                    "--start",
                    start,
                    "--end",
                    end,
                    "--timeframes",
                    *timeframes,
                ]
            )
        if dukascopy_symbols:
            _run(
                [
                    sys.executable,
                    "scripts/build_timeframes.py",
                    "--symbols",
                    *dukascopy_symbols,
                    "--timeframes",
                    *timeframes,
                    "--start",
                    start,
                    "--end",
                    end,
                ]
            )

    if do_validate:
        _run(
            [
                sys.executable,
                "scripts/validate_dataset.py",
                "--symbols",
                *symbols,
                "--timeframes",
                *timeframes,
                "--expected-start",
                start,
                "--expected-end",
                end,
            ],
            check=False,
        )

    if do_features:
        for symbol in symbols:
            _run(
                [
                    sys.executable,
                    "scripts/extract_features.py",
                    "--symbol",
                    symbol,
                    "--start",
                    f"{start}-01T00:00:00Z",
                    "--end",
                    f"{end}-30T23:59:59Z",
                ],
                check=False,
            )

    manifest_path = _write_manifest(config, config_path)

    if args.backtest:
        _run_stage1_backtests(config)

    if do_export:
        package_path = _export_mt5_package(config, manifest_path)
        print("Stage 2 handoff:")
        print(f"  scp {package_path} <mt5-server>:/tmp/")
        print("  On MT5 server: extract and run broker-side verification against the same manifest.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
