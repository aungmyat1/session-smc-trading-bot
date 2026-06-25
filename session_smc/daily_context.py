"""
D1 daily context module — TRIAL_ST_A2_D1_001.

Clean interface for the ST-A2 + D1 context A/B replay framework.
Extends daily_bias.py with structured liquidity levels and target classification.

Provides
--------
DailyContext       — structured dataclass (vs plain dict in daily_bias.py)
build_d1_context() — constructs DailyContext from H4 bars
apply_d1_gates()   — evaluates enabled gates, returns (pass_flag, rejection_reason)

Gate index
----------
Gate A  d1_bias_filter      D1 swing structure must not conflict with 4H+1H bias
Gate B  d1_location_filter  Session bar open must be in discount (long) / premium (short)
Gate C  d1_poi_filter       Architecture stub — reserved for TRIAL_ST_A2_D1_POI_001

Usage
-----
    ctx = build_d1_context(candles_4h, session_open_dt, price=candle["open"])
    if ctx is None:
        # insufficient daily history — skip D1 gates for this day
        ...
    ok, reason = apply_d1_gates(ctx, htf_bias, session_open_price=candle["open"], cfg=cfg)
    if not ok:
        continue   # D1 gate blocked the trade
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .daily_bias import (
    aggregate_to_daily,
    build_daily_context as _build_d2_ctx,
    classify_location,
)
from .swing_detector import swing_highs, swing_lows

Candle = dict
PIP = 0.0001
_UTC = timezone.utc


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class DailyContext:
    """
    Full D1 daily context for one session.

    Fields
    ------
    pdh / pdl          : previous calendar day's high / low
    daily_mid          : midpoint of PDH/PDL range
    daily_bias         : 'bullish' | 'bearish' | 'neutral'  (D1 swing structure)
    daily_location     : 'premium' | 'discount' | 'equilibrium'  (price vs PDH/PDL mid)
    daily_liquidity    : dict with recent swing highs/lows as liquidity levels
    daily_target       : 'draw_to_highs' | 'draw_to_lows' | 'none'
    daily_target_level : price of the next likely liquidity draw (or None)
    """
    pdh: float
    pdl: float
    daily_mid: float
    daily_bias: str
    daily_location: str
    daily_liquidity: dict
    daily_target: str
    daily_target_level: Optional[float]


# ── Builder ───────────────────────────────────────────────────────────────────

def build_d1_context(
    candles_4h: list[Candle],
    before_dt,
    price: Optional[float] = None,
    swing_n: int = 3,
    lookback_swings: int = 3,
) -> Optional[DailyContext]:
    """
    Build D1 context for a session starting at before_dt.

    Parameters
    ----------
    candles_4h     : H4 bars — used to build D1 candles internally
    before_dt      : UTC datetime of session open bar
    price          : current price for location / target classification.
                     If None, uses daily_mid.
    swing_n        : swing confirmation bars (default 3)
    lookback_swings: number of recent swing levels to retain

    Returns
    -------
    DailyContext, or None if there is insufficient daily history.

    No lookahead: only fully closed daily bars (date < before_dt.date()) are used.
    """
    ctx = _build_d2_ctx(candles_4h, before_dt, swing_n)
    if ctx is None:
        return None

    pdh = ctx["pdh"]
    pdl = ctx["pdl"]
    daily_mid = ctx["daily_mid"]
    structure = ctx["structure"]

    # Re-derive closed D1 bars for swing analysis
    def _parse(t) -> datetime:
        if isinstance(t, datetime):
            return t if t.tzinfo else t.replace(tzinfo=_UTC)
        return datetime.fromisoformat(str(t).replace("Z", "+00:00"))

    before = _parse(before_dt)
    cutoff = before.date().isoformat()
    closed = [d for d in aggregate_to_daily(candles_4h) if d["time"][:10] < cutoff]

    # Recent confirmed D1 swings as liquidity levels
    sh_idxs = swing_highs(closed, swing_n)
    sl_idxs = swing_lows(closed, swing_n)

    recent_shs = [
        {"price": closed[i]["high"], "date": closed[i]["time"][:10]}
        for i in sh_idxs[-lookback_swings:]
    ]
    recent_sls = [
        {"price": closed[i]["low"], "date": closed[i]["time"][:10]}
        for i in sl_idxs[-lookback_swings:]
    ]

    daily_liquidity = {
        "pdh": pdh,
        "pdl": pdl,
        "swing_highs": recent_shs,
        "swing_lows": recent_sls,
    }

    # Location of the provided price vs PDH/PDL midpoint
    ref_price = price if price is not None else daily_mid
    location = classify_location(ref_price, pdh, pdl)

    # Daily target — next likely draw in structure direction
    daily_target = "none"
    daily_target_level: Optional[float] = None

    if structure == "bullish" and recent_shs:
        # Draw to the last confirmed D1 swing high above current price
        candidates = [s for s in recent_shs if s["price"] > ref_price]
        if candidates:
            daily_target = "draw_to_highs"
            daily_target_level = min(candidates, key=lambda s: s["price"])["price"]
    elif structure == "bearish" and recent_sls:
        # Draw to the last confirmed D1 swing low below current price
        candidates = [s for s in recent_sls if s["price"] < ref_price]
        if candidates:
            daily_target = "draw_to_lows"
            daily_target_level = max(candidates, key=lambda s: s["price"])["price"]

    return DailyContext(
        pdh=pdh,
        pdl=pdl,
        daily_mid=daily_mid,
        daily_bias=structure,
        daily_location=location,
        daily_liquidity=daily_liquidity,
        daily_target=daily_target,
        daily_target_level=daily_target_level,
    )


# ── Gate evaluator ────────────────────────────────────────────────────────────

def apply_d1_gates(
    ctx: DailyContext,
    htf_bias: str,
    session_open_price: float,
    swept_level: Optional[float] = None,
    cfg: Optional[dict] = None,
) -> tuple[bool, str]:
    """
    Evaluate all enabled D1 gates for a potential trade.

    Parameters
    ----------
    ctx                : DailyContext for the current session's date
    htf_bias           : '4H+1H bias — 'bullish' | 'bearish'
    session_open_price : open price of the current killzone bar
    swept_level        : the swept session level (for Gate C / future POI gate)
    cfg                : gate enable flags (see below)

    Gate config keys (all bool, default True unless noted)
    -------------------------------------------------------
    d1_bias_filter       Gate A — D1 bias must agree with HTF bias
    d1_location_filter   Gate B — session bar open in discount/premium zone
    d1_poi_filter        Gate C — STUB, default False (TRIAL_ST_A2_D1_POI_001)
    d1_poi_pips          Gate C threshold, default 30.0

    Returns
    -------
    (True,  "PASS")    — all enabled gates pass, trade is allowed
    (False, reason)    — a gate blocked, reason describes which and why
    """
    c = cfg or {}

    # ── Gate A: D1 structure must not conflict with HTF bias ─────────────────
    if c.get("d1_bias_filter", True):
        ds = ctx.daily_bias
        if ds != "neutral" and ds != htf_bias:
            return False, f"gate_A_bias: d1={ds} vs htf={htf_bias}"

    # ── Gate B: price location must support trade direction ───────────────────
    if c.get("d1_location_filter", True):
        loc = classify_location(session_open_price, ctx.pdh, ctx.pdl)
        if htf_bias == "bullish" and loc == "premium":
            return False, "gate_B_location: bullish but price above D1 midpoint (premium)"
        if htf_bias == "bearish" and loc == "discount":
            return False, "gate_B_location: bearish but price below D1 midpoint (discount)"

    # ── Gate C: POI proximity — ARCHITECTURE STUB ─────────────────────────────
    # Reserved for TRIAL_ST_A2_D1_POI_001. Never enable in TRIAL_ST_A2_D1_001.
    # Setting d1_poi_filter=True here will trigger an assertion to prevent misuse.
    if c.get("d1_poi_filter", False):
        assert False, (
            "d1_poi_filter is reserved for TRIAL_ST_A2_D1_POI_001. "
            "Do not enable in TRIAL_ST_A2_D1_001."
        )

    return True, "PASS"
