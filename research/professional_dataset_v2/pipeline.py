from __future__ import annotations

import hashlib
import json
import math
import os
import gc
import shutil
import subprocess
import tarfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "tick_dataset.yaml"
DATASET_DIR = ROOT / "datasets" / "professional_3y_4symbol_v2"
ARTIFACTS = ROOT / "artifacts"

FOREX_TICK_SCHEMA = pa.schema(
    [
        ("timestamp_utc", pa.timestamp("ns", tz="UTC")),
        ("symbol", pa.string()),
        ("bid", pa.float64()),
        ("ask", pa.float64()),
        ("spread", pa.float64()),
        ("volume", pa.float64()),
        ("year", pa.int16()),
        ("month", pa.int8()),
        ("day", pa.int8()),
    ]
)

BTC_TICK_SCHEMA = pa.schema(
    [
        ("timestamp_utc", pa.timestamp("ns", tz="UTC")),
        ("symbol", pa.string()),
        ("price", pa.float64()),
        ("quantity", pa.float64()),
        ("side", pa.string()),
        ("year", pa.int16()),
        ("month", pa.int8()),
        ("day", pa.int8()),
    ]
)


@dataclass(frozen=True)
class QualityThresholds:
    missing_pct: float = 0.1
    duplicate_pct: float = 0.01
    timestamp_errors: int = 0


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def month_range(start: str, end: str) -> list[str]:
    sy, sm = [int(part) for part in start.split("-", 1)]
    ey, em = [int(part) for part in end.split("-", 1)]
    out: list[str] = []
    year, month = sy, sm
    while (year, month) <= (ey, em):
        out.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            month = 1
            year += 1
    return out


def raw_source_files(config: dict[str, Any], symbol: str, raw_root: Path | None = None) -> list[Path]:
    raw_root = raw_root or (ROOT / "data/raw")
    source = config["sources"][symbol]
    if source["provider"] == "bitget_spot":
        return sorted((raw_root / "bitget" / symbol).glob("**/*.parquet"))
    return sorted((raw_root / "dukascopy" / symbol).glob("**/ticks.parquet"))


def source_file_month(path: Path, source: dict[str, Any]) -> str | None:
    if source["provider"] == "bitget_spot":
        return None
    try:
        year = path.parts[-3]
        month = path.parts[-2]
        return f"{int(year):04d}-{int(month):02d}"
    except Exception:
        return None


def has_tick_month(tick_root: Path, symbol: str, month: str) -> bool:
    year, mon = month.split("-", 1)
    return any((tick_root / symbol / f"year={year}" / f"month={mon}").glob("day=*/ticks.parquet"))


def raw_dates_for_symbol(config: dict[str, Any], symbol: str, raw_root: Path | None = None) -> set[str]:
    source = config["sources"][symbol]
    dates: set[str] = set()
    for path in raw_source_files(config, symbol, raw_root):
        try:
            parquet_file = pq.ParquetFile(path)
            for batch in parquet_file.iter_batches(batch_size=250_000, columns=["timestamp_utc"] if "timestamp_utc" in parquet_file.schema_arrow.names else ["timestamp_ms"]):
                frame = batch.to_pandas()
                if "timestamp_utc" in frame:
                    ts = pd.to_datetime(frame["timestamp_utc"], utc=True)
                else:
                    ts = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
                dates.update(ts.dt.strftime("%Y-%m-%d").unique().tolist())
        except Exception:
            continue
    return dates


def tick_dates_for_symbol(tick_root: Path, symbol: str) -> set[str]:
    dates: set[str] = set()
    for path in (tick_root / symbol).glob("year=*/month=*/day=*/ticks.parquet"):
        try:
            year = path.parts[-4].split("=", 1)[1]
            month = path.parts[-3].split("=", 1)[1]
            day = path.parts[-2].split("=", 1)[1]
            dates.add(f"{year}-{month}-{day}")
        except Exception:
            continue
    return dates


def tick_months_for_symbol(tick_root: Path, symbol: str) -> set[str]:
    months: set[str] = set()
    for path in (tick_root / symbol).glob("year=*/month=*/day=*/ticks.parquet"):
        try:
            year = path.parts[-4].split("=", 1)[1]
            month = path.parts[-3].split("=", 1)[1]
            months.add(f"{year}-{month}")
        except Exception:
            continue
    return months


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "UNKNOWN"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _write_parquet(path: Path, frame: pd.DataFrame, schema: pa.Schema) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    table = pa.Table.from_pandas(frame, schema=schema, preserve_index=False)
    pq.write_table(table, tmp, compression="snappy", row_group_size=100_000)
    os.replace(tmp, path)


def _partitioned_path(root: Path, symbol: str, ts: pd.Timestamp) -> Path:
    return root / symbol / f"year={ts.year:04d}" / f"month={ts.month:02d}" / f"day={ts.day:02d}" / "ticks.parquet"


