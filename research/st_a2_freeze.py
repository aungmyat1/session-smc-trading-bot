from __future__ import annotations

import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from research.research_validation import dataset_hash, load_yaml, st_a2_validation_report, write_json
from scripts.backtest_session_liquidity import simulate_trade
from scripts.replay_parquet import load_h4, load_m15
from strategy.session_liquidity.bias_filter import htf_bias
from strategy.session_liquidity.displacement_detector import detect_displacement, wilder_atr
from strategy.session_liquidity.entry_engine import build_signal
from strategy.session_liquidity.session_builder import AsianRange, classify_session, classify_session_v2
from strategy.session_liquidity.sweep_detector import detect_sweep

ROOT = Path(__file__).resolve().parents[1]
STRATEGY_CONFIG = ROOT / "config" / "strategies" / "ST-A2_v1.yaml"
BENCHMARK_CONFIG = ROOT / "config" / "research_benchmark.yaml"
REGISTRATION_MANIFEST = ROOT / "artifacts" / "ST-A2_registration_manifest.json"
LEDGER_DIR = ROOT / "research" / "trade_ledgers"
LEDGER_MANIFEST = ROOT / "artifacts" / "ST-A2_trade_ledger_manifest.json"
VALIDATION_REPORT = ROOT / "artifacts" / "ST-A2_validation_report.json"
BASELINE_RELEASE_REPORT = ROOT / "artifacts" / "ST-A2_baseline_release_report.md"

LEDGER_COLUMNS = [
    "trade_id",
    "strategy_id",
    "strategy_version",
    "strategy_hash",
    "dataset_version",
    "dataset_hash",
    "symbol",
    "timeframe",
    "entry_time",
    "exit_time",
    "entry_price",
    "exit_price",
    "stop_loss",
    "take_profit",
    "position_size",
    "gross_pnl",
    "spread_cost",
    "commission",
    "commission_cost",
    "slippage",
    "slippage_cost",
    "net_pnl",
    "market_regime",
    "session",
    "smc_context",
]

