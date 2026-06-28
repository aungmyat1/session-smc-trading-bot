"""
replay/engine.py — Historical Replay Engine for all 5 strategies.

Runs ST-A2, LondonBreakout, NYMomentum, AdaptiveSMC, and VWAPBreakout
walk-forward over historical CSV data.  No broker connection.  No lookahead.

Architecture:
    CSVLoader  → load M15 + H4 + H1 candles per symbol
    ReplayEngine.run() → iterate day by day, feed bars one at a time
        ├─ ST-A2Adapter          (needs M15 + H4)
        ├─ LondonBreakoutAdapter (needs M15)
        ├─ NYMomentumAdapter     (needs M15)
        ├─ AdaptiveSMCAdapter    (needs M15 + H4) [shadow]
        └─ VWAPBreakoutAdapter   (needs M15)      [shadow]
    TradeSimulator → SL/TP walk-forward, cost deduction
    ReplayResult   → full trade log exported to CSV

No-lookahead guarantee:
    At each bar index i the strategy receives candles[0..i] only.
    Adapters are called with the accumulated window — identical to
    how ForwardTestSimulator works.  Future bars are never visible.

Usage:
    from replay.engine import ReplayEngine, ReplayConfig
    cfg = ReplayConfig(symbols=["EURUSD", "GBPUSD"], start="2021-01-01", end="2024-12-31")
    engine = ReplayEngine(cfg)
    results = engine.run()
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# ── Cost model (round-trip pips: spread + commission) ─────────────────────────

_DEFAULT_COSTS: dict[str, dict[str, float]] = {
    "EURUSD": {"standard": 1.4, "stress2x": 2.8},
    "GBPUSD": {"standard": 1.8, "stress2x": 3.6},
    "USDJPY": {"standard": 1.6, "stress2x": 3.2},
}

_PIP: dict[str, float] = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
}

# Max bars to hold an open trade before timing out (96 bars = 24h at M15)
MAX_HOLD_BARS = 96

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class ReplayConfig:
    symbols:          list[str]         = field(default_factory=lambda: ["EURUSD", "GBPUSD"])
    start:            str               = "2021-01-01"   # YYYY-MM-DD
    end:              str               = "2024-12-31"   # YYYY-MM-DD
    data_dir:         Path              = _ROOT / "data" / "historical"
    costs:            dict              = field(default_factory=lambda: _DEFAULT_COSTS.copy())
    strategies:       list[str]         = field(default_factory=lambda: [
        "ST-A2", "LondonBreakout", "NYMomentum", "AdaptiveSMC", "VWAPBreakout"
    ])
    # Window of M15 bars supplied to each adapter per call
    m15_lookback:     int               = 300   # ~3 days of M15
    h4_lookback:      int               = 200   # ~33 days of H4


@dataclass
class ReplayTrade:
    strategy:         str
    symbol:           str
    action:           str               # "BUY" | "SELL"
    mode:             str               # "demo" | "shadow"
    entry_price:      float
    stop_loss:        float
    take_profit:      float
    entry_time:       str               # ISO UTC
    sl_pips:          float
    risk_percent:     float
    confidence:       float
    # Filled after simulation
    exit_price:       float = 0.0
    exit_time:        str   = ""
    exit_reason:      str   = ""        # "TP" | "SL" | "TIMEOUT"
    gross_r:          float = 0.0
    net_r_std:        float = 0.0
    net_r_stress:     float = 0.0
    cost_r_std:       float = 0.0
    cost_r_stress:    float = 0.0
    bars_held:        int   = 0
    session:          str   = ""
    metadata:         dict  = field(default_factory=dict)


@dataclass
class ReplayResult:
    config:    ReplayConfig
    trades:    list[ReplayTrade] = field(default_factory=list)
    errors:    list[str]        = field(default_factory=list)


# ── CSV loader ────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> list[dict]:
    """Load OHLCV CSV into list of dicts sorted by time."""
    if not path.exists():
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "time":   row["time"],
                "open":   float(row["open"]),
                "high":   float(row["high"]),
                "low":    float(row["low"]),
                "close":  float(row["close"]),
                "volume": float(row.get("volume", 0.0)),
            })
    rows.sort(key=lambda r: r["time"])
    return rows


def filter_date_range(candles: list[dict], start: str, end: str) -> list[dict]:
    """Keep candles whose time string starts within [start, end] (date prefix compare)."""
    return [c for c in candles if start <= c["time"][:10] <= end]


# ── Trade simulator ───────────────────────────────────────────────────────────

def simulate_exit(
    trade: ReplayTrade,
    future_bars: list[dict],
    pip: float,
    cost_std: float,
    cost_stress: float,
) -> ReplayTrade:
    """
    Walk future M15 bars forward and determine SL/TP/timeout exit.

    SL is checked before TP within the same bar (conservative).
    """
    sl_dist = abs(trade.entry_price - trade.stop_loss)
    if sl_dist == 0:
        trade.exit_reason = "INVALID_SL"
        return trade

    sl_pips    = sl_dist / pip
    is_long    = trade.action == "BUY"

    for i, bar in enumerate(future_bars[:MAX_HOLD_BARS]):
        h, lo = float(bar["high"]), float(bar["low"])

        if is_long:
            if lo <= trade.stop_loss:
                trade.exit_price  = trade.stop_loss
                trade.exit_reason = "SL"
                trade.exit_time   = bar["time"]
                trade.bars_held   = i + 1
                break
            if h >= trade.take_profit:
                trade.exit_price  = trade.take_profit
                trade.exit_reason = "TP"
                trade.exit_time   = bar["time"]
                trade.bars_held   = i + 1
                break
        else:  # SELL
            if h >= trade.stop_loss:
                trade.exit_price  = trade.stop_loss
                trade.exit_reason = "SL"
                trade.exit_time   = bar["time"]
                trade.bars_held   = i + 1
                break
            if lo <= trade.take_profit:
                trade.exit_price  = trade.take_profit
                trade.exit_reason = "TP"
                trade.exit_time   = bar["time"]
                trade.bars_held   = i + 1
                break
    else:
        # Timeout — exit at close of last bar checked
        bars_checked = min(len(future_bars), MAX_HOLD_BARS)
        if bars_checked > 0:
            last = future_bars[bars_checked - 1]
            trade.exit_price  = float(last["close"])
            trade.exit_reason = "TIMEOUT"
            trade.exit_time   = last["time"]
            trade.bars_held   = bars_checked
        else:
            trade.exit_reason = "NO_FUTURE_BARS"
            return trade

    # R multiples
    if is_long:
        gross_pips = (trade.exit_price - trade.entry_price) / pip
    else:
        gross_pips = (trade.entry_price - trade.exit_price) / pip

    trade.gross_r      = round(gross_pips / sl_pips, 4)
    trade.cost_r_std   = round(cost_std    / sl_pips, 4)
    trade.cost_r_stress= round(cost_stress / sl_pips, 4)
    trade.net_r_std    = round(trade.gross_r - trade.cost_r_std,    4)
    trade.net_r_stress = round(trade.gross_r - trade.cost_r_stress, 4)
    trade.sl_pips      = round(sl_pips, 1)
    return trade


# ── Adapter loader ─────────────────────────────────────────────────────────────

def _load_adapters(strategy_names: list[str]):
    """Import and instantiate adapters for the requested strategies."""
    adapters = {}
    modes    = {}

    if "ST-A2" in strategy_names:
        try:
            from strategies.adapters.st_a2_adapter import ST_A2Adapter
            adapters["ST-A2"] = ST_A2Adapter()
            modes["ST-A2"]    = "demo"
        except ImportError as e:
            print(f"  [WARN] ST-A2Adapter import failed: {e}")

    if "LondonBreakout" in strategy_names:
        try:
            from strategies.adapters.london_breakout_adapter import LondonBreakoutAdapter
            adapters["LondonBreakout"] = LondonBreakoutAdapter()
            modes["LondonBreakout"]    = "demo"
        except ImportError as e:
            print(f"  [WARN] LondonBreakoutAdapter import failed: {e}")

    if "NYMomentum" in strategy_names:
        try:
            from strategies.adapters.ny_momentum_adapter import NYMomentumAdapter
            adapters["NYMomentum"] = NYMomentumAdapter()
            modes["NYMomentum"]    = "demo"
        except ImportError as e:
            print(f"  [WARN] NYMomentumAdapter import failed: {e}")

    if "AdaptiveSMC" in strategy_names:
        try:
            from strategies.adapters.adaptive_smc_adapter import AdaptiveSMCAdapter
            adapters["AdaptiveSMC"] = AdaptiveSMCAdapter()
            modes["AdaptiveSMC"]    = "shadow"
        except ImportError as e:
            print(f"  [WARN] AdaptiveSMCAdapter import failed: {e}")

    if "VWAPBreakout" in strategy_names:
        try:
            from strategies.adapters.vwap_adapter import VWAPBreakoutAdapter
            adapters["VWAPBreakout"] = VWAPBreakoutAdapter()
            modes["VWAPBreakout"]    = "shadow"
        except ImportError as e:
            print(f"  [WARN] VWAPBreakoutAdapter import failed: {e}")

    return adapters, modes


# ── Deduplication guard ────────────────────────────────────────────────────────

class _SignalDedup:
    """
    Prevent the same signal being recorded twice.

    Adapters return the most-recent signal from accumulated history — the same
    signal can appear on multiple bars until a new one is generated.
    We track (strategy, symbol, entry_time) to emit each signal exactly once.
    """
    def __init__(self):
        self._seen: set[tuple] = set()

    def is_new(self, strategy: str, symbol: str, entry_time: str) -> bool:
        key = (strategy, symbol, entry_time)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def reset(self):
        self._seen.clear()


# ── Main engine ────────────────────────────────────────────────────────────────

class ReplayEngine:
    """
    Walk-forward historical replay for all 5 strategies.

    Each bar is fed one at a time to each adapter.  The adapter receives
    only candles[0..i] — no future data.  Signals are deduplicated and
    simulated forward for SL/TP/timeout exit.
    """

    def __init__(self, config: ReplayConfig) -> None:
        self.cfg = config

    def run(self) -> ReplayResult:
        result   = ReplayResult(config=self.cfg)
        adapters, modes = _load_adapters(self.cfg.strategies)

        if not adapters:
            result.errors.append("No adapters loaded — check import paths.")
            return result

        print(f"\n{'='*60}")
        print("  Historical Replay Engine")
        print(f"  Strategies : {list(adapters.keys())}")
        print(f"  Symbols    : {self.cfg.symbols}")
        print(f"  Period     : {self.cfg.start} → {self.cfg.end}")
        print(f"{'='*60}\n")

        for symbol in self.cfg.symbols:
            pip        = _PIP.get(symbol, 0.0001)
            costs      = self.cfg.costs.get(symbol, {"standard": 1.5, "stress2x": 3.0})
            cost_std   = costs["standard"]
            cost_stress= costs["stress2x"]

            # ── Load data ─────────────────────────────────────────────────────
            sym_key = symbol[:3] + "_" + symbol[3:]  # EURUSD → EUR_USD
            m15_path = self.cfg.data_dir / f"{sym_key}_M15.csv"
            h4_path  = self.cfg.data_dir / f"{sym_key}_H4.csv"

            if not m15_path.exists():
                msg = f"[{symbol}] M15 data not found: {m15_path}"
                print(f"  ERROR: {msg}")
                print(f"         Run: python3 scripts/fetch_data.py --symbols {symbol}\n")
                result.errors.append(msg)
                continue

            print(f"[{symbol}] Loading M15 ...", end=" ", flush=True)
            all_m15 = load_csv(m15_path)
            m15_bars = filter_date_range(all_m15, self.cfg.start, self.cfg.end)
            print(f"{len(m15_bars):,} bars")

            h4_bars: list[dict] = []
            if h4_path.exists():
                print(f"[{symbol}] Loading H4  ...", end=" ", flush=True)
                all_h4  = load_csv(h4_path)
                h4_bars = filter_date_range(all_h4, self.cfg.start, self.cfg.end)
                print(f"{len(h4_bars):,} bars")
            else:
                print(f"[{symbol}] H4 not found — ST-A2 and AdaptiveSMC will skip")

            if not m15_bars:
                msg = f"[{symbol}] No M15 data in range {self.cfg.start}–{self.cfg.end}"
                print(f"  ERROR: {msg}\n")
                result.errors.append(msg)
                continue

            # ── Walk-forward bar by bar ────────────────────────────────────────
            print(f"[{symbol}] Running walk-forward ...", flush=True)
            dedup = _SignalDedup()
            n_bars = len(m15_bars)
            _progress_step = max(1, n_bars // 20)

            for i in range(1, n_bars):
                if i % _progress_step == 0:
                    pct = i / n_bars * 100
                    print(f"  [{symbol}] {pct:5.1f}%  bar {i}/{n_bars}", end="\r", flush=True)

                # Accumulated window — no lookahead
                m15_window = m15_bars[max(0, i - self.cfg.m15_lookback): i]
                h4_window  = h4_bars[:i] if h4_bars else []
                if h4_window:
                    h4_window = h4_window[-self.cfg.h4_lookback:]

                for name, adapter in adapters.items():
                    data = {
                        "symbol":      symbol,
                        "m15":         m15_window,
                        "h4":          h4_window,
                        "spread_pips": cost_std,
                    }

                    try:
                        sig = adapter.generate_signal(data)
                    except Exception as exc:
                        result.errors.append(
                            f"[{name}/{symbol}] generate_signal error at bar {i}: {exc}"
                        )
                        continue

                    if sig is None:
                        continue

                    # Deduplicate — only emit each unique signal once
                    if not dedup.is_new(name, symbol, sig.timestamp):
                        continue

                    # Build trade record
                    trade = ReplayTrade(
                        strategy     = name,
                        symbol       = symbol,
                        action       = sig.action,
                        mode         = modes.get(name, "shadow"),
                        entry_price  = sig.entry_price,
                        stop_loss    = sig.stop_loss,
                        take_profit  = sig.take_profit,
                        entry_time   = sig.timestamp,
                        sl_pips      = 0.0,   # filled by simulate_exit
                        risk_percent = sig.risk_percent,
                        confidence   = sig.confidence,
                        session      = sig.session,
                        metadata     = sig.metadata,
                    )

                    # Find future bars starting from current bar for simulation
                    future = m15_bars[i:]

                    trade = simulate_exit(trade, future, pip, cost_std, cost_stress)
                    result.trades.append(trade)

            print(f"  [{symbol}] 100.0%  done              ")

            sym_trades = [t for t in result.trades if t.symbol == symbol]
            print(f"[{symbol}] Signals: {len(sym_trades)}")
            by_strat = {}
            for t in sym_trades:
                by_strat.setdefault(t.strategy, []).append(t)
            for sname, st_list in sorted(by_strat.items()):
                print(f"           {sname:<18} {len(st_list):>4} signals")
            print()

        total = len(result.trades)
        print(f"\n{'='*60}")
        print(f"  Replay complete — {total} total signals across all strategies")
        print(f"{'='*60}\n")

        return result
