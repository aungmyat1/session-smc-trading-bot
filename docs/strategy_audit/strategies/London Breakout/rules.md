# Rules: London Breakout

Every rule in execution order. Each entry documents purpose, inputs, output, code
location, and failure modes.

---

## Rule 1 — Minimum Bar Count Guard (Adapter)

**Purpose:** Prevent strategy execution when insufficient M15 history is available.
**Inputs:** `len(data["m15"])` — count of M15 candle dicts in the feed payload.
**Output:** Returns `None` (no signal) if bar count < 30.
**Code location:** `strategies/adapters/london_breakout_adapter.py:generate_signal:36`
**Failure modes:**
- Rule is checked before calling the strategy; if passed, the strategy internally may
  still find 0 Asian bars if the 30 bars don't cover 00:00–06:00 UTC (no error raised,
  `_build_asian_range` returns None → empty signal list).
- Portfolio runner independently enforces a stricter 50-bar minimum
  (`run_portfolio.py:195`); the adapter's 30-bar rule can never be the binding constraint
  in that path.

---

## Rule 2 — Asian Range Construction

**Purpose:** Define the consolidation range that the breakout must breach.
**Inputs:** All M15 candle dicts where `00 <= utc_hour(candle) < 06` (UTC).
**Output:** `{"high": float, "low": float}` or `None` if no bars fall in window.
**Code location:** `adaptive/strategies/london_breakout_strategy.py:_build_asian_range:54-61`
**Failure modes:**
- If `candle["time"]` is missing or not a parseable ISO string or `datetime`, `_utc_hour`
  returns `-1`, and that candle is excluded from the Asian set. Silent exclusion — no
  warning logged.
- If candles are not chronologically ordered, correctness is unaffected (max/min over
  all qualifying bars).
- If the input dataset starts mid-session (e.g., only covers 03:00–09:00 UTC), only
  bars from 03:00–05:45 form the range. The range will be underestimated.

---

## Rule 3 — Asian Range Validation

**Purpose:** Ensure the Asian range is wide enough to cover fees and narrow enough to
indicate genuine consolidation. Too-narrow ranges produce undersized risk/reward;
too-wide ranges indicate a trending Asian session unsuitable for breakout trading.
**Inputs:** `asian_high`, `asian_low`, pip size for the symbol.
**Output:** Continues processing if `15.0 <= range_pips <= 50.0`; returns `[]` otherwise.
**Code location:** `adaptive/strategies/london_breakout_strategy.py:generate_signals:93-95`
**Failure modes:**
- If `pip` is 0.0 (unknown symbol fallback), `range_pips` will be infinite →
  validation always fails. The strategy returns `[]` silently.
- YAML values (`adaptive_engine.yaml` lines 40-41) are never read by the strategy;
  the code uses hardcoded constants. Editing the YAML has no effect.

---

## Rule 4 — London Bar Filter

**Purpose:** Skip all candles outside the London session; only breakout candles during
London open hours are valid.
**Inputs:** UTC hour of each candle.
**Output:** Boolean — True if `06 <= utc_hour <= 09`.
**Code location:** `adaptive/strategies/london_breakout_strategy.py:_is_london_bar:68-69`
**Failure modes:**
- The inclusive upper bound (`<= 09`) means the 09:00 UTC candle (09:00–09:15) is
  included. If the London session is defined as ending at 09:00, the 09:00 bar
  technically belongs to post-London. This is a boundary edge case.
- `_utc_hour` returning -1 for unparseable timestamps causes that candle to be excluded
  (−1 does not satisfy the window condition).

---

## Rule 5 — Breakout Detection

**Purpose:** Identify the first candle during London where price closes decisively
outside the Asian range.
**Inputs:** `candle["close"]`, `asian_high`, `asian_low`.
**Output:** Sets `breakout_direction = "LONG"` or `"SHORT"` and records `breakout_bar`.
  Advances to the next candle (does not emit a signal on the breakout bar itself).
**Code location:** `adaptive/strategies/london_breakout_strategy.py:generate_signals:111-117`
**Failure modes:**
- Only the first qualifying breakout is tracked. If LONG breakout occurs and no retest
  follows, then a subsequent SHORT breakout in the same session is never detected
  (state is stuck on LONG until a retest or session end).