def _normalize_forex(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    out = frame.copy()
    if "timestamp_utc" in out:
        out["timestamp_utc"] = pd.to_datetime(out["timestamp_utc"], utc=True)
    elif "timestamp_ms" in out:
        out["timestamp_utc"] = pd.to_datetime(out["timestamp_ms"], unit="ms", utc=True)
    else:
        raise ValueError("forex tick frame needs timestamp_utc or timestamp_ms")
    if "volume" not in out:
        if "ask_vol" in out and "bid_vol" in out:
            out["volume"] = pd.to_numeric(out["ask_vol"], errors="coerce").fillna(0.0) + pd.to_numeric(out["bid_vol"], errors="coerce").fillna(0.0)
        elif "ask_vol" in out:
            out["volume"] = pd.to_numeric(out["ask_vol"], errors="coerce").fillna(0.0)
        elif "bid_vol" in out:
            out["volume"] = pd.to_numeric(out["bid_vol"], errors="coerce").fillna(0.0)
        else:
            out["volume"] = 0.0
    out["symbol"] = symbol
    out["bid"] = pd.to_numeric(out["bid"], errors="coerce")
    out["ask"] = pd.to_numeric(out["ask"], errors="coerce")
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0.0)
    out["spread"] = pd.to_numeric(out.get("spread", out["ask"] - out["bid"]), errors="coerce")
    out = out.dropna(subset=["timestamp_utc", "bid", "ask", "spread"])
    out = out.sort_values("timestamp_utc").drop_duplicates("timestamp_utc")
    out["year"] = out["timestamp_utc"].dt.year.astype("int16")
    out["month"] = out["timestamp_utc"].dt.month.astype("int8")
    out["day"] = out["timestamp_utc"].dt.day.astype("int8")
    return out[["timestamp_utc", "symbol", "bid", "ask", "spread", "volume", "year", "month", "day"]]


def _normalize_btc(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    out = frame.copy()
    if "timestamp_utc" in out:
        out["timestamp_utc"] = pd.to_datetime(out["timestamp_utc"], utc=True)
    elif "timestamp_ms" in out:
        out["timestamp_utc"] = pd.to_datetime(out["timestamp_ms"], unit="ms", utc=True)
    else:
        raise ValueError("BTC tick frame needs timestamp_utc or timestamp_ms")
    if "price" not in out and "close" in out:
        out["price"] = out["close"]
    if "quantity" not in out:
        if "volume" in out:
            out["quantity"] = out["volume"]
        elif "base_volume" in out:
            out["quantity"] = out["base_volume"]
        elif "usdt_volume" in out:
            out["quantity"] = out["usdt_volume"]
        else:
            out["quantity"] = 0.0
    if "side" not in out:
        out["side"] = "unknown"
    out["symbol"] = symbol
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce").fillna(0.0)
    out = out.dropna(subset=["timestamp_utc", "price"])
    out = out.sort_values("timestamp_utc").drop_duplicates("timestamp_utc")
    out["year"] = out["timestamp_utc"].dt.year.astype("int16")
    out["month"] = out["timestamp_utc"].dt.month.astype("int8")
    out["day"] = out["timestamp_utc"].dt.day.astype("int8")
    return out[["timestamp_utc", "symbol", "price", "quantity", "side", "year", "month", "day"]]


def normalize_tick_file(input_path: Path, output_root: Path, symbol: str, asset_class: str) -> dict[str, Any]:
    schema = BTC_TICK_SCHEMA if asset_class == "crypto" else FOREX_TICK_SCHEMA
    parquet_file = pq.ParquetFile(input_path)
    writers: dict[Path, pq.ParquetWriter] = {}
    temp_paths: dict[Path, Path] = {}
    row_counts: dict[Path, int] = {}
    total_rows = 0
    try:
        for batch in parquet_file.iter_batches(batch_size=100_000):
            frame = batch.to_pandas()
            normalized = _normalize_btc(frame, symbol) if asset_class == "crypto" else _normalize_forex(frame, symbol)
            total_rows += int(len(normalized))
            for _, daily in normalized.groupby([normalized["year"], normalized["month"], normalized["day"]], sort=True):
                ts = pd.Timestamp(daily["timestamp_utc"].iloc[0])
                out_path = _partitioned_path(output_root, symbol, ts)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
                if out_path not in writers:
                    temp_paths[out_path] = tmp_path
                    writers[out_path] = pq.ParquetWriter(tmp_path, schema, compression="snappy")
                    row_counts[out_path] = 0
                table = pa.Table.from_pandas(daily.reset_index(drop=True), schema=schema, preserve_index=False)
                writers[out_path].write_table(table)
                row_counts[out_path] += int(len(daily))
    finally:
        for writer in writers.values():
            writer.close()

    written: list[dict[str, Any]] = []
    for out_path in sorted(temp_paths):
        os.replace(temp_paths[out_path], out_path)
        written.append({"path": display_path(out_path), "rows": row_counts[out_path], "sha256": sha256_file(out_path)})
    gc.collect()
    return {"symbol": symbol, "input": str(input_path), "rows": total_rows, "partitions": written}


def _month_key(value: str) -> tuple[int, int]:
    year, month = value.split("-", 1)
    return int(year), int(month)


def resume_tick_materialization(
    config: dict[str, Any],
    raw_root: Path,
    output_root: Path,
    symbols: list[str] | None = None,
    from_month: str | None = None,
    workers: int = 1,
) -> dict[str, Any]:
    results: dict[str, Any] = {"status": "PASS", "symbols": {}}
    from_key = _month_key(from_month) if from_month else None
    for symbol in symbols or config["symbols"]:
        source = config["sources"][symbol]
        raw_files: list[Path] = []
        skipped: list[str] = []
        for raw_file in raw_source_files(config, symbol, raw_root):
            month = source_file_month(raw_file, source)
            if from_key and month and _month_key(month) < from_key:
                skipped.append(str(raw_file))
                continue
            raw_files.append(raw_file)

        processed: list[dict[str, Any]] = []
        if workers > 1 and len(raw_files) > 1:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [
                    pool.submit(normalize_tick_file, raw_file, output_root, symbol, source["asset_class"])
                    for raw_file in raw_files
                ]
                for future in as_completed(futures):
                    processed.append(future.result())
                    gc.collect()
        else:
            for raw_file in raw_files:
                processed.append(normalize_tick_file(raw_file, output_root, symbol, source["asset_class"]))
                gc.collect()
        results["symbols"][symbol] = {"processed_files": len(processed), "skipped_files": len(skipped), "results": processed}
    return results


def investigate_partitions(config: dict[str, Any], tick_root: Path, refresh_plan_path: Path) -> dict[str, Any]:
    plan = json.loads(refresh_plan_path.read_text(encoding="utf-8")) if refresh_plan_path.exists() else refresh_plan(config, tick_root)
    reports: list[dict[str, Any]] = []
    for action in plan.get("actions", []):
        symbol = action.get("symbol")
        partition = action.get("month") or action.get("path", "UNKNOWN")
        reason = action.get("reason", "UNKNOWN")
        status = "UNKNOWN"
        details = reason
        recommended_action = "investigate"
        if reason == "checksum_mismatch":
            status = "CHECKSUM_MISMATCH"
            recommended_action = "replace_partition"
        elif reason == "empty_file":
            status = "VALIDATION_FAILED"
            recommended_action = "replace_partition"
        elif reason == "missing_partition" and symbol:
            source = config["sources"][symbol]
            raw_files = raw_source_files(config, symbol)
            raw_exists = bool(raw_files)
            if source["provider"] == "bitget_spot" and raw_exists:
                status = "NORMALIZATION_INTERRUPTED"
                details = "Raw Bitget source exists but no tick partitions are materialized."
                recommended_action = "resume"
            elif raw_exists:
                raw_month = any(source_file_month(path, source) == partition for path in raw_files)
                if raw_month:
                    status = "MEMORY_PROTECTION_STOP" if symbol == "XAUUSD" else "NORMALIZATION_INTERRUPTED"
                    details = "Raw monthly source exists; prior normalization did not complete the tick partitions."
                    recommended_action = "resume"
                else:
                    status = "DOWNLOAD_MISSING"
                    details = "No raw monthly source found for this partition."
                    recommended_action = "download"
            else:
                status = "DOWNLOAD_MISSING"
                details = "No raw source files found for symbol."
                recommended_action = "download"
        reports.append({"symbol": symbol, "partition": partition, "status": status, "details": details, "recommended_action": recommended_action})
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_actions": len(reports),
        "partitions": reports,
    }
    _atomic_write_json(ROOT / "artifacts/partition_investigation_report.json", payload)
    return payload


