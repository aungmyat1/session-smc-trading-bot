"""
Research Database Builder — batch feature extraction from processed OHLCV.

Produces 7 feature layers in research_db/:
  Stage 1  candles/       — SYMBOL_TF.parquet (copy from data/processed/)
  Stage 2  sessions/      — SYMBOL_sessions.parquet (London + NY per day)
  Stage 3  asian_ranges/  — SYMBOL_asian.parquet (Asian range per day)
  Stage 4  swings/        — SYMBOL_{H4,M15}_swings.parquet (SH/SL with HH/HL/LH/LL)
  Stage 5  structure/     — SYMBOL_{H4,M15}_structure.parquet (BOS/CHoCH events)
  Stage 6  liquidity/     — SYMBOL_sweeps.parquet (Asian range sweeps in killzone)
  Stage 7  fvgs/          — SYMBOL_M15_fvgs.parquet (3-bar FVG with fill status)

Usage:
    python3 scripts/build_research_db.py --symbols EURUSD
    python3 scripts/build_research_db.py --symbols EURUSD --start 2024-01-01 --end 2024-12-31
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA_PROC = ROOT / "data" / "processed"
RDB       = ROOT / "research_db"
PIP       = 0.0001
_UTC      = timezone.utc

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("build_rdb")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_utc(t) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def _load(symbol: str, tf: str) -> list[dict]:
    path = DATA_PROC / symbol / f"{tf}.parquet"
    if not path.exists():
        log.error("Missing %s — run build_timeframes.py first", path)
        return []
    df = pd.read_parquet(path, columns=["timestamp_utc", "open", "high", "low", "close"])
    df["time"] = pd.to_datetime(df["timestamp_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df[["time", "open", "high", "low", "close"]].sort_values("time").to_dict("records")


def _filter(bars: list[dict], start: str | None, end: str | None) -> list[dict]:
    if start:
        s = start if "T" in start else start + "T00:00:00Z"
        bars = [b for b in bars if b["time"] >= s]
    if end:
        e = end if "T" in end else end + "T23:59:59Z"
        bars = [b for b in bars if b["time"] <= e]
    return bars


def _save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, compression="snappy")
    log.info("  %-52s  %d rows", str(path.relative_to(ROOT)), len(df))


# ── Stage 1 — Candles ─────────────────────────────────────────────────────────

def stage_candles(symbol: str) -> None:
    log.info("[%s] Stage 1 — candles", symbol)
    out_dir = RDB / "candles"
    out_dir.mkdir(parents=True, exist_ok=True)
    for tf in ("M1", "M5", "M15", "H1", "H4", "D1"):
        src = DATA_PROC / symbol / f"{tf}.parquet"
        if src.exists():
            dst = out_dir / f"{symbol}_{tf}.parquet"
            shutil.copy2(src, dst)
            log.info("  %-52s  copied", str(dst.relative_to(ROOT)))


# ── Stage 2 — Sessions ────────────────────────────────────────────────────────

def stage_sessions(symbol: str, m15: list[dict]) -> pd.DataFrame:
    log.info("[%s] Stage 2 — sessions", symbol)
    from strategy.session_liquidity.session_builder import classify_session

    by_date_sess: dict[tuple, list] = {}
    for c in m15:
        dt = _parse_utc(c["time"])
        sess = classify_session(dt)
        if sess is None:
            continue
        key = (str(dt.date()), sess)
        by_date_sess.setdefault(key, []).append(c)

    rows = []
    for (d, sess), bars in sorted(by_date_sess.items()):
        highs  = [b["high"]  for b in bars]
        lows   = [b["low"]   for b in bars]
        opens  = [b["open"]  for b in bars]
        closes = [b["close"] for b in bars]
        rows.append({
            "date":        d,
            "session":     sess,
            "start_ts":    bars[0]["time"],
            "end_ts":      bars[-1]["time"],
            "session_open":  opens[0],
            "session_high":  max(highs),
            "session_low":   min(lows),
            "session_close": closes[-1],
            "midpoint":      (max(highs) + min(lows)) / 2.0,
            "range_pips":    round((max(highs) - min(lows)) / PIP, 1),
            "n_bars":        len(bars),
        })

    df = pd.DataFrame(rows)
    _save(df, RDB / "sessions" / f"{symbol}_sessions.parquet")
    return df


# ── Stage 3 — Asian Ranges ────────────────────────────────────────────────────

def stage_asian_ranges(symbol: str, m15: list[dict]) -> pd.DataFrame:
    log.info("[%s] Stage 3 — asian ranges", symbol)
    from strategy.session_liquidity.session_builder import build_asian_range

    dates = sorted({_parse_utc(b["time"]).date() for b in m15})
    rows = []
    for d in dates:
        ar = build_asian_range(m15, d)
        if ar is None:
            continue
        rows.append({
            "date":       str(d),
            "high":       ar.high,
            "low":        ar.low,
            "midpoint":   (ar.high + ar.low) / 2.0,
            "range_pips": ar.range_pips,
        })

    df = pd.DataFrame(rows)
    _save(df, RDB / "asian_ranges" / f"{symbol}_asian.parquet")
    return df


# ── Stage 4 — Swings ──────────────────────────────────────────────────────────

def _swings_df(candles: list[dict], tf: str, n: int) -> pd.DataFrame:
    from session_smc.swing_detector import swing_highs, swing_lows

    sh_idxs = swing_highs(candles, n)
    sl_idxs = swing_lows(candles, n)

    rows = []
    for i in sh_idxs:
        rows.append({"ts": candles[i]["time"], "swing_type": "SH",
                     "price": candles[i]["high"], "bar_idx": i, "tf": tf})
    for i in sl_idxs:
        rows.append({"ts": candles[i]["time"], "swing_type": "SL",
                     "price": candles[i]["low"], "bar_idx": i, "tf": tf})

    df = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)
    if df.empty:
        df["classification"] = []
        return df

    # HH / HL / LH / LL classification vs prior swing of same type
    prev_sh = prev_sl = None
    labels = []
    for _, row in df.iterrows():
        if row["swing_type"] == "SH":
            if prev_sh is None:
                labels.append("SH")
            else:
                labels.append("HH" if row["price"] > prev_sh else "LH")
            prev_sh = row["price"]
        else:
            if prev_sl is None:
                labels.append("SL")
            else:
                labels.append("HL" if row["price"] > prev_sl else "LL")
            prev_sl = row["price"]
    df["classification"] = labels
    return df


def stage_swings(symbol: str, h4: list[dict], m15: list[dict]) -> None:
    log.info("[%s] Stage 4 — swings", symbol)
    df_h4  = _swings_df(h4,  "H4",  n=3)
    df_m15 = _swings_df(m15, "M15", n=3)
    _save(df_h4,  RDB / "swings" / f"{symbol}_H4_swings.parquet")
    _save(df_m15, RDB / "swings" / f"{symbol}_M15_swings.parquet")


# ── Stage 5 — Structure Events ────────────────────────────────────────────────

def _structure_events(candles: list[dict], tf: str, n: int) -> list[dict]:
    from session_smc.swing_detector import swing_highs, swing_lows

    sh_idxs = swing_highs(candles, n)
    sl_idxs = swing_lows(candles, n)

    state     = "neutral"
    active_sh = None  # (price, ts)
    active_sl = None  # (price, ts)
    sh_ptr = sl_ptr = 0
    events: list[dict] = []

    for idx in range(len(candles)):
        # Advance to newly confirmed swings: swing at si confirmed when idx == si+n
        while sh_ptr < len(sh_idxs) and sh_idxs[sh_ptr] + n <= idx:
            si = sh_idxs[sh_ptr]
            active_sh = (candles[si]["high"], candles[si]["time"])
            sh_ptr += 1
        while sl_ptr < len(sl_idxs) and sl_idxs[sl_ptr] + n <= idx:
            si = sl_idxs[sl_ptr]
            active_sl = (candles[si]["low"], candles[si]["time"])
            sl_ptr += 1

        close = candles[idx]["close"]
        ts    = candles[idx]["time"]

        if active_sh is not None and close > active_sh[0]:
            etype = "BOS_UP" if state == "bullish" else "CHoCH_UP"
            events.append({"ts": ts, "event_type": etype, "tf": tf,
                           "break_price": active_sh[0], "ref_ts": active_sh[1],
                           "prior_state": state})
            state = "bullish"
            active_sh = None

        if active_sl is not None and close < active_sl[0]:
            etype = "BOS_DOWN" if state == "bearish" else "CHoCH_DOWN"
            events.append({"ts": ts, "event_type": etype, "tf": tf,
                           "break_price": active_sl[0], "ref_ts": active_sl[1],
                           "prior_state": state})
            state = "bearish"
            active_sl = None

    return events


def stage_structure(symbol: str, h4: list[dict], m15: list[dict]) -> None:
    log.info("[%s] Stage 5 — structure (BOS/CHoCH)", symbol)
    ev_h4  = _structure_events(h4,  "H4",  n=3)
    ev_m15 = _structure_events(m15, "M15", n=3)
    _save(pd.DataFrame(ev_h4),  RDB / "structure" / f"{symbol}_H4_structure.parquet")
    _save(pd.DataFrame(ev_m15), RDB / "structure" / f"{symbol}_M15_structure.parquet")


# ── Stage 6 — Liquidity Sweeps ───────────────────────────────────────────────

def stage_liquidity(
    symbol: str, m15: list[dict], asian_df: pd.DataFrame
) -> None:
    log.info("[%s] Stage 6 — liquidity sweeps", symbol)
    from strategy.session_liquidity.session_builder import classify_session

    ar_map = {row["date"]: row for _, row in asian_df.iterrows()}
    rows: list[dict] = []

    for c in m15:
        dt   = _parse_utc(c["time"])
        sess = classify_session(dt)
        if sess is None:
            continue

        d   = str(dt.date())
        ar  = ar_map.get(d)
        if ar is None:
            continue

        ar_high = float(ar["high"])
        ar_low  = float(ar["low"])

        # Bullish sweep: wick below Asian low, close back above it
        if c["low"] < ar_low and c["close"] > ar_low:
            rows.append({
                "ts":           c["time"],
                "date":         d,
                "session":      sess,
                "direction":    "bullish",
                "swept_level":  ar_low,
                "wick_extreme": c["low"],
                "close":        c["close"],
                "wick_pips":    round((ar_low - c["low"]) / PIP, 1),
                "ar_high":      ar_high,
                "ar_low":       ar_low,
                "ar_range_pips": float(ar["range_pips"]),
            })

        # Bearish sweep: wick above Asian high, close back below it
        if c["high"] > ar_high and c["close"] < ar_high:
            rows.append({
                "ts":           c["time"],
                "date":         d,
                "session":      sess,
                "direction":    "bearish",
                "swept_level":  ar_high,
                "wick_extreme": c["high"],
                "close":        c["close"],
                "wick_pips":    round((c["high"] - ar_high) / PIP, 1),
                "ar_high":      ar_high,
                "ar_low":       ar_low,
                "ar_range_pips": float(ar["range_pips"]),
            })

    df = pd.DataFrame(rows)
    _save(df, RDB / "liquidity" / f"{symbol}_sweeps.parquet")


# ── Stage 7 — FVGs ──────────────────────────────────────────────────────────

def stage_fvgs(symbol: str, m15: list[dict]) -> None:
    log.info("[%s] Stage 7 — FVGs", symbol)
    from session_smc.structure_detector import atr as compute_atr

    atr_vals = compute_atr(m15, 14)
    n = len(m15)
    rows: list[dict] = []

    for i in range(1, n - 1):
        prev_c = m15[i - 1]
        disp_c = m15[i]
        next_c = m15[i + 1]

        # Bullish FVG: gap between prev high and next low
        if next_c["low"] > prev_c["high"]:
            fvg_bottom = prev_c["high"]
            fvg_top    = next_c["low"]
            size_pips  = round((fvg_top - fvg_bottom) / PIP, 1)
            atr_v      = atr_vals[i] if atr_vals[i] == atr_vals[i] else 0.0
            atr_ratio  = round((fvg_top - fvg_bottom) / atr_v, 3) if atr_v > 0 else None

            # Scan forward for fill or invalidation (from i+2: bar i+1 created the FVG)
            filled_ts = None
            for j in range(i + 2, n):
                c = m15[j]
                if c["low"] <= fvg_top:          # price entered zone from above
                    if c["close"] < fvg_bottom:  # invalidated (closed through gap)
                        filled_ts = None
                        break
                    filled_ts = c["time"]         # held above bottom → valid retest
                    break

            rows.append({
                "created_ts":  disp_c["time"],
                "direction":   "bullish",
                "fvg_top":     fvg_top,
                "fvg_bottom":  fvg_bottom,
                "fvg_mid":     round((fvg_top + fvg_bottom) / 2, 5),
                "size_pips":   size_pips,
                "atr_ratio":   atr_ratio,
                "filled":      filled_ts is not None,
                "filled_ts":   filled_ts,
                "disp_open":   disp_c["open"],
                "disp_close":  disp_c["close"],
            })

        # Bearish FVG: gap between prev low and next high
        if next_c["high"] < prev_c["low"]:
            fvg_top    = prev_c["low"]
            fvg_bottom = next_c["high"]
            size_pips  = round((fvg_top - fvg_bottom) / PIP, 1)
            atr_v      = atr_vals[i] if atr_vals[i] == atr_vals[i] else 0.0
            atr_ratio  = round((fvg_top - fvg_bottom) / atr_v, 3) if atr_v > 0 else None

            filled_ts = None
            for j in range(i + 2, n):           # start from i+2 (i+1 created the FVG)
                c = m15[j]
                if c["high"] >= fvg_bottom:      # price entered zone from below
                    if c["close"] > fvg_top:     # invalidated
                        filled_ts = None
                        break
                    filled_ts = c["time"]         # valid retest
                    break

            rows.append({
                "created_ts":     disp_c["time"],
                "direction":      "bearish",
                "fvg_top":        fvg_top,
                "fvg_bottom":     fvg_bottom,
                "fvg_mid":        round((fvg_top + fvg_bottom) / 2, 5),
                "size_pips":      size_pips,
                "atr_ratio":      atr_ratio,
                "filled":         filled_ts is not None,
                "filled_ts":      filled_ts,
                "disp_open":      disp_c["open"],
                "disp_close":     disp_c["close"],
            })

    df = pd.DataFrame(rows)
    _save(df, RDB / "fvgs" / f"{symbol}_M15_fvgs.parquet")


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(symbol: str) -> None:
    print(f"\n{'═' * 62}")
    print(f"  research_db/ feature inventory — {symbol}")
    print(f"{'═' * 62}")
    dirs = ["candles", "sessions", "asian_ranges", "swings",
            "structure", "liquidity", "fvgs"]
    for d in dirs:
        path = RDB / d
        files = sorted(path.glob(f"{symbol}*.parquet")) if path.exists() else []
        for f in files:
            try:
                n = len(pd.read_parquet(f, columns=[pd.read_parquet(f).columns[0]]))
            except Exception:
                n = "?"
            print(f"  {str(f.relative_to(ROOT)):<52}  {n:>6} rows")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Build research_db feature layers from processed OHLCV")
    p.add_argument("--symbols", nargs="+", default=["EURUSD"])
    p.add_argument("--start",   default=None, help="Filter start date YYYY-MM-DD")
    p.add_argument("--end",     default=None, help="Filter end date YYYY-MM-DD")
    p.add_argument("--stages",  nargs="+", type=int,
                   default=[1, 2, 3, 4, 5, 6, 7],
                   help="Which stages to run (default: all)")
    args = p.parse_args()

    for sym in args.symbols:
        log.info("Building research_db for %s  %s → %s",
                 sym, args.start or "all", args.end or "all")

        # Load base data (stages 2-7 need this; stage 1 copies files directly)
        m15_full = _load(sym, "M15")
        h4_full  = _load(sym, "H4")
        m15 = _filter(m15_full, args.start, args.end)
        h4  = _filter(h4_full,  args.start, args.end)

        if 1 in args.stages:
            stage_candles(sym)
        if 2 in args.stages:
            sess_df = stage_sessions(sym, m15)
        if 3 in args.stages:
            # Asian ranges need full M15 (previous-day bars needed)
            asian_df = stage_asian_ranges(sym, m15_full)
            if args.start or args.end:
                asian_df = asian_df[
                    (asian_df["date"] >= (args.start or "0000")) &
                    (asian_df["date"] <= (args.end   or "9999"))
                ]
        if 4 in args.stages:
            stage_swings(sym, h4, m15)
        if 5 in args.stages:
            stage_structure(sym, h4, m15)
        if 6 in args.stages:
            if 3 not in args.stages:
                ar_path = RDB / "asian_ranges" / f"{sym}_asian.parquet"
                asian_df = pd.read_parquet(ar_path) if ar_path.exists() else pd.DataFrame()
            stage_liquidity(sym, m15, asian_df)
        if 7 in args.stages:
            stage_fvgs(sym, m15)

        print_summary(sym)


if __name__ == "__main__":
    main()