- Breakout detection uses `close > ah` (strictly greater). A close exactly at the
  Asian High does not trigger. This is correct but undocumented.
- `breakout_bar` is recorded but never used in signal construction; it is dead state.

---

## Rule 6 — Retest Zone Check (LONG)

**Purpose:** Confirm that price has pulled back to the broken Asian High before entry,
filtering out immediate continuation moves where chasing would be high-risk.
**Inputs:** `candle["low"]`, `asian_high`, pip size.
**Output:** Triggers entry if `(ah - 2*pip) <= candle.low <= (ah + 0.3*pip)`.
**Code location:** `adaptive/strategies/london_breakout_strategy.py:generate_signals:121-151`
**Failure modes:**
- The 2-pip lower tolerance is a magic number with no documented rationale.
- Retest uses `candle["low"]`, meaning the candle's wick (not close) must touch the
  zone. Entry is still at `candle["close"]`. If close is well above the zone, entry
  could be far from the level, eroding the edge of retest-based entry.
- Once a retest fires and a signal is emitted, `breakout_direction` is reset to None.
  The session has one opportunity to fire; if the retest candle is missed or not
  qualifying, the signal is lost.

---

## Rule 7 — Retest Zone Check (SHORT)

**Purpose:** Mirror of Rule 6 for SHORT direction.
**Inputs:** `candle["high"]`, `asian_low`, pip size.
**Output:** Triggers entry if `(al - 0.3*pip) <= candle.high <= (al + 2*pip)`.
**Code location:** `adaptive/strategies/london_breakout_strategy.py:generate_signals:153-182`
**Failure modes:** Same as Rule 6 with directions reversed.

---

## Rule 8 — Risk Calculation (LONG)

**Purpose:** Compute stop loss and take profit distances.
**Inputs:** `entry = candle.close`, `sl = asian_low - pip`, `TP_RR = 1.5`.
**Output:** `risk = entry - sl`; `tp = entry + risk * 1.5`. If `risk <= 0`, signal
  is discarded and `breakout_direction` is reset.
**Code location:** `adaptive/strategies/london_breakout_strategy.py:generate_signals:127-131`
**Failure modes:**
- `risk <= 0` can occur if the entry close is below the SL level (i.e., if the retest
  candle closes below `asian_low - pip`). This is a degenerate case but handled
  gracefully with `continue`.
- TP_RR = 1.5 is hardcoded; the YAML value is not read.

---

## Rule 9 — Risk Calculation (SHORT)

**Purpose:** Mirror of Rule 8 for SHORT direction.
**Inputs:** `entry = candle.close`, `sl = asian_high + pip`, `TP_RR = 1.5`.
**Output:** `risk = sl - entry`; `tp = entry - risk * 1.5`.
**Code location:** `adaptive/strategies/london_breakout_strategy.py:generate_signals:157-163`
**Failure modes:** Same as Rule 8.

---

## Rule 10 — AdaptiveSignal Metadata Hardcoding

**Purpose:** Populate signal metadata for downstream scoring.
**Inputs:** None (values are constants).
**Output:** `metadata["liquidity_swept"] = False`, `metadata["structure_confirmed"] = True`
  always.
**Code location:** `adaptive/strategies/london_breakout_strategy.py:generate_signals:147-149, 177-179`
**Failure modes:**
- `liquidity_swept = False` means the 2-point liquidity bonus in the scorer is
  permanently unavailable. The strategy structurally cannot score 9 or 10.
- `structure_confirmed = True` unconditionally awards 2 structure points even though
  the only "structure" confirmed is the mechanical retest zone check.

---

## Rule 11 — Signal Wrapper (Adapter)

**Purpose:** Convert `AdaptiveSignal` to `core.Signal` for consumption by the
execution layer.
**Inputs:** Last element of `generate_signals()` output list.
**Output:** `Signal` object with `action = "BUY"/"SELL"`, `risk_percent = 0.25`,
  `confidence = min(1.0, rr / 2.0)`.
**Code location:** `strategies/adapters/london_breakout_adapter.py:generate_signal:43-69`
**Failure modes:**
- Only `raw_list[-1]` is used; if multiple signals are in the list (theoretically
  possible if the one-per-session guard is somehow bypassed), earlier signals are
  silently dropped.
