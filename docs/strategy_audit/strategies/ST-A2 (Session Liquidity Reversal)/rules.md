# Rules: ST-A2 (Session Liquidity Reversal)

Rules are listed in execution order (the order they are evaluated in run_strategy()).

---

## Rule 1 — Sort and Pre-compute ATR

**Purpose:** Ensure chronological order and pre-compute ATR across full history in one pass.

**Inputs:**
- candles_m15: unsorted list of M15 bar dicts with keys time, high, low, open, close.
- atr_period: int (default 14).

**Output:**
- sorted_m15: list sorted by candle["time"].
- atr_map: dict mapping candle["time"] → float|None, one entry per bar.

**Code location:** session_strategy.py:run_strategy():82-84

**Failure modes:**
- If candles_m15 is empty, returns empty signals immediately (line 78-79).
- ATR is None for the first atr_period bars (indices 0..13 with default period=14). Displacement
  detection on those bars will return DisplacementResult(detected=False, reason='atr_unavailable').
- If candle["time"] keys are not comparable (mixed str/datetime types), sort may raise TypeError.
  The _utc() helper normalises times inside classify_session but atr_map uses raw candle["time"]
  as the key; lookup will fail if types differ between sorted_m15 and atr_map keys.

---

## Rule 2 — Pre-group Killzone Bars by Date

**Purpose:** Avoid O(n_bars × n_days) re-scanning. Each bar is classified once into its date bucket.

**Inputs:**
- sorted_m15: sorted M15 bars.
- classify_session(): returns 'london', 'new_york', or None.

**Output:**
- _kz_by_date: dict mapping date → list of (candle, session_str) tuples.
- trade_dates: sorted list of unique EST calendar dates with at least one killzone bar.

**Code location:** session_strategy.py:run_strategy():88-95

**Failure modes:**
- Bars outside killzones (classify_session returns None) are silently excluded. Days with no
  killzone bars will not appear in trade_dates and will not be processed at all.
- If candle["time"] cannot be parsed by _utc(), datetime.fromisoformat raises ValueError.
  No try/except here; propagates as unhandled exception.

---

## Rule 3 — Asian Range Build (Phase 1)

**Purpose:** Establish the daily Asian session high and low that define the liquidity sweep levels.

**Inputs:**
- sorted_m15: all M15 bars.
- trade_date: current EST calendar date being processed.

**Output:**
- AsianRange(trade_date, high, low) or None.

**Code location:** session_strategy.py:run_strategy():100-102; session_builder.py:build_asian_range():45-82

**Failure modes:**
- Returns None if fewer than 4 Asian bars are found for the date. Day is skipped entirely.
- Asian window is defined by EST hour: prev_day hour >= 18 OR curr_day hour < 2. DST changes
  the UTC equivalent but EST-hour logic is DST-safe via zoneinfo. However, the window is
  fixed; it does not adjust for non-standard market hours or partial sessions.
- AsianRange.range_pips uses 0.0001 as pip divisor. Correct for 5-decimal FX; wrong for JPY pairs
  or 2-decimal instruments.

---

## Rule 4 — Minimum Asian Range Filter (Phase 4)

**Purpose:** Skip days where the Asian range is too narrow for the strategy to clear fees.

**Inputs:**
- asian.range_pips: float.
- min_range_pips: dict keyed by normalised symbol (EURUSD or GBPUSD).
- min_range: float = cfg["min_range_pips"].get(_norm(symbol), 15.0). Falls back to 15.0 for
  unknown symbols.

**Output:**
- Continue or skip day.

**Code location:** session_strategy.py:run_strategy():106-108

