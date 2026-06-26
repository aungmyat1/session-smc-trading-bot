# Strategy: 11-Phase SMC Session Chain (Strategy B / session_smc)

## Version / Status

- **Module version:** No explicit version constant. Inferred from commit history and VERDICT_LOG.
- **Status:** UNVALIDATED — Phase-0 backtest (scripts/backtest_stb.py) has NOT been run.
  The signal chain code is complete and passes 127 unit tests, but no 5-year holdout result
  exists for this chain. VERDICT_LOG ST-B entry reads "PENDING — EXP05 FAIL unlocks this."
- **Trial ID:** ST-B (pre-registered)
- **Prior evidence note:** EXP05 Variant D (CHoCH+BOS gate on ST-A2 displacement window)
  produced 2 signals from 29 candidates (6.9% pass rate). ST-B uses the same confirmation
  chain but entry is at FVG retest, not displacement close. Full-session-window operation
  has never been tested end-to-end on real 5yr data.

---

## Description

A fully AND-gated 11-phase Smart Money Concepts (SMC) signal chain for session-based FX
trading. The chain starts with higher-timeframe bias (4H + 1H swing structure), builds a
session range on 15M bars, waits for a session-level liquidity sweep, then requires
sequential structural confirmation: Change of Character (CHoCH), Break of Structure (BOS),
and a displacement candle that creates a Fair Value Gap (FVG). Entry is at the close of the
first bar that retests the FVG from above (long) or below (short) without invalidating it.

All 11 phases are hard AND-gates. Missing any single phase returns None (no trade).
Optional D2 daily context gates (daily structure, premium/discount location, PDH/PDL
proximity) are overlaid via DEFAULT_CONFIG flags that default to True but can be disabled.

The module is self-contained in `session_smc/` and is not currently wired to any execution
adapter or portfolio runner (see ST_B_RESEARCH_PLAN.md §B.2).

---

## Trading Philosophy

"Wait for smart money to sweep session liquidity, then confirm the reversal on 15M with
structure (CHoCH + BOS) and momentum (displacement + FVG). Enter on the retest — not on
the break." (SIGNAL_SPEC.md)

The hypothesis is that the FVG retest entry, combined with the full structural confirmation
chain (CHoCH + BOS), produces a higher-probability reversal entry than the simpler
ST-A2 chain (sweep + displacement only). EXP05 Variant D confirmed the CHoCH+BOS+FVG layer
is extremely selective (~7% pass rate on ST-A2 signals), making this a high-precision,
low-frequency strategy.

---

## Market / Timeframe / Session / Direction

| Field | Value |
|---|---|
| Instruments | EURUSD, GBPUSD |
| Broker | VT Markets (Standard account) |
| HTF bias | 4H + 1H (swing structure) |
| Execution timeframe | 15M |
| Sessions | London 07:00–10:00 UTC (12 bars) / New York 13:00–16:00 UTC (12 bars) |
| Direction | Long (bullish bias) or Short (bearish bias) — determined by HTF bias |
| Maximum signals | One per session per day |
| Entry type | Bar-close (no lookahead, no limit orders at FVG midpoint in code) |

---

## Signal Chain (phase-by-phase, in execution order)

All phases are evaluated in `generate_signal_A()` in `session_smc/confirmation_entry.py`.

### Stage 0 — D2 Daily Context (optional filter layer, evaluated before Phase 2)

- `build_daily_context(candles_4h, session_start_time, swing_n)` is called once per session.
- Builds D1 candles from H4 data (no separate download). Returns PDH, PDL, daily midpoint,
  and daily swing structure (bullish/bearish/neutral).
- Returns None if fewer than 2 closed daily bars exist; all D2 gates are skipped in that case.

**D2 Gate A** (`d2_structure_gate`, default True):
- Daily swing structure must not conflict with 4H+1H bias.
- Neutral daily structure = no block. Only fires when daily = bearish and bias = bullish, or vice versa.
- Code: `confirmation_entry.py:131–134`

**D2 Gate B** (`d2_location_gate`, default True):
- Session open price must be in discount (bullish trade) or premium (bearish trade)
  relative to PDH/PDL midpoint.
- Code: `confirmation_entry.py:140–146`

**D2 Gate C** (`d2_poi_gate`, default True):
- The swept session level must be within `d2_poi_pips` (default 30.0) of PDL (bullish)
  or PDH (bearish). Evaluated after Phase 5 (sweep known).
- Code: `confirmation_entry.py:169–177`

---

### Phase 1 — Session Active

- Enforced by the caller / backtest orchestrator, not inside `generate_signal_A()`.
- Session candles must be 15M bars from the session window (London or NY).
- Minimum bar count gate: `n >= session_range_bars + 6` (default 14 bars minimum).
- Code: `confirmation_entry.py:117`

