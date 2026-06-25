"""
RESEARCH-01 — Local research logger.

Appends structured records to CSV files in the research/ directory.
Schema is DuckDB/BigQuery-ready: ISO-8601 timestamps, UUID IDs, typed columns.

Usage:
    from research.logger import log_backtest_run, log_trade, generate_run_id

    run_id = generate_run_id()
    # ... run backtest, collect trades ...
    log_trade(trade_record)
    log_backtest_run(summary_record)

For testing:
    research.logger._set_base_dir(Path("/tmp/test_research"))
"""

import csv
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Base directory (override in tests via _set_base_dir) ─────────────────────

_BASE_DIR: Path = Path(__file__).parent


def _set_base_dir(path: Path) -> None:
    """Redirect all CSV writes to a different directory. Testing only."""
    global _BASE_DIR
    _BASE_DIR = path


def _csv(name: str) -> Path:
    return _BASE_DIR / name


# ── Timestamp helper ──────────────────────────────────────────────────────────

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_run_id() -> str:
    """
    Generate a unique backtest run ID.

    Format: YYYYMMDDTHHMMSS-<6hex>
    Human-readable, time-sortable, and unique enough for local research logs.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{ts}-{suffix}"


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class BacktestRun:
    """One completed backtest execution.  Maps to backtest_runs.csv."""
    run_id: str
    timestamp_utc: str
    strategy_id: str           # e.g. 'SA' | 'SB'
    strategy_version: str      # semver or git tag
    symbol: str                # 'EURUSD' | 'GBPUSD'
    timeframe: str             # 'M15'
    start_date: str            # 'YYYY-MM-DD'
    end_date: str
    rr: float
    spread_model: str          # 'standard' | '2x'
    spread_pips: float
    trade_count: int
    win_count: int
    loss_count: int
    gross_pf: float
    net_pf_std: float
    net_pf_2x: float
    win_rate_pct: float
    avg_r: float
    max_dd_r: float
    total_net_r: float
    gate_passed: bool          # True if meets n≥100 + PF>1.0 gate
    notes: str = ""


@dataclass
class TradeRecord:
    """One completed trade.  Maps to trades.csv."""
    trade_id: str
    run_id: str
    timestamp_utc: str         # signal timestamp
    symbol: str
    session: str               # 'london' | 'new_york'
    side: str                  # 'long' | 'short'
    entry: float
    stop_loss: float
    take_profit: float
    sl_pips: float
    rr: float
    exit_price: float
    exit_reason: str           # 'tp' | 'sl' | 'timeout'
    bars_held: int
    gross_r: float
    spread_cost_r: float
    net_r: float
    asian_high: float
    asian_low: float
    asian_range_pips: float
    htf_bias: str              # 'bullish' | 'bearish'
    sweep_bar_time: str        # ISO-8601
    displacement_bar_time: str # ISO-8601
    notes: str = ""


@dataclass
class SignalRecord:
    """One generated signal, whether it led to a trade or was rejected.  Maps to signal_log.csv."""
    signal_id: str
    run_id: str
    timestamp_utc: str
    symbol: str
    session: str
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    sl_pips: float
    rr: float
    asian_high: float
    asian_low: float
    asian_range_pips: float
    htf_bias: str
    sweep_bar_time: str
    displacement_bar_time: str
    fired: bool                # True = trade placed; False = rejected post-signal
    rejection_reason: str = "" # empty when fired=True


@dataclass
class GateRejection:
    """One gate rejection — a bar that failed an AND-gate condition.  Maps to gate_rejections.csv."""
    rejection_id: str
    run_id: str
    timestamp_utc: str
    symbol: str
    session: str               # 'london' | 'new_york' | ''
    gate_name: str             # 'no_session' | 'already_traded' | 'no_asian_range' |
                               # 'range_too_small' | 'neutral_bias' | 'sweep_timeout' |
                               # 'displacement_absent' | 'degenerate_sl'
    reason: str                # human-readable detail
    bar_time: str              # ISO-8601 of the rejected bar
    asian_range_pips: float    # 0.0 if not yet built
    htf_bias: str              # 'bullish' | 'bearish' | 'neutral' | ''
    price: float               # bar close at rejection time


@dataclass
class MarketCondition:
    """Market snapshot at signal evaluation time.  Maps to market_conditions.csv."""
    condition_id: str
    run_id: str
    timestamp_utc: str
    symbol: str
    session: str
    htf_bias: str
    atr_pips: float
    asian_range_pips: float
    asian_high: float
    asian_low: float
    price_close: float


@dataclass
class StrategyVersion:
    """Strategy parameter set.  Maps to strategy_versions.csv."""
    version_id: str
    strategy_id: str           # 'SA' | 'SB'
    created_utc: str
    rr: float
    sl_buffer_pips: float
    displacement_atr_mult: float
    min_asian_range_pips_eurusd: float
    min_asian_range_pips_gbpusd: float
    swing_n: int
    atr_period: int
    notes: str = ""


# ── CSV write helper ──────────────────────────────────────────────────────────

def _append_row(path: Path, record: Any) -> None:
    """
    Append a dataclass record to a CSV file.

    Creates the file (and parent directories) if absent.
    Writes the header only when the file is new or empty — never repeats it.
    """
    row = asdict(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)


# ── Public logging functions ──────────────────────────────────────────────────

def log_backtest_run(record: BacktestRun) -> None:
    """Append a completed backtest summary to backtest_runs.csv."""
    _append_row(_csv("backtest_runs.csv"), record)


def log_trade(record: TradeRecord) -> None:
    """Append a completed trade to trades.csv."""
    _append_row(_csv("trades.csv"), record)


def log_signal(record: SignalRecord) -> None:
    """Append a generated signal to signal_log.csv."""
    _append_row(_csv("signal_log.csv"), record)


def log_rejection(record: GateRejection) -> None:
    """Append a gate rejection to gate_rejections.csv."""
    _append_row(_csv("gate_rejections.csv"), record)


def log_market_condition(record: MarketCondition) -> None:
    """Append a market conditions snapshot to market_conditions.csv."""
    _append_row(_csv("market_conditions.csv"), record)


def log_strategy_version(record: StrategyVersion) -> None:
    """Append a strategy parameter set to strategy_versions.csv."""
    _append_row(_csv("strategy_versions.csv"), record)


# ── Convenience constructors ──────────────────────────────────────────────────

def new_trade_id() -> str:
    return str(uuid.uuid4())


def new_signal_id() -> str:
    return str(uuid.uuid4())


def new_rejection_id() -> str:
    return str(uuid.uuid4())


def new_condition_id() -> str:
    return str(uuid.uuid4())


def new_version_id() -> str:
    return str(uuid.uuid4())
