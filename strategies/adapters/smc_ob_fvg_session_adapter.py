"""
SMC Order Block + FVG Session adapter.

Detection engine uses joshyattridge/smart-money-concepts (smartmoneyconcepts package):
  - Swing highs/lows → BOS/CHoCH via smc.swing_highs_lows + smc.bos_choch
  - Order blocks with mitigation tracking via smc.ob
  - Fair value gaps with mitigation tracking via smc.fvg

Entry logic:
  1. Most recent BOS establishes direction (bullish / bearish)
  2. Find latest unmitigated OB in that direction
  3. Find latest unmitigated FVG in that direction, within 1 ATR of the OB
  4. If current price is inside the OB zone → signal (market order, kill-zone only)

Input schema:
    {
        "symbol": str,
        "m15": list[dict],     # required; accepts "time" or "timestamp"
        "spread_pips": float,  # optional
        "config": dict,        # optional overrides
    }
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Optional

import numpy as np
import pandas as pd
from smartmoneyconcepts import smc

from core.base_strategy import BaseStrategy
from shared.strategy_api import Signal

_PIP: dict[str, float] = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "XAUUSD": 0.1,
}

DEFAULT_CONFIG: dict = {
    "risk_per_trade": 0.01,
    "rr_ratio": 3.0,
    "atr_period": 14,
    "swing_length": 10,
    "fvg_zone_atr_mult": 1.0,    # max gap between OB and FVG (in ATR units)
    "stop_buffer_pips": 5.0,
    "max_spread_pips": 3.0,
    "london_start": "07:00",
    "london_end": "11:00",
    "ny_start": "12:00",
    "ny_end": "16:00",
    "max_daily_trades": 2,
    "use_equity_bagging": True,
    "min_bars": 80,
}


def _parse_hhmm(value: str) -> time:
    h, m = str(value).split(":", 1)
    return time(int(h), int(m))


def _normalize_frame(candles: list[dict]) -> pd.DataFrame:
    rows = []
    for c in candles:
        ts = c.get("timestamp", c.get("time"))
        if ts is None:
            continue
        rows.append({
            "timestamp": ts,
            "open":   float(c["open"]),
            "high":   float(c["high"]),
            "low":    float(c["low"]),
            "close":  float(c["close"]),
            "volume": float(c.get("volume", c.get("tickVolume", 0))),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame.from_records(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def _atr(df: pd.DataFrame, period: int) -> float:
    prev = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    series = tr.rolling(period, min_periods=period).mean()
    val = series.iloc[-1]
    return float(val) if pd.notna(val) else 0.0


def _in_window(ts: pd.Timestamp, start_text: str, end_text: str) -> bool:
    cur = ts.time()
    return _parse_hhmm(start_text) <= cur < _parse_hhmm(end_text)


def _session(ts: pd.Timestamp, cfg: dict) -> Optional[str]:
    if _in_window(ts, cfg["london_start"], cfg["london_end"]):
        return "london"
    if _in_window(ts, cfg["ny_start"], cfg["ny_end"]):
        return "new_york"
    return None


def _zone_gap(low_a: float, high_a: float, low_b: float, high_b: float) -> float:
    """Distance between two zones (0 if they overlap)."""
    if high_a < low_b:
        return low_b - high_a
    if high_b < low_a:
        return low_a - high_b
    return 0.0


class SMCOrderBlockFVGSessionAdapter(BaseStrategy):
    @property
    def name(self) -> str:
        return "SMCOrderBlockFVGSession"

    def generate_signal(self, data: dict) -> Optional[Signal]:
        symbol  = str(data.get("symbol", "")).strip()
        candles = data.get("m15", [])
        cfg     = {**DEFAULT_CONFIG, **(data.get("config") or {})}

        if not symbol or len(candles) < int(cfg["min_bars"]):
            return None

        spread_pips = float(data.get("spread_pips", 0.0) or 0.0)
        if spread_pips > float(cfg["max_spread_pips"]):
            return None

        df = _normalize_frame(candles)
        if df.empty or len(df) < int(cfg["min_bars"]):
            return None

        # ── Session gate ────────────────────────────────────────────────────
        session = _session(df["timestamp"].iloc[-1], cfg)
        if session is None:
            return None

        # ── ATR ─────────────────────────────────────────────────────────────
        atr_val = _atr(df, int(cfg["atr_period"]))
        if atr_val <= 0:
            return None

        pip   = _PIP.get(symbol, 0.0001)
        price = float(df["close"].iloc[-1])

        # ── SMC analysis (smc package) ───────────────────────────────────────
        ohlc = df[["open", "high", "low", "close", "volume"]].copy()

        swing = smc.swing_highs_lows(ohlc, swing_length=int(cfg["swing_length"]))

        bos_df = smc.bos_choch(ohlc, swing, close_break=True)
        # Most recent BOS (not CHoCH — we want continuation, not reversal)
        bos_rows = bos_df[bos_df["BOS"].notna() & (bos_df["BOS"] != 0)]
        if bos_rows.empty:
            return None
        latest_bos = bos_rows.iloc[-1]
        direction = "bullish" if latest_bos["BOS"] == 1 else "bearish"
        bos_index = int(bos_rows.index[-1])

        # ── Order block ──────────────────────────────────────────────────────
        ob_df = smc.ob(ohlc, swing, close_mitigation=False)
        ob_side = 1 if direction == "bullish" else -1
        # Active = OB in our direction, not yet mitigated (MitigatedIndex == 0)
        active_obs = ob_df[
            ob_df["OB"].notna()
            & (ob_df["OB"] == ob_side)
            & (ob_df["MitigatedIndex"] == 0)
            & (ob_df.index >= bos_index)
        ]
        if active_obs.empty:
            # Fallback: any active OB in direction regardless of BOS index
            active_obs = ob_df[
                ob_df["OB"].notna()
                & (ob_df["OB"] == ob_side)
                & (ob_df["MitigatedIndex"] == 0)
            ]
        if active_obs.empty:
            return None

        latest_ob = active_obs.iloc[-1]
        ob_top    = float(latest_ob["Top"])
        ob_bottom = float(latest_ob["Bottom"])
        if ob_top <= ob_bottom:
            ob_top, ob_bottom = ob_bottom, ob_top  # ensure correct orientation

        # ── Check price is inside the OB zone ───────────────────────────────
        buffer = float(cfg["stop_buffer_pips"]) * pip
        if direction == "bullish":
            in_zone = ob_bottom - buffer <= price <= ob_top + buffer
        else:
            in_zone = ob_bottom - buffer <= price <= ob_top + buffer
        if not in_zone:
            return None

        # ── Fair value gap ───────────────────────────────────────────────────
        fvg_df = smc.fvg(ohlc, join_consecutive=False)
        fvg_side = 1 if direction == "bullish" else -1
        active_fvgs = fvg_df[
            fvg_df["FVG"].notna()
            & (fvg_df["FVG"] == fvg_side)
            & (fvg_df["MitigatedIndex"] == 0)
        ]
        if active_fvgs.empty:
            return None

        # Find the FVG closest (smallest gap) to the OB zone
        def zone_gap_to_ob(row: pd.Series) -> float:
            return _zone_gap(float(row["Bottom"]), float(row["Top"]), ob_bottom, ob_top)

        gaps = active_fvgs.apply(zone_gap_to_ob, axis=1)
        min_gap_idx = gaps.idxmin()
        best_fvg_gap = float(gaps.loc[min_gap_idx])

        if best_fvg_gap > atr_val * float(cfg["fvg_zone_atr_mult"]):
            return None

        fvg_top    = float(active_fvgs.loc[min_gap_idx, "Top"])
        fvg_bottom = float(active_fvgs.loc[min_gap_idx, "Bottom"])

        # ── Confluence zone & levels ─────────────────────────────────────────
        zone_high = max(ob_top, fvg_top)
        zone_low  = min(ob_bottom, fvg_bottom)
        rr        = float(cfg["rr_ratio"])

        if direction == "bullish":
            stop_loss   = zone_low - buffer
            risk        = price - stop_loss
            if risk <= 0:
                return None
            take_profit = price + risk * rr
            action      = "BUY"
        else:
            stop_loss   = zone_high + buffer
            risk        = stop_loss - price
            if risk <= 0:
                return None
            take_profit = price - risk * rr
            action      = "SELL"

        # Asian range for context
        today = df["timestamp"].iloc[-1].date()
        asian = df[
            (df["timestamp"].dt.date == today)
            & (df["timestamp"].dt.hour < 8)
        ]

        return Signal(
            timestamp=datetime.now(timezone.utc).isoformat(),
            strategy_name=self.name,
            symbol=symbol,
            action=action,
            order_type="MARKET",
            entry_price=price,
            stop_loss=float(stop_loss),
            take_profit=float(take_profit),
            risk_percent=float(cfg["risk_per_trade"]) * 100.0,
            confidence=min(1.0, rr / 3.0),
            metadata={
                "session":             session,
                "reason":              "ob_fvg_bos_confluence",
                "structure_direction": direction,
                "bos_index":           bos_index,
                "ob_top":              ob_top,
                "ob_bottom":           ob_bottom,
                "fvg_top":             fvg_top,
                "fvg_bottom":          fvg_bottom,
                "fvg_gap_to_ob":       round(best_fvg_gap / pip, 2),
                "risk_pips":           round(risk / pip, 2),
                "reward_pips":         round(abs(take_profit - price) / pip, 2),
                "rr":                  rr,
                "atr_pips":            round(atr_val / pip, 2),
                "asian_high":          float(asian["high"].max()) if not asian.empty else None,
                "asian_low":           float(asian["low"].min()) if not asian.empty else None,
                "spread_pips":         spread_pips,
                "use_equity_bagging":  bool(cfg["use_equity_bagging"]),
                "max_daily_trades":    int(cfg["max_daily_trades"]),
            },
        )
