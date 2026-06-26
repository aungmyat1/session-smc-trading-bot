# Flow — 11-Phase SMC Session Chain (Strategy B / session_smc)

ASCII flowchart of the complete execution path from data ingestion to signal output.
Every decision gate shows the early-exit condition (→ None).

---

## Data Ingestion (Caller's Responsibility)

```
External data source (CSV / MetaAPI / Parquet)
    |
    +-- M15 bars (session window, typically 20 bars)
    |       sliced to session: London 07:00-10:00 UTC
    |                          New York 13:00-16:00 UTC
    |
    +-- H4 bars (200 bars before session open, bar-close safe)
    |       [scripts/backtest.py: cutoff = session_start - 4h]
    |
    +-- H1 bars (200 bars before session open, or M15 proxy)
    |
    v
generate_signal_A(symbol, candles_4h, candles_1h, session_candles, session_name, config)
```

---

## Stage 0 — D2 Daily Context Build

```
[confirmation_entry.py:123]
    |
    v
build_daily_context(candles_4h, session_candles[0]["time"], swing_n=3)
  [daily_bias.py:61]
    |
    +-- aggregate_to_daily(candles_4h)  →  list of D1 OHLC candles
    |     [daily_bias.py:32–58]
    |     Date key = first 10 chars of H4 bar "time" field
    |
    +-- filter: keep only closed days (date < session_start_date)
    |
    +-- len(closed) < 2?
    |       YES → d2_ctx = None  (D2 gates all skipped silently)
    |       NO  → classify_structure(closed, swing_n=3) → daily structure
    |
    v
d2_ctx = { pdh, pdl, daily_mid, structure } or None
```

---

## Phase 2 — HTF Bias

```
[confirmation_entry.py:126–128]
    |
    v
htf_bias(candles_4h, candles_1h, swing_n=3)
  [structure_detector.py:17–37]
    |
    +-- classify_structure(candles_4h, swing_n=3)  →  b4
    |     [swing_detector.py:93–127]
    |     swing_highs() + swing_lows() → last 2 of each
    |     HH+HL → 'bullish' | LL+LH → 'bearish' | other → 'neutral'
    |
    +-- classify_structure(candles_1h, swing_n=3)  →  b1
    |
    +-- b4='bullish' AND b1!='bearish'  →  bias = 'bullish'
    +-- b4='bearish' AND b1!='bullish'  →  bias = 'bearish'
    +-- otherwise                        →  bias = 'neutral'
    |
    v
bias == 'neutral'?
    YES → RETURN None  [early exit: Phase 2 fail]
    NO  → continue
```

---

## D2 Gate A — Daily Structure Alignment

```
[confirmation_entry.py:131–134]
    |
    v
d2_ctx is not None AND d2_structure_gate=True?
    NO  → skip gate (d2_ctx=None or gate disabled)
    YES →
        ds = d2_ctx["structure"]
        ds != 'neutral' AND ds != bias?
            YES → RETURN None  [early exit: D2 Gate A fail]
            NO  → continue
```

---

## D2 Gate B — Price Location

```
[confirmation_entry.py:140–146]
    |
    v
d2_ctx is not None AND d2_location_gate=True?
    NO  → skip gate
    YES →
        session_open_price = float(session_candles[0]["open"])
        location = classify_location(session_open_price, pdh, pdl)
        [daily_bias.py:112–127]
            price > mid → 'premium'
            price < mid → 'discount'
            price == mid or pdh<=pdl → 'equilibrium'
        |
        bias='bullish' AND location='premium'?  →  RETURN None
        bias='bearish' AND location='discount'? →  RETURN None
        otherwise → continue
```

---

## Phase 3 — Session Range Build

```
[confirmation_entry.py:149–151]
    |
    v
build_session_range(session_candles, range_bars=8, min_range_pips=10.0)
  [liquidity_detector.py:19–50]
    |
    +-- bars = session_candles[:8]
    +-- len(bars) < 8?     →  RETURN None  [insufficient bars]
    +-- high = max(bar.high), low = min(bar.low)
    +-- range_pips = (high - low) / 0.0001
    +-- range_pips < 10.0? →  RETURN None  [range too narrow]
    |
    v
sess_range = { high, low, midpoint, range_pips }
```

