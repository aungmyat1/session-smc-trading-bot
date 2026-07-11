from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = ROOT / "config" / "research_benchmark.yaml"
OPTIMIZATION_DIAGNOSTICS = ROOT / "config" / "strategy_optimization_diagnostics.yaml"
ARTIFACTS = ROOT / "artifacts"


def load_yaml(path: Path | str = DEFAULT_BENCHMARK) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def dataset_hash(config: dict[str, Any]) -> str:
    checksums_path = ROOT / str(config["dataset"]["checksums_path"])
    checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    return str(checksums.get("dataset_hash") or checksums.get("artifact_hash") or "")


def git_state() -> dict[str, Any]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    except Exception:
        commit = "UNKNOWN"
        dirty = None
    return {"commit": commit, "dirty": dirty}


def run_metadata(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": config["dataset"]["version"],
        "dataset_hash": dataset_hash(config),
        "git": git_state(),
    }


def optimization_diagnostics(path: Path | str | None = None) -> list[dict[str, str]]:
    payload = load_yaml(path or OPTIMIZATION_DIAGNOSTICS)
    return [dict(row) for row in payload.get("diagnostics", [])]


def _processed_path(config: dict[str, Any], symbol: str, timeframe: str) -> Path:
    return ROOT / str(config["dataset"]["processed_root"]) / symbol / f"{timeframe}.parquet"


def _load_bars(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=columns)
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    return frame.sort_values("timestamp_utc").reset_index(drop=True)