def validate_dataset_completeness(config: dict[str, Any], tick_root: Path) -> dict[str, Any]:
    symbols: dict[str, Any] = {}
    total_expected = 0
    total_actual = 0
    total_missing = 0
    total_corrupt = 0
    plan = refresh_plan(config, tick_root)
    for symbol in config["symbols"]:
        actual = len(list((tick_root / symbol).glob("year=*/month=*/day=*/ticks.parquet")))
        missing = sum(1 for action in plan.get("actions", []) if action.get("symbol") == symbol)
        corrupted: list[str] = []
        for path in sorted((tick_root / symbol).glob("year=*/month=*/day=*/ticks.parquet")):
            try:
                meta = pq.read_metadata(path)
                if meta.num_rows <= 0:
                    corrupted.append(display_path(path))
            except Exception:
                corrupted.append(display_path(path))
        expected = actual + missing
        pct = (actual / expected * 100.0) if expected else 0.0
        status = "COMPLETE" if not missing and not corrupted and expected > 0 else "INCOMPLETE"
        symbols[symbol] = {
            "expected_partitions": expected,
            "actual_partitions": actual,
            "missing_partitions": missing,
            "corrupted_partitions": corrupted,
            "completion_percentage": pct,
            "status": status,
        }
        total_expected += expected
        total_actual += actual
        total_missing += missing
        total_corrupt += len(corrupted)
    completion_pct = (total_actual / total_expected * 100.0) if total_expected else 0.0
    gate = release_gate_status(total_missing, total_corrupt, 0)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": gate,
        "completion_pct": completion_pct,
        "expected_partitions": total_expected,
        "actual_partitions": total_actual,
        "missing_partitions": total_missing,
        "corrupted_partitions": total_corrupt,
        "symbols": symbols,
    }
    _atomic_write_json(ROOT / "artifacts/dataset_status.json", payload)
    return payload


def release_gate_status(missing_partitions: int, corrupted_partitions: int, checksum_failures: int) -> str:
    if missing_partitions == 0 and corrupted_partitions == 0 and checksum_failures == 0:
        return "PASS"
    if missing_partitions <= 5 and corrupted_partitions <= 1 and checksum_failures == 0:
        return "PASS_WITH_WARNINGS"
    return "FAIL"


def validate_checksums(dataset_dir: Path = DATASET_DIR) -> dict[str, Any]:
    path = dataset_dir / "checksums.json"
    if not path.exists():
        return {"status": "FAIL", "reason": "missing checksums.json"}
    data = json.loads(path.read_text(encoding="utf-8"))
    files = data.get("sha256", [])
    digest = hashlib.sha256()
    failures = []
    for item in files:
        file_path = ROOT / item["path"]
        if not file_path.exists():
            failures.append({"path": item["path"], "reason": "missing"})
            continue
        actual = sha256_file(file_path)
        if actual != item["sha256"]:
            failures.append({"path": item["path"], "reason": "mismatch"})
        digest.update(item["sha256"].encode("ascii"))
    status = "PASS" if not failures and digest.hexdigest() == data.get("dataset_hash") else "FAIL"
    return {
        "status": status,
        "expected_hash": data.get("dataset_hash"),
        "actual_hash": digest.hexdigest(),
        "failure_count": len(failures),
        "failures": failures,
    }


