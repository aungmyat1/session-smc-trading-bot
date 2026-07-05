# Lookahead Audit — ST-A Strategy
# 2026-06-20 | Pre-backtest gate

Scope: every module that touches candle data in the signal chain + backtest engine.
Verdict per check: **PASS** | **WARN** | **FAIL**

---

## §1 — Audit Checklist

| # | Check | Result |
|---|-------|--------|
| 1 | Swing detection uses only closed bars | PASS |
| 2 | Swing confirmation requires n right-side bars to close | PASS |
| 3 | HTF bias uses only bars closed before session open | PASS* |
| 4 | H4 bars excluded if close time > session open | **FAIL → FIXED** |
| 5 | Session range uses only first range_bars (not full session) | PASS |
| 6 | Sweep detection uses bar's own OHLC (no future bar) | PASS |
| 7 | CHoCH reference built from bars before sweep only | PASS |
| 8 | BOS level uses swing confirmed before sweep | PASS |
| 9 | Displacement bounded by [sweep_idx, bos_idx] | PASS |
| 10 | FVG candles[d+1] is closed before retest starts | PASS |
| 11 | FVG retest scan starts at d+2 (d+1 already closed) | PASS |
| 12 | Entry = close of retest bar (bar-close, never bar-open) | PASS |
| 13 | Exit simulation starts at entry_bar+1 (no same-bar fill) | PASS |
| 14 | Walk-forward is strictly chronological (no future sessions) | PASS |
| 15 | No pandas / numpy shift(-1) or rolling lookahead | PASS (pure Python) |
| 16 | SESSION_BARS allows signal chain to complete | **FAIL → FIXED** |
| 17 | 1H bias context excludes current/future bars | PASS (fidelity WARN) |
| 18 | Session classification (informational) uses full session ATR | WARN |

---

## §2 — Module-by-Module Findings

---

### `session_smc/swing_detector.py` — PASS

**swing_highs / swing_lows**
```python
for i in range(n, len(highs) - n):
    if all(highs[i-j] < h ...) and all(highs[i+j] < h ...):
```
- Loop range `[n, len-n)` ensures n right-side bars exist in the slice.
- Callers pass a slice that ends at the known horizon (e.g. `candles[:sweep_idx]`).
- The most recent confirmable swing is at index `len-n-1` — correctly requires n future closed bars before confirming.

**last_swing_high / last_swing_low**
```python
limit = before_idx if before_idx is not None else len(candles)
idxs = swing_highs(candles[:limit], n)
```
- `before_idx` is EXCLUSIVE upper bound. Candle at `before_idx` is never accessed.

**classify_structure**
- Delegates to `swing_highs` / `swing_lows` on a pre-sliced subset. No independent data access.

**Verdict: PASS — no lookahead.**

---

### `session_smc/structure_detector.py` — PASS

**atr()**
```python
tr[0] = candles[0].high - candles[0].low          # no prior close for bar 0
tr[i] = max(h-l, |h-prev_close|, |l-prev_close|)  # uses candles[i-1].close only
result[period] = mean(tr[1:period+1])              # seed = past bars
result[i] = (result[i-1] * (period-1) + tr[i]) / period
```
- Strictly causal. ATR[i] depends only on candles[0..i]. No forward look.

**detect_choch()**
```python
window = candles[max(0, sweep_idx - lookback) : sweep_idx]  # exclusive of sweep bar
reference = max(c["high"] for c in window)
for i in range(sweep_idx + 1, len(candles)):                  # starts AFTER sweep
    if candles[i]["close"] > reference: return ...
```
- Reference built entirely from bars before sweep. Scan starts at sweep+1.
- PASS — no access to bars before sweep in the scan; no future reference.

**detect_bos()**
```python
for i in range(after_idx + 1, len(candles)):
    if candles[i]["close"] > swing_level: return ...
```
- `after_idx` = CHoCH index. Scan starts at CHoCH+1.
- `swing_level` was set by `last_swing_high(before_idx=sweep_idx)` — purely historical.