PIP_SIZE = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.1}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "UNKNOWN"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strategy_payload(path: Path = STRATEGY_CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def canonical_strategy_hash(path: Path = STRATEGY_CONFIG) -> str:
    payload = strategy_payload(path)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return _sha256_bytes(encoded)


def registration_manifest(path: Path = STRATEGY_CONFIG, benchmark_path: Path = BENCHMARK_CONFIG) -> dict[str, Any]:
    strategy = strategy_payload(path)
    benchmark = load_yaml(benchmark_path)
    config_hash = file_sha256(path)
    return {
        "strategy_id": strategy["strategy_id"],
        "version": str(strategy["version"]),
        "status": "FROZEN" if strategy.get("status", {}).get("frozen") else "UNFROZEN",
        "dataset_version": benchmark["dataset"]["version"],
        "dataset_hash": dataset_hash(benchmark),
        "strategy_hash": canonical_strategy_hash(path),
        "configuration_hash": config_hash,
        "created_at": _now(),
        "git_commit": _git_commit(),
    }


def write_registration_manifest(output_path: Path = REGISTRATION_MANIFEST) -> dict[str, Any]:
    manifest = registration_manifest()
    write_json(output_path, manifest)
    return manifest


def _load_spread_map(symbol: str) -> dict[str, float]:
    path = ROOT / "data" / "processed" / symbol / "M15.parquet"
    if not path.exists():
        return {}
    frame = pd.read_parquet(path, columns=["timestamp_utc", "spread_avg"])
    frame["time"] = pd.to_datetime(frame["timestamp_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {str(row.time): float(row.spread_avg) for row in frame.itertuples(index=False) if pd.notna(row.spread_avg)}


def _load_regime_map(symbol: str) -> dict[str, str]:
    path = ROOT / "research" / "market_regimes" / f"{symbol}.parquet"
    if not path.exists():
        return {}
    frame = pd.read_parquet(path, columns=["timestamp", "regime"])
    frame["time"] = pd.to_datetime(frame["timestamp"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {str(row.time): str(row.regime) for row in frame.itertuples(index=False)}


def _load_smc_map(symbol: str) -> dict[str, list[dict[str, Any]]]:
    path = ROOT / "research" / "smc_events" / f"{symbol}.parquet"
    if not path.exists():
        return {}
    frame = pd.read_parquet(path)
    frame["time"] = pd.to_datetime(frame["timestamp_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    out: dict[str, list[dict[str, Any]]] = {}
    for row in frame.itertuples(index=False):
        out.setdefault(str(row.time), []).append(
            {
                "event_type": str(row.event_type),
                "direction": str(row.direction),
                "price": float(row.price),
                "strength": float(row.strength),
            }
        )
    return out


def _fallback_spread(symbol: str) -> float:
    path = ROOT / "research" / "cost_models" / f"{symbol}.json"
    if not path.exists():
        return 0.0
    payload = json.loads(path.read_text(encoding="utf-8"))
    return float(payload.get("spread_p50", 0.0) or 0.0)


def _trade_id(row: dict[str, Any]) -> str:
    keys = ["strategy_id", "strategy_version", "dataset_hash", "symbol", "entry_time", "exit_time", "entry_price", "stop_loss", "take_profit"]
    raw = "|".join(str(row.get(key, "")) for key in keys)
    return "sta2-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _parse_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _precompute_asian_ranges(candles_m15: list[dict[str, Any]]) -> dict[Any, AsianRange]:
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    eastern = ZoneInfo("America/New_York")
    buckets: dict[Any, dict[str, list[float]]] = {}
    for candle in candles_m15:
        est = _parse_utc(candle["time"]).astimezone(eastern)
        if est.hour >= 18:
            trade_date = est.date() + timedelta(days=1)
        elif est.hour < 2:
            trade_date = est.date()
        else:
            continue
        bucket = buckets.setdefault(trade_date, {"highs": [], "lows": []})
        bucket["highs"].append(float(candle["high"]))
        bucket["lows"].append(float(candle["low"]))
    return {
        trade_date: AsianRange(trade_date=trade_date, high=max(values["highs"]), low=min(values["lows"]))
        for trade_date, values in buckets.items()
        if len(values["highs"]) >= 4
    }


def _run_strategy_fast(candles_m15: list[dict[str, Any]], candles_4h: list[dict[str, Any]], symbol: str, config: dict[str, Any]) -> list[Any]:
    cfg = dict(config)
    session_mode = str(cfg.get("session_mode", "legacy")).lower()
    rr = float(cfg["rr"])
    sl_buf = float(cfg["sl_buffer_pips"])
    mult = float(cfg["displacement_mult"])
    period = int(cfg["atr_period"])
    timeout = int(cfg["sweep_timeout_bars"])
    min_sl_pips = float(cfg.get("min_sl_pips", 0.0))
    min_range = float(cfg["min_range_pips"].get(symbol, 15.0))
    sorted_m15 = sorted(candles_m15, key=lambda row: row["time"])
    atrs = wilder_atr(sorted_m15, period)
    atr_map = {candle["time"]: atr for candle, atr in zip(sorted_m15, atrs)}
    asian_ranges = _precompute_asian_ranges(sorted_m15)
    killzone_by_date: dict[Any, list[tuple[dict[str, Any], str]]] = {}
    for candle in sorted_m15:
        dt = _parse_utc(candle["time"])
        session = classify_session_v2(dt) if session_mode == "v2" else classify_session(dt)
        if session is not None:
            killzone_by_date.setdefault(dt.date(), []).append((candle, session))

    signals: list[Any] = []
    for trade_date in sorted(killzone_by_date):
        asian = asian_ranges.get(trade_date)
        if asian is None or asian.range_pips < min_range:
            continue
        session_traded: set[str] = set()
        pending: dict[str, Any] | None = None
        for bar_idx, (candle, session) in enumerate(killzone_by_date.get(trade_date, [])):
            if session_mode == "v2" and session == "asian":
                continue
            if session == "newyork":
                session = "new_york"
            if session in session_traded:
                continue
            if pending and pending["session"] != session:
                pending = None
            bar_time = _parse_utc(candle["time"])
            bias = htf_bias(candles_4h, bar_time)
            if pending is None:
                if bias == "neutral":
                    continue
                sweep = detect_sweep(candle, asian.high, asian.low, bias)
                if sweep.detected:
                    pending = {"sweep": sweep, "bar_idx": bar_idx, "session": session}
                continue
            bars_since = bar_idx - int(pending["bar_idx"])
            if bars_since > timeout:
                pending = None
                continue
            disp = detect_displacement(candle, atr_map.get(candle["time"]), pending["sweep"].side, mult)
            if not disp.detected:
                continue
            sig = build_signal(candle, pending["sweep"], disp, asian, session, rr, sl_buf)
            pending = None
            if sig is not None and sig.risk_pips >= min_sl_pips:
                signals.append(sig)
                session_traded.add(session)
    return signals


def _ledger_hash(rows: list[dict[str, Any]]) -> str:
    normalized = [{key: row.get(key) for key in LEDGER_COLUMNS} for row in rows]
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _empty_ledger_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=LEDGER_COLUMNS)


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=LEDGER_COLUMNS) if rows else _empty_ledger_frame()
    table = pa.Table.from_pandas(frame, preserve_index=False)
    pq.write_table(table, path, compression="snappy")


def _gross_profit_factor(values: list[float]) -> float:
    wins = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def _max_drawdown(values: list[float]) -> float:
    running = peak = worst = 0.0
    for value in values:
        running += value
        peak = max(peak, running)
        worst = max(worst, peak - running)
    return worst


def _sortino(values: list[float]) -> float:
    if not values:
        return 0.0
    downside = [value for value in values if value < 0]
    if not downside:
        return 0.0
    dd = pstdev(downside) if len(downside) > 1 else abs(downside[0])
    return mean(values) / dd * math.sqrt(len(values)) if dd else 0.0


def generate_ledgers(
    strategy_config: Path = STRATEGY_CONFIG,
    output_dir: Path = LEDGER_DIR,
    overwrite: bool = False,
) -> dict[str, Any]:
    strategy = strategy_payload(strategy_config)
    manifest = write_registration_manifest()
    benchmark = load_yaml(BENCHMARK_CONFIG)
    ds_hash = dataset_hash(benchmark)
    symbols = list(strategy["market"]["symbols"])
    cfg = dict(strategy["parameters"])
    cfg["min_range_pips"] = dict(strategy["parameters"]["min_range_pips"])
    commission_pips = dict(strategy.get("cost_model", {}).get("commission_pips_round_trip", {}))
    slippage_pips = dict(strategy.get("cost_model", {}).get("slippage_pips_round_trip", {}))

    all_rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for symbol in symbols:
        output_path = output_dir / f"ST-A2_v1_{symbol}.parquet"
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"Frozen ledger already exists: {output_path}. Pass --overwrite to regenerate.")
        m15 = load_m15(symbol)
        h4 = load_h4(symbol)
        spread_map = _load_spread_map(symbol)
        regime_map = _load_regime_map(symbol)
        smc_map = _load_smc_map(symbol)
        fallback_spread = _fallback_spread(symbol)
        time_index = {bar["time"]: idx for idx, bar in enumerate(m15)}
        signals = _run_strategy_fast(m15, h4, symbol, cfg)
        rows: list[dict[str, Any]] = []
        pip_size = PIP_SIZE.get(symbol, 0.0001)
        for signal in signals:
            entry_time = signal.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
            idx = time_index.get(entry_time)
            if idx is None:
                continue
            future_bars = m15[idx + 1 :]
            outcome, gross_r, exit_price, exit_time, _bars_held = simulate_trade(
                signal.entry,
                signal.stop_loss,
                signal.side,
                float(signal.rr),
                future_bars,
            )
            risk_price = abs(float(signal.entry) - float(signal.stop_loss))
            spread_price = float(spread_map.get(entry_time, fallback_spread) or 0.0)
            commission_price = float(commission_pips.get(symbol, 0.0) or 0.0) * pip_size
            slippage_price = float(slippage_pips.get(symbol, 0.0) or 0.0) * pip_size
            spread_cost = spread_price / risk_price if risk_price else 0.0
            commission_cost = commission_price / risk_price if risk_price else 0.0
            slippage_cost = slippage_price / risk_price if risk_price else 0.0
            row = {
                "trade_id": "",
                "strategy_id": strategy["strategy_id"],
                "strategy_version": str(strategy["version"]),
                "strategy_hash": manifest["strategy_hash"],
                "dataset_version": benchmark["dataset"]["version"],
                "dataset_hash": ds_hash,
                "symbol": symbol,
                "timeframe": str(strategy["timeframes"]["execution"]),
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": float(signal.entry),
                "exit_price": float(exit_price),
                "stop_loss": float(signal.stop_loss),
                "take_profit": float(signal.take_profit),
                "position_size": 1.0,
                "gross_pnl": float(gross_r),
                "spread_cost": float(spread_cost),
                "commission": float(commission_cost),
                "commission_cost": float(commission_cost),
                "slippage": float(slippage_cost),
                "slippage_cost": float(slippage_cost),
                "net_pnl": float(gross_r - spread_cost - commission_cost - slippage_cost),
                "market_regime": regime_map.get(entry_time, "UNKNOWN"),
                "session": str(signal.session),
                "smc_context": json.dumps(smc_map.get(entry_time, []), sort_keys=True, separators=(",", ":")),
            }
            row["trade_id"] = _trade_id(row)
            rows.append(row)
        rows.sort(key=lambda row: (row["entry_time"], row["trade_id"]))
        _write_parquet(output_path, rows)
        files.append(
            {
                "path": str(output_path.relative_to(ROOT)),
                "symbol": symbol,
                "trade_count": len(rows),
                "parquet_sha256": file_sha256(output_path),
                "content_hash": _ledger_hash(rows),
            }
        )
        all_rows.extend(rows)

    all_rows.sort(key=lambda row: (row["entry_time"], row["symbol"], row["trade_id"]))
    ledger_manifest = {
        "strategy": strategy["strategy_id"],
        "version": str(strategy["version"]),
        "strategy_hash": manifest["strategy_hash"],
        "dataset": benchmark["dataset"]["version"],
        "dataset_hash": ds_hash,
        "trade_count": len(all_rows),
        "ledger_hash": _ledger_hash(all_rows),
        "status": "FROZEN",
        "created_at": _now(),
        "files": files,
        "schema": LEDGER_COLUMNS,
    }
    write_json(LEDGER_MANIFEST, ledger_manifest)
    return ledger_manifest


def load_ledgers(path: Path = LEDGER_DIR) -> list[dict[str, Any]]:
    files = sorted(path.glob("ST-A2_v1_*.parquet")) if path.is_dir() else [path]
    rows: list[dict[str, Any]] = []
    for file_path in files:
        if not file_path.exists():
            continue
        frame = pd.read_parquet(file_path)
        rows.extend(frame.to_dict("records"))
    return sorted(rows, key=lambda row: (str(row.get("entry_time", "")), str(row.get("symbol", "")), str(row.get("trade_id", ""))))


def baseline_release_report(
    validation: dict[str, Any],
    registration: dict[str, Any],
    ledger_manifest: dict[str, Any],
    output_path: Path = BASELINE_RELEASE_REPORT,
) -> str:
    metrics = validation.get("metrics", {})
    status = validation.get("status")
    if status == "PASS":
        decision = "READY_FOR_OPTIMIZATION"
    elif int(metrics.get("trades", metrics.get("trade_count", 0)) or 0) == 0:
        decision = "INSUFFICIENT_DATA"
    else:
        decision = "FAILED_BASELINE"

    lines = [
        "# ST-A2 Baseline Release Report",
        "",
        "## Strategy",
        "",
        f"- Version: {registration['version']}",
        f"- Strategy hash: `{registration['strategy_hash']}`",
        "- Rules: frozen in `config/strategies/ST-A2_v1.yaml`",
        "",
        "## Dataset",
        "",
        f"- Version: {registration['dataset_version']}",
        f"- Hash: `{registration['dataset_hash']}`",
        "- Coverage: `professional_3y_4symbol_v2` benchmark periods",
        "",
        "## Results",
        "",
        f"- Trades: {metrics.get('trades', 0)}",
        f"- Win rate: {metrics.get('win_rate', 0.0):.4f}",
        f"- Profit factor after cost: {metrics.get('profit_factor_after_cost', 0.0):.4f}",
        f"- Sharpe ratio: {metrics.get('sharpe_ratio', metrics.get('sharpe', 0.0)):.4f}",
        f"- Maximum drawdown: {metrics.get('maximum_drawdown', metrics.get('max_drawdown', 0.0)):.4f}",
        f"- Gross profit: {metrics.get('gross_profit', 0.0):.4f}",
        f"- Spread cost: {metrics.get('spread_cost', 0.0):.4f}",
        f"- Commission cost: {metrics.get('commission_cost', 0.0):.4f}",
        f"- Slippage cost: {metrics.get('slippage_cost', 0.0):.4f}",
        f"- Net profit: {metrics.get('net_profit', 0.0):.4f}",
        "",
        "## Ledger",
        "",
        f"- Trade count: {ledger_manifest.get('trade_count', 0)}",
        f"- Ledger hash: `{ledger_manifest.get('ledger_hash', '')}`",
        "",
        "## Decision",
        "",
        decision,
        "",
        "No live trading configuration, broker credentials, MT5 execution code, or strategy parameters were changed.",
        "",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return decision


def generate_baseline(overwrite: bool = False) -> dict[str, Any]:
    registration = write_registration_manifest()
    ledger_manifest = generate_ledgers(overwrite=overwrite)
    validation = st_a2_validation_report(LEDGER_DIR)
    write_json(VALIDATION_REPORT, validation)
    decision = baseline_release_report(validation, registration, ledger_manifest)
    return {
        "registration_manifest": str(REGISTRATION_MANIFEST),
        "ledger_manifest": str(LEDGER_MANIFEST),
        "validation_report": str(VALIDATION_REPORT),
        "baseline_release_report": str(BASELINE_RELEASE_REPORT),
        "decision": decision,
        "trade_count": ledger_manifest["trade_count"],
        "ledger_hash": ledger_manifest["ledger_hash"],
        "validation_status": validation["status"],
    }