---

### Phase 2 — HTF Bias (4H + 1H)

- `htf_bias(candles_4h, candles_1h, swing_n=3)` in `structure_detector.py:17–37`.
- 4H structure computed by `classify_structure(candles_4h, swing_n)`.
- 1H structure computed by `classify_structure(candles_1h, swing_n)`.
- Rules: 4H bullish AND 1H not bearish → 'bullish'; 4H bearish AND 1H not bullish → 'bearish';
  all other combinations → 'neutral' → return None.
- `classify_structure` requires at least 2 confirmed swing highs AND 2 confirmed swing lows
  (needs `2n+1 = 7` bars minimum at swing_n=3). Returns 'neutral' if insufficient history.
- Code: `structure_detector.py:17–37`, `swing_detector.py:93–127`

---

### Phase 3 — Session Range Build

- `build_session_range(session_candles, range_bars=8, min_range_pips=10.0)` in `liquidity_detector.py:19–50`.
- Uses the first `range_bars` (default 8) 15M bars = first 2 hours of the session.
- Computes session High, Low, Midpoint, and range_pips.
- Returns None if: fewer than `range_bars` bars available, or range < `min_range_pips`.
- PIP hardcoded as 0.0001 (EURUSD/GBPUSD).
- Code: `liquidity_detector.py:19–50`

---

### Phase 4 — Session Classification (informational)

- `classify_session(session_candles, session_range, atr_period=14)` in `liquidity_detector.py:55–80`.
- ATR ratio = session range / ATR(14). RANGE if < 0.5; TREND if > 0.7; MIXED otherwise.
- **NOT a hard gate.** Result is assigned to `_sess_class` and discarded. No early return.
- Code: `confirmation_entry.py:155`

---

### Phase 5 — Liquidity Sweep

- `detect_sweep(session_candles, sess_range, bias, from_idx=sweep_start_bar)` in `liquidity_detector.py:85–128`.
- Scans from `sweep_start_bar` (default 8) onwards.
- Bullish: wick below session Low (`c["low"] < s_low`) AND close back above Low (`c["close"] > s_low`).
- Bearish: wick above session High (`c["high"] > s_high`) AND close back below High (`c["close"] < s_high`).
- Returns: `{index, sweep_price, wick_extreme, direction}` or None.
- Code: `liquidity_detector.py:85–128`

---

### Phase 6 — 15M CHoCH (Change of Character)

- `detect_choch(session_candles, sweep_idx, bias, lookback=8)` in `structure_detector.py:78–114`.
- Reference level = max high (bullish) or min low (bearish) of the `lookback` bars immediately
  before the sweep bar. Window: `[max(0, sweep_idx - lookback) : sweep_idx]`.
- CHoCH = first bar after sweep_idx whose close breaks the reference in trade direction.
- Returns: `{index, reference}` or None.
- Code: `structure_detector.py:78–114`

---

### Phase 7 — 15M BOS (Break of Structure)

- BOS level = last confirmed swing high (bullish) or swing low (bearish) from bars before sweep_idx.
- `last_swing_high/last_swing_low(session_candles, swing_n, before_idx=sweep_idx)` in `swing_detector.py`.
- If no prior swing exists (insufficient session history), `bos_level = None` → `detect_bos` returns None → signal fails.
- `detect_bos(session_candles, choch_idx, bias, bos_level)` in `structure_detector.py:119–149`.
- BOS = first bar after choch_idx whose close breaks bos_level in trade direction.
- Returns: `{index, level}` or None.
- Code: `confirmation_entry.py:187–197`, `structure_detector.py:119–149`

---

### Phase 8 — 15M Displacement

- `detect_displacement(session_candles, start_idx, end_idx, bias, atr_vals, atr_mult=1.5)` in `structure_detector.py:154–198`.
- Search window: `[sweep_idx, bos_idx]` inclusive.
- Displacement = first bar with `(high - low) >= atr_mult * ATR(14)` and body in trade direction
  (bullish: close > open; bearish: close < open).
- ATR values are pre-computed via `atr(session_candles, atr_period=14)` in `structure_detector.py:42–73`.
- Skips bars where ATR is NaN (insufficient history, typically first 14 bars).
- Returns: `{index, high, low, open, close}` or None.
- Code: `structure_detector.py:154–198`

---

### Phase 9a — FVG Detection

- `find_fvg(session_candles, displacement_idx, bias)` in `poi_detector.py:36–78`.
- Requires `displacement_idx - 1 >= 0` and `displacement_idx + 1 < n`.
- Bullish FVG: `session_candles[d+1].low > session_candles[d-1].high`. Gap = (d-1 high, d+1 low).
- Bearish FVG: `session_candles[d+1].high < session_candles[d-1].low`. Gap = (d+1 high, d-1 low).
- Returns: `{top, bottom, midpoint, displacement_idx}` or None.
- Code: `poi_detector.py:36–78`

