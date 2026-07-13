"""
SMC-LSS_v0 — shared setup detector for experiments E1/E2/E3/combined.

Not an entry model itself. Factors out the common, order-independent
chain (liquidity sweep -> CHoCH -> inducement -> displacement -> supply/
demand shift + HTF context) so E1/E2/E3 differ only in their trigger
condition and SL/TP construction, not in duplicated event-detection code.

No-lookahead discipline: `find_setups` makes a single forward pass over
`m5_candles`. At candle index i, only candles[0:i+1] and the sweep pool
built from indices < i are consulted. `SupplyDemandShiftEvent.pullback_index`
(from strategies.smc_lss.entries.detect_supply_demand_shift) is the first
bar at or after which the setup becomes actionable — experiments must not
enter before that bar.
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from strategies.smc_lss.context import SessionContext, build_session_context
from strategies.smc_lss.displacement import DisplacementResult, detect_displacement, wilder_atr
from strategies.smc_lss.entries import SupplyDemandShiftEvent, detect_supply_demand_shift
from strategies.smc_lss.exits import SMCTrade, build_trade_record, risk_reward_target, simulate_trade
from strategies.smc_lss.liquidity import LiquiditySweepEvent, detect_liquidity_sweep
from strategies.smc_lss.structure import StructureBreakEvent, apply_inducement, detect_choch

DEFAULT_RR = 2.0
DEFAULT_SL_BUFFER_ATR = 0.1
DEFAULT_MAX_BARS = 96

DEFAULT_CONFIG = {
    "swing_lookback": 10,
    "sweep_atr_threshold": 0.25,
    "structure_lookback": 10,
    "inducement_window": 3,
    "displacement_body_atr": 1.5,
    "atr_period": 14,
}


@dataclass
class SMCSetup:
    symbol: str
    direction: str                       # 'long' | 'short'
    sweep: LiquiditySweepEvent
    choch: StructureBreakEvent
    displacement_index: int
    displacement: DisplacementResult
    shift: SupplyDemandShiftEvent
    context: SessionContext


def _date_of(ts: object) -> str:
    return str(ts)[:10]


def build_daily_context_map(
    d1_candles: list[dict], h1_candles: list[dict], cfg: dict
) -> "dict[str, SessionContext]":
    """One SessionContext per D1 candle date, built only from data strictly
    before that day (previous closed D1 candles + H1 candles preceding the
    day's D1 open timestamp)."""
    context_by_date: "dict[str, SessionContext]" = {}
    h1_cursor = 0
    for idx, d1 in enumerate(d1_candles):
        date_str = _date_of(d1["timestamp"])
        d1_ts = str(d1["timestamp"])
        while h1_cursor < len(h1_candles) and str(h1_candles[h1_cursor]["timestamp"]) < d1_ts:
            h1_cursor += 1
        ctx = build_session_context(
            d1_candles[:idx],
            float(d1["open"]),
            h1_candles[:h1_cursor],
            atr_period=cfg["atr_period"],
            displacement_body_atr=cfg["displacement_body_atr"],
        )
        if ctx is not None:
            context_by_date[date_str] = ctx
    return context_by_date


def find_setups(
    m5_candles: list[dict],
    d1_candles: list[dict],
    h1_candles: list[dict],
    *,
    symbol: str,
    cfg: "dict | None" = None,
) -> list[SMCSetup]:
    cfg = {**DEFAULT_CONFIG, **(cfg or {})}
    swing_lookback = cfg["swing_lookback"]
    sweep_atr_threshold = cfg["sweep_atr_threshold"]
    structure_lookback = cfg["structure_lookback"]
    inducement_window = cfg["inducement_window"]
    displacement_body_atr = cfg["displacement_body_atr"]
    atr_period = cfg["atr_period"]

    atrs = wilder_atr(m5_candles, period=atr_period)
    context_by_date = build_daily_context_map(d1_candles, h1_candles, cfg)

    sweep_pool: "dict[str, list[int]]" = {"long": [], "short": []}
    sweep_events_by_index: "dict[int, LiquiditySweepEvent]" = {}
    setups: list[SMCSetup] = []

    min_index = max(2 * structure_lookback, swing_lookback, atr_period + 1)

    for i in range(min_index, len(m5_candles)):
        sweep = detect_liquidity_sweep(
            m5_candles, i, symbol=symbol, atr=atrs[i],
            swing_lookback=swing_lookback, sweep_atr_threshold=sweep_atr_threshold,
        )
        if sweep is not None:
            sweep_pool[sweep.direction].append(i)
            sweep_events_by_index[i] = sweep

        choch = detect_choch(m5_candles, i, symbol=symbol, structure_lookback=structure_lookback)
        if choch is None:
            continue

        choch = apply_inducement(
            choch, sweep_pool[choch.direction], i, inducement_window=inducement_window
        )
        if not choch.inducement or choch.inducement_sweep_index is None:
            continue

        sweep_event = sweep_events_by_index.get(choch.inducement_sweep_index)
        if sweep_event is None:
            continue

        displacement = detect_displacement(
            m5_candles[i], atrs[i], choch.direction, body_atr_mult=displacement_body_atr
        )
        if not displacement.detected:
            continue

        shift = detect_supply_demand_shift(
            m5_candles,
            symbol=symbol,
            sweep=sweep_event,
            displacement_index=i,
            structure_level=choch.broken_level,
            direction=choch.direction,
            as_of_index=len(m5_candles) - 1,
        )
        if shift is None:
            continue

        context = context_by_date.get(_date_of(m5_candles[shift.pullback_index]["timestamp"]))
        if context is None:
            continue

        setups.append(SMCSetup(
            symbol=symbol,
            direction=choch.direction,
            sweep=sweep_event,
            choch=choch,
            displacement_index=i,
            displacement=displacement,
            shift=shift,
            context=context,
        ))

    return setups


def sweep_extreme(setup: SMCSetup) -> float:
    """Actual wick extreme of the inducement sweep (swept_level is the
    broken swing level, not the wick tip; penetration recovers the wick)."""
    if setup.direction == "long":
        return setup.sweep.swept_level - setup.sweep.penetration
    return setup.sweep.swept_level + setup.sweep.penetration


def build_setup_trade(
    setup: SMCSetup,
    m5_candles: list[dict],
    branch: str,
    *,
    spread_price_units: float = 0.0,
    rr: float = DEFAULT_RR,
    sl_buffer_atr: float = DEFAULT_SL_BUFFER_ATR,
    max_bars: int = DEFAULT_MAX_BARS,
) -> "SMCTrade | None":
    """Shared entry/SL/TP construction for E1/E2/E3/combined: entry at the
    close of the FVG-pullback confirmation bar, SL beyond the sweep wick
    extreme plus a fixed ATR buffer, TP at a fixed reward-risk ratio (no
    parameter sweep — see module docstrings)."""
    entry_index = setup.shift.pullback_index
    if entry_index + 1 >= len(m5_candles):
        return None

    entry_price = float(m5_candles[entry_index]["close"])
    buffer = sl_buffer_atr * setup.sweep.atr
    extreme = sweep_extreme(setup)
    sl = extreme - buffer if setup.direction == "long" else extreme + buffer
    risk = abs(entry_price - sl)
    if risk == 0:
        return None
    tp = risk_reward_target(entry_price, sl, setup.direction, rr)

    sim = simulate_trade(
        entry_price, sl, tp, setup.direction,
        m5_candles[entry_index + 1:], max_bars=max_bars,
    )
    return build_trade_record(
        trade_id=str(uuid.uuid4()),
        symbol=setup.symbol,
        branch=branch,
        entry_time=m5_candles[entry_index].get("timestamp"),
        entry_price=entry_price,
        direction=setup.direction,
        sim=sim,
        spread_price_units=spread_price_units,
        risk_price_units=risk,
    )