- `risk_percent = 0.25` (0.25% of account) is hardcoded in the adapter. This
  conflicts with the portfolio config value of 0.20% (`strategy_portfolio.yaml:30`)
  and the adaptive engine default of 0.50% (`adaptive_engine.yaml:12`). The actual
  lot size calculation uses a separate function (`execution/demo_risk_manager.py`);
  it is unclear which value governs actual sizing.
- `confidence` uses `rr / 2.0` where rr is computed from the signal's own SL/TP.
  Since TP_RR is always 1.5, confidence is always 0.75 unless floating point deviation
  occurs. This is deterministic but the formula is undocumented.
- Adapter overwrites `timestamp` with `datetime.now(timezone.utc)` rather than using
  the candle timestamp from `raw.timestamp`. The two times can differ by up to one
  tick interval.

---

## Rule 12 — Regime Filter

**Purpose:** Block the signal if market regime is unsuitable.
**Inputs:** Recent M15 candles, `spread_pips` from context.
**Output:** "REJECTED" with reason `REGIME_BLOCKED` (if UNSAFE) or
  `REGIME_MISMATCH` (if regime not in `{"BREAKOUT", "RANGING"}`).
**Code location:** `adaptive/engine/trade_router.py:route_signal:87-100`
**Failure modes:**
- Regime detection requires `2 * ADX_PERIOD + 1 = 29` candles minimum. With fewer
  bars, `detect_regime` returns `{"regime": "UNSAFE", "confidence": 0.5}`, causing
  all signals to be rejected with `REGIME_BLOCKED`.
- `TRENDING` regime causes `REGIME_MISMATCH` rejection, even if the breakout is
  technically valid. This is a conservative choice but may over-filter on strong
  trending days when breakouts are most reliable.
- `_BLOCKED_REGIMES = {"UNSAFE"}` is hardcoded; the `filters.blocked_regimes` yaml
  key is not read by trade_router.

---

## Rule 13 — Signal Scoring

**Purpose:** Score the signal 0-10 against objective quality criteria.
**Inputs:** `AdaptiveSignal`, context dict (htf_bias, utc_hour, spread_pips, atr_pct, news_event).
**Output:** Approved if `score >= 7`.
**Code location:** `adaptive/engine/signal_scorer.py:score_signal:75-137`

Scoring breakdown:

| Criterion | Points | For London Breakout |
|-----------|--------|---------------------|
| HTF bias aligned | 2 | Depends on external htf_bias context |
| Liquidity event | 2 | Always 0 (liquidity_swept hardcoded False) |
| Structure confirmation | 2 | Always 2 (structure_confirmed hardcoded True) |
| Active session | 1 | 1 if current UTC hour in [6,9] |
| Spread acceptable | 1 | 1 if spread <= pair threshold |
| Volatility acceptable | 1 | 1 if ATR% in [0.001, 0.008] |
| News clear | 1 | Always 1 (news filter is stub) |

**Maximum possible score:** 8/10 (if HTF bias aligned, session active, spread ok, volatility ok, news clear).
**Without HTF bias:** maximum 6/10 → always rejected.

**Failure modes:**
- If `context["htf_bias"]` is not provided or is "NEUTRAL", the signal can never pass
  the minimum score of 7 (max without bias = 6). This is not documented as a
  hard requirement but is a structural consequence.
- `atr_pct` defaults to 0.0 in scorer (`context.get("atr_pct", 0.0)`) if not
  provided. `_volatility_acceptable(0.0)` returns False (0.0 < _MIN_ATR_PCT 0.001).
  If ATR is not supplied, volatility check fails and score drops by 1.
- `utc_hour` defaults to 0 if not in context. 00:00 UTC is not in the London window
  [6,9], so active_session score = 0.

---

## Rule 14 — Risk Manager Check (Adaptive Engine Path)

**Purpose:** Enforce intra-day risk limits before approving execution.
**Inputs:** Signal, current risk state dict, config.
**Output:** Approved if all 5 checks pass; rejected with `RISK_BLOCKED: <failed checks>`.
**Code location:** `adaptive/engine/risk_manager.py:check_risk:65-113`

Checks (in order):
1. `not_halted` — state["halted"] must be False.
2. `daily_loss_ok` — accumulated daily loss pct < 1.5%.
3. `trade_count_ok` — trades_today < 6.
4. `consec_loss_ok` — consecutive_losses < 3.
5. `no_correlation` — no existing LONG EURUSD if signal is LONG GBPUSD (or vice versa).

