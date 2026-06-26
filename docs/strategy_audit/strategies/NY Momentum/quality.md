# Code Quality: NY Momentum

Each finding lists: Severity | Category | Description | File:line

Severity levels: CRITICAL | HIGH | MEDIUM | LOW

---

## CRITICAL

### QC-01 — Risk state counters never updated from trade outcomes

**Severity:** CRITICAL
**Category:** Dead logic / broken safety
**Description:** `risk_manager.record_trade()` is never called from `run_shadow.py`. As a result, `state["consecutive_losses"]`, `state["trades_today"]`, and `state["daily_loss_pct"]` are permanently 0 throughout the shadow runner lifecycle. The three most important risk guards (`max_consecutive_losses`, `max_trades_per_day`, `max_daily_loss`) all check these counters and will never trigger. The risk manager's halt logic is effectively disabled.
**File:** `adaptive/run_shadow.py` : `_tick` — absence of `risk_manager.record_trade()` call after `paper.update()` returns a closed trade (lines 162–168). Contrast with `adaptive/engine/risk_manager.py` : `record_trade` : line 116.

---

### QC-02 — metadata flags hardcoded True inflate signal scoring by 4 points

**Severity:** CRITICAL
**Category:** Inconsistency between config and code / misleading validation
**Description:** Every `AdaptiveSignal` emitted by `ny_momentum_strategy.generate_signals()` sets `metadata["liquidity_swept"] = True` and `metadata["structure_confirmed"] = True` unconditionally (lines 136–138 and 162–164). The signal scorer awards +2 points for each of these, for a guaranteed floor score of 4 points on every ny_momentum signal. This means any signal with HTF bias aligned (unlikely in NEUTRAL markets) would automatically score 6/10, and any signal in-session during non-news conditions would score 7/10 regardless of actual market structure quality. The scoring system is not independently evaluating these criteria.
**File:** `adaptive/strategies/ny_momentum_strategy.py` : lines 133–138, 159–164; `adaptive/engine/signal_scorer.py` : `_has_liquidity_event` : line 44, `_has_structure_confirmation` : line 48.

---

## HIGH

### QC-03 — session-end forced closure never called

**Severity:** HIGH
**Category:** Dead code (unreachable in runtime) / missing feature
**Description:** `PaperExecution.close_all()` is defined and documented but is never called from `run_shadow.py`. Open paper trades persist indefinitely after the NY session ends (15:00 UTC) and are updated with M15 prices from the next Asian/London session. This violates the CLAUDE.md §4 session close rule ("If trade still open at session end, close remainder at market") and produces inaccurate paper trading results by allowing overnight exposure.
**File:** `adaptive/simulation/paper_execution.py` : `close_all` : line 88 (defined but unreachable from shadow runner). `adaptive/run_shadow.py` : `_tick` : no call to `close_all` anywhere.

---

### QC-04 — Adapter takes only last signal; silently discards earlier ones

**Severity:** HIGH
**Category:** Logic error / silent data loss
**Description:** `NYMomentumAdapter.generate_signal()` calls `generate_signals()` which may return a list of up to 2 signals (one LONG, one SHORT, if both sweeps and both retests happen within the same NY session). The adapter uses `raw_list[-1]` without checking the length. If both signals are generated, the first is silently discarded. The adapter also does not log the discard.
**File:** `strategies/adapters/ny_momentum_adapter.py` : `generate_signal` : line 43 (`raw = raw_list[-1]`).

---

### QC-05 — CircuitBreaker instantiated but never wired into execution path

**Severity:** HIGH
**Category:** Dead code
**Description:** `core/circuit_breaker.py` defines a full `CircuitBreaker` class with per-strategy rate limiting, consecutive loss tracking, and cooldown enforcement. It is never imported, instantiated, or called from `run_shadow.py`, `trade_router.py`, or any file in the adaptive engine path. The class is completely unreachable during shadow trading.
**File:** `core/circuit_breaker.py` : entire file (defined, not wired). Confirmed by absence of any `import circuit_breaker` in the adaptive engine module tree.

---

### QC-06 — Duplicate pip size definitions with inconsistent symbol coverage

**Severity:** HIGH
**Category:** Duplicated logic / inconsistency
**Description:** `_PIP_SIZE` in `ny_momentum_strategy.py` (line 25–29) and `_PIP` in `ny_momentum_adapter.py` (line 14) both define pip sizes for EURUSD, GBPUSD, USDJPY with identical values. However, the adapter adds XAUUSD (pip=0.1) which the strategy does not have. If XAUUSD is passed to `generate_signals()`, the strategy falls back to pip=0.0001, producing a 1000x error in sweep buffer and retest zone calculations. The strategy would generate signals with retest zones of 0.0001 instead of 0.1 for XAUUSD.
**File:** `adaptive/strategies/ny_momentum_strategy.py` : line 25–29; `strategies/adapters/ny_momentum_adapter.py` : line 14.

---