**detect_displacement()**
```python
for i in range(start_idx, min(end_idx + 1, len(candles))):
```
- `start_idx = sweep_idx`, `end_idx = bos_idx`. Bounded window, no bar beyond BOS.

**Verdict: PASS — all chronologically anchored.**

---

### `session_smc/liquidity_detector.py` — PASS (WARN on classify_session)

**build_session_range()**
```python
bars = candles[:range_bars]   # first 8 bars only
```
- Hardcoded slice. Never touches bars after position 7.

**detect_sweep()**
```python
for i in range(from_idx, len(candles)):
    c = candles[i]
    if c["low"] < s_low and c["close"] > s_low: return ...
```
- Each bar evaluated at its own CLOSE. First occurrence returned immediately.
- No future-bar reference. PASS.

**classify_session()** — WARN (informational only)
```python
atr_vals = compute_atr(candles, atr_period)  # uses ALL candles passed
```
- In the backtest, `candles` = full 20-bar session window including bars after potential entry.
- Session ATR includes bars the strategy hasn't processed yet at entry time.
- **Impact: NONE** — `classify_session` is called at Phase 4, flagged as "informational, not a hard gate" in `confirmation_entry.py:123`. It does not determine whether a signal fires.
- In live trading, this function would naturally only see bars up to the current moment.

**Verdict: PASS overall. WARN on classify_session (advisory use only, not gate).**

---

### `session_smc/poi_detector.py` — PASS

**find_fvg()**
```python
prev_c = candles[d - 1]    # bar before displacement
next_c = candles[d + 1]    # bar after displacement  ← potential concern
```
- `candles[d+1]` is the "FVG confirming bar" — required to define the gap.
- Is this lookahead? **No.** The retest scan starts at `d+2`:
  ```python
  retest_idx = check_fvg_retest(session_candles, fvg, bias, di + 2)
  ```
  At retest time `t ≥ d+2`, bar `d+1` has already closed. The FVG zone
  (`bottom=candles[d-1].high`, `top=candles[d+1].low`) was observable the moment
  bar `d+1` closed — which is before any entry decision is made.
- Guard in `confirmation_entry.py:163`: `if di + 1 >= n: return None` ensures
  bar `d+1` exists in the slice before `find_fvg` is called.

**check_fvg_retest()**
```python
for i in range(from_idx, len(candles)):  # from_idx = di + 2
```
- Forward-only scan from di+2. Each bar evaluated at its own OHLC. PASS.

**Verdict: PASS — FVG uses d+1 which is always closed before entry.**

---

### `session_smc/confirmation_entry.py` — PASS

Signal chain ordering (strictly chronological):
```
range_bars[0:8]         ← Phase 3: session range (past)
sweep at si ≥ 8        ← Phase 5: first sweep found
choch at ci > si       ← Phase 6: first CHoCH after sweep
bos_swing before si    ← Phase 7a: swing from session open range
bos at bi > ci         ← Phase 7b: first BOS after CHoCH
disp in [si, bi]       ← Phase 8: first displacement
d+1 in candles         ← Phase 9a guard
retest at ri ≥ di+2    ← Phase 9b: first retest after FVG confirm
entry = candles[ri].close   ← bar-close fill, no intrabar
```
- Every phase anchor is strictly ≥ the previous. No backward jumps.
- Entry uses `retest_idx`, and by the time it's identified, all prior bars
  (sweep, CHoCH, BOS, displacement, FVG-confirming) have closed.
- `sl = max(wick_sl, range_sl)` and TP derived from `entry` — no future data.

**Verdict: PASS — signal chain is fully causal. Entry is bar-close.**

---

### `scripts/backtest.py` — FIXED (2 bugs)

#### Bug 1 — H4 Incomplete Bar Lookahead (CRITICAL) → **FIXED**

**Before fix:**
```python
result = [c for c in candles_4h_sorted if c["time"] < before_time]
```

**Problem:** At London open (07:00Z), this includes the H4 bar starting at 04:00Z.
That bar's CLOSE time is 08:00Z — it was still forming when London opened.
Same issue at NY open (13:00Z) including H4 12:00Z bar (closes 16:00Z).