---

### Phase 9b — FVG Retest

- `check_fvg_retest(session_candles, fvg, bias, from_idx=displacement_idx+2)` in `poi_detector.py:81–117`.
- Scans from `displacement_idx + 2` (the bar after the FVG-confirming bar).
- Bullish retest: `bar.low <= fvg.top` (entered zone) AND `bar.close >= fvg.bottom` (held above bottom).
  Invalidated: `bar.close < fvg.bottom` (closed through gap).
- Bearish retest: `bar.high >= fvg.bottom` AND `bar.close <= fvg.top`.
  Invalidated: `bar.close > fvg.top`.
- Returns: index of retest bar, or None (invalid or no retest within session).
- Code: `poi_detector.py:81–117`

---

### Phase 11 — Minimum Bars Remaining

- `bars_remaining = n - 1 - retest_idx`
- Gate: `bars_remaining < min_bars_remaining` (default 2) → return None.
- Note: Phase 11 is evaluated in the code BEFORE Phase 10 (risk params). The numbering follows
  the spec doc but the code ordering is Phase 11 then Phase 10.
- Code: `confirmation_entry.py:223–225`

---

### Phase 10 — Risk Parameters

- Entry = `session_candles[retest_idx]["close"]`
- SL candidates:
  - Wick-based: `wick_extreme - sl_buffer_pips * PIP` (bullish) or `wick_extreme + sl_buffer_pips * PIP` (bearish)
  - Range-based: `entry - sl_range_pct * range_size` (bullish) or `entry + sl_range_pct * range_size` (bearish)
- SL = tighter of the two (max for bullish, min for bearish → closest to entry).
- Degenerate SL gate: if `sl >= entry` (bullish) or `sl <= entry` (bearish) → return None.
- TP1 = entry ± `tp1_r * sl_pips * PIP` (default 4R)
- TP2 = entry ± `tp2_r * sl_pips * PIP` (default 5R)
- Code: `confirmation_entry.py:228–253`

---

## Entry Rules

- Entry is at the **close of the FVG retest bar** (bar-close, no lookahead).
- One entry per session (enforced by caller; `generate_signal_A` returns the first valid signal).
- Entry direction: 'long' (bullish bias) or 'short' (bearish bias).
- No pending-order entry at FVG midpoint (the Signal.entry field is the retest bar close).

---

## Confirmation Rules

All 11 phases must pass. In code order:
1. Sufficient bars (n >= range_bars + 6)
2. HTF bias not neutral
3. D2 Gate A (daily structure alignment) — if D2 context available
4. D2 Gate B (price location) — if D2 context available
5. Session range built and wide enough
6. Sweep detected from bar 8 onwards
7. D2 Gate C (swept level near PDH/PDL) — if D2 context available
8. CHoCH detected after sweep
9. BOS detected after CHoCH (requires prior swing history)
10. Displacement detected in [sweep, bos] window
11. FVG exists on displacement bar
12. FVG retest occurs without invalidation
13. Min bars remaining >= 2
14. SL is on the correct side of entry (degenerate SL check)

---

## Exit Rules (TP / SL / BE / Trailing / Partial)

Defined in Signal dataclass fields and documented in CLAUDE.md §4 / SIGNAL_SPEC.md.
The signal chain computes exit levels; execution is handled by the caller.

| Exit | Level | Rule |
|---|---|---|
| TP1 | entry ± 4R (default tp1_r=4.0) | Close 75% of position; move SL to breakeven |
| TP2 | entry ± 5R (default tp2_r=5.0) | Trail remaining 25%; close at session end if still open |
| SL | sl field in Signal | Full close |
| Session end | Last session bar close | Close any open remainder at market (no overnight) |
| Breakeven | After TP1 hit | SL moves to entry price (enforced by execution layer, not this module) |

Note: The partial-close TP1/TP2 split and BE logic are not implemented in `confirmation_entry.py`.
They are specified in CLAUDE.md §4 and ST_B_RESEARCH_PLAN.md §A.4 but have no execution code.
The backtest runner (scripts/backtest.py) simulates full close at TP1 only (no partial-close).

---

## Filters (Spread / Volatility / Session / News)