### QC-07 — Config values for ny_momentum are entirely ignored by the strategy

**Severity:** HIGH
**Category:** Inconsistency between config and code
**Description:** `adaptive/config/adaptive_engine.yaml` contains a `ny_momentum:` section with `sweep_buffer_pips: 1` and `tp_rr: 2.0`. The strategy reads neither of these; it uses hardcoded module-level constants `SWEEP_BUFFER = 1` and `TP_RR = 2.0`. Changing the YAML has zero effect on strategy behavior. The same applies to session window definitions in `sessions:` and filter thresholds in `filters:` — the strategy and scorer use their own constants. The YAML config gives a false impression of configurability.
**File:** `adaptive/config/adaptive_engine.yaml` : lines 19–26, 29–37, 44–47; `adaptive/strategies/ny_momentum_strategy.py` : lines 31–37; `adaptive/engine/signal_scorer.py` : lines 15–32.

---

### QC-08 — risk_manager correlation guard only blocks LONG/LONG, not SHORT/SHORT

**Severity:** HIGH
**Category:** Inconsistency / incomplete logic
**Description:** `_SAME_DIRECTION_BLOCKED = {"LONG"}` at line 35 of `risk_manager.py` means the correlated-position check only fires for simultaneous LONG on EURUSD and GBPUSD. Two concurrent SHORT positions on correlated pairs are explicitly permitted. This is asymmetric and likely unintentional given the stated purpose of preventing over-exposure on correlated pairs.
**File:** `adaptive/engine/risk_manager.py` : line 35, `_correlated` : lines 50–62.

---

## MEDIUM

### QC-09 — Adapter signal timestamp diverges from candle timestamp

**Severity:** MEDIUM
**Category:** Inconsistency
**Description:** `AdaptiveSignal.timestamp` in the strategy is set to the candle's own `time` field (line 99, 131, 157 of strategy). The `Signal` created by the adapter sets `timestamp = datetime.now(timezone.utc).isoformat()` (adapter line 52) — the wall-clock time of the adapter call, not the candle time. On backtests or replayed data, all signals appear to have been generated at the replay execution time. This invalidates TTL checks and makes journal entries difficult to correlate with candles.
**File:** `strategies/adapters/ny_momentum_adapter.py` : line 52; `adaptive/strategies/ny_momentum_strategy.py` : lines 99, 131, 157.

---

### QC-10 — Long retest zone upper bound allows entry above London High

**Severity:** MEDIUM
**Category:** Logic error / potential false signals
**Description:** The long retest zone is `[lh - 1*pip, lh + 2*pip]`. A candle that closes 1–2 pips above the London High would satisfy the retest condition even though the close is above (not at) the swept level. Entry at that close would be above the reference level, reducing the quality of the retest. The intent appears to be entry at or just below the London High (the retest touches the level from above), but the zone allows entry above the level too.
**File:** `adaptive/strategies/ny_momentum_strategy.py` : lines 115–117.

---

### QC-11 — Retest zone is asymmetric between LONG and SHORT without explanation

**Severity:** MEDIUM
**Category:** Magic number / undocumented design
**Description:** LONG retest zone: `[lh - 1pip, lh + 2pip]` (3-pip window, 1 below, 2 above). SHORT retest zone: `[ll - 2pip, ll + 1pip]` (3-pip window, 2 below, 1 above). The asymmetry between LONG (more tolerance above) and SHORT (more tolerance below) is not commented or documented. Both windows are 3 pips wide but the skew is flipped. This may be intentional (allowing entry slightly past the swept level on continuation) but is not explained.
**File:** `adaptive/strategies/ny_momentum_strategy.py` : lines 115–116 (LONG), 143–144 (SHORT).

---

### QC-12 — awaiting_retest cleared even when signal silently dropped (risk=0)

**Severity:** MEDIUM
**Category:** Logic error / silent failure
**Description:** When the retest condition fires but `risk <= 0`, the signal is not appended. However, `awaiting_retest_long = False` (line 140) and `awaiting_retest_short = False` (line 168) are set unconditionally after the retest condition check — outside the `if risk > 0:` block. The retest opportunity is consumed even when no signal was generated. After this, no further retest is possible for the session.
**File:** `adaptive/strategies/ny_momentum_strategy.py` : line 140 (LONG clear outside `if risk > 0`), line 168 (SHORT clear outside `if risk > 0`).

---

### QC-13 — PortfolioManager.get_risk_pct returns 0.20 (20%) for NYMomentum

**Severity:** MEDIUM
**Category:** Magic number / likely unit error
**Description:** `RISK_TIERS["tier2"] = 0.20` at `core/portfolio_manager.py` line 23. If this is interpreted as 20% of account per trade, it is catastrophically large. The description says "risk_pct applied per trade (% of account)" but the value 0.20 in context of other risk controls (0.5% = 0.005) suggests this should be `0.002` (0.2%). This is not currently called in the shadow runner, but if wired to lot sizing, it would produce 40x the intended risk.
**File:** `core/portfolio_manager.py` : lines 22–24.

