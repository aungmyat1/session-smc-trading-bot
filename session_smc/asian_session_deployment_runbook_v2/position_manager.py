"""
smc_bot/position_manager.py
Session-aware in-position management for the asian_session signal path.

Rules per session type:
  SWEEP / RANGE : close first_close_pct (75%) at opposite box edge → SL to BE
  TREND / OVERLAP: close 75% at 4R → SL to BE → trail remainder at 1×ATR

State persisted in data/position_state.json so bot survives restarts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

STATE_FILE = Path("data/position_state.json")


# ─────────────────────────────────────────────────────────────────────────────
# State persistence helpers
# ─────────────────────────────────────────────────────────────────────────────


def load_state() -> dict:
    """Load position state from disk. Returns {} if file missing."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error("Failed to load position state: %s — starting fresh", e)
        return {}


def save_state(state: dict) -> None:
    """Persist position state to disk atomically."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(STATE_FILE)


def register_position(
    position_id: str,
    signal,  # SessionSignal
    lots: float,
    state: dict,
) -> None:
    """
    Store position metadata after a new trade is placed.
    Merges into in-memory state dict (caller must save_state afterwards).
    """
    state[position_id] = {
        "instrument": signal.instrument,
        "session": signal.session,
        "setup": signal.setup,
        "side": signal.side,
        "entry": signal.entry,
        "sl": signal.sl,
        "tp": signal.tp,
        "box_high": signal.box_high,
        "box_low": signal.box_low,
        "lots": lots,
        "mgmt": signal.mgmt,
        "first_close_done": False,
        "opened_at": datetime.now(timezone.utc).isoformat(),
    }
    log.info(
        "Registered positionId=%s [%s/%s %s]",
        position_id,
        signal.instrument,
        signal.session,
        signal.setup,
    )


def purge_closed_positions(state: dict, open_position_ids: list[str]) -> dict:
    """
    Remove any position from state that no longer appears in MetaAPI open positions.
    Returns updated state dict.
    """
    stale = [pid for pid in state if pid not in open_position_ids]
    for pid in stale:
        log.info("Purging closed position %s from state", pid)
        del state[pid]
    return state


# ─────────────────────────────────────────────────────────────────────────────
# ATR helper (used for trailing stop)
# ─────────────────────────────────────────────────────────────────────────────


def _calc_atr(df_1h: pd.DataFrame, period: int = 14) -> float:
    high_low = df_1h["high"] - df_1h["low"]
    high_close = (df_1h["high"] - df_1h["close"].shift()).abs()
    low_close = (df_1h["low"] - df_1h["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return float(atr)


# ─────────────────────────────────────────────────────────────────────────────
# Core management function — called each run_cycle
# ─────────────────────────────────────────────────────────────────────────────


async def manage_positions(
    executor,  # MetaApiExecutor instance
    data: dict,  # {'EURUSD': {'df_1h': pd.DataFrame}, ...}
    state: dict,  # in-memory state loaded from disk
    cfg: dict,
) -> None:
    """
    Iterate all tracked positions and apply session-specific management rules.
    Mutates `state` in place; caller must save_state() after this returns.
    """
    if not state:
        return

    open_positions = await executor.get_open_positions()
    open_ids = [p.get("id") for p in open_positions]

    # Purge any closed positions first
    purge_closed_positions(state, open_ids)

    for position_id, pos in list(state.items()):
        if position_id not in open_ids:
            continue  # already purged or closed between iterations

        instrument = pos["instrument"]
        side = pos["side"]
        entry = pos["entry"]
        sl = pos["sl"]
        box_high = pos["box_high"]
        box_low = pos["box_low"]
        lots = pos["lots"]
        mgmt = pos["mgmt"]
        setup = pos["setup"]
        first_done = pos["first_close_done"]

        # ── Current price ─────────────────────────────────────────────────
        try:
            price_info = await executor.get_current_price(instrument)
        except Exception as e:
            log.error("[%s] Failed to get price: %s", instrument, e)
            continue

        mid = price_info["mid"]

        # ── R distance ────────────────────────────────────────────────────
        sl_dist = abs(entry - sl)
        if sl_dist == 0:
            continue

        r = (mid - entry) / sl_dist if side == "long" else (entry - mid) / sl_dist

        log.debug(
            "[%s/%s] posId=%s side=%s mid=%.5f entry=%.5f r=%.2f first_done=%s",
            instrument,
            setup,
            position_id,
            side,
            mid,
            entry,
            r,
            first_done,
        )

        # ── ATR for trailing stop ─────────────────────────────────────────
        df_1h = data.get(instrument, {}).get("df_1h")
        atr = _calc_atr(df_1h) if df_1h is not None else sl_dist

        first_close_pct = mgmt.get("first_close_pct", 0.75)
        first_close_target = mgmt.get("first_close_target", "opposite_box_edge")
        trail_remainder = mgmt.get("trail_remainder", False)

        # ─────────────────────────────────────────────────────────────────
        # SWEEP / RANGE : close 75% at opposite box edge → BE
        # ─────────────────────────────────────────────────────────────────
        if setup in ("sweep", "range") and not first_done:
            target_reached = False

            if side == "long" and mid >= box_high:
                target_reached = True
                log.info(
                    "[%s] SWEEP/RANGE long: price %.5f reached box_high %.5f — partial close",
                    instrument,
                    mid,
                    box_high,
                )
            elif side == "short" and mid <= box_low:
                target_reached = True
                log.info(
                    "[%s] SWEEP/RANGE short: price %.5f reached box_low %.5f — partial close",
                    instrument,
                    mid,
                    box_low,
                )

            if target_reached:
                partial_lots = round(lots * first_close_pct, 2)
                try:
                    await executor.place_reduce_only(
                        position_id,
                        partial_lots,
                        comment=f"first_close_{setup}",
                    )
                    await executor.set_sl(position_id, entry)  # SL → BE
                    state[position_id]["first_close_done"] = True
                    state[position_id]["sl"] = entry
                    log.info(
                        "[%s] First close done (%.2f lots) SL→BE=%.5f",
                        instrument,
                        partial_lots,
                        entry,
                    )
                except Exception as e:
                    log.error("[%s] First close failed: %s", instrument, e)

        # ─────────────────────────────────────────────────────────────────
        # TREND / OVERLAP : close 75% at 4R → BE → trail remainder
        # ─────────────────────────────────────────────────────────────────
        elif setup in ("trend",) and not first_done:
            trend_r_target = cfg.get("asian", {}).get("trend_first_close_r", 4.0)

            if first_close_target == "4R":
                trend_r_target = 4.0
            elif first_close_target == "opposite_box_edge":
                # recalculate dynamically
                trend_r_target = (
                    (box_high - entry) / sl_dist
                    if side == "long"
                    else (entry - box_low) / sl_dist
                )

            if r >= trend_r_target:
                partial_lots = round(lots * first_close_pct, 2)
                try:
                    await executor.place_reduce_only(
                        position_id,
                        partial_lots,
                        comment="first_close_trend",
                    )
                    await executor.set_sl(position_id, entry)  # SL → BE
                    state[position_id]["first_close_done"] = True
                    state[position_id]["sl"] = entry
                    log.info(
                        "[%s] Trend first close at %.1fR (%.2f lots) SL→BE=%.5f",
                        instrument,
                        r,
                        partial_lots,
                        entry,
                    )
                except Exception as e:
                    log.error("[%s] Trend first close failed: %s", instrument, e)

        # ─────────────────────────────────────────────────────────────────
        # Trailing stop — applies to overlap/trend remainder after first close
        # ─────────────────────────────────────────────────────────────────
        if first_done and trail_remainder:
            current_sl = state[position_id]["sl"]

            if side == "long":
                trail_sl = mid - atr
                if (
                    trail_sl > current_sl and trail_sl > entry
                ):  # only tighten, stay above BE
                    try:
                        await executor.set_sl(position_id, trail_sl)
                        state[position_id]["sl"] = trail_sl
                        log.info(
                            "[%s] Trail SL long: %.5f → %.5f (price=%.5f ATR=%.5f)",
                            instrument,
                            current_sl,
                            trail_sl,
                            mid,
                            atr,
                        )
                    except Exception as e:
                        log.error("[%s] Trail SL failed: %s", instrument, e)

            elif side == "short":
                trail_sl = mid + atr
                if (
                    trail_sl < current_sl and trail_sl < entry
                ):  # only tighten, stay below BE
                    try:
                        await executor.set_sl(position_id, trail_sl)
                        state[position_id]["sl"] = trail_sl
                        log.info(
                            "[%s] Trail SL short: %.5f → %.5f (price=%.5f ATR=%.5f)",
                            instrument,
                            current_sl,
                            trail_sl,
                            mid,
                            atr,
                        )
                    except Exception as e:
                        log.error("[%s] Trail SL failed: %s", instrument, e)