def cost_model_validation(cost_root: Path = ROOT / "research/cost_models") -> dict[str, Any]:
    report: dict[str, Any] = {"status": "PASS", "symbols": {}}
    for symbol_file in sorted(cost_root.glob("*.json")):
        if symbol_file.name == "metadata.json":
            continue
        data = json.loads(symbol_file.read_text(encoding="utf-8"))
        gross_pnl = 100.0
        spread_cost = float(data.get("spread_p50", 0.0)) * 10_000.0 if "spread_p50" in data else 0.0
        commission = 0.0
        slippage = 0.0
        if "commission" in data:
            commission = float(data["commission"].get("maker_fee", 0.0) + data["commission"].get("taker_fee", 0.0)) * 10_000.0
            slippage = float(data.get("slippage", {}).get("slippage_p50", 0.0) + data.get("slippage", {}).get("slippage_p90", 0.0))
        net_pnl = gross_pnl - spread_cost - commission - slippage
        report["symbols"][symbol_file.stem] = {
            "gross_pnl": gross_pnl,
            "commission": commission,
            "spread_cost": spread_cost,
            "slippage_cost": slippage,
            "net_pnl": net_pnl,
            "status": "PASS" if gross_pnl >= net_pnl else "FAIL",
        }
        if gross_pnl < net_pnl:
            report["status"] = "FAIL"
    return report


def smc_distribution_validation(output_root: Path = ROOT / "research/smc_events") -> dict[str, Any]:
    core_labels = {"BOS", "FVG", "LiquiditySweep", "Displacement"}
    report: dict[str, Any] = {"status": "PASS", "symbols": {}}
    for path in sorted(output_root.glob("*.parquet")):
        frame = pd.read_parquet(path, columns=["event_type", "direction"])
        counts = frame["event_type"].value_counts().to_dict()
        missing_core = sorted(label for label in core_labels if counts.get(label, 0) <= 0)
        negatives = int((frame["direction"].astype(str).str.len() == 0).sum())
        status = "PASS"
        if missing_core or negatives > 0:
            status = "WARN"
            report["status"] = "PASS_WITH_WARNINGS" if report["status"] == "PASS" else report["status"]
        report["symbols"][path.stem] = {
            "counts": counts,
            "missing_core_labels": missing_core,
            "empty_direction_rows": negatives,
            "status": status,
        }
    return report


def regime_distribution_validation(output_root: Path = ROOT / "research/market_regimes") -> dict[str, Any]:
    expected_labels = {
        "TREND_LOW_VOL",
        "TREND_HIGH_VOL",
        "RANGE_LOW_VOL",
        "RANGE_HIGH_VOL",
        "LONDON_OPEN",
        "NEWYORK_OPEN",
        "NEWS_WINDOW",
    }
    report: dict[str, Any] = {"status": "PASS", "symbols": {}}
    for path in sorted(output_root.glob("*.parquet")):
        frame = pd.read_parquet(path, columns=["timestamp", "regime"])
        counts = frame["regime"].value_counts().to_dict()
        missing = sorted(label for label in expected_labels if label not in counts)
        report["symbols"][path.stem] = {
            "counts": counts,
            "missing_labels": missing,
            "timestamp_errors": int(pd.to_datetime(frame["timestamp"], utc=True, errors="coerce").isna().sum()),
            "status": "PASS" if not missing else "WARN",
        }
        if missing:
            report["status"] = "PASS_WITH_WARNINGS" if report["status"] == "PASS" else report["status"]
    return report


def release_validation_report(dataset_dir: Path = DATASET_DIR) -> dict[str, Any]:
    completeness = validate_dataset_completeness(load_config(DEFAULT_CONFIG), ROOT / "data/tick")
    checksum = validate_checksums(dataset_dir)
    quality_path = ROOT / "artifacts/data_quality_report.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
    release_status = release_gate_status(
        int(completeness.get("missing_partitions", 0)),
        int(completeness.get("corrupted_partitions", 0)),
        int(checksum.get("failure_count", 0)),
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_status": release_status,
        "completion_pct": completeness.get("completion_pct", 0.0),
        "dataset_completeness": completeness,
        "checksum_validation": checksum,
        "quality_status": quality.get("status"),
        "quality_metrics": quality,
    }
    _atomic_write_json(ROOT / "artifacts/release_validation_report.json", payload)
    return payload


def update_release_manifest(dataset_dir: Path = DATASET_DIR) -> dict[str, Any]:
    manifest_path = dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    quality_path = ROOT / "artifacts/data_quality_report.json"
    quality_hash = sha256_file(quality_path) if quality_path.exists() else None
    export_path = ROOT / "artifacts/professional_dataset_v2.tar.gz"
    export_hash = sha256_file(export_path) if export_path.exists() else None
    release_report = json.loads((ROOT / "artifacts/release_validation_report.json").read_text(encoding="utf-8")) if (ROOT / "artifacts/release_validation_report.json").exists() else {}
    completeness = release_report.get("dataset_completeness", {})
    manifest.update(
        {
            "quality_hash": quality_hash,
            "export_hash": export_hash,
            "release_status": release_report.get("release_status", "RC1"),
            "completion_pct": round(float(completeness.get("completion_pct", 0.0)), 4),
            "validation_status": release_report.get("release_status", "FAIL"),
        }
    )
    _atomic_write_json(manifest_path, manifest)
    return manifest


