"""
Live Trading Status Dashboard — Vantage Demo (MetaAPI)
Adapted from github.com/aungmyat1/simple-smc-ag-trading-bot/dashboard/server.py

Pairs:   EURUSD · GBPUSD · XAUUSD
Strategy: SMCOrderBlockFVGSession (BOS → OB → FVG → Zone → Kill-zone → Signal)

Data sources (all local, no runtime MetaAPI calls):
  logs/strategy_demo_state.json  — account, positions, session, last signal
  logs/candles/{SYMBOL}_M15.json — M15 OHLCV written by the demo runner each tick
  logs/smc_ob_fvg_demo.log       — system log tail
  logs/trades.jsonl              — trade event history

Run:
    uvicorn dashboard.status_server:app --host 0.0.0.0 --port 8090
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PAIRS = ["EURUSD", "GBPUSD", "XAUUSD"]
_PIP  = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.1}

try:
    from strategies.adapters.smc_ob_fvg_session_adapter import DEFAULT_CONFIG as _STRAT_CFG
except Exception:
    _STRAT_CFG: dict = {}

app = FastAPI(docs_url=None, redoc_url=None)


# ── helpers ────────────────────────────────────────────────────────────────────

def _fmt(v, symbol: str = "EURUSD") -> str:
    try:
        f = float(v)
        return f"{f:.2f}" if symbol == "XAUUSD" else f"{f:.5f}"
    except Exception:
        return str(v)


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - prev).abs(),
                    (df["low"]  - prev).abs()], axis=1).max(axis=1)
    s = tr.rolling(period, min_periods=period).mean()
    v = s.iloc[-1]
    return float(v) if pd.notna(v) else 0.0


def _zone_gap(low_a: float, high_a: float, low_b: float, high_b: float) -> float:
    if high_a < low_b: return low_b - high_a
    if high_b < low_a: return low_a - high_b
    return 0.0


# ── data loaders ───────────────────────────────────────────────────────────────

def _load_state() -> dict:
    p = ROOT / "logs" / "strategy_demo_state.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _load_candles(symbol: str) -> pd.DataFrame:
    p = ROOT / "logs" / "candles" / f"{symbol}_M15.json"
    if not p.exists():
        return pd.DataFrame()
    try:
        raw = json.loads(p.read_text())
        rows = []
        for c in raw:
            ts = c.get("time") or c.get("timestamp")
            if ts is None:
                continue
            rows.append({"timestamp": ts, "open": float(c["open"]),
                         "high": float(c["high"]), "low": float(c["low"]),
                         "close": float(c["close"]),
                         "volume": float(c.get("volume", c.get("tickVolume", 0)))})
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df.sort_values("timestamp").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _load_trades(n: int = 25) -> list[dict]:
    p = ROOT / "logs" / "trades.jsonl"
    if not p.exists():
        return []
    try:
        lines = p.read_text().splitlines()
        rows = []
        for ln in reversed(lines):
            try:
                d = json.loads(ln)
                if d.get("event") not in ("ERROR", None) or d.get("event") is None:
                    rows.append(d)
                if len(rows) >= n:
                    break
            except Exception:
                continue
        return rows
    except Exception:
        return []


def _load_log(n: int = 30) -> list[str]:
    for log_name in ("smc_ob_fvg_demo.log", "strategy_demo.log"):
        p = ROOT / "logs" / log_name
        if p.exists():
            try:
                return p.read_text().splitlines()[-n:]
            except Exception:
                pass
    return ["(log not found — runner not started yet)"]


# ── SMC pipeline analysis ──────────────────────────────────────────────────────

def _analyze(df: pd.DataFrame, symbol: str) -> dict:
    """Run BOS → OB → FVG → zone check. Return pipeline stage 0-5."""
    base = {"stage": 0, "bias": "neutral", "price": 0.0, "symbol": symbol,
            "ok": False, "ob_zones": [], "fvg_zones": [], "swing_high": None,
            "swing_low": None, "signal": "FLAT", "blocker": "—",
            "atr_pips": 0.0}
    if df.empty or len(df) < 60:
        base["blocker"] = "No candle cache — runner not started or first tick pending"
        return base

    try:
        from smartmoneyconcepts import smc as _smc
    except ImportError:
        base["blocker"] = "smartmoneyconcepts not installed"
        return base

    pip   = _PIP.get(symbol, 0.0001)
    ohlc  = df[["open","high","low","close","volume"]].copy()
    price = float(ohlc["close"].iloc[-1])
    atr   = _atr(df)
    if atr <= 0:
        base["price"] = price
        base["blocker"] = "ATR=0 (insufficient data)"
        return base

    try:
        swing = _smc.swing_highs_lows(ohlc, swing_length=10)
    except Exception as e:
        base["price"] = price
        base["blocker"] = f"swing_highs_lows error: {e}"
        return base

    # Swing levels for chart
    sh_vals = ohlc["high"].values[swing["HighLow"].values == 1]
    sl_vals = ohlc["low"].values[swing["HighLow"].values == -1]
    swing_high = float(sh_vals[-1]) if len(sh_vals) else None
    swing_low  = float(sl_vals[-1]) if len(sl_vals) else None

    # BOS
    try:
        bos_df   = _smc.bos_choch(ohlc, swing, close_break=True)
        bos_rows = bos_df[bos_df["BOS"].notna() & (bos_df["BOS"] != 0)]
    except Exception as e:
        return {**base, "price": price, "blocker": f"bos_choch error: {e}"}

    if bos_rows.empty:
        return {**base, "price": price, "ok": True, "atr_pips": round(atr/pip, 2),
                "swing_high": swing_high, "swing_low": swing_low,
                "blocker": "No BOS detected yet — market structure building"}

    direction = "bullish" if float(bos_rows.iloc[-1]["BOS"]) == 1 else "bearish"
    bos_idx   = int(bos_rows.index[-1])

    # Order blocks
    try:
        ob_df   = _smc.ob(ohlc, swing, close_mitigation=False)
        ob_side = 1 if direction == "bullish" else -1
        act_obs = ob_df[ob_df["OB"].notna() & (ob_df["OB"] == ob_side)
                        & (ob_df["MitigatedIndex"] == 0)]
    except Exception as e:
        return {**base, "price": price, "bias": direction, "stage": 1, "ok": True,
                "atr_pips": round(atr/pip,2), "swing_high": swing_high, "swing_low": swing_low,
                "blocker": f"ob error: {e}"}

    ob_zones = []
    for _, row in act_obs.iterrows():
        top, bot = float(row["Top"]), float(row["Bottom"])
        if top < bot:
            top, bot = bot, top
        ob_zones.append({"kind": "OB", "direction": direction, "high": top, "low": bot})

    if act_obs.empty:
        return {**base, "price": price, "bias": direction, "stage": 1, "ok": True,
                "ob_zones": ob_zones, "atr_pips": round(atr/pip,2),
                "swing_high": swing_high, "swing_low": swing_low,
                "blocker": f"BOS {'▲' if direction=='bullish' else '▼'} detected — no active OB yet"}

    latest_ob  = act_obs.iloc[-1]
    ob_top     = float(latest_ob["Top"])
    ob_bottom  = float(latest_ob["Bottom"])
    if ob_top < ob_bottom:
        ob_top, ob_bottom = ob_bottom, ob_top

    # FVGs
    try:
        fvg_df   = _smc.fvg(ohlc, join_consecutive=False)
        fvg_side = 1 if direction == "bullish" else -1
        act_fvgs = fvg_df[fvg_df["FVG"].notna() & (fvg_df["FVG"] == fvg_side)
                          & (fvg_df["MitigatedIndex"] == 0)]
    except Exception:
        act_fvgs = pd.DataFrame()

    fvg_zones = []
    for _, row in act_fvgs.iterrows():
        fvg_zones.append({"kind": "FVG", "direction": direction,
                          "high": float(row["Top"]), "low": float(row["Bottom"])})

    # Find FVG closest to OB
    best_fvg = None
    if not act_fvgs.empty:
        gaps = act_fvgs.apply(
            lambda r: _zone_gap(float(r["Bottom"]), float(r["Top"]), ob_bottom, ob_top), axis=1)
        idx  = gaps.idxmin()
        if float(gaps.loc[idx]) <= atr:
            r = act_fvgs.loc[idx]
            best_fvg = {"high": float(r["Top"]), "low": float(r["Bottom"])}

    if best_fvg is None:
        return {**base, "price": price, "bias": direction, "stage": 2, "ok": True,
                "ob_zones": ob_zones, "fvg_zones": fvg_zones,
                "atr_pips": round(atr/pip,2), "swing_high": swing_high, "swing_low": swing_low,
                "blocker": f"OB [{_fmt(ob_bottom,symbol)}–{_fmt(ob_top,symbol)}] found — no nearby FVG confirmation yet"}

    # Confluence zone
    zone_high = max(ob_top, best_fvg["high"])
    zone_low  = min(ob_bottom, best_fvg["low"])
    buf       = 5 * pip
    in_zone   = zone_low - buf <= price <= zone_high + buf

    if not in_zone:
        return {**base, "price": price, "bias": direction, "stage": 3, "ok": True,
                "ob_zones": ob_zones, "fvg_zones": fvg_zones,
                "best_fvg": best_fvg, "ob_top": ob_top, "ob_bottom": ob_bottom,
                "zone_high": zone_high, "zone_low": zone_low,
                "atr_pips": round(atr/pip,2), "swing_high": swing_high, "swing_low": swing_low,
                "blocker": f"OB+FVG confluence [{_fmt(zone_low,symbol)}–{_fmt(zone_high,symbol)}] — price {_fmt(price,symbol)} not yet in zone"}

    # Check kill zone (UTC)
    ts_last = df["timestamp"].iloc[-1]
    hm = ts_last.hour * 60 + ts_last.minute
    in_kill = (7*60 <= hm < 11*60) or (12*60 <= hm < 16*60)
    session  = "london" if 7*60 <= hm < 11*60 else "new_york" if 12*60 <= hm < 16*60 else None

    if not in_kill:
        return {**base, "price": price, "bias": direction, "stage": 4, "ok": True,
                "ob_zones": ob_zones, "fvg_zones": fvg_zones,
                "best_fvg": best_fvg, "ob_top": ob_top, "ob_bottom": ob_bottom,
                "zone_high": zone_high, "zone_low": zone_low,
                "atr_pips": round(atr/pip,2), "swing_high": swing_high, "swing_low": swing_low,
                "blocker": f"Price in OB+FVG zone — waiting for London (07-11) or NY (12-16) kill zone"}

    signal = "LONG" if direction == "bullish" else "SHORT"
    sl     = zone_low - buf if direction == "bullish" else zone_high + buf
    risk   = abs(price - sl)
    tp     = price + risk * 3 if direction == "bullish" else price - risk * 3

    return {**base, "price": price, "bias": direction, "stage": 5, "ok": True,
            "signal": signal, "session": session,
            "ob_zones": ob_zones, "fvg_zones": fvg_zones,
            "best_fvg": best_fvg, "ob_top": ob_top, "ob_bottom": ob_bottom,
            "zone_high": zone_high, "zone_low": zone_low,
            "sl": sl, "tp": tp,
            "atr_pips": round(atr/pip,2), "swing_high": swing_high, "swing_low": swing_low,
            "blocker": None}


# ── SVG chart ──────────────────────────────────────────────────────────────────

def _render_chart_svg(df: pd.DataFrame, pipe: dict, pos_list: list[dict]) -> str:
    symbol = pipe.get("symbol", "EURUSD")
    is_xau = symbol == "XAUUSD"

    N  = 60
    df = df.tail(N).reset_index(drop=True)
    n  = len(df)
    if n < 5:
        return "<p style='color:#f85149'>Not enough candle data yet.</p>"

    W, H            = 1020, 430
    ML, MR, MT, MB = 74, 180, 44, 34
    CW = W - ML - MR
    CH = H - MT - MB

    p_hi = float(df["high"].max())
    p_lo = float(df["low"].min())
    extras: list[float] = []
    for z in pipe.get("ob_zones", []) + pipe.get("fvg_zones", []):
        extras += [z["low"], z["high"]]
    for k in ("swing_high", "swing_low", "sl", "tp"):
        if pipe.get(k):
            extras.append(pipe[k])
    for pos in pos_list:
        for k in ("sl", "tp", "entry"):
            try:
                v = float(pos[k])
                if v > 0:
                    extras.append(v)
            except Exception:
                pass
    if extras:
        p_hi = max(p_hi, max(e for e in extras if e > 0))
        p_lo = min(p_lo, min(e for e in extras if e > 0))
    pad   = (p_hi - p_lo) * 0.16
    p_max = p_hi + pad
    p_min = p_lo - pad
    p_rng = p_max - p_min

    def py(price: float) -> float:
        return MT + CH * (1.0 - (float(price) - p_min) / p_rng)

    def px_i(i: int) -> float:
        return ML + CW * i / max(n - 1, 1)

    def fmt_lbl(v: float) -> str:
        return f"{v:.2f}" if is_xau else f"{v:.5f}"

    bw  = max(4.5, CW / n * 0.62)
    bhw = bw / 2
    o: list[str] = []
    o.append(
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto;display:block;background:#0d1117;border-radius:6px">'
    )

    # Grid
    for pct in (0.15, 0.35, 0.5, 0.65, 0.85):
        yg = MT + CH * pct
        pg = p_max - p_rng * pct
        o.append(f'<line x1="{ML}" y1="{yg:.1f}" x2="{ML+CW}" y2="{yg:.1f}" stroke="#1c2230" stroke-width="1"/>')
        o.append(f'<text x="{ML-6}" y="{yg+4:.1f}" text-anchor="end" fill="#3d4a5a" font-family="monospace" font-size="9">{fmt_lbl(pg)}</text>')
    o.append(f'<rect x="{ML}" y="{MT}" width="{CW}" height="{CH}" fill="none" stroke="#1c2230" stroke-width="1"/>')

    # Swing H/L + dealing range
    s_hi = pipe.get("swing_high")
    s_lo = pipe.get("swing_low")
    if s_hi and s_lo and p_min < s_lo < s_hi < p_max:
        ysh  = py(s_hi)
        ysl  = py(s_lo)
        ymid = (ysh + ysl) / 2
        mid_p = (s_hi + s_lo) / 2
        bias  = pipe.get("bias", "neutral")
        if bias == "bullish":
            o.append(f'<rect x="{ML}" y="{ymid:.1f}" width="{CW}" height="{ysl-ymid:.1f}" fill="#0a1f0a" opacity="0.5"/>')
            o.append(f'<text x="{ML+CW-4}" y="{(ymid+ysl)/2+4:.1f}" text-anchor="end" fill="#204a20" font-family="monospace" font-size="9" font-weight="600">DISCOUNT</text>')
        elif bias == "bearish":
            o.append(f'<rect x="{ML}" y="{ysh:.1f}" width="{CW}" height="{ymid-ysh:.1f}" fill="#1f0a0a" opacity="0.5"/>')
            o.append(f'<text x="{ML+CW-4}" y="{(ysh+ymid)/2+4:.1f}" text-anchor="end" fill="#4a2020" font-family="monospace" font-size="9" font-weight="600">PREMIUM</text>')
        o.append(f'<line x1="{ML}" y1="{ysh:.1f}" x2="{ML+CW}" y2="{ysh:.1f}" stroke="#7a3030" stroke-width="1.2" stroke-dasharray="8,4"/>')
        o.append(f'<text x="{ML+CW+6}" y="{ysh+4:.1f}" fill="#c05050" font-family="monospace" font-size="8">SwgH {fmt_lbl(s_hi)}</text>')
        o.append(f'<line x1="{ML}" y1="{ysl:.1f}" x2="{ML+CW}" y2="{ysl:.1f}" stroke="#207a30" stroke-width="1.2" stroke-dasharray="8,4"/>')
        o.append(f'<text x="{ML+CW+6}" y="{ysl+4:.1f}" fill="#40c060" font-family="monospace" font-size="8">SwgL {fmt_lbl(s_lo)}</text>')
        o.append(f'<line x1="{ML}" y1="{ymid:.1f}" x2="{ML+CW}" y2="{ymid:.1f}" stroke="#6060a0" stroke-width="1" stroke-dasharray="4,4"/>')
        o.append(f'<text x="{ML+CW+6}" y="{ymid+4:.1f}" fill="#8888cc" font-family="monospace" font-size="8">50% {fmt_lbl(mid_p)}</text>')

    # FVG zones (drawn first, behind OBs)
    for z in pipe.get("fvg_zones", []):
        zy1 = py(z["high"])
        zy2 = py(z["low"])
        zh  = max(1.0, zy2 - zy1)
        o.append(f'<rect x="{ML}" y="{zy1:.1f}" width="{CW}" height="{zh:.1f}" fill="#1c1205" stroke="#6a5010" stroke-width="0.8" opacity="0.65"/>')
        o.append(f'<text x="{ML+8}" y="{(zy1+zy2)/2+4:.1f}" fill="#a07020" font-family="monospace" font-size="8">FVG</text>')

    # OB zones
    for z in pipe.get("ob_zones", []):
        zy1 = py(z["high"])
        zy2 = py(z["low"])
        zh  = max(1.0, zy2 - zy1)
        col = "#0a1528" if z["direction"] == "bullish" else "#1a0a0a"
        sc  = "#1e4080" if z["direction"] == "bullish" else "#802010"
        lbl = "#4a9eff" if z["direction"] == "bullish" else "#f85149"
        o.append(f'<rect x="{ML}" y="{zy1:.1f}" width="{CW}" height="{zh:.1f}" fill="{col}" stroke="{sc}" stroke-width="0.9" opacity="0.75"/>')
        o.append(f'<text x="{ML+8}" y="{(zy1+zy2)/2+4:.1f}" fill="{lbl}" font-family="monospace" font-size="8">OB</text>')

    # Candles
    for i, row in df.iterrows():
        xi    = px_i(i)
        yo    = py(row["open"])
        yc    = py(row["close"])
        yh    = py(row["high"])
        yl    = py(row["low"])
        bull  = row["close"] >= row["open"]
        fill  = "#238636" if bull else "#da3633"
        stroke= "#2ea043" if bull else "#f85149"
        body_y = min(yo, yc)
        body_h = max(1.0, abs(yc - yo))
        o.append(f'<line x1="{xi:.1f}" y1="{yh:.1f}" x2="{xi:.1f}" y2="{yl:.1f}" stroke="{stroke}" stroke-width="1.2"/>')
        o.append(f'<rect x="{xi-bhw:.1f}" y="{body_y:.1f}" width="{bw:.1f}" height="{body_h:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="0.5"/>')

    # SL / TP overlay (open position or signal)
    sig_sl = pipe.get("sl")
    sig_tp = pipe.get("tp")
    for pos in pos_list:
        if pos.get("symbol") == pipe.get("symbol"):
            try: sig_sl = float(pos["sl"])
            except Exception: pass
            try: sig_tp = float(pos["tp"])
            except Exception: pass
    if sig_sl and p_min < sig_sl < p_max:
        ys = py(sig_sl)
        o.append(f'<line x1="{ML}" y1="{ys:.1f}" x2="{ML+CW}" y2="{ys:.1f}" stroke="#f85149" stroke-width="1.5" stroke-dasharray="6,3"/>')
        o.append(f'<text x="{ML+CW+6}" y="{ys+4:.1f}" fill="#f85149" font-family="monospace" font-size="8">SL {fmt_lbl(sig_sl)}</text>')
    if sig_tp and p_min < sig_tp < p_max:
        yt = py(sig_tp)
        o.append(f'<line x1="{ML}" y1="{yt:.1f}" x2="{ML+CW}" y2="{yt:.1f}" stroke="#3fb950" stroke-width="1.5" stroke-dasharray="6,3"/>')
        o.append(f'<text x="{ML+CW+6}" y="{yt+4:.1f}" fill="#3fb950" font-family="monospace" font-size="8">TP {fmt_lbl(sig_tp)}</text>')

    # Current price line
    cur_y = py(pipe["price"]) if pipe.get("price") else None
    if cur_y and MT <= cur_y <= MT + CH:
        o.append(f'<line x1="{ML}" y1="{cur_y:.1f}" x2="{ML+CW}" y2="{cur_y:.1f}" stroke="#58a6ff" stroke-width="1" stroke-dasharray="3,3" opacity="0.7"/>')
        o.append(f'<text x="{ML+CW+6}" y="{cur_y+4:.1f}" fill="#58a6ff" font-family="monospace" font-size="8" font-weight="700">{fmt_lbl(pipe["price"])}</text>')

    o.append("</svg>")
    return "".join(o)


# ── HTML builder helpers ───────────────────────────────────────────────────────

_CSS = """
:root{--bg:#0d1117;--bg2:#161b22;--bg3:#1c2230;--border:#30363d;--text:#c9d1d9;
  --muted:#6e7681;--green:#3fb950;--red:#f85149;--yellow:#d29922;
  --blue:#58a6ff;--orange:#e3b341;--mono:'JetBrains Mono','Fira Code','Courier New',monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--mono);font-size:13px;line-height:1.55;padding:16px}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.header{display:flex;align-items:center;justify-content:space-between;background:var(--bg2);
  border:1px solid var(--border);border-radius:8px;padding:12px 18px;margin-bottom:14px}
