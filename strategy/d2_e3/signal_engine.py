"""D2 E3 signal engine — streaming stateful version of the backtest logic.

Processes M15 bars in order, maintains per-symbol state across polls.
Mirrors optimize_d2_rules.py logic exactly (session 08-16, liq_or_rr target).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

PIP: dict[str, float] = {"EURUSD": 0.0001, "GBPUSD": 0.0001}
SL_BUFFER_PIPS: dict[str, float] = {"EURUSD": 2.0, "GBPUSD": 2.0}
_PIVOT_LB = 12  # bars for rolling swing H/L used in MSS check


@dataclass
class D2E3Params:
    session_start: int = 8  # UTC hour (inclusive)
    session_end: int = 16  # UTC hour (exclusive)
    confirm_bars: int = 12  # max bars after sweep to wait for MSS
    entry_wait_bars: int = 3  # max bars after MSS to wait for limit fill
    min_stop_pips: float = 2.0
    max_stop_pips: float = 25.0
    rr: float = 2.0  # fallback fixed RR when liq target < 1.2R
    cooldown_bars: int = 3
    max_hold_bars: int = 32  # 8 h at M15


@dataclass
class Signal:
    type: str  # setup_detected | mss_confirmed | entry_filled | trade_closed | setup_expired
    symbol: str
    direction: str  # long | short
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    exit_price: float = 0.0
    exit_reason: str = ""
    r: float = 0.0
    bar_time: str = ""
    detail: str = ""


def _bar_hour(bar: dict) -> int:
    t = bar["time"]
    if isinstance(t, str):
        return int(t[11:13])
    return t.hour


def _bar_time_str(bar: dict) -> str:
    t = bar["time"]
    return t if isinstance(t, str) else t.isoformat()


class D2E3Engine:
    """Stateful D2 E3 signal engine. One instance per symbol."""

    def __init__(self, symbol: str, params: Optional[D2E3Params] = None) -> None:
        self.symbol = symbol
        self.p = params or D2E3Params()
        self.pip = PIP[symbol]
        self.sl_buf = SL_BUFFER_PIPS[symbol] * self.pip

        # ── State (persists across polls) ────────────────────────────────
        self.pending: Optional[dict] = None
        self.open_trade: Optional[dict] = None
        self.cooldown_until_bar: int = -1
        self.last_bar_time: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────

    def process_bars(self, bars: list[dict]) -> list[Signal]:
        """Process all bars newer than last_bar_time. Returns list of signals."""
        ctx = _build_context(bars)
        new_start = self._find_new_start(bars)
        signals: list[Signal] = []
        for i in range(new_start, len(ctx)):
            sigs = self._step(i, ctx)
            signals.extend(sigs)
            self.last_bar_time = _bar_time_str(ctx[i])
        return signals

    def reset(self) -> None:
        self.pending = None
        self.open_trade = None
        self.cooldown_until_bar = -1
        self.last_bar_time = None

    # ── Internal ──────────────────────────────────────────────────────────

    def _find_new_start(self, bars: list[dict]) -> int:
        if not self.last_bar_time:
            return 0
        for i, b in enumerate(bars):
            if _bar_time_str(b) > self.last_bar_time:
                return i
        return len(bars)  # nothing new

    def _step(self, i: int, ctx: list[dict]) -> list[Signal]:
        b = ctx[i]
        h, lo, c = b["high"], b["low"], b["close"]
        t = _bar_time_str(b)
        pdh, pdl = b["pdh"], b["pdl"]
        phl, pll = b["phl"], b["pll"]
        sigs: list[Signal] = []

        # ── Manage open trade ─────────────────────────────────────────────
        if self.open_trade:
            ot = self.open_trade
            bars_held = i - ot["entry_bar_i"]
            exit_price = exit_reason = None

            if ot["direction"] == "long":
                if lo <= ot["stop"]:
                    exit_price, exit_reason = ot["stop"], "SL"
                elif h >= ot["target"]:
                    exit_price, exit_reason = ot["target"], "TP"
            else:
                if h >= ot["stop"]:
                    exit_price, exit_reason = ot["stop"], "SL"
                elif lo <= ot["target"]:
                    exit_price, exit_reason = ot["target"], "TP"

            if exit_price is None and bars_held >= self.p.max_hold_bars:
                exit_price, exit_reason = c, "TIME"

            if exit_price is not None:
                risk = abs(ot["entry"] - ot["stop"])
                r = (
                    (exit_price - ot["entry"]) / risk
                    if ot["direction"] == "long"
                    else (ot["entry"] - exit_price) / risk
                )
                sigs.append(
                    Signal(
                        type="trade_closed",
                        symbol=self.symbol,
                        direction=ot["direction"],
                        entry=ot["entry"],
                        stop=ot["stop"],
                        target=ot["target"],
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                        r=round(r, 3),
                        bar_time=t,
                    )
                )
                self.open_trade = None
                self.pending = None
                self.cooldown_until_bar = i + self.p.cooldown_bars
            return sigs

        # ── Manage pending setup ──────────────────────────────────────────
        if self.pending:
            pd = self.pending
            age = i - pd["sweep_bar_i"]

            if age > self.p.confirm_bars + self.p.entry_wait_bars + 2:
                sigs.append(
                    Signal(
                        type="setup_expired",
                        symbol=self.symbol,
                        direction=pd["direction"],
                        bar_time=t,
                    )
                )
                self.pending = None
                return sigs

            if not pd["confirmed"]:
                if age <= self.p.confirm_bars:
                    mss = False
                    if pd["direction"] == "short" and not math.isnan(pll):
                        mss = c < pll
                    elif pd["direction"] == "long" and not math.isnan(phl):
                        mss = c > phl
                    if mss:
                        entry = (h + lo) / 2.0
                        stop = self._stop(pd, entry)
                        pd.update(
                            confirmed=True,
                            entry=entry,
                            fill_deadline_bar=i + self.p.entry_wait_bars,
                        )
                        sigs.append(
                            Signal(
                                type="mss_confirmed",
                                symbol=self.symbol,
                                direction=pd["direction"],
                                entry=entry,
                                stop=stop,
                                target=self._target(pd, entry, stop),
                                bar_time=t,
                            )
                        )
                else:
                    sigs.append(
                        Signal(
                            type="setup_expired",
                            symbol=self.symbol,
                            direction=pd["direction"],
                            bar_time=t,
                            detail="no_mss",
                        )
                    )
                    self.pending = None
            else:
                # Waiting for limit fill
                if i <= pd["fill_deadline_bar"]:
                    entry = pd["entry"]
                    filled = h >= entry if pd["direction"] == "short" else lo <= entry
                    if filled:
                        ot = self._make_trade(pd, i)
                        if ot:
                            self.open_trade = ot
                            sigs.append(
                                Signal(
                                    type="entry_filled",
                                    symbol=self.symbol,
                                    direction=ot["direction"],
                                    entry=ot["entry"],
                                    stop=ot["stop"],
                                    target=ot["target"],
                                    bar_time=t,
                                )
                            )
                        else:
                            self.pending = None
                else:
                    sigs.append(
                        Signal(
                            type="setup_expired",
                            symbol=self.symbol,
                            direction=pd["direction"],
                            bar_time=t,
                            detail="fill_expired",
                        )
                    )
                    self.pending = None
            return sigs

        # ── Scan for sweep ────────────────────────────────────────────────
        if i < self.cooldown_until_bar:
            return sigs
        if not (self.p.session_start <= _bar_hour(b) < self.p.session_end):
            return sigs
        if math.isnan(pdh) or math.isnan(pdl) or math.isnan(phl) or math.isnan(pll):
            return sigs

        if h > pdh and c < pdh:
            direction, extreme = "short", h
        elif lo < pdl and c > pdl:
            direction, extreme = "long", lo
        else:
            return sigs

        self.pending = {
            "symbol": self.symbol,
            "direction": direction,
            "sweep_bar_i": i,
            "sweep_time": t,
            "sweep_high": h,
            "sweep_low": lo,
            "pdh": pdh,
            "pdl": pdl,
            "extreme": extreme,
            "confirmed": False,
        }
        lvl = "PDH" if direction == "short" else "PDL"
        sigs.append(
            Signal(
                type="setup_detected",
                symbol=self.symbol,
                direction=direction,
                bar_time=t,
                detail=f"{lvl} sweep at {extreme:.5f}",
            )
        )
        return sigs

    def _stop(self, pd: dict, entry: float) -> float:
        if pd["direction"] == "short":
            return pd["sweep_high"] + self.sl_buf
        return pd["sweep_low"] - self.sl_buf

    def _target(self, pd: dict, entry: float, stop: float) -> float:
        risk = abs(entry - stop)
        if pd["direction"] == "short":
            liq = pd["pdl"]
            if liq < entry and (entry - liq) / risk >= 1.2:
                return liq
            return entry - self.p.rr * risk
        else:
            liq = pd["pdh"]
            if liq > entry and (liq - entry) / risk >= 1.2:
                return liq
            return entry + self.p.rr * risk

    def _make_trade(self, pd: dict, bar_i: int) -> Optional[dict]:
        entry = pd["entry"]
        stop = self._stop(pd, entry)
        risk = abs(entry - stop)
        if risk <= 0:
            return None
        risk_pips = risk / self.pip
        if not (self.p.min_stop_pips <= risk_pips <= self.p.max_stop_pips):
            return None
        return {
            "direction": pd["direction"],
            "entry": float(entry),
            "stop": float(stop),
            "target": float(self._target(pd, entry, stop)),
            "entry_bar_i": bar_i,
        }


# ── Context builder (PDH/PDL + rolling pivot H/L) ────────────────────────────


def _build_context(bars: list[dict]) -> list[dict]:
    """Add pdh, pdl, phl (rolling pivot high), pll (rolling pivot low) to each bar."""
    _n = len(bars)

    # Day → {high, low} accumulated
    day_hl: dict[str, list[float]] = {}
    day_keys: list[str] = []
    for b in bars:
        t = b["time"]
        d = t[:10] if isinstance(t, str) else t.strftime("%Y-%m-%d")
        if d not in day_hl:
            day_hl[d] = [float("-inf"), float("inf")]  # [high, low]
            day_keys.append(d)
        day_hl[d][0] = max(day_hl[d][0], b["high"])
        day_hl[d][1] = min(day_hl[d][1], b["low"])

    # Map each bar's date → previous day's H/L
    day_set = sorted(set(day_keys))
    prev_map: dict[str, tuple] = {}
    for i, d in enumerate(day_set):
        if i > 0:
            pd_key = day_set[i - 1]
            prev_map[d] = (day_hl[pd_key][0], day_hl[pd_key][1])
        else:
            prev_map[d] = (float("nan"), float("nan"))

    result = []
    for i, b in enumerate(bars):
        t = b["time"]
        d = t[:10] if isinstance(t, str) else t.strftime("%Y-%m-%d")
        pdh, pdl = prev_map.get(d, (float("nan"), float("nan")))

        # Rolling pivot: max high / min low of prior _PIVOT_LB bars
        lo = max(0, i - _PIVOT_LB)
        if i >= 3:
            phl = max(bars[j]["high"] for j in range(lo, i))
            pll = min(bars[j]["low"] for j in range(lo, i))
        else:
            phl = pll = float("nan")

        result.append({**b, "pdh": pdh, "pdl": pdl, "phl": phl, "pll": pll})

    return result