def production_release_report(dataset_dir: Path = DATASET_DIR) -> dict[str, Any]:
    release_report = json.loads((ROOT / "artifacts/release_validation_report.json").read_text(encoding="utf-8")) if (ROOT / "artifacts/release_validation_report.json").exists() else release_validation_report(dataset_dir)
    pkg = ROOT / "artifacts/professional_dataset_v2.tar.gz"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_duration_seconds": None,
        "dataset_size_bytes": pkg.stat().st_size if pkg.exists() else 0,
        "partition_counts": {
            symbol: len(list((ROOT / "data/tick" / symbol).glob("year=*/month=*/day=*/ticks.parquet")))
            for symbol in ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD"]
        },
        "quality_status": release_report.get("quality_status"),
        "checksum_status": release_report.get("checksum_validation", {}).get("status"),
        "release_status": release_report.get("release_status"),
    }
    _atomic_write_json(ROOT / "artifacts/production_release_report.json", payload)
    return payload


def validate_tick_partitions(tick_root: Path, symbols: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {"status": "PASS", "symbols": {}}
    for symbol in symbols:
        rows = 0
        bad_spread = 0
        timestamp_errors = 0
        duplicate_rows = 0
        last_ts: pd.Timestamp | None = None
        for path in sorted((tick_root / symbol).glob("year=*/month=*/day=*/ticks.parquet")):
            cols = ["timestamp_utc"]
            schema_names = pq.read_schema(path).names
            if "spread" in schema_names:
                cols.append("spread")
            frame = pd.read_parquet(path, columns=cols)
            rows += pq.read_metadata(path).num_rows
            ts = frame["timestamp_utc"]
            if not pd.api.types.is_datetime64_any_dtype(ts):
                ts = pd.to_datetime(ts, utc=True)
            timestamp_errors += int(ts.isna().sum())
            duplicate_rows += int(frame.duplicated(subset=["timestamp_utc"]).sum())
            if last_ts is not None and not frame.empty and ts.iloc[0] < last_ts:
                timestamp_errors += 1
            if not frame.empty:
                last_ts = ts.iloc[-1]
            if "spread" in frame.columns:
                bad_spread += int((pd.to_numeric(frame["spread"], errors="coerce") < 0).sum())
        symbol_status = "PASS" if rows and not timestamp_errors and not bad_spread else "FAIL"
        results["symbols"][symbol] = {
            "status": symbol_status,
            "rows": rows,
            "duplicate_pct": (duplicate_rows / rows * 100.0) if rows else 100.0,
            "timestamp_errors": timestamp_errors,
            "spread_outliers": bad_spread,
        }
        if symbol_status != "PASS":
            results["status"] = "FAIL"
    return results


def build_cost_models(
    tick_root: Path,
    output_root: Path,
    symbols: list[str],
    processed_root: Path | None = None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat(), "models": {}}
    for symbol in symbols:
        if symbol == "BTCUSD":
            commission = {"maker_fee": 0.001, "taker_fee": 0.001, "source": "configurable_public_exchange_default"}
            slippage = {"slippage_p50": 0.0, "slippage_p90": 0.0, "slippage_p99": 0.0, "source": "placeholder_until_trade_intensity_loaded"}
            (output_root / "commission_model.yaml").write_text(yaml.safe_dump(commission, sort_keys=True), encoding="utf-8")
            (output_root / "slippage_model.yaml").write_text(yaml.safe_dump(slippage, sort_keys=True), encoding="utf-8")
            summary["models"][symbol] = {"commission": commission, "slippage": slippage}
            continue
        spreads: list[pd.Series] = []
        volumes: list[pd.Series] = []
        timestamps: list[pd.Series] = []
        source = "tick"
        for path in sorted((tick_root / symbol).glob("year=*/month=*/day=*/ticks.parquet")):
            frame = pd.read_parquet(path, columns=["timestamp_utc", "spread", "volume"])
            if frame.empty:
                continue
            spreads.append(pd.to_numeric(frame["spread"], errors="coerce").dropna())
            volumes.append(pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0))
            timestamps.append(pd.to_datetime(frame["timestamp_utc"], utc=True))
        if not spreads and processed_root is not None:
            path = processed_root / symbol / "M5.parquet"
            if path.exists():
                frame = pd.read_parquet(path, columns=["timestamp_utc", "spread_avg", "volume"])
                spread = pd.to_numeric(frame["spread_avg"], errors="coerce").dropna()
                if not spread.empty:
                    source = "processed_m5_spread_avg"
                    spreads.append(spread)
                    volumes.append(pd.to_numeric(frame.loc[spread.index, "volume"], errors="coerce").fillna(0.0))
                    timestamps.append(pd.to_datetime(frame.loc[spread.index, "timestamp_utc"], utc=True))
        if not spreads:
            continue
        spread = pd.concat(spreads, ignore_index=True)
        ts = pd.concat(timestamps, ignore_index=True)
        volume = pd.concat(volumes, ignore_index=True)
        frame = pd.DataFrame({"timestamp_utc": ts, "spread": spread, "volume": volume})
        sessions = {
            "asian_profile": frame[frame["timestamp_utc"].dt.hour.between(0, 5)]["spread"].median(),
            "london_profile": frame[frame["timestamp_utc"].dt.hour.between(7, 10)]["spread"].median(),
            "newyork_profile": frame[frame["timestamp_utc"].dt.hour.between(12, 16)]["spread"].median(),
        }
        model = {
            "symbol": symbol,
            "spread_p50": float(spread.quantile(0.50)),
            "spread_p90": float(spread.quantile(0.90)),
            "spread_p99": float(spread.quantile(0.99)),
            "rows": int(len(spread)),
            "source": source,
            **{key: (None if math.isnan(value) else float(value)) for key, value in sessions.items()},
        }
        _atomic_write_json(output_root / f"{symbol}.json", model)
        summary["models"][symbol] = model
    return summary