def _expected_delta(timeframe: str) -> pd.Timedelta:
    value = timeframe.upper()
    if value.startswith("M"):
        return pd.Timedelta(minutes=int(value[1:]))
    if value.startswith("H"):
        return pd.Timedelta(hours=int(value[1:]))
    if value.startswith("D"):
        return pd.Timedelta(days=int(value[1:]))
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def price_integrity_report(config: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for symbol in config["symbols"]:
        for timeframe in config["timeframes"]:
            path = _processed_path(config, symbol, timeframe)
            if not path.exists():
                rows.append({"symbol": symbol, "timeframe": timeframe, "status": "MISSING", "path": str(path.relative_to(ROOT))})
                continue
            frame = _load_bars(path, ["timestamp_utc", "open", "high", "low", "close"])
            high_bad = frame["high"] < frame[["open", "close"]].max(axis=1)
            low_bad = frame["low"] > frame[["open", "close"]].min(axis=1)
            duplicates = int(frame["timestamp_utc"].duplicated().sum())
            deltas = frame["timestamp_utc"].diff().dropna()
            expected = _expected_delta(timeframe)
            large_gaps = int((deltas > expected * 1.5).sum())
            returns = frame["close"].pct_change().abs().dropna()
            threshold = float(returns.quantile(0.999) * 5) if not returns.empty else 0.0
            abnormal = int((returns > threshold).sum()) if threshold > 0 else 0
            status = "PASS" if not (int(high_bad.sum()) or int(low_bad.sum()) or duplicates) else "FAIL"
            rows.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "path": str(path.relative_to(ROOT)),
                    "rows": int(len(frame)),
                    "start": frame["timestamp_utc"].iloc[0].isoformat() if len(frame) else None,
                    "end": frame["timestamp_utc"].iloc[-1].isoformat() if len(frame) else None,
                    "ohlc_high_violations": int(high_bad.sum()),
                    "ohlc_low_violations": int(low_bad.sum()),
                    "duplicate_timestamps": duplicates,
                    "large_timestamp_gaps": large_gaps,
                    "abnormal_candles": abnormal,
                    "timezone": "UTC",
                    "status": status,
                }
            )
    return {"status": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL", "files": rows}


def return_distribution_report(config: dict[str, Any], timeframe: str = "M15") -> dict[str, Any]:
    symbols: dict[str, Any] = {}
    for symbol in config["symbols"]:
        path = _processed_path(config, symbol, timeframe)
        if not path.exists():
            symbols[symbol] = {"status": "MISSING"}
            continue
        frame = _load_bars(path, ["timestamp_utc", "open", "high", "low", "close"])
        returns = frame["close"].pct_change().dropna()
        movement = ((frame["high"] - frame["low"]) / frame["open"].replace(0, math.nan)).dropna()
        abs_returns = returns.abs()
        rolling_vol = returns.rolling(20).std().dropna()
        clustering = float(abs_returns.autocorr(lag=1)) if len(abs_returns) > 2 else 0.0
        symbols[symbol] = {
            "status": "PASS",
            "timeframe": timeframe,
            "rows": int(len(frame)),
            "average_return": float(returns.mean()) if len(returns) else 0.0,
            "volatility": float(returns.std(ddof=0)) if len(returns) else 0.0,
            "max_candle_movement": float(movement.max()) if len(movement) else 0.0,
            "percentile_moves": {
                "p50": float(abs_returns.quantile(0.50)) if len(abs_returns) else 0.0,
                "p95": float(abs_returns.quantile(0.95)) if len(abs_returns) else 0.0,
                "p99": float(abs_returns.quantile(0.99)) if len(abs_returns) else 0.0,
            },
            "volatility_clustering": {
                "abs_return_autocorr_lag1": 0.0 if math.isnan(clustering) else clustering,
                "rolling_volatility_p95": float(rolling_vol.quantile(0.95)) if len(rolling_vol) else 0.0,
            },
        }
    return {"status": "PASS" if all(v.get("status") == "PASS" for v in symbols.values()) else "FAIL", "symbols": symbols}


def spread_validation_report(config: dict[str, Any], timeframe: str = "M5") -> dict[str, Any]:
    symbols: dict[str, Any] = {}
    for symbol in config["symbols"]:
        path = _processed_path(config, symbol, timeframe)
        if not path.exists():
            symbols[symbol] = {"status": "MISSING"}
            continue
        frame = _load_bars(path, ["timestamp_utc", "open", "ask_open", "bid_open", "spread_avg", "spread_max"])
        spread = frame.get("spread_avg")
        source = "spread_avg"
        if spread is None or spread.isna().all():
            spread = frame["ask_open"] - frame["bid_open"]
            source = "ask_open_minus_bid_open"
        spread = pd.to_numeric(spread, errors="coerce").dropna()
        if symbol == "BTCUSD":
            symbols[symbol] = {
                "status": "PASS" if len(spread) else "WARN",
                "asset_class": "crypto",
                "source": source,
                "rows": int(len(spread)),
                "commission_model": config["cost_model"]["commission_model"],
                "slippage_model": config["cost_model"]["slippage_model"],
                "execution_impact": {
                    "median_spread": float(spread.quantile(0.50)) if len(spread) else None,
                    "p95_spread": float(spread.quantile(0.95)) if len(spread) else None,
                    "p99_spread": float(spread.quantile(0.99)) if len(spread) else None,
                },
            }
        else:
            symbols[symbol] = {
                "status": "PASS" if len(spread) else "FAIL",
                "asset_class": "forex",
                "source": source,
                "rows": int(len(spread)),
                "median_spread": float(spread.quantile(0.50)) if len(spread) else None,
                "p95_spread": float(spread.quantile(0.95)) if len(spread) else None,
                "p99_spread": float(spread.quantile(0.99)) if len(spread) else None,
            }
    return {"status": "PASS" if all(v.get("status") in {"PASS", "WARN"} for v in symbols.values()) else "FAIL", "symbols": symbols}


def run_dataset_research_audit(config_path: Path | str = DEFAULT_BENCHMARK, outdir: Path = ARTIFACTS) -> dict[str, Any]:
    config = load_yaml(config_path)
    metadata = run_metadata(config)
    price = {**metadata, **price_integrity_report(config)}
    returns = {**metadata, **return_distribution_report(config)}
    spreads = {**metadata, **spread_validation_report(config)}
    write_json(outdir / "dataset_research_audit.json", price)
    write_json(outdir / "return_distribution_report.json", returns)
    write_json(outdir / "spread_validation_report.json", spreads)
    return {"dataset_research_audit": price, "return_distribution_report": returns, "spread_validation_report": spreads}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##+\s+{re.escape(heading)}.*?$([\s\S]*?)(?=^##+\s+|\Z)", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def strategy_audit_inventory(
    catalog_path: Path | str = ROOT / "config" / "strategy_catalog.yaml",
    config_path: Path | str = DEFAULT_BENCHMARK,
) -> dict[str, Any]:
    config = load_yaml(config_path)
    catalog_file = Path(catalog_path)
    if not catalog_file.is_absolute():
        catalog_file = ROOT / catalog_file
    catalog = yaml.safe_load(catalog_file.read_text(encoding="utf-8")) or {}
    strategies = []
    for name, manifest in sorted((catalog.get("strategies") or {}).items()):
        if not isinstance(manifest, dict):
            continue
        spec_path = manifest.get("strategy_spec_path")
        spec_text = ""
        spec_hash = None
        if spec_path:
            resolved = ROOT / str(spec_path)
            if resolved.exists():
                spec_text = resolved.read_text(encoding="utf-8")
                spec_hash = _file_sha256(resolved)
        strategies.append(
            {
                "strategy": name,
                "strategy_version": str(manifest.get("version", "")),
                "status": manifest.get("status"),
                "approved": bool(manifest.get("approved", False)),
                "current": bool(manifest.get("current", False)),
                "parameters": {
                    "catalog_requirements": manifest.get("requirements", {}),
                    "portfolio_parameters": manifest.get("parameters", {}),
                },
                "symbols": list(manifest.get("symbols", [])),
                "timeframes": list(manifest.get("timeframes", [])),
                "entry_logic": _section(spec_text, "Entry Rules") or _section(spec_text, "Signal Chain"),
                "exit_logic": _section(spec_text, "Exit Rules"),
                "risk_model": _section(spec_text, "Risk") or _section(spec_text, "Kill Switch / Safety"),
                "strategy_spec_path": spec_path,
                "strategy_spec_hash": spec_hash,
            }
        )
    return {**run_metadata(config), "catalog_path": str(catalog_file.relative_to(ROOT)), "strategies": strategies}