---

## Phase 4 — Session Classification (informational)

```
[confirmation_entry.py:155]
    |
    v
_sess_class = classify_session(session_candles, sess_range, atr_period=14)
  [liquidity_detector.py:55–80]
    ratio = session_range / ATR(14)[-1]
    ratio < 0.5 → 'RANGE'
    ratio > 0.7 → 'TREND'
    else        → 'MIXED'

Result is DISCARDED. No gate. No logging. Execution continues regardless.
```

---

## ATR Pre-computation

```
[confirmation_entry.py:158]
    |
    v
atr_vals = atr(session_candles, atr_period=14)
  [structure_detector.py:42–73]
    Index 0: TR = high - low (no prior close)
    Indices 1..13: individual TRs, result[i] = NaN
    Index 14: seed = mean(TR[1..14])
    Index 15+: Wilder's: result[i] = (result[i-1] * 13 + TR[i]) / 14

atr_vals[0..13] = NaN  (these bars skipped in displacement detection)
```

---

## Phase 5 — Sweep Detection

```
[confirmation_entry.py:161–165]
    |
    v
detect_sweep(session_candles, sess_range, bias, from_idx=8)
  [liquidity_detector.py:85–128]
    |
    Scan from bar 8 onwards:
    |
    bias='bullish':
        bar.low < sess_range.low AND bar.close > sess_range.low?
            YES → sweep = { index=i, sweep_price=sess_range.low,
                            wick_extreme=bar.low, direction='bullish' }
                  return immediately (first sweep wins)
    |
    bias='bearish':
        bar.high > sess_range.high AND bar.close < sess_range.high?
            YES → sweep = { index=i, sweep_price=sess_range.high,
                            wick_extreme=bar.high, direction='bearish' }
                  return immediately
    |
    No sweep found? → RETURN None  [early exit: Phase 5 fail]
    |
    v
sweep = { index, sweep_price, wick_extreme, direction }
```

---

## D2 Gate C — POI Proximity

```
[confirmation_entry.py:169–177]
    |
    v
d2_ctx is not None AND d2_poi_gate=True?
    NO  → skip gate
    YES →
        poi_threshold = 30.0 * 0.0001 = 0.0030
        swept_level = sweep["sweep_price"]
        bias='bullish': abs(swept_level - pdl) > poi_threshold? → RETURN None
        bias='bearish': abs(swept_level - pdh) > poi_threshold? → RETURN None
        otherwise → continue
```

---

## Phase 6 — CHoCH Detection

```
[confirmation_entry.py:180–183]
    |
    v
detect_choch(session_candles, sweep_idx, bias, lookback=8)
  [structure_detector.py:78–114]
    |
    win_start = max(0, sweep_idx - 8)
    window = session_candles[win_start : sweep_idx]
    empty window? → return None
    |
    bias='bullish':
        reference = max(bar.high for bar in window)
        Scan from sweep_idx+1:
            bar.close > reference? → choch = { index=i, reference }; return
    |
    bias='bearish':
        reference = min(bar.low for bar in window)
        Scan from sweep_idx+1:
            bar.close < reference? → choch = { index=i, reference }; return
    |
    No CHoCH? → RETURN None  [early exit: Phase 6 fail]
```

---

## Phase 7 — BOS Level + BOS Detection

```
[confirmation_entry.py:187–197]
    |
    v
BOS level derivation:
    bias='bullish':
        last_swing_high(session_candles, swing_n=3, before_idx=sweep_idx)
        [swing_detector.py:56–71]
            swing_highs(session_candles[:sweep_idx], n=3) → indices
            no indices? → bos_swing = None → bos_level = None
    bias='bearish':
        last_swing_low(session_candles, swing_n=3, before_idx=sweep_idx)
    |
    v
detect_bos(session_candles, choch_idx, bias, bos_level)
  [structure_detector.py:119–149]
    |
    bos_level is None? → return None immediately → RETURN None  [Phase 7 fail: no prior swing]
    |
    bias='bullish': scan from choch_idx+1: bar.close > bos_level? → bos = { index, level }
    bias='bearish': scan from choch_idx+1: bar.close < bos_level? → bos = { index, level }
    No BOS? → RETURN None  [early exit: Phase 7 fail]
```