| Filter | Status | Implementation |
|---|---|---|
| Spread filter | Specified in config/demo.yaml (max_spread_pips) but NOT checked inside session_smc/ | Not enforced in signal chain |
| Volatility (ATR) | ATR used for displacement detection and session classification | Enforced in Phase 8 |
| Session time | Enforced by caller; session_smc/ itself has no clock check | Phase 1 in spec |
| Session range width | Min 10 pips (Phase 3) | Enforced |
| Min bars remaining | >= 2 bars before session end (Phase 11) | Enforced |
| News filter | Mentioned in CLAUDE.md §7 alerts; no code in session_smc/ | NOT enforced |
| Weekday filter | Weekend skip in scripts/backtest.py; not in session_smc/ | External only |
| Min SL pips | NOT in DEFAULT_CONFIG (see Known Limitations) | NOT enforced in module |

---

## Kill Switch / Safety

The `session_smc/` module does not contain circuit breaker or kill switch logic. It is a
signal generator only. Safety controls are in `execution/risk_manager.py` and
`execution/demo_risk_manager.py`, which are not called by this module.

Risk controls (from execution layer, not session_smc):
- `max_daily_loss_r`: halts on breach (circuit breaker, state persisted to `logs/bot_state.json`)
- `max_weekly_loss_r`: weekly halt
- `max_consecutive_losses`: halt until next day
- Kill switch (10% drawdown from peak): requires manual `KILL_SWITCH_OVERRIDE=true` in `.env`

None of these are enforced within `session_smc/`. The module can generate signals regardless
of account state. Integration with risk manager requires the execution adapter layer.

---

## Known Limitations

1. **No backtest result.** ST-B has never been run on 5yr data. Signal chain is untested at scale.
   EXP05 Variant D found ~7% pass rate on ST-A2 signals — 5yr trade count likely 10–60 total.

2. **min_sl_pips absent from DEFAULT_CONFIG.** ST_B_RESEARCH_PLAN.md §E.5 explicitly notes this.
   ST-A2's min_sl_pips=5.0 gate is applied externally in the backtest runner but is not inside
   the signal chain. Signals with SL < 5 pip are not rejected by the module.

3. **No session-scope swing history.** Phase 7 BOS uses only session_candles (bars from session
   open). Early sweeps (bar 8–10) may have insufficient swing history, causing Phase 7 to fail.
   ST_B_RESEARCH_PLAN.md §E.4 documents this as a known architecture issue.

4. **PIP hardcoded for EURUSD/GBPUSD.** `liquidity_detector.py:14` has `PIP: float = 0.0001`.
   Adding JPY pairs or other pip-size instruments requires a parameter change.

5. **Phase numbering mismatch.** In `confirmation_entry.py`, Phase 11 (min_bars_remaining) is
   evaluated before Phase 10 (risk params), contrary to the spec document numbering.

6. **Partial-close not implemented.** The Signal dataclass has only tp1 and tp2 fields. The
   75%/25% partial-close logic is in the spec but not in the signal chain or any backtest runner
   for this module. `scripts/backtest.py` uses full close at TP1 only.

7. **D2 gates default True but trial history shows they are over-restrictive.** ST-D2-6M and
   TRIAL_ST_A2_D1_001 both show D2/D1 gates filtering 68–100% of signals with degraded PF.
   Having them default True in DEFAULT_CONFIG for an unvalidated module is a risk.

8. **Session classification result silently discarded.** Phase 4 computes RANGE/TREND/MIXED
   but the result is not used, not logged, and not exposed in the Signal dataclass.

9. **No execution adapter.** Unlike ST-A2 (which has `strategies/adapters/st_a2_adapter.py`),
   the `session_smc/` chain has no portfolio adapter. It cannot be connected to `run_portfolio.py`
   without writing one.

---

## Dependencies (modules, external)

### Internal module dependencies

```
confirmation_entry.py
  → structure_detector.py      (htf_bias, atr, detect_choch, detect_bos, detect_displacement)
  → liquidity_detector.py      (build_session_range, classify_session, detect_sweep)
  → poi_detector.py            (find_fvg, check_fvg_retest)
  → swing_detector.py          (last_swing_high, last_swing_low, classify_structure)
  → daily_bias.py              (build_daily_context, classify_location)
      → swing_detector.py      (classify_structure)
  (daily_context.py is NOT imported by confirmation_entry.py — separate module)
```

### External dependencies

- Python stdlib only: `dataclasses`, `typing`, `datetime`, `math`
- No third-party packages required for signal generation
- Data format: `list[dict]` with keys `time`, `open`, `high`, `low`, `close`

### Caller requirements

- Must supply: `candles_4h`, `candles_1h`, `session_candles` (pre-sliced to session window),
  `session_name` ('london' | 'newyork'), `symbol`, optional `config` dict.
- Must enforce session boundaries (Phase 1) before calling.
- Must enforce `min_sl_pips` floor after receiving Signal (not inside module).
- Must implement partial-close and BE logic in execution layer.