def _parquet_stats(path: Path) -> tuple[int, list[str]]:
    try:
        meta = pq.read_metadata(path)
        schema = meta.schema.to_arrow_schema()
        return meta.num_rows, schema.names
    except Exception:
        return 0, []


def dataset_quality(processed_root: Path, output_path: Path, thresholds: QualityThresholds = QualityThresholds()) -> dict[str, Any]:
    metrics: dict[str, Any] = {"status": "PASS", "thresholds": thresholds.__dict__, "files": []}
    for path in sorted(processed_root.glob("*/*.parquet")):
        rows, cols = _parquet_stats(path)
        frame = pd.read_parquet(path)
        ts_col = "timestamp_utc" if "timestamp_utc" in frame.columns else "timestamp"
        ts = pd.to_datetime(frame[ts_col], utc=True, errors="coerce")
        duplicate_pct = float(frame.duplicated(subset=[ts_col]).sum() / max(len(frame), 1) * 100.0)
        optional_cols = {col for col in ("spread_avg", "spread_max") if col in frame.columns and frame[col].isna().all()}
        required_frame = frame.drop(columns=sorted(optional_cols)) if optional_cols else frame
        missing_pct = float(required_frame.isna().sum().sum() / max(len(required_frame) * max(len(required_frame.columns), 1), 1) * 100.0)
        optional_missing_pct = float(frame[list(optional_cols)].isna().sum().sum() / max(len(frame) * max(len(optional_cols), 1), 1) * 100.0) if optional_cols else 0.0
        timestamp_errors = int(ts.isna().sum() + max(0, int((ts.diff().dt.total_seconds().dropna() < 0).sum())))
        ohlc_bad = 0
        if {"open", "high", "low", "close"}.issubset(frame.columns):
            ohlc_bad = int(((frame["high"] < frame[["open", "close", "low"]].max(axis=1)) | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))).sum())
        status = "PASS"
        if missing_pct > thresholds.missing_pct or duplicate_pct > thresholds.duplicate_pct or timestamp_errors != thresholds.timestamp_errors or ohlc_bad:
            status = "FAIL"
            metrics["status"] = "FAIL"
        metrics["files"].append(
            {
                "path": display_path(path),
                "rows": rows,
                "columns": cols,
                "missing_pct": missing_pct,
                "optional_missing_pct": optional_missing_pct,
                "optional_missing_columns": sorted(optional_cols),
                "duplicate_pct": duplicate_pct,
                "timestamp_errors": timestamp_errors,
                "ohlc_consistency": ohlc_bad,
                "status": status,
            }
        )
    _atomic_write_json(output_path, metrics)
    return metrics


def create_manifest(config: dict[str, Any], dataset_dir: Path = DATASET_DIR, quality_report: Path | None = None) -> dict[str, Any]:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    processed_root = ROOT / config.get("processed_root", "data/processed")
    quality = {}
    if quality_report and quality_report.exists():
        quality = json.loads(quality_report.read_text(encoding="utf-8"))
    record_counts: dict[str, dict[str, int]] = {}
    feature_counts: dict[str, int] = {}
    for symbol in config["symbols"]:
        record_counts[symbol] = {}
        for timeframe in config["timeframes"]:
            path = processed_root / symbol / f"{timeframe}.parquet"
            record_counts[symbol][timeframe] = _parquet_stats(path)[0] if path.exists() else 0
    for root_name in ("research/market_regimes", "research/smc_events"):
        root = ROOT / root_name
        feature_counts[root_name] = sum(_parquet_stats(path)[0] for path in root.glob("*.parquet"))
    manifest = {
        "dataset_id": config.get("dataset_id", "professional_3y_4symbol_v2"),
        "build_time": datetime.now(timezone.utc).isoformat(),
        "sources": config.get("sources", {}),
        "symbols": config["symbols"],
        "timeframes": config["timeframes"],
        "record_counts": record_counts,
        "feature_counts": feature_counts,
        "quality_metrics": quality,
        "git_commit": git_commit(),
    }
    _atomic_write_json(dataset_dir / "manifest.json", manifest)
    metadata = {
        "dataset_id": manifest["dataset_id"],
        "window": config.get("window"),
        "immutable": True,
        "supersedes": "professional_3y_4symbol_v1",
    }
    (dataset_dir / "metadata.yaml").write_text(yaml.safe_dump(metadata, sort_keys=True), encoding="utf-8")
    return manifest