**Failure modes:**
- If symbol is not 'EURUSD' or 'GBPUSD', the 15.0 pip fallback is used (not GBPUSD's 20.0).
  Symbol normalisation via _norm() strips slashes and underscores and upcases.
- Range filter runs before killzone loop; a day with a narrow Asian range but a valid later
  sweep opportunity is correctly skipped entirely.

---

## Rule 5 — One Trade Per Session (Phase 10)

**Purpose:** Prevent multiple signals in the same session on the same day.

**Inputs:**
- session_traded: set of session strings already signalled today.
- session: current bar's session string.

**Output:**
- Continue or skip bar.

**Code location:** session_strategy.py:run_strategy():124-125

**Failure modes:**
- session_traded is reset per trade_date (per day loop iteration). Correct behaviour.
- If two bars at the exact same time both classify as the same session (degenerate input),
  only the first will produce a signal; the second will be blocked correctly.

---

## Rule 6 — Pending Sweep Session Change Cancel

**Purpose:** Prevent a sweep found in one session from being matched with displacement in another session.

**Inputs:**
- pending: dict with session key from the bar that found the sweep.
- session: current bar's session.

**Output:**
- Cancel pending (set to None) if sessions differ.

**Code location:** session_strategy.py:run_strategy():129-132

**Failure modes:**
- Only checks when pending is not None. If pending is None, this rule is a no-op.
- Session change is detected correctly as long as classify_session() is deterministic for a given UTC time.

---

## Rule 7 — 4H HTF Bias Gate (Phase 2)

**Purpose:** Ensure no trades are taken against the prevailing 4H trend structure.

**Inputs:**
- candles_4h: full list of 4H bars.
- bar_time: UTC datetime of current M15 bar.
- swing_n: 2 (hardcoded default; not in config).

**Output:**
- bias: 'bullish' | 'bearish' | 'neutral'.
- If 'neutral': skip bar.

**Code location:** session_strategy.py:run_strategy():135; bias_filter.py:htf_bias():77-128

**Failure modes:**
- htf_bias is called for EVERY killzone bar, including when a sweep is pending. This is
  correct (bias re-evaluated each bar) but potentially expensive for large datasets.
- If candles_4h is empty or shorter than 2*swing_n+1 bars, returns 'neutral' immediately.
- Strict inequality means equal consecutive swing highs/lows yield 'neutral', not bullish/bearish.
  This is by design but may filter valid setups in tight-range 4H structure.
- cutoff = before_dt - timedelta(hours=4) is computed from the M15 bar open time, not its close
  time. The M15 bar close = open + 15min. Using M15 open is conservative (excludes the partially
  formed 4H bar correctly); this is not lookahead.

---

## Rule 8 — Liquidity Sweep Detection (Phase 5)

**Purpose:** Identify a candle that sweeps the Asian range and closes back inside, in the direction of bias.

**Inputs:**
- candle: current M15 bar dict.
- asian.high, asian.low: float.
- bias: 'bullish' or 'bearish'.

**Output:**
- SweepResult(detected=True, side, sweep_price, reason) or SweepResult(detected=False, ...).
- If detected: set as pending sweep.

**Code location:** session_strategy.py:run_strategy():144-153; sweep_detector.py:detect_sweep():44-121

**Failure modes:**
- Only called when no sweep is pending. Correct; prevents double-pending.
- Only called when bias != 'neutral'. Enforced at Rule 7.
- Bullish sweep sweep_price = candle.low (the wick low that pierced asian_low).
- Bearish sweep sweep_price = candle.high (the wick high that pierced asian_high).
- Both wick breach and close-back must use strict inequality. Touch events are rejected.
- If candle has both low < asian_low AND high > asian_high (engulfing the full range), only the
  bias-matched direction is evaluated. The other direction is ignored, not an error.
- detect_sweep has a try/except for KeyError/TypeError/ValueError on candle field access (line 67-74).
  Returns invalid_candle reason on failure.

---

## Rule 9 — Displacement Timeout Check

**Purpose:** Cancel a pending sweep if displacement has not appeared within the timeout window.

**Inputs:**
- bars_since: bar_idx - pending["bar_idx"].
- timeout: sweep_timeout_bars (default 4).

**Output:**
- Cancel pending if bars_since > timeout.

**Code location:** session_strategy.py:run_strategy():157-163

**Failure modes:**
- bars_since is counted in killzone bars (bars that appear in _kz_by_date), not calendar time.
  Non-killzone bars between sweep and displacement are not counted. This is the intended behaviour.
- Timeout is strictly greater than: a displacement on bar_idx + 4 (bars_since==4) is still accepted;
  bars_since==5 triggers cancellation. From the code: `if bars_since > timeout`. With timeout=4,
  bars_since=4 passes (4 > 4 is False).

---

## Rule 10 — Displacement Detection (Phase 6)

**Purpose:** Confirm institutional rejection candle after the sweep.

**Inputs:**
- candle: current M15 bar.
- atr: Wilder ATR(14) from atr_map for this bar's time.
- direction: pending sweep side ('long' or 'short').
- mult: displacement_mult (default 1.2).

**Output:**
- DisplacementResult(detected=True, side, body_size, atr, close_position, reason) or False.

**Code location:** session_strategy.py:run_strategy():165-166; displacement_detector.py:detect_displacement():107-209

**Failure modes:**
- atr_map lookup uses candle["time"] as key. If the time type differs from the key stored at
  sort time (e.g., one is datetime and the other is str), atr returns None. This causes
  atr_unavailable reason and displacement is not detected, silently missing valid setups.
- atr=0 → atr_zero rejection. Prevents division, but a zero ATR implies flat-line data (unusual).
- candle_range=0 → zero_range_candle rejection. Correct guard.
- If direction is neither 'long' nor 'short': returns unknown_direction reason (detected=False).

---

## Rule 11 — Signal Construction (Phases 7-9)

**Purpose:** Build the Signal dataclass from confirmed sweep and displacement.

**Inputs:**
- candle: displacement candle (entry from close).
- sweep: SweepResult (detected=True).
- displacement: DisplacementResult (detected=True).
- asian: AsianRange.
- session: 'london' or 'new_york'.
- rr: float (from config, default 3.0).
- sl_buf: sl_buffer_pips (default 2.0).

**Output:**
- Signal dataclass or None.

**Code location:** session_strategy.py:run_strategy():170-173; entry_engine.py:build_signal():52-171

**Failure modes:**
- Returns None on any of 8 guard failures: sweep not detected, displacement not detected,
  invalid session, asian_range degenerate, rr <= 0, sl_buffer_pips < 0, candle missing 'close',
  or risk <= 0 (degenerate SL geometry).
- SL is placed at sweep_price ± sl_buffer_pips × 0.0001. No maximum SL check here (RISK_SPEC.md
  specifies 50pip max but this is not enforced in build_signal or session_strategy.py).
- Timestamp falls back to datetime.now(_UTC) if candle["time"] is None or unparseable.
  This means the signal timestamp may not match the actual bar time on data quality issues.

---

## Rule 12 — Minimum SL Filter (ST-A2 gate)

**Purpose:** Reject signals where the sweep wick is too small for the trade to clear fees at 2x stress.

**Inputs:**
- sig.risk_pips: float (computed in build_signal).
- min_sl_pips: float (default 5.0).

**Output:**
- Append signal to signals list (and mark session_traded) if risk_pips >= min_sl_pips.
- Reject (log SIGNAL_REJECTED event) if risk_pips < min_sl_pips.

**Code location:** session_strategy.py:run_strategy():178-188

**Failure modes:**
- This is a post-build filter, not a pre-build guard. build_signal() is called and returns a
  Signal object; then the Signal's risk_pips is checked. Minor inefficiency (builds a Signal
  that is then discarded) but no correctness issue.