Consequence: HTF bias was computed using an incomplete H4 bar, potentially
reflecting price action that hadn't happened yet at the signal decision point.

**After fix (line ~117):**
```python
cutoff_dt = datetime.fromisoformat(before_time.replace("Z", "+00:00")) - timedelta(hours=4)
cutoff = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
result = [c for c in candles_4h_sorted if c["time"] <= cutoff]
```

Now at London 07:00Z: cutoff = 03:00Z → last H4 included = 00:00Z bar
(which closes at 04:00Z, well before London open). ✓

At NY 13:00Z: cutoff = 09:00Z → last H4 included = 08:00Z bar
(which closes at 12:00Z, before NY open). ✓

---

#### Bug 2 — SESSION_BARS Too Short to Generate Signals (CRITICAL) → **FIXED**

**Before fix:**
```python
SESSION_BARS = 12   # 3 hours
```

**Problem:** `generate_signal_A` minimum check:
```python
if n < range_bars + 6:   # 8 + 6 = 14
    return None
```
With `n = SESSION_BARS = 12 < 14`, this gate **always fired**. Zero trades
would ever be generated. The backtest would silently return n=0, which fails
the gate (n < 50) trivially and gives no signal-quality information.

**After fix:**
```python
SESSION_BARS = 20   # 5 hours — 8 range bars + 12 bars for signal chain
```

Rationale:
- London 07:00Z signal window extended to 12:00Z (signal chains often complete 1-2h after range)
- NY 13:00Z extended to 18:00Z
- 20-bar window gives 20-8=12 bars for sweep→CHoCH→BOS→disp→FVG→retest
- No cross-contamination: London ends at 12:00 before NY starts at 13:00 ✓
- Consistent with test data in `build_bullish_session()` which uses 20 bars

---

#### WARN — 1H Context Uses M15 Bars as Proxy

```python
candles_1h_ctx = candles_15m[max(0, i - 200):i]  # M15 bars before session
```

- **Not lookahead**: `[:i]` excludes the current session open bar. All included bars are closed. ✓
- **Fidelity issue**: `classify_structure(candles_1h_ctx, swing_n=3)` runs swing detection on M15 bars. A swing high confirmed over 3 M15 bars (45 min) is structurally different from a 1H swing high confirmed over 3 H1 bars (3 hours). This may over-confirm or under-confirm bias.
- **Mitigation**: Download H1 data via `fetch_data.py --granularities M15 H4 H1` before running the backtest. Update `backtest.py` to use `EUR_USD_H1.csv` and `GBP_USD_H1.csv` for the 1H bias.

---

## §3 — Verdict Summary

| Module | Lookahead | Status |
|--------|-----------|--------|
| `swing_detector.py` | None found | ✅ PASS |
| `structure_detector.py` | None found | ✅ PASS |
| `liquidity_detector.py` | classify_session advisory only | ✅ PASS (⚠ WARN) |
| `poi_detector.py` | FVG d+1 confirmed before entry | ✅ PASS |
| `confirmation_entry.py` | Fully causal, bar-close entry | ✅ PASS |
| `backtest.py` | H4 incomplete bar (fixed) | ✅ PASS after fix |
| `backtest.py` | SESSION_BARS zero-trade bug (fixed) | ✅ PASS after fix |

**Overall: PASS — backtest is ready to run with no known lookahead bias.**

---

## §4 — Remaining Before Backtest

1. **Obtain OANDA credentials** — add `OANDA_API_KEY` and `OANDA_ACCOUNT_TYPE=practice` to `.env`
2. **Download H1 data** — add `H1` to `fetch_data.py` run, update backtest to use `EUR_USD_H1.csv`
3. **Run Stage C1**: `python3 scripts/fetch_data.py --granularities M15 H4 H1`
4. **Run DATA_AUDIT** — verify no gaps, no duplicates, UTC consistency
5. **Run Stage C2**: `python3 scripts/backtest.py`
6. **Run PERFORMANCE_AUDIT** — break down by year / month / session

**Gate: n ≥ 50 AND PF > 1.0 at standard AND 2× spread stress, for each symbol independently.**