def write_strategy_audit_report(out: Path = ARTIFACTS / "strategy_audit_report.json") -> dict[str, Any]:
    payload = strategy_audit_inventory()
    write_json(out, payload)
    return payload


def _profit_factor(values: list[float]) -> float:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def _max_drawdown_pct(values: list[float], initial_equity: float = 100.0) -> float:
    equity = initial_equity
    peak = initial_equity
    worst = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        if peak:
            worst = max(worst, (peak - equity) / peak * 100.0)
    return worst


def trade_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = [float(t.get("net_pnl", t.get("net_r", t.get("std_net_r", 0.0))) or 0.0) for t in trades]
    wins = [value for value in pnl if value > 0]
    monthly: dict[str, float] = {}
    for trade, value in zip(trades, pnl):
        ts = str(trade.get("exit_time") or trade.get("entry_time") or trade.get("timestamp") or "")
        month = ts[:7] if len(ts) >= 7 else "unknown"
        monthly[month] = monthly.get(month, 0.0) + value
    std = pstdev(pnl) if len(pnl) > 1 else 0.0
    sharpe = (mean(pnl) / std * math.sqrt(len(pnl))) if std else 0.0
    total = sum(pnl)
    largest_month_share = max((abs(v) for v in monthly.values()), default=0.0) / abs(total) if total else 0.0
    return {
        "trades": len(pnl),
        "win_rate": len(wins) / len(pnl) if pnl else 0.0,
        "profit_factor": _profit_factor(pnl),
        "profit_factor_after_cost": _profit_factor(pnl),
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown_pct(pnl),
        "average_R": mean(pnl) if pnl else 0.0,
        "expectancy": mean(pnl) if pnl else 0.0,
        "monthly_returns": monthly,
        "largest_month_dependency": largest_month_share,
    }