- If build_signal returns None (Rule 11 failure), Rule 12 is not reached (None check at line 175).

---

## Rule 13 — Adapter Translation (ST2Adapter.generate_signal)

**Purpose:** Translate the latest session_liquidity.Signal into a canonical core.Signal.

**Inputs:**
- data dict: { symbol, m15 (list of M15 bar dicts), h4 (list of 4H bar dicts), config (optional) }.

**Output:**
- core.Signal or None.

**Code location:** strategies/adapters/st_a2_adapter.py:ST2Adapter.generate_signal():24-78

**Failure modes:**
- If len(m15) < 50, returns None immediately without calling run_strategy (line 50-51).
  The 50-bar threshold is hardcoded and undocumented.
- Only the last signal from run_strategy is returned (raw_signals[-1]). If multiple signals
  are generated (one per session), only the most recent is surfaced.
- risk_percent is hardcoded as 0.25 (0.25% of account). RISK_SPEC.md specifies 1%.
- If import of session_strategy fails (ImportError), returns None silently (line 42-43).
  The caller will see no signal and no error. Silent failure.
- timestamp is set to datetime.now(timezone.utc) at the time of adapter call, not the
  displacement candle timestamp. This may differ from the signal's internal timestamp.
  The original Signal.timestamp (bar close time) is not forwarded to core.Signal.
# ST-A2 Rules

## Entry Rules

- Build the Asian range from completed M15 candles.
- Skip the day if the Asian range is missing.
- Skip the day if the Asian range is below the minimum range threshold.
- Require a non-neutral H4 bias.
- Require a strict wick breach of the Asian high or low.
- Require a close back inside the range in the direction of the bias.
- Require a displacement candle within `sweep_timeout_bars`.
- Reject the signal if the stop distance is below `min_sl_pips`.

## Invalidation Rules

- The sweep is cancelled when the session changes before displacement appears.
- Only one signal per session is allowed inside a calendar day.
- The signal is rejected when `build_signal()` returns `None`.

## Geometry Rules

- Long stop is placed below the sweep wick minus the buffer.
- Short stop is placed above the sweep wick plus the buffer.
- TP is computed from the configured RR and the stop distance.