---

## Phase 8 — Displacement Detection

```
[confirmation_entry.py:200–209]
    |
    v
detect_displacement(session_candles, start=sweep_idx, end=bos_idx,
                    bias, atr_vals, atr_mult=1.5)
  [structure_detector.py:154–198]
    |
    Scan [sweep_idx .. bos_idx] inclusive:
        atr_val = atr_vals[i]
        atr_val is NaN? → skip bar
        (bar.high - bar.low) < 1.5 * atr_val? → skip bar
        bias='bullish': bar.close > bar.open?
            YES → disp = { index, high, low, open, close }; return
        bias='bearish': bar.close < bar.open?
            YES → disp = { index, high, low, open, close }; return
    |
    No displacement? → RETURN None  [early exit: Phase 8 fail]
    |
    v
disp = { index (di), high, low, open, close }
|
di + 1 >= n?  →  RETURN None  [boundary check: no room for FVG]
```

---

## Phase 9a — FVG Detection

```
[confirmation_entry.py:212–214]
    |
    v
find_fvg(session_candles, displacement_idx=di, bias)
  [poi_detector.py:36–78]
    |
    d < 1 OR d+1 >= n? → return None
    |
    bias='bullish':
        bottom = session_candles[d-1]["high"]
        top    = session_candles[d+1]["low"]
        top > bottom? → fvg = { top, bottom, midpoint, displacement_idx }
        top <= bottom? → return None (no gap, wicks overlap)
    |
    bias='bearish':
        top    = session_candles[d-1]["low"]
        bottom = session_candles[d+1]["high"]
        top > bottom? → fvg = { top, bottom, midpoint, displacement_idx }
    |
    No FVG? → RETURN None  [early exit: Phase 9a fail, wicks overlap]
```

---

## Phase 9b — FVG Retest Detection

```
[confirmation_entry.py:218–220]
    |
    v
check_fvg_retest(session_candles, fvg, bias, from_idx=di+2)
  [poi_detector.py:81–117]
    |
    Scan from di+2 onwards:
    |
    bias='bullish':
        bar.low <= fvg.top?     (price entered the gap from above)
            bar.close < fvg.bottom? → return None  [INVALIDATED]
            else                     → return i     [RETEST CONFIRMED]
        bar.low > fvg.top?      → continue (price above zone, keep watching)
    |
    bias='bearish':
        bar.high >= fvg.bottom? (price entered the gap from below)
            bar.close > fvg.top? → return None  [INVALIDATED]
            else                  → return i     [RETEST CONFIRMED]
        bar.high < fvg.bottom?  → continue
    |
    End of session_candles without retest? → return None
    |
    FVG invalidated before retest? → RETURN None  [early exit: Phase 9b fail]
    No retest in session window?   → RETURN None  [early exit: Phase 9b fail]
```

---

## Phase 11 — Minimum Bars Remaining

```
[confirmation_entry.py:223–225]
    (Note: Phase 11 evaluated before Phase 10 in code)
    |
    v
bars_remaining = n - 1 - retest_idx
bars_remaining < 2?
    YES → RETURN None  [too close to session end]
    NO  → continue
```

---

## Phase 10 — Risk Parameter Computation

```
[confirmation_entry.py:228–253]
    |
    v
entry = session_candles[retest_idx]["close"]
range_size = sess_range["high"] - sess_range["low"]
wick_ext   = sweep["wick_extreme"]
buf        = sl_buffer_pips * 0.0001   (default 3.0 * 0.0001 = 0.0003)
range_sl_dist = sl_range_pct * range_size  (default 0.25 * range)
    |
    bias='bullish':
        wick_sl  = wick_ext - buf            (below wick, with buffer)
        range_sl = entry - range_sl_dist     (below entry by 25% range)
        sl = max(wick_sl, range_sl)          (tighter = higher price)
        sl >= entry? → RETURN None  [degenerate SL]
        sl_pips = (entry - sl) / 0.0001
        tp1 = entry + 4.0 * sl_pips * 0.0001
        tp2 = entry + 5.0 * sl_pips * 0.0001
        direction = 'long'
    |
    bias='bearish':
        wick_sl  = wick_ext + buf
        range_sl = entry + range_sl_dist
        sl = min(wick_sl, range_sl)          (tighter = lower price)
        sl <= entry? → RETURN None  [degenerate SL]
        sl_pips = (sl - entry) / 0.0001
        tp1 = entry - 4.0 * sl_pips * 0.0001
        tp2 = entry - 5.0 * sl_pips * 0.0001
        direction = 'short'
```