**Failure modes:**
- Risk state is not persisted by the trade_router; the caller must persist and
  re-supply it. If state is lost between ticks, counters reset to zero (undersafe).
- Correlation guard only blocks LONG+LONG, not SHORT+SHORT (`_SAME_DIRECTION_BLOCKED = {"LONG"}`
  at risk_manager.py:35). SHORT correlation between EURUSD and GBPUSD is unguarded.

---

## Rule 15 — CircuitBreaker (Portfolio Runner Path)

**Purpose:** Per-strategy rate limiting and consecutive loss cooldown.
**Inputs:** Strategy name, internal state (signal timestamps, trade count, loss count).
**Output:** `(True, "")` approved or `(False, reason)` blocked.
**Code location:** `core/circuit_breaker.py:check:70-99`

Checks:
1. Cooldown — if in cooldown period, reject.
2. Signal rate — max 6 signals/hour (default; LondonBreakout config example shows 3).
3. Daily trade limit — max 4 trades/day (default; example shows 3).
4. Consecutive losses — max 4 before cooldown (default; example shows 4).

**Failure modes:**
- CircuitBreaker is initialized with `CircuitBreaker()` (no config) at
  `run_portfolio.py:72`, meaning it always uses `_DEFAULTS` (6/hr, 4/day, 4 losses),
  not the LondonBreakout-specific values shown in the docstring example.
  The config example in the docstring is illustrative only — it is never loaded.

---

## Rule 16 — PortfolioManager Evaluation (Portfolio Runner Path)

**Purpose:** Enforce portfolio-wide limits: total open positions, daily/weekly/monthly
loss limits, and correlation group constraints.
**Inputs:** List of approved signals.
**Output:** Subset of signals that pass all portfolio limits.
**Code location:** `core/portfolio_manager.py:evaluate` (not read; referenced by
  `run_portfolio.py:268`)
**Failure modes:**
- Correlation groups in `strategy_portfolio.yaml` (lines 13-16) include
  `[EURUSD, GBPUSD, EURGBP]` and `[GBPUSD, GBPJPY, EURGBP]`. Whether the
  PortfolioManager reads this YAML dynamically was not confirmed in the read files.

---

## Rule 17 — Spread Guard (Portfolio Runner)

**Purpose:** Skip data fetch and signal generation for a symbol when spread is
excessive at the portfolio runner level.
**Inputs:** `px["spread_pips"]` from price fetch, `_MAX_SPREAD` dict.
**Output:** Symbol skipped (no signals generated) if spread exceeds threshold.
**Code location:** `scripts/run_portfolio.py:192-193`
**Failure modes:**
- USDJPY max spread here is 1.5 (`run_portfolio.py:125`), but the scorer uses 2.0
  (`signal_scorer.py:21`). A USDJPY trade with spread 1.6 pips would be skipped here
  before reaching the scorer. The portfolio runner is more restrictive for USDJPY.

---

## Rule 18 — News Filter

**Purpose:** Block trading during high-impact news events.
**Inputs:** Symbol name.
**Output:** `{"safe_to_trade": True, "source": "stub", "reason": "news_filter_stub"}` always.
**Code location:** `adaptive/filters/news_filter.py:is_safe:32-44`
**Failure modes:**
- CRITICAL: The news filter is a stub. `self._live = False` means the real news-fetch
  path is never reached. The filter will return safe=True regardless of actual news.
  There is a `# flip to True when real feed is wired` comment but no wiring exists.

---

## Rule 19 — DRY_RUN Enforcement

**Purpose:** Ensure no real orders are placed until explicitly enabled.
**Inputs:** `DRY_RUN` environment variable.
**Output:** If dry_run=True (default), execution returns simulated result.
  If dry_run=False, raises `NotImplementedError`.
**Code location:** `adaptive/execution/demo_executor.py:execute:59-61`
  Also: `scripts/run_portfolio.py:387-393` (mode=live → `sys.exit(1)`)
**Failure modes:**
- The portfolio runner (`run_portfolio.py`) and the shadow runner (`run_shadow.py`)
  each enforce `dry_run=True` independently. If one path is accidentally bypassed,
  the other still protects. Defense in depth is present.