def load_trade_ledger(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return list(payload.get("trades", []))
        return list(payload)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def st_a2_validation_report(trades_path: Path | None, config_path: Path | str = DEFAULT_BENCHMARK) -> dict[str, Any]:
    config = load_yaml(config_path)
    base = run_metadata(config)
    if trades_path is None:
        return {
            **base,
            "strategy": "ST-A2",
            "status": "BLOCKED",
            "reason": "No immutable trade ledger supplied. Run a pre-registered replay/backtest first.",
            "required_trade_fields": ["entry_price", "exit_price", "spread_cost", "commission", "slippage", "gross_pnl", "net_pnl"],
        }
    trades = load_trade_ledger(trades_path)
    missing = sorted(
        {
            field
            for trade in trades
            for field in ["entry_price", "exit_price", "spread_cost", "commission", "slippage", "gross_pnl", "net_pnl"]
            if field not in trade
        }
    )
    metrics = trade_metrics(trades)
    gates = config["acceptance_gates"]
    passed = (
        not missing
        and metrics["trades"] >= int(gates["trades_min"])
        and metrics["profit_factor_after_cost"] > float(gates["profit_factor_min"])
        and metrics["sharpe"] > float(gates["sharpe_min"])
        and metrics["max_drawdown"] < float(gates["max_drawdown_pct_max"])
        and metrics["expectancy"] > float(gates["expectancy_min"])
        and metrics["largest_month_dependency"] <= 0.5
    )
    return {
        **base,
        "strategy": "ST-A2",
        "status": "PASS" if passed else "FAIL",
        "trade_ledger": str(trades_path),
        "missing_required_trade_fields": missing,
        "metrics": metrics,
        "acceptance_gates": gates,
    }


def validation_matrix(config_path: Path | str = DEFAULT_BENCHMARK) -> list[dict[str, Any]]:
    config = load_yaml(config_path)
    portfolio = yaml.safe_load((ROOT / "config" / "strategy_portfolio.yaml").read_text(encoding="utf-8")) or {}
    rows = []
    for strategy, manifest in sorted((portfolio.get("strategies") or {}).items()):
        pairs = list(manifest.get("pairs", []))
        for symbol in pairs:
            rows.append(
                {
                    "strategy": strategy,
                    "symbol": symbol,
                    "timeframe": "M15",
                    "trades": "",
                    "PF": "",
                    "Sharpe": "",
                    "DD": "",
                    "status": "NOT_RUN",
                    "dataset_version": config["dataset"]["version"],
                    "dataset_hash": dataset_hash(config),
                }
            )
    return rows


def write_validation_matrix(out: Path = ARTIFACTS / "strategy_validation_matrix.csv") -> list[dict[str, Any]]:
    rows = validation_matrix()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["strategy", "symbol", "timeframe", "trades", "PF", "Sharpe", "DD", "status", "dataset_version", "dataset_hash"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


WALK_FORWARD_WINDOWS = [
    {"name": "test_1", "training": {"start": "2023-07-01", "end": "2024-12-31"}, "validation": {"start": "2025-01-01", "end": "2025-06-30"}},
    {"name": "test_2", "training": {"start": "2024-01-01", "end": "2025-06-30"}, "validation": {"start": "2025-07-01", "end": "2025-12-31"}},
    {"name": "test_3", "training": {"start": "2024-07-01", "end": "2025-12-31"}, "validation": {"start": "2026-01-01", "end": "2026-06-30"}},
]


def walk_forward_report(trades_path: Path | None = None, config_path: Path | str = DEFAULT_BENCHMARK) -> dict[str, Any]:
    config = load_yaml(config_path)
    report = {**run_metadata(config), "status": "NOT_RUN", "windows": WALK_FORWARD_WINDOWS}
    if trades_path is None:
        report["reason"] = "No trade ledger supplied."
        return report
    trades = load_trade_ledger(trades_path)
    rows = []
    for window in WALK_FORWARD_WINDOWS:
        validation = window["validation"]
        subset = [
            trade
            for trade in trades
            if validation["start"] <= str(trade.get("entry_time") or trade.get("timestamp") or "")[:10] <= validation["end"]
        ]
        rows.append({**window, "metrics": trade_metrics(subset)})
    report["status"] = "PASS" if all(row["metrics"]["expectancy"] > 0 for row in rows) else "FAIL"
    report["windows"] = rows
    return report


def robustness_report(trades_path: Path | None = None, config_path: Path | str = DEFAULT_BENCHMARK) -> dict[str, Any]:
    from research.robustness import monte_carlo_resampling

    config = load_yaml(config_path)
    report = {
        **run_metadata(config),
        "status": "NOT_RUN",
        "parameter_sensitivity": {
            "status": "PLANNED",
            "parameters": ["stop_loss", "take_profit", "confirmation_window", "session_filter"],
            "constraint": "sensitivity only; no brute-force optimization",
        },
        "optimization_diagnostics": optimization_diagnostics(),
        "monte_carlo": {"status": "NOT_RUN"},
    }
    if trades_path is None:
        report["reason"] = "No trade ledger supplied."
        return report
    trades = load_trade_ledger(trades_path)
    normalized = [{**trade, "std_net_r": float(trade.get("net_pnl", trade.get("net_r", trade.get("std_net_r", 0.0))) or 0.0)} for trade in trades]
    mc = monte_carlo_resampling(normalized, r_key="std_net_r")
    report["monte_carlo"] = mc
    report["status"] = "PASS" if mc.get("passed") else "FAIL"
    return report