def generate_checksums(dataset_dir: Path = DATASET_DIR, extra_roots: list[Path] | None = None) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    roots = [
        dataset_dir,
        ROOT / "data/processed",
        ROOT / "artifacts/data_quality_report.json",
        ROOT / "artifacts/tick_validation_report.json",
        ROOT / "artifacts/dataset_refresh_plan.json",
        ROOT / "artifacts/partition_investigation_report.json",
        ROOT / "artifacts/dataset_status.json",
        ROOT / "artifacts/release_validation_report.json",
        ROOT / "artifacts/cost_model_validation_report.json",
        ROOT / "artifacts/smc_distribution_report.json",
        ROOT / "artifacts/regime_distribution_report.json",
        ROOT / "artifacts/production_release_report.json",
        ROOT / "research/cost_models",
        ROOT / "research/market_regimes",
        ROOT / "research/smc_events",
    ]
    if extra_roots:
        roots.extend(extra_roots)
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            files.append({"path": display_path(root), "sha256": sha256_file(root), "bytes": root.stat().st_size})
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name != "checksums.json"):
            files.append({"path": display_path(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    digest = hashlib.sha256()
    for item in files:
        digest.update(item["sha256"].encode("ascii"))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sha256": files,
        "dataset_hash": digest.hexdigest(),
        "artifact_hash": digest.hexdigest(),
    }
    _atomic_write_json(dataset_dir / "checksums.json", payload)
    return payload


def generate_market_regimes(processed_root: Path, output_root: Path, symbols: list[str], timeframe: str = "M15") -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat(), "symbols": {}}
    schema = pa.schema(
        [
            ("timestamp", pa.timestamp("ns", tz="UTC")),
            ("symbol", pa.string()),
            ("regime", pa.string()),
            ("volatility_score", pa.float64()),
            ("trend_score", pa.float64()),
        ]
    )
    for symbol in symbols:
        path = processed_root / symbol / f"{timeframe}.parquet"
        if not path.exists():
            continue
        frame = pd.read_parquet(path, columns=["timestamp_utc", "open", "high", "low", "close"])
        frame = frame.sort_values("timestamp_utc").reset_index(drop=True)
        returns = frame["close"].pct_change().abs()
        volatility = returns.rolling(96, min_periods=10).std().fillna(0.0)
        trend = (frame["close"] - frame["close"].rolling(96, min_periods=10).mean()).abs() / frame["close"].replace(0, np.nan)
        vol_cut = volatility.quantile(0.70)
        trend_cut = trend.quantile(0.70)
        labels = []
        for ts, vol, tr in zip(pd.to_datetime(frame["timestamp_utc"], utc=True), volatility, trend.fillna(0.0)):
            hour = ts.hour
            if 7 <= hour <= 9:
                label = "LONDON_OPEN"
            elif 12 <= hour <= 14:
                label = "NEWYORK_OPEN"
            else:
                prefix = "TREND" if tr >= trend_cut else "RANGE"
                suffix = "HIGH_VOL" if vol >= vol_cut else "LOW_VOL"
                label = f"{prefix}_{suffix}"
            labels.append(label)
        out = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(frame["timestamp_utc"], utc=True),
                "symbol": symbol,
                "regime": labels,
                "volatility_score": volatility.astype("float64"),
                "trend_score": trend.fillna(0.0).astype("float64"),
            }
        )
        out_path = output_root / f"{symbol}.parquet"
        _write_parquet(out_path, out, schema)
        summary["symbols"][symbol] = {"rows": int(len(out)), "path": display_path(out_path)}
    return summary


def extract_smc_events(processed_root: Path, output_root: Path, symbols: list[str], timeframe: str = "M15") -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            ("timestamp_utc", pa.timestamp("ns", tz="UTC")),
            ("symbol", pa.string()),
            ("event_type", pa.string()),
            ("direction", pa.string()),
            ("price", pa.float64()),
            ("strength", pa.float64()),
        ]
    )
    summary: dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat(), "symbols": {}}
    for symbol in symbols:
        path = processed_root / symbol / f"{timeframe}.parquet"
        if not path.exists():
            continue
        frame = pd.read_parquet(path, columns=["timestamp_utc", "open", "high", "low", "close"])
        frame = frame.sort_values("timestamp_utc").reset_index(drop=True)
        prev_high = frame["high"].rolling(20, min_periods=5).max().shift(1)
        prev_low = frame["low"].rolling(20, min_periods=5).min().shift(1)
        body = (frame["close"] - frame["open"]).abs()
        atr = (frame["high"] - frame["low"]).rolling(20, min_periods=5).mean()
        rows: list[dict[str, Any]] = []
        for idx, row in frame.iterrows():
            ts = row["timestamp_utc"]
            if pd.notna(prev_high.iloc[idx]) and row["high"] > prev_high.iloc[idx] and row["close"] < prev_high.iloc[idx]:
                rows.append({"timestamp_utc": ts, "symbol": symbol, "event_type": "LiquiditySweep", "direction": "bearish", "price": float(row["high"]), "strength": float(row["high"] - prev_high.iloc[idx])})
            if pd.notna(prev_low.iloc[idx]) and row["low"] < prev_low.iloc[idx] and row["close"] > prev_low.iloc[idx]:
                rows.append({"timestamp_utc": ts, "symbol": symbol, "event_type": "LiquiditySweep", "direction": "bullish", "price": float(row["low"]), "strength": float(prev_low.iloc[idx] - row["low"])})
            if pd.notna(prev_high.iloc[idx]) and row["close"] > prev_high.iloc[idx]:
                rows.append({"timestamp_utc": ts, "symbol": symbol, "event_type": "BOS", "direction": "bullish", "price": float(row["close"]), "strength": float(row["close"] - prev_high.iloc[idx])})
            if pd.notna(prev_low.iloc[idx]) and row["close"] < prev_low.iloc[idx]:
                rows.append({"timestamp_utc": ts, "symbol": symbol, "event_type": "BOS", "direction": "bearish", "price": float(row["close"]), "strength": float(prev_low.iloc[idx] - row["close"])})
            if pd.notna(atr.iloc[idx]) and atr.iloc[idx] > 0 and body.iloc[idx] > 1.5 * atr.iloc[idx]:
                rows.append({"timestamp_utc": ts, "symbol": symbol, "event_type": "Displacement", "direction": "bullish" if row["close"] > row["open"] else "bearish", "price": float(row["close"]), "strength": float(body.iloc[idx] / atr.iloc[idx])})
            if idx >= 2:
                prev2 = frame.iloc[idx - 2]
                if row["low"] > prev2["high"]:
                    rows.append({"timestamp_utc": ts, "symbol": symbol, "event_type": "FVG", "direction": "bullish", "price": float((row["low"] + prev2["high"]) / 2.0), "strength": float(row["low"] - prev2["high"])})
                if row["high"] < prev2["low"]:
                    rows.append({"timestamp_utc": ts, "symbol": symbol, "event_type": "FVG", "direction": "bearish", "price": float((row["high"] + prev2["low"]) / 2.0), "strength": float(prev2["low"] - row["high"])})
        out = pd.DataFrame(rows, columns=["timestamp_utc", "symbol", "event_type", "direction", "price", "strength"])
        out_path = output_root / f"{symbol}.parquet"
        _write_parquet(out_path, out, schema)
        summary["symbols"][symbol] = {"rows": int(len(out)), "path": display_path(out_path)}
    return summary