.logo{font-size:16px;font-weight:700;color:var(--blue);letter-spacing:.05em}
.badge{font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600;letter-spacing:.06em}
.badge-demo{background:#1c2f50;color:var(--blue);border:1px solid #2d4a7a}
.badge-live{background:#3a1a1a;color:var(--red);border:1px solid #6b2020}
.header-right{color:var(--muted);font-size:12px;text-align:right}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px}
.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}
.full-width{grid-column:1/-1}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:14px 16px}
.card-title{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
  color:var(--muted);margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.metric{display:flex;justify-content:space-between;align-items:baseline;margin:5px 0}
.metric-label{color:var(--muted);font-size:12px}
.metric-value{font-size:14px;font-weight:600}
.green{color:var(--green)}.red{color:var(--red)}.yellow{color:var(--yellow)}
.blue{color:var(--blue)}.muted{color:var(--muted)}.orange{color:var(--orange)}
.gate{display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--border)}
.gate:last-child{border-bottom:none}
.gate-icon{font-size:14px;width:20px;text-align:center}
.gate-label{color:var(--muted);width:80px;font-size:12px}
.gate-value{font-size:12px;flex:1}
.gate-pass{color:var(--green)}
.gate-warn{color:var(--yellow)}
.tag{font-size:10px;padding:1px 6px;border-radius:3px;font-weight:600;white-space:nowrap}
.tag-ob{background:#0d2040;color:var(--blue);border:1px solid #1e4080}
.tag-fvg{background:#1c1200;color:var(--orange);border:1px solid #6a5010}
.tag-long{background:#0a2010;color:var(--green);border:1px solid #204010}
.tag-short{background:#200a0a;color:var(--red);border:1px solid #601010}
.signal-badge{display:inline-block;font-size:14px;font-weight:700;padding:5px 16px;
  border-radius:6px;letter-spacing:.05em}
.sig-long{background:#0f2d1a;color:var(--green);border:1px solid #2a6030}
.sig-short{background:#2d0f0f;color:var(--red);border:1px solid #6b2020}
.sig-flat{background:#1c2230;color:var(--muted);border:1px solid #30363d}
.sig-watch{background:#1a1800;color:var(--yellow);border:1px solid #5a4800}
.pair-pill{display:inline-block;font-size:11px;padding:2px 10px;border-radius:12px;
  font-weight:700;letter-spacing:.04em;margin-left:6px}
.trades-table{width:100%;border-collapse:collapse;font-size:12px}
.trades-table th{color:var(--muted);font-weight:600;text-align:left;padding:4px 8px;
  border-bottom:1px solid var(--border)}
.trades-table td{padding:4px 8px;border-bottom:1px solid #1c2230}
.log-box{font-size:11px;line-height:1.5;background:#0a0d12;border:1px solid var(--border);
  border-radius:4px;padding:8px 10px;max-height:240px;overflow-y:auto;white-space:pre-wrap;
  word-break:break-all}
.log-error{color:var(--red)}.log-warn{color:var(--yellow)}
.log-signal{color:var(--green)}.log-debug{color:#3d4a5a}.log-info{color:var(--text)}
.tab-bar{display:flex;gap:6px}
.tab-btn{background:#0d1117;border:1px solid var(--border);color:var(--muted);
  font-family:var(--mono);font-size:12px;font-weight:600;padding:4px 14px;
  border-radius:5px;cursor:pointer;letter-spacing:.04em;transition:all .15s}
.tab-btn:hover{border-color:var(--blue);color:var(--text)}
.tab-active{background:#1c2f50!important;border-color:var(--blue)!important;color:var(--blue)!important}
.chart-panel{width:100%}
"""


def _gate_row(icon: str, label: str, value: str, cls: str = "") -> str:
    return (f'<div class="gate"><span class="gate-icon">{icon}</span>'
            f'<span class="gate-label">{label}</span>'
            f'<span class="gate-value {cls}">{value}</span></div>')


def _pair_card(symbol: str, pipe: dict) -> str:
    stage  = pipe.get("stage", 0)
    bias   = pipe.get("bias", "neutral")
    price  = pipe.get("price", 0)
    sig    = pipe.get("signal", "FLAT")
    blocker= pipe.get("blocker") or "—"
    atr    = pipe.get("atr_pips", 0)

    stage_colors = ["#4a5568","#d29922","#e3b341","#58a6ff","#c97dff","#3fb950"]
    sc    = stage_colors[min(stage, 5)]
    icons = ["⬜","⬜","⬜","⬜","👁","✅"]
    sicon = icons[min(stage, 5)]

    bias_col = "#3fb950" if bias == "bullish" else "#f85149" if bias == "bearish" else "#6e7681"
    bias_lbl = ("▲ BULL" if bias == "bullish" else "▼ BEAR" if bias == "bearish" else "NEUTRAL")

    sig_cls = ("sig-long" if sig == "LONG" else "sig-short" if sig == "SHORT"
               else "sig-watch" if stage == 4 else "sig-flat")
    sig_txt = ("▲ LONG" if sig == "LONG" else "▼ SHORT" if sig == "SHORT"
               else "👁 WATCHING" if stage == 4 else "— FLAT")

    steps = [
        ("BOS",      stage >= 1),
        ("OB",       stage >= 2),
        ("FVG",      stage >= 3),
        ("In Zone",  stage >= 4),
        ("Kill Zone",stage >= 5),
    ]
    bar = "".join(
        f'<span style="flex:1;text-align:center;padding:3px 2px;background:{"#1a3a1a" if ok else "#0d1117"};'
        f'border-radius:4px;border:1px solid {"#3fb95040" if ok else "#30363d"};'
        f'font-size:9px;color:{"#3fb950" if ok else "#4a5568"}">{("✅ " if ok else "⬜ ") + lbl}</span>'
        for lbl, ok in steps
    )

    ob_z  = pipe.get("ob_zones", [])
    fvg_z = pipe.get("fvg_zones", [])
    zone_h= pipe.get("zone_high")
    zone_l= pipe.get("zone_low")
    zone_str = f'{_fmt(zone_l, symbol)}–{_fmt(zone_h, symbol)}' if zone_h else "—"

    return f"""<div class="card">
  <div class="card-title" style="display:flex;justify-content:space-between;align-items:center">
    <span>{symbol}</span>
    <span style="color:{bias_col};font-size:11px;font-weight:700">{bias_lbl}</span>
  </div>
  <div style="display:flex;gap:5px;margin-bottom:10px;align-items:stretch">{bar}</div>
  <div class="metric">
    <span class="metric-label">Price</span>
    <span class="metric-value blue">{_fmt(price, symbol)}</span>
  </div>
  <div class="metric">
    <span class="metric-label">ATR(14)</span>
    <span class="metric-value muted">{atr} pips</span>
  </div>
  <div class="metric">
    <span class="metric-label">OBs</span>
    <span class="metric-value">{len(ob_z)} active</span>
  </div>
  <div class="metric">
    <span class="metric-label">FVGs</span>
    <span class="metric-value">{len(fvg_z)} active</span>
  </div>
  <div class="metric">
    <span class="metric-label">Zone</span>
    <span class="metric-value" style="font-size:11px">{zone_str}</span>
  </div>
  <div style="margin-top:10px;font-size:11px;color:#8a9ab0;border-top:1px solid var(--border);padding-top:8px">
    {blocker if stage < 5 else "All conditions met"}
  </div>
  <div style="margin-top:10px;text-align:center">
    <span class="signal-badge {sig_cls}">{sig_txt}</span>
  </div>
</div>"""


# ── Strategy guide ──────────────────────────────────────────────────────────────

def _example_setup_svg() -> str:
    """Static annotated SVG illustrating a bullish BOS→OB→FVG→Zone setup."""
    # Candle data: (x_center, y_open, y_close, y_high, y_low)
    # y scale: smaller y = higher price. Price mapped from 0-200 → y = 250 - 1.15*price
    CDATA = [
        ( 22,  68,  91,  63,  97),  # C0  bearing - sets swing high
        ( 57,  91, 114,  87, 120),  # C1  bearish
        ( 92, 114, 135, 110, 141),  # C2  bearish
        (127, 135, 118, 114, 140),  # C3  bullish bounce
        (162, 118, 133, 114, 137),  # C4  bearish
        (197, 133, 152, 129, 158),  # C5  bearish
        (232, 152, 172, 149, 178),  # C6  bearish
        (267, 172, 187, 168, 192),  # C7  ORDER BLOCK (last bear before BOS)
        (302, 187,  64,  60, 190),  # C8  BOS CANDLE (breaks swing high y=63)
        (337,  64,  80,  60,  86),  # C9  pullback (FVG bottom = low y=86)
        (372,  80, 100,  76, 106),  # C10 pullback
        (407, 100, 126,  97, 132),  # C11 entering FVG
        (442, 126, 149, 122, 155),  # C12 into OB zone
        (477, 149, 179, 145, 183),  # C13 ENTRY (price in OB zone)
        (512, 179, 156, 152, 183),  # C14 bullish reversal
        (547, 156, 135, 131, 159),  # C15 bullish
        (582, 135, 120, 116, 138),  # C16 hits TP
    ]
    BHW      = 9
    y_swing  = 63    # swing high horizontal line
    y_ob_t   = 168   # OB top  (C7 high)
    y_ob_b   = 192   # OB bottom (C7 low)
    y_fvg_t  = 86    # FVG top   (C9 low)
    y_fvg_b  = 168   # FVG bottom (C7 high = OB top)
    y_sl     = 198   # stop loss
    y_tp     = 122   # take profit 3:1
    y_entry  = 179   # entry (C13 close)
    x_bos    = 302   # C8 x
    x_c13    = 477   # entry candle x
    x_end    = 608
    LX       = 622

    o: list[str] = []
    o.append('<svg viewBox="0 0 782 295" xmlns="http://www.w3.org/2000/svg" '
             'style="width:100%;height:auto;display:block;background:#0a0d12;border-radius:5px">')

    # Grid
    for yg in (60, 100, 140, 180, 220):
        o.append(f'<line x1="10" y1="{yg}" x2="{x_end}" y2="{yg}" stroke="#161c24" stroke-width="1"/>')

    # Phase labels at bottom
    phases = [
        (22,  267, "#4a5568", "① Downtrend"),
        (302, 302, "#3fb950", "② BOS ▲"),
        (337, 477, "#a07020", "③ Pullback"),
        (477, 477, "#58a6ff", "④ Entry"),
        (512, 582, "#3fb950", "⑤ To TP"),
    ]
    for x1, x2, col, lbl in phases:
        xm = (x1 + x2) // 2
        o.append(f'<text x="{xm}" y="284" text-anchor="middle" fill="{col}" '
                 f'font-family="monospace" font-size="8">{lbl}</text>')

    # Swing high dashed line
    o.append(f'<line x1="10" y1="{y_swing}" x2="{x_bos}" y2="{y_swing}" '
             f'stroke="#6060a0" stroke-width="1.2" stroke-dasharray="5,3"/>')
    o.append(f'<text x="{x_bos - 4}" y="{y_swing - 5}" text-anchor="end" fill="#8080c0" '
             f'font-family="monospace" font-size="8">Swing High</text>')

    # FVG zone rectangle
    fvg_x  = x_bos - BHW
    fvg_w  = x_c13 + BHW - fvg_x
    fvg_h  = y_fvg_b - y_fvg_t
    o.append(f'<rect x="{fvg_x}" y="{y_fvg_t}" width="{fvg_w}" height="{fvg_h}" '
             f'fill="#1a1100" stroke="#6a5010" stroke-width="1" opacity="0.8"/>')
    o.append(f'<text x="{fvg_x + 6}" y="{(y_fvg_t + y_fvg_b) // 2 + 4}" fill="#a07020" '
             f'font-family="monospace" font-size="9" font-weight="bold">FVG</text>')

    # OB zone rectangle
    ob_x = 267 - BHW
    ob_w = x_c13 + BHW - ob_x
    ob_h = y_ob_b - y_ob_t
    o.append(f'<rect x="{ob_x}" y="{y_ob_t}" width="{ob_w}" height="{ob_h}" '
             f'fill="#061428" stroke="#1e4080" stroke-width="1.3"/>')
    o.append(f'<text x="{ob_x + 6}" y="{(y_ob_t + y_ob_b) // 2 + 4}" fill="#4a9eff" '
             f'font-family="monospace" font-size="9" font-weight="bold">OB</text>')

    # Candles
    for i, (xc, yo, yc, yh, yl) in enumerate(CDATA):
        bull   = yc < yo
        fill   = "#238636" if bull else "#da3633"
        stroke = "#2ea043" if bull else "#f85149"
        by, bh = min(yo, yc), max(1, abs(yc - yo))
        o.append(f'<line x1="{xc}" y1="{yh}" x2="{xc}" y2="{yl}" stroke="{stroke}" stroke-width="1.2"/>')
        o.append(f'<rect x="{xc - BHW}" y="{by}" width="{BHW * 2}" height="{bh}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="0.6"/>')

    # Highlight C7 (OB candle) outline
    xc7, yo7, yc7, yh7, yl7 = CDATA[7]
    o.append(f'<rect x="{xc7 - BHW}" y="{min(yo7,yc7)}" width="{BHW*2}" height="{abs(yc7-yo7)}" '
             f'fill="none" stroke="#58a6ff" stroke-width="2.2"/>')

    # BOS label above C8
    xc8, _, yc8, yh8, _ = CDATA[8]
    o.append(f'<text x="{xc8}" y="{yh8 - 6}" text-anchor="middle" fill="#3fb950" '
             f'font-family="monospace" font-size="9" font-weight="bold">BOS ▲</text>')

    # Entry candle highlight
    xc13, yo13, yc13, _, yl13 = CDATA[13]
    o.append(f'<rect x="{xc13 - BHW - 2}" y="{min(yo13,yc13) - 2}" width="{BHW*2+4}" height="{abs(yc13-yo13)+4}" '
             f'fill="none" stroke="#58a6ff" stroke-width="1.8" stroke-dasharray="3,2"/>')
    o.append(f'<text x="{xc13}" y="{yl13 + 13}" text-anchor="middle" fill="#58a6ff" '
             f'font-family="monospace" font-size="8">ENTRY</text>')

    # SL dashed line
    o.append(f'<line x1="{x_c13 - 20}" y1="{y_sl}" x2="{x_end}" y2="{y_sl}" '
             f'stroke="#f85149" stroke-width="1.5" stroke-dasharray="5,3"/>')
    # TP dashed line
    o.append(f'<line x1="{x_c13 - 20}" y1="{y_tp}" x2="{x_end}" y2="{y_tp}" '
             f'stroke="#3fb950" stroke-width="1.5" stroke-dasharray="5,3"/>')
    # Entry dotted line
    o.append(f'<line x1="{x_c13 + BHW}" y1="{y_entry}" x2="{x_end}" y2="{y_entry}" '
             f'stroke="#58a6ff" stroke-width="1" stroke-dasharray="3,3" opacity="0.6"/>')

    # RR bracket on right
    xb = x_end - 4
    o.append(f'<line x1="{xb}" y1="{y_tp}" x2="{xb}" y2="{y_sl}" stroke="#555" stroke-width="1"/>')
    o.append(f'<line x1="{xb-3}" y1="{y_entry}" x2="{xb+3}" y2="{y_entry}" stroke="#58a6ff" stroke-width="1.5"/>')
    o.append(f'<line x1="{xb-3}" y1="{y_sl}" x2="{xb+3}" y2="{y_sl}" stroke="#f85149" stroke-width="1.5"/>')
    o.append(f'<line x1="{xb-3}" y1="{y_tp}" x2="{xb+3}" y2="{y_tp}" stroke="#3fb950" stroke-width="1.5"/>')

    # Right-side labels
    rlbls = [
        (LX, y_swing + 4,                 "#8080c0", "Swing High (BOS trigger level)"),
        (LX, y_fvg_t + 11,                "#a07020", "▸ Fair Value Gap (FVG)"),
        (LX, (y_fvg_t+y_fvg_b)//2 + 4,   "#a07020", "  price imbalance zone"),
        (LX, y_ob_t + 10,                 "#4a9eff", "▸ Order Block (OB)"),
        (LX, (y_ob_t+y_ob_b)//2 + 4,     "#4a9eff", "  last bear before BOS"),
        (LX, y_entry + 4,                 "#58a6ff", "▸ Entry price"),
        (LX, y_sl + 4,                    "#f85149", "▸ Stop Loss (below OB)"),
        (LX, y_tp + 4,                    "#3fb950", "▸ Take Profit  3:1 RR"),
    ]
    for lx, ly, col, txt in rlbls:
        o.append(f'<text x="{lx}" y="{ly}" fill="{col}" font-family="monospace" font-size="9">{txt}</text>')

    o.append('</svg>')
    return "".join(o)


def _kill_zone_svg(utc_hour: int, utc_minute: int) -> str:
    W, H   = 760, 68
    BX, BW = 10, 740
    BY, BH = 18, 26
    ph     = BW / 24  # pixels per hour

    def hx(h: float) -> float:
        return BX + h * ph

    o: list[str] = []
    o.append(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
             f'style="width:100%;height:auto;display:block;background:#0a0d12;border-radius:4px">')

    # Background bar
    o.append(f'<rect x="{BX}" y="{BY}" width="{BW}" height="{BH}" fill="#161b22" rx="3"/>')

    # Asian session (faint)
    o.append(f'<rect x="{hx(0):.1f}" y="{BY}" width="{hx(7)-hx(0):.1f}" height="{BH}" '
             f'fill="#1a1505" rx="2" opacity="0.7"/>')

    # London kill zone
    o.append(f'<rect x="{hx(7):.1f}" y="{BY}" width="{hx(11)-hx(7):.1f}" height="{BH}" '
             f'fill="#0f2f50" rx="0"/>')
    o.append(f'<text x="{(hx(7)+hx(11))/2:.1f}" y="{BY+BH//2+5}" text-anchor="middle" '
             f'fill="#58a6ff" font-family="monospace" font-size="10" font-weight="bold">LONDON</text>')

    # NY kill zone
    o.append(f'<rect x="{hx(12):.1f}" y="{BY}" width="{hx(16)-hx(12):.1f}" height="{BH}" '
             f'fill="#0f2f50" rx="0"/>')
    o.append(f'<text x="{(hx(12)+hx(16))/2:.1f}" y="{BY+BH//2+5}" text-anchor="middle" '
             f'fill="#58a6ff" font-family="monospace" font-size="10" font-weight="bold">NEW YORK</text>')

    # Hour ticks
    for h in range(0, 25):
        tx = hx(h)
        is_key = h in (0, 6, 7, 11, 12, 16, 20, 24)
        o.append(f'<line x1="{tx:.1f}" y1="{BY+BH}" x2="{tx:.1f}" y2="{BY+BH+4}" '
                 f'stroke="{"#4a5568" if is_key else "#2a3040"}" stroke-width="{"1.2" if is_key else "0.7"}"/>')
        if h % 4 == 0:
            o.append(f'<text x="{tx:.1f}" y="{BY+BH+14}" text-anchor="middle" fill="#4a5568" '
                     f'font-family="monospace" font-size="8">{h:02d}:00</text>')

    # Zone boundary labels
    for h, lbl in ((7,"07"), (11,"11"), (12,"12"), (16,"16")):
        o.append(f'<text x="{hx(h):.1f}" y="{BY-4}" text-anchor="middle" fill="#3a5080" '
                 f'font-family="monospace" font-size="8">{lbl}:00</text>')

    # Session labels in dead zones
    o.append(f'<text x="{(hx(0)+hx(7))/2:.1f}" y="{BY+BH//2+5}" text-anchor="middle" '
             f'fill="#3a3010" font-family="monospace" font-size="9">ASIAN</text>')
    o.append(f'<text x="{(hx(16)+hx(24))/2:.1f}" y="{BY+BH//2+5}" text-anchor="middle" '
             f'fill="#2a3040" font-family="monospace" font-size="9">DEAD ZONE</text>')

    # Current time needle
    cur_x = hx(utc_hour + utc_minute / 60)
    in_kz = (7 <= utc_hour < 11) or (12 <= utc_hour < 16)
    nc    = "#3fb950" if in_kz else "#6e7681"
    o.append(f'<line x1="{cur_x:.1f}" y1="{BY-2}" x2="{cur_x:.1f}" y2="{BY+BH+2}" '
             f'stroke="{nc}" stroke-width="2"/>')
    o.append(f'<polygon points="{cur_x-4:.1f},{BY-2} {cur_x+4:.1f},{BY-2} {cur_x:.1f},{BY+4}" '
             f'fill="{nc}"/>')
    o.append(f'<text x="{cur_x:.1f}" y="{BY-7}" text-anchor="middle" fill="{nc}" '
             f'font-family="monospace" font-size="8" font-weight="bold">'
             f'{utc_hour:02d}:{utc_minute:02d} UTC</text>')

    o.append('</svg>')
    return "".join(o)


def _strategy_section(utc_now: datetime) -> str:
    cfg = _STRAT_CFG
    risk_pct  = float(cfg.get("risk_per_trade", 0.01)) * 100
    rr        = float(cfg.get("rr_ratio", 3.0))
    sw        = int(cfg.get("swing_length", 10))
    atr_p     = int(cfg.get("atr_period", 14))
    buf_pips  = float(cfg.get("stop_buffer_pips", 5.0))
    max_sp    = float(cfg.get("max_spread_pips", 3.0))
    max_dt    = int(cfg.get("max_daily_trades", 2))
    min_bars  = int(cfg.get("min_bars", 80))
    fvg_mult  = float(cfg.get("fvg_zone_atr_mult", 1.0))

    params_rows = "".join(
        f'<tr><td class="muted">{k}</td><td style="font-weight:600;color:var(--blue)">{v}</td></tr>'
        for k, v in [
            ("Risk / trade",       f"{risk_pct:.0f}%"),
            ("RR ratio",           f"{rr:.0f}:1"),
            ("Swing length",       f"{sw} bars"),
            ("ATR period",         f"{atr_p} bars"),
            ("Stop buffer",        f"{buf_pips:.0f} pips"),
            ("Max spread",         f"{max_sp:.0f} pips"),
            ("Max daily trades",   f"{max_dt}"),
            ("Min bars required",  f"{min_bars}"),
            ("FVG proximity",      f"≤ {fvg_mult:.0f}× ATR"),
            ("Pairs",              "EURUSD · GBPUSD · XAUUSD"),
            ("Timeframe",          "M15"),
        ]
    )

    rules = [
        ("BOS — Break of Structure",
         "Wait for price to break above (bullish) or below (bearish) a confirmed swing high/low. "
         "This establishes the structural direction. Uses <code>smc.bos_choch(close_break=True)</code>."),
        ("OB — Order Block",
         "Find the last opposing candle immediately before the BOS move — this is the institutional "
         "order block. Only unmitigated OBs qualify (<code>MitigatedIndex == 0</code>). "
         "Bullish BOS → last bearish candle is the OB."),
        ("FVG — Fair Value Gap",
         "Find an unmitigated FVG in the same direction as BOS, within <strong>1× ATR</strong> of the OB. "
         "FVG = gap between candle[n-1] high and candle[n+1] low (imbalance). "
         "Price respects these gaps as magnets."),
        ("Price in Confluence Zone",
         "Current price must be inside the OB zone (± 5-pip buffer). "
         "The OB+FVG confluence zone is the entry area — price retracing into institutional demand/supply."),
        ("Kill Zone Gate",
         "Signal is only valid during <strong>London 07:00–11:00 UTC</strong> or "
         "<strong>New York 12:00–16:00 UTC</strong>. "
         "Institutional order flow concentrates in these windows."),
    ]

    rules_html = "".join(
        f'<div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)">'
        f'<div style="min-width:26px;height:26px;background:#0f2f50;border-radius:50%;display:flex;'
        f'align-items:center;justify-content:center;font-size:12px;font-weight:700;color:var(--blue);'
        f'flex-shrink:0">{i+1}</div>'
        f'<div><div style="font-weight:600;font-size:12px;margin-bottom:3px">{title}</div>'
        f'<div style="font-size:11px;color:#8a9ab0;line-height:1.6">{desc}</div></div>'
        f'</div>'
        for i, (title, desc) in enumerate(rules)
    )

    exit_html = (
        '<div style="font-size:11px;color:#8a9ab0;line-height:1.8">'
        f'<div><span style="color:var(--red);font-weight:600">Stop Loss</span> — '
        f'Below OB low (bullish) or above OB high (bearish), + {buf_pips:.0f}-pip buffer</div>'
        f'<div><span style="color:var(--green);font-weight:600">Take Profit</span> — '
        f'Risk × {rr:.0f} (3:1 reward-to-risk, single TP, no partials)</div>'
        f'<div><span style="color:var(--yellow);font-weight:600">Order Type</span> — '
        f'Market order at close of signal candle</div>'
        f'<div><span style="color:var(--blue);font-weight:600">Sizing</span> — '
        f'{risk_pct:.0f}% equity risk, lots = risk / (SL distance × pip value)</div>'
        f'<div><span style="color:var(--muted);font-weight:600">Max per day</span> — '
        f'{max_dt} trades per pair per day (daily counter resets at midnight UTC)</div>'
        '</div>'
    )

    kz_svg     = _kill_zone_svg(utc_now.hour, utc_now.minute)
    ex_svg     = _example_setup_svg()

    return f"""<div class="card" style="grid-column:1/-1;margin-bottom:12px">
  <details>
    <summary style="cursor:pointer;font-size:10px;font-weight:700;letter-spacing:.12em;
      text-transform:uppercase;color:var(--muted);padding-bottom:10px;list-style:none;
      display:flex;justify-content:space-between;align-items:center">
      <span>Strategy Guide — SMCOrderBlockFVGSession</span>
      <span style="font-size:11px;color:var(--blue)">▼ expand</span>
    </summary>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:8px">

      <!-- Entry rules -->
      <div>
        <div style="font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--muted);
          margin-bottom:10px;text-transform:uppercase">Entry Rules (5-stage gate)</div>
        {rules_html}
      </div>

      <!-- Parameters + exit rules -->
      <div style="display:flex;flex-direction:column;gap:12px">
        <div>
          <div style="font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--muted);
            margin-bottom:8px;text-transform:uppercase">Live Parameters</div>
          <table class="trades-table" style="font-size:12px">
            <tbody>{params_rows}</tbody>
          </table>
        </div>
        <div>
          <div style="font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--muted);
            margin-bottom:8px;text-transform:uppercase">Exit Rules</div>
          {exit_html}
        </div>
      </div>

    </div>

    <!-- Kill zone timeline -->
    <div style="margin-top:14px">
      <div style="font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--muted);
        margin-bottom:8px;text-transform:uppercase">Kill Zone Timeline (UTC)</div>
      {kz_svg}
    </div>

    <!-- Annotated example setup -->
    <div style="margin-top:14px">
      <div style="font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--muted);
        margin-bottom:8px;text-transform:uppercase">Example Setup — Bullish BOS → OB → FVG → Entry</div>
      {ex_svg}
    </div>

  </details>
</div>"""


def _build_html(state: dict, pipes: dict, dfs: dict,
                trades: list[dict], log_lines: list[str], elapsed: int, now_str: str,
                utc_now: datetime | None = None) -> str:
    if utc_now is None:
        utc_now = datetime.now(timezone.utc)
    live = state.get("live_trading", False)
    mode = state.get("mode", "demo")
    badge_cls = "badge-live" if live else "badge-demo"
    badge_lbl = "LIVE" if live else "DEMO"
    session   = state.get("session_gate", "closed")
    strategy  = state.get("strategy", "SMCOrderBlockFVGSession")
    runner_ok = bool(state.get("status") == "running")
    runner_pid= state.get("pid", "?")

    # Header
    header = f"""<div class="header">
  <div style="display:flex;align-items:center;gap:14px">
    <span class="logo">⚡ SMC-Forex Demo</span>
    <span class="badge {badge_cls}">{badge_lbl}</span>
    <span style="color:var(--muted);font-size:12px">EURUSD · GBPUSD · XAUUSD</span>
    <span style="font-size:12px;color:{'var(--green)' if runner_ok else 'var(--red)'}"
          title="runner PID {runner_pid}">{"● RUNNING" if runner_ok else "● STOPPED"}</span>
  </div>
  <div class="header-right">
    {now_str}<br>
    <span class="muted">{strategy}</span> · {elapsed}ms · <a class="muted" href="/dashboard/">↻ refresh</a>
  </div>
</div>"""

    # Account card
    acct  = state.get("account", {})
    bal   = acct.get("balance", 0)
    eq    = acct.get("equity", 0)
    fm    = acct.get("free_margin", 0)
    pnl   = eq - bal
    pnl_c = "green" if pnl >= 0 else "red"
    acct_html = f"""<div class="card">
  <div class="card-title">Vantage Demo Account</div>
  <div class="metric"><span class="metric-label">Balance</span>
    <span class="metric-value">${bal:.2f}</span></div>
  <div class="metric"><span class="metric-label">Equity</span>
    <span class="metric-value">${eq:.2f}</span></div>
  <div class="metric"><span class="metric-label">Float P&L</span>
    <span class="metric-value {pnl_c}">${pnl:+.2f}</span></div>
  <div class="metric"><span class="metric-label">Free margin</span>
    <span class="metric-value muted">${fm:.2f}</span></div>
</div>"""

    # Session card
    sess_col  = "#3fb950" if session in ("london","new_york") else "#d29922" if session == "asian" else "#4a5568"
    sess_icon = "🟢" if session in ("london","new_york") else "🟡" if session == "asian" else "⚫"
    sess_lbl  = session.replace("_"," ").upper()
    ldt = state.get("last_tick_at","—")
    ldt_short = ldt[:19].replace("T"," ") if ldt != "—" else "—"
    ldec = state.get("last_decision", "—")
    sess_html = f"""<div class="card">
  <div class="card-title">Session Status</div>
  <div class="metric"><span class="metric-label">Session</span>
    <span class="metric-value" style="color:{sess_col}">{sess_icon} {sess_lbl}</span></div>
  <div class="metric"><span class="metric-label">London</span>
    <span class="metric-value muted">07:00–11:00 UTC</span></div>
  <div class="metric"><span class="metric-label">New York</span>
    <span class="metric-value muted">12:00–16:00 UTC</span></div>
  <div class="metric"><span class="metric-label">Last tick</span>
    <span class="metric-value muted" style="font-size:11px">{ldt_short}</span></div>
  <div class="metric"><span class="metric-label">Decision</span>
    <span class="metric-value muted" style="font-size:11px">{ldec}</span></div>
</div>"""

    # Last signal card
    ls = state.get("last_signal") or {}
    if ls:
        ls_sym = ls.get("symbol","—")
        ls_act = ls.get("action","—")
        ls_col = "#3fb950" if ls_act == "BUY" else "#f85149" if ls_act == "SELL" else "#6e7681"
        ls_ts  = (ls.get("timestamp","")[:19].replace("T"," "))
        sig_card = f"""<div class="card">
  <div class="card-title">Last Signal</div>
  <div class="metric"><span class="metric-label">Symbol</span>
    <span class="metric-value blue">{ls_sym}</span></div>
  <div class="metric"><span class="metric-label">Action</span>
    <span class="metric-value" style="color:{ls_col};font-size:16px;font-weight:700">{ls_act}</span></div>
  <div class="metric"><span class="metric-label">Entry</span>
    <span class="metric-value">{ls.get("entry_price","—")}</span></div>
  <div class="metric"><span class="metric-label">SL</span>
    <span class="metric-value red">{ls.get("stop_loss","—")}</span></div>
  <div class="metric"><span class="metric-label">TP</span>
    <span class="metric-value green">{ls.get("take_profit","—")}</span></div>
  <div class="metric"><span class="metric-label">Lots</span>
    <span class="metric-value muted">{ls.get("lots","—")}</span></div>
  <div class="metric"><span class="metric-label">At</span>
    <span class="metric-value muted" style="font-size:11px">{ls_ts}</span></div>
</div>"""
    else:
        sig_card = f"""<div class="card">
  <div class="card-title">Last Signal</div>
  <div style="text-align:center;padding:24px;color:var(--muted)">No signal yet</div>
</div>"""

    # Open positions card
    pos_list = state.get("open_positions", [])
    if pos_list:
        pos_rows = "".join(
            f'<tr>'
            f'<td class="blue">{p.get("symbol","?")}</td>'
            f'<td><span class="tag {"tag-long" if p.get("direction","")=="buy" else "tag-short"}">'
            f'{"▲ L" if p.get("direction","")=="buy" else "▼ S"}</span></td>'
            f'<td>{p.get("entry","—")}</td>'
            f'<td class="red">{p.get("sl","—")}</td>'
            f'<td class="green">{p.get("tp","—")}</td>'
            f'<td class="{"green" if float(p.get("profit",0))>=0 else "red"}">'
            f'{float(p.get("profit",0)):+.2f}</td></tr>'
            for p in pos_list
        )
        pos_html = f"""<div class="card full-width">
  <div class="card-title">Open Positions ({len(pos_list)})</div>
  <table class="trades-table">
    <thead><tr><th>Symbol</th><th>Dir</th><th>Entry</th><th>SL</th><th>TP</th><th>P&L</th></tr></thead>
    <tbody>{pos_rows}</tbody>
  </table>
</div>"""
    else:
        pos_html = ""  # no open positions — omit card

    # Tabbed chart panel — one tab per pair, one chart visible at a time
    def _tab_label(symbol: str) -> str:
        pipe  = pipes.get(symbol, {})
        stage = pipe.get("stage", 0)
        sig   = pipe.get("signal", "FLAT")
        dot   = "🟢" if sig in ("LONG","SHORT") else "🟡" if stage >= 3 else "⚫"
        arrow = " ▲" if sig == "LONG" else " ▼" if sig == "SHORT" else ""
        return f"{dot} {symbol}{arrow}"

    tab_labels = {s: _tab_label(s) for s in PAIRS}
    tab_panels = ""
    for i, symbol in enumerate(PAIRS):
        pipe  = pipes.get(symbol, {})
        stage = pipe.get("stage", 0)
        sig   = pipe.get("signal", "FLAT")
        svg   = _render_chart_svg(dfs.get(symbol, pd.DataFrame()), pipe, pos_list)
        display = "block" if i == 0 else "none"
        tab_panels += (
            f'<div id="chart-panel-{symbol}" class="chart-panel" style="display:{display}">'
            f'<div style="font-size:10px;color:var(--muted);margin-bottom:8px;letter-spacing:.08em">'
            f'SMC ZONES · M15 · last 60 bars · Stage {stage}/5'
            f'{"  <span style=\'color:var(--green)\'>▲ LONG SIGNAL</span>" if sig=="LONG" else "  <span style=\'color:var(--red)\'>▼ SHORT SIGNAL</span>" if sig=="SHORT" else ""}'
            f'</div>{svg}</div>'
        )

    tab_btns = "".join(
        f'<button class="tab-btn{"  tab-active" if i==0 else ""}" '
        f'onclick="showChart(\'{s}\')" id="tab-btn-{s}">{tab_labels[s]}</button>'
        for i, s in enumerate(PAIRS)
    )
    charts_html = f"""<div class="card" style="grid-column:1/-1">
  <div class="card-title" style="display:flex;align-items:center;justify-content:space-between">
    <span>Live M15 Charts</span>
    <div class="tab-bar">{tab_btns}</div>
  </div>
  {tab_panels}
</div>"""

    # Per-pair pipeline cards
    pair_cards = "".join(_pair_card(s, pipes.get(s, {})) for s in PAIRS)

    # Trades table
    actual_trades = [t for t in trades if t.get("event") not in ("ERROR",)]
    if actual_trades:
        trade_rows = "".join(
            f'<tr><td class="muted">{t.get("ts","")[:19].replace("T"," ")}</td>'
            f'<td class="blue">{t.get("symbol","—")}</td>'
            f'<td><span class="tag {"tag-long" if t.get("action","")=="BUY" else "tag-short"}">'
            f'{t.get("event","?")}</span></td>'
            f'<td>{t.get("entry_price","—") or t.get("price","—")}</td>'
            f'<td class="red">{t.get("stop_loss","—")}</td>'
            f'<td class="green">{t.get("take_profit","—")}</td></tr>'
            for t in actual_trades[:25]
        )
        trades_html = f"""<div class="card full-width">
  <div class="card-title">Recent Trades</div>
  <div style="overflow-x:auto">
  <table class="trades-table">
    <thead><tr><th>Time (UTC)</th><th>Symbol</th><th>Event</th><th>Entry</th><th>SL</th><th>TP</th></tr></thead>
    <tbody>{trade_rows}</tbody>
  </table></div>
</div>"""
    else:
        trades_html = """<div class="card full-width">
  <div class="card-title">Recent Trades</div>
  <div style="text-align:center;padding:18px;color:var(--muted)">No completed trades yet.</div>
</div>"""

    # Log
    def _lcls(ln: str) -> str:
        l = ln.lower()
        if "error" in l or "exception" in l: return "log-error"
        if "warn" in l: return "log-warn"
        if "signal" in l or "order" in l or "open" in l: return "log-signal"
        if "debug" in l: return "log-debug"
        return "log-info"
    log_rows = "".join(f'<div class="{_lcls(ln)}">{ln}</div>' for ln in log_lines)
    log_html = f"""<div class="card full-width">
  <div class="card-title">System Log — last 30 lines</div>
  <div class="log-box" id="lb">{log_rows}</div>
</div>"""

    maybe_pos = f'<div class="grid-2" style="margin-bottom:12px">{pos_html}</div>' if pos_html else ""

    _JS = (
        "<script>"
        "const lb=document.getElementById('lb');if(lb)lb.scrollTop=lb.scrollHeight;"
        "const _PAIRS=['EURUSD','GBPUSD','XAUUSD'];"
        "function showChart(sym){"
        "_PAIRS.forEach(function(s){"
        "var p=document.getElementById('chart-panel-'+s);"
        "var b=document.getElementById('tab-btn-'+s);"
        "if(p)p.style.display=s===sym?'block':'none';"
        "if(b){b.classList.toggle('tab-active',s===sym);}"
        "});}"
        "</script>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>SMC Demo Dashboard</title>
  <style>{_CSS}</style>
</head>
<body>
  {header}
  <div class="grid-3" style="margin-bottom:12px">{acct_html}{sess_html}{sig_card}</div>
  {maybe_pos}
  <div class="grid-2" style="margin-bottom:12px">{charts_html}</div>
  <div class="grid-3" style="margin-bottom:12px">{pair_cards}</div>
  <div class="grid-2">{_strategy_section(utc_now)}</div>
  <div class="grid-2" style="margin-bottom:12px">{trades_html}</div>
  <div class="grid-2">{log_html}</div>
  {_JS}
</body>
</html>"""


# ── routes ─────────────────────────────────────────────────────────────────────

@app.get("/dashboard/", response_class=HTMLResponse)
async def dashboard():
    t0 = time.monotonic()

    state = _load_state()
    dfs   = {s: _load_candles(s) for s in PAIRS}
    pipes = {s: _analyze(dfs[s], s) for s in PAIRS}
    trades    = _load_trades()
    log_lines = _load_log()

    elapsed  = int((time.monotonic() - t0) * 1000)
    utc_now  = datetime.now(timezone.utc)
    now_str  = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")

    html = _build_html(state, pipes, dfs, trades, log_lines, elapsed, now_str, utc_now)
    return HTMLResponse(content=html)


@app.get("/api/status")
async def api_status():
    state = _load_state()
    dfs   = {s: _load_candles(s) for s in PAIRS}
    pipes = {s: _analyze(dfs[s], s) for s in PAIRS}
    return {
        "ts":      datetime.now(timezone.utc).isoformat(),
        "account": state.get("account", {}),
        "session": state.get("session_gate", "closed"),
        "runner":  state.get("status", "unknown"),
        "pairs":   {s: {"stage": pipes[s]["stage"], "signal": pipes[s]["signal"],
                        "bias": pipes[s]["bias"], "price": pipes[s]["price"]}
                    for s in PAIRS},
        "open_positions": state.get("open_positions", []),
        "last_signal":    state.get("last_signal"),
    }


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/dashboard/")


if __name__ == "__main__":
    import uvicorn
    port = int(__import__("os").getenv("LIVE_DASHBOARD_PORT", "8090"))
    uvicorn.run("dashboard.status_server:app", host="0.0.0.0", port=port, log_level="warning")