---

### QC-14 — M5 candles fetched but never used

**Severity:** MEDIUM
**Category:** Dead code / inefficiency
**Description:** `run_shadow.py` fetches `m5 = await feed.get_candles(symbol, "M5", 100)` (line 149) but `m5` is never passed to any strategy, scorer, or context builder. It is a dead variable that incurs an API call each tick.
**File:** `adaptive/run_shadow.py` : `_tick` : line 149.

---

### QC-15 — HTF bias derivation in run_shadow.py is a simplified heuristic

**Severity:** MEDIUM
**Category:** Inconsistency / placeholder
**Description:** `_derive_htf_bias()` in `run_shadow.py` uses a simple `H4 close vs 20-bar mean ±0.1%` heuristic (lines 223–234). This is not the CLAUDE.md §2 Phase 2 bias definition (HH+HL bullish / LL+LH bearish, swing_n=3) and is not the same as what the project's `session_smc/bias.py` module likely computes. The ±0.1% band is a magic number with no documented basis.
**File:** `adaptive/run_shadow.py` : `_derive_htf_bias` : lines 223–234.

---

## LOW

### QC-16 — MIN_SCORE duplicated between signal_scorer.py and adaptive_engine.yaml

**Severity:** LOW
**Category:** Duplicated logic
**Description:** `MIN_SCORE = 7` is defined as a module constant in `adaptive/engine/signal_scorer.py` (line 15) and also as `filters.min_score: 7` in `adaptive/config/adaptive_engine.yaml` (line 19). The scorer reads only its constant; the YAML value is unused. If someone changes the YAML, the scorer's behaviour does not change.
**File:** `adaptive/engine/signal_scorer.py` : line 15; `adaptive/config/adaptive_engine.yaml` : line 19.

---

### QC-17 — No test coverage for ny_momentum signal generation

**Severity:** LOW
**Category:** Missing tests
**Description:** The `tests/` directory (per CLAUDE.md §8) should contain `test_session.py`, `test_sweep.py`, and `test_confirmation.py`, but no tests for ny_momentum sweep detection, retest entry logic, or adapter signal translation exist. Edge cases (risk=0 silent drop, no London bars, unrecognised symbol) are untested.
**File:** `tests/` directory (by expected layout from CLAUDE.md §8).

---

### QC-18 — _utc_hour returns -1 for unrecognised time formats, silently drops candles

**Severity:** LOW
**Category:** Missing error handling
**Description:** `_utc_hour()` returns `-1` when the `time` field is not a str or datetime (line 46–48 of strategy). Callers treat `-1` as a valid hour: `_build_london_levels` silently excludes the candle (since -1 < 6); the NY loop silently skips it (since -1 < 11). No warning is emitted. Malformed candle data is silently dropped with no observability.
**File:** `adaptive/strategies/ny_momentum_strategy.py` : `_utc_hour` : lines 40–48.

---

### QC-19 — StateStore.needs_daily_reset uses local date, not UTC date

**Severity:** LOW
**Category:** Inconsistency
**Description:** `StateStore.needs_daily_reset()` compares `last_dt.date()` against `datetime.now(timezone.utc).date()`. If the server is in a non-UTC timezone, `datetime.now(timezone.utc).date()` is still UTC, but `last_dt` is parsed via `fromisoformat()` which may have or lack timezone info depending on how it was stored. The `reset_daily()` stores `datetime.now(timezone.utc).isoformat()` (with timezone), so parsing is consistent. However, date comparison uses the fromisoformat result's `.date()` which is UTC-aware. This is consistent but subtly timezone-sensitive if the stored string ever lacks tzinfo.
**File:** `adaptive/state/state_store.py` : `needs_daily_reset` : lines 84–94.

---

### QC-20 — NewsFilter stub always clears, always awards +1 scoring point

**Severity:** LOW
**Category:** Placeholder / missing feature
**Description:** `NewsFilter._live = False` is hardcoded in `__init__` (line 29). The filter always returns `safe_to_trade=True` with `source="stub"`. The signal scorer awards +1 point for `_news_clear()` which returns `not context.get("news_event", False)`. In `run_shadow.py`, `news_event` is set to `not news["safe_to_trade"]` which is always `False` (stub). Therefore the news scoring point is always 1. No TODO comment marks this for future activation.
**File:** `adaptive/filters/news_filter.py` : lines 28–30, 43–44; `adaptive/engine/signal_scorer.py` : `_news_clear` : line 68–70; `adaptive/run_shadow.py` : line 189.

---

## Summary by Severity

| Severity | Count | IDs |
|---|---|---|
| CRITICAL | 2 | QC-01, QC-02 |
| HIGH | 6 | QC-03, QC-04, QC-05, QC-06, QC-07, QC-08 |
| MEDIUM | 7 | QC-09 through QC-15 |
| LOW | 5 | QC-16 through QC-20 |
| **Total** | **20** | |