def refresh_plan(config: dict[str, Any], tick_root: Path, checksums_path: Path | None = None) -> dict[str, Any]:
    months = month_range(config["window"]["start"], config["window"]["end"])
    planned: dict[str, Any] = {"full_rebuild_required": False, "actions": []}
    for symbol in config["symbols"]:
        for month in months:
            y, m = month.split("-")
            partitions = sorted((tick_root / symbol / f"year={y}" / f"month={m}").glob("day=*/ticks.parquet"))
            if not partitions:
                planned["actions"].append({"action": "download_month", "symbol": symbol, "month": month, "reason": "missing_partition"})
            for path in partitions:
                if path.stat().st_size == 0:
                    planned["actions"].append({"action": "replace_partition", "path": display_path(path), "reason": "empty_file"})
    if checksums_path and checksums_path.exists():
        known = json.loads(checksums_path.read_text(encoding="utf-8")).get("sha256", [])
        for item in known:
            path = ROOT / item["path"]
            if path.exists() and sha256_file(path) != item["sha256"]:
                planned["actions"].append({"action": "replace_partition", "path": item["path"], "reason": "checksum_mismatch"})
    return planned


def export_package(dataset_dir: Path = DATASET_DIR, output_path: Path | None = None) -> Path:
    if output_path is None:
        output_path = ARTIFACTS / "professional_dataset_v2.tar.gz"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    roots = {
        "dataset": ROOT / "data/processed",
        "manifest": dataset_dir / "manifest.json",
        "checksums": dataset_dir / "checksums.json",
        "quality_report": ARTIFACTS / "data_quality_report.json",
        "tick_validation": ARTIFACTS / "tick_validation_report.json",
        "refresh_plan": ARTIFACTS / "dataset_refresh_plan.json",
        "partition_investigation": ARTIFACTS / "partition_investigation_report.json",
        "dataset_status": ARTIFACTS / "dataset_status.json",
        "release_validation": ARTIFACTS / "release_validation_report.json",
        "cost_model_validation": ARTIFACTS / "cost_model_validation_report.json",
        "smc_distribution": ARTIFACTS / "smc_distribution_report.json",
        "regime_distribution": ARTIFACTS / "regime_distribution_report.json",
        "production_release": ARTIFACTS / "production_release_report.json",
        "cost_models": ROOT / "research/cost_models",
        "market_regimes": ROOT / "research/market_regimes",
        "smc_events": ROOT / "research/smc_events",
        "metadata": dataset_dir,
    }
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    with tarfile.open(tmp, "w:gz") as archive:
        for arc_root, path in roots.items():
            if not path.exists():
                continue
            if path.is_file():
                archive.add(path, arcname=f"{arc_root}/{path.name}")
            else:
                for child in sorted(p for p in path.rglob("*") if p.is_file()):
                    archive.add(child, arcname=f"{arc_root}/{child.relative_to(path)}")
    os.replace(tmp, output_path)
    return output_path


def load_to_sqlite(db_path: Path, dataset_dir: Path = DATASET_DIR) -> dict[str, Any]:
    import sqlite3

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS dataset_manifests (
              dataset_id TEXT PRIMARY KEY,
              manifest_json TEXT NOT NULL,
              loaded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS data_quality (
              path TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              metrics_json TEXT NOT NULL
            );
            """
        )
        manifest_path = dataset_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            con.execute(
                "INSERT OR REPLACE INTO dataset_manifests VALUES (?, ?, ?)",
                (manifest["dataset_id"], json.dumps(manifest, sort_keys=True), datetime.now(timezone.utc).isoformat()),
            )
        quality_path = ARTIFACTS / "data_quality_report.json"
        if quality_path.exists():
            quality = json.loads(quality_path.read_text(encoding="utf-8"))
            for item in quality.get("files", []):
                con.execute(
                    "INSERT OR REPLACE INTO data_quality VALUES (?, ?, ?)",
                    (item["path"], item["status"], json.dumps(item, sort_keys=True)),
                )
    return {"db_path": display_path(db_path), "status": "PASS"}


def copy_tree_incremental(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and out.stat().st_size == path.stat().st_size and sha256_file(out) == sha256_file(path):
            continue
        shutil.copy2(path, out)