---

## Signal Output

```
[confirmation_entry.py:255–273]
    |
    v
Signal(
    symbol        = symbol,
    direction     = 'long' | 'short',
    entry         = session_candles[retest_idx]["close"],
    sl            = sl,
    tp1           = tp1,
    tp2           = tp2,
    sl_pips       = sl_pips,
    rr            = tp1_r = 4.0,         ← always tp1_r, not actual realized R
    setup_type    = 'A',
    session       = session_name,
    bar_time      = session_candles[retest_idx].get("time"),
    sweep_idx     = si,
    choch_idx     = ci,
    bos_idx       = bi,
    displacement_idx = di,
    retest_idx    = retest_idx,
    session_range = sess_range,
)
    |
    v
RETURN Signal  [all 11 phases passed]
```

---

## Summary: All Early-Exit Conditions

| Gate | Condition | Code Location |
|---|---|---|
| Min bars | n < range_bars + 6 | confirmation_entry.py:117 |
| HTF bias | bias == 'neutral' | confirmation_entry.py:128 |
| D2 Gate A | daily structure conflicts bias | confirmation_entry.py:134 |
| D2 Gate B | price location wrong for trade direction | confirmation_entry.py:144–146 |
| Session range | range None or < 10 pip | confirmation_entry.py:151 |
| D2 Gate C | swept level too far from PDH/PDL | confirmation_entry.py:174–177 |
| Sweep | no sweep found in session | confirmation_entry.py:163 |
| CHoCH | no CHoCH after sweep | confirmation_entry.py:183 |
| BOS level | no prior swing (insufficient history) | structure_detector.py:137 |
| BOS | no break of structure after CHoCH | confirmation_entry.py:197 |
| Displacement | no large candle in [sweep, bos] window | confirmation_entry.py:205 |
| FVG boundary | displacement is last bar | confirmation_entry.py:209 |
| FVG | wicks overlap, no gap | confirmation_entry.py:214 |
| FVG retest | invalidated or no retest in session | confirmation_entry.py:220 |
| Min bars remaining | < 2 bars left in session | confirmation_entry.py:225 |
| Degenerate SL | SL on wrong side of entry | confirmation_entry.py:238–250 |

---

## Module Dependency Graph

```
confirmation_entry.py
    |
    +---------> structure_detector.py
    |                |
    |                +------> swing_detector.py
    |
    +---------> liquidity_detector.py
    |                |
    |                +------> structure_detector.py  (ATR import)
    |
    +---------> poi_detector.py
    |
    +---------> swing_detector.py
    |
    +---------> daily_bias.py
                     |
                     +------> swing_detector.py

daily_context.py  (NOT imported by confirmation_entry.py — standalone module)
    |
    +------> daily_bias.py
    |             |
    |             +------> swing_detector.py
    +------> swing_detector.py
```

---

## Backtest Harness Flow (scripts/backtest.py)

```
main()
    |
    for symbol in [EURUSD, GBPUSD]:
        load M15, H4, H1 CSVs
        |
        Walk M15 bars:
            if bar is session start (London 07:00 / NY 13:00 UTC, weekday):
                extract session window: candles_15m[i : i+20]
                get h4_before: H4 bars with close time <= session_start − 4h (last 200)
                get h1_before: real H1 or M15 proxy (last 200)
                |
                generate_signal_A(symbol, h4, h1, session_window, session_name, config)
                    → Signal or None
                |
                if Signal:
                    _simulate_trade(sig, session_candles, entry_bar, symbol, session)
                        scan bars after entry for SL hit / TP1 hit / session end
                        compute gross_r, net_r_standard, net_r_stress
                        → Trade
                |
                advance i by SESSION_BARS (skip rest of session)
        |
        compute_metrics(trades, "net_r_standard") and ("net_r_stress")
        gate check: n >= 50 AND PF > 1.0 at both
        append to VERDICT_LOG.md
```
