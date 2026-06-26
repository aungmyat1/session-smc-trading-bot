# Code Quality: London Breakout

Code quality findings for the London Breakout strategy and its supporting pipeline.
Each finding includes severity, file:line, description, and evidence.

Severity levels:
- CRITICAL: Incorrect behavior, safety risk, or data integrity issue
- HIGH: Significant logic bug, missing guard, or config inconsistency with real impact
- MEDIUM: Code smell, maintainability issue, or latent bug unlikely to trigger now
- LOW: Style, documentation, or minor inconsistency

---

## CRITICAL Findings

### C1 — News Filter Is a Non-Functional Stub

**Severity:** CRITICAL
**File:** `adaptive/filters/news_filter.py:28-44`
**Finding:** `self._live = False` is hardcoded in `__init__`. The `is_safe()` method
returns `{"safe_to_trade": True, "source": "stub"}` for every call, unconditionally.
The live path (`_fetch_live_events`) is never reached. High-impact news events (BOE,
ECB, NFP, CPI) that coincide with the London window (06:00–09:00 UTC) cause adverse
fills in breakout strategies. The scorer awards 1 point for "news_clear=True" which
is permanently True, making news events appear safe when they are not.
**Evidence:**
```python
# news_filter.py:29
self._live = False   # flip to True when real feed is wired
# news_filter.py:43-44
if not self._live:
    return {"safe_to_trade": True, "source": "stub", "reason": "news_filter_stub"}
```

---

### C2 — No Phase-0 Backtest Gate Passed

**Severity:** CRITICAL
**File:** `config/strategy_portfolio.yaml:28-34`; CLAUDE.md §3
**Finding:** LondonBreakout is configured with `execution_mode: demo`, meaning it
places real demo orders in the portfolio runner path. CLAUDE.md §3 requires Phase-0
backtest (n≥50, net PF>1.0 at standard AND 2× spread stress) before demo execution.
No entry for LondonBreakout exists in `docs/VERDICT_LOG.md` (not read, but no
reference to it was found anywhere in the codebase). The strategy is in live demo
execution without validated performance data.
**Evidence:** `strategy_portfolio.yaml:30`: `execution_mode: demo` for LondonBreakout.

---

### C3 — risk_per_trade Has Three Conflicting Values

**Severity:** CRITICAL
**Files:**
- `strategies/adapters/london_breakout_adapter.py:60` — `risk_percent=0.25`
- `config/strategy_portfolio.yaml:30` — `risk: 0.20`
- `adaptive/engine/risk_manager.py:24` — `"risk_per_trade": 0.005` (0.5%)
**Finding:** Three separate risk-per-trade values exist across three files. The adapter
hardcodes 0.25% in the `Signal` object. The portfolio YAML sets 0.20%. The adaptive
engine default is 0.50%. Without reading `execution/demo_risk_manager.py:calculate_lots`,
it is unclear which value actually governs lot size. This ambiguity directly impacts
position sizing and therefore risk exposure.
**Evidence:** Adapter line 60: `risk_percent=0.25,` — hardcoded, no reference to config.

---

## HIGH Findings

### H1 — liquidity_swept Hardcoded False Permanently Limits Score

**Severity:** HIGH
**File:** `adaptive/strategies/london_breakout_strategy.py:147,178`
**Finding:** `metadata["liquidity_swept"] = False` is hardcoded on every emitted signal.
The signal scorer awards 2 points for `liquidity_swept=True` (`signal_scorer.py:112-113`).
Since this is always False, the maximum achievable score is 8/10. Without HTF bias
aligned (2 more points), the signal scores 6/10, which always fails the threshold of 7.
This means HTF bias alignment is a de-facto hard requirement for London Breakout, even
though the code and documentation treat it as a bonus. The constraint is invisible and
undocumented.
**Evidence:**
```python
# london_breakout_strategy.py:147-149
"liquidity_swept":     False,  # hardcoded
"structure_confirmed": True,   # hardcoded
```

---

### H2 — YAML Config Parameters Are Never Read by the Strategy

**Severity:** HIGH
**Files:** `adaptive/config/adaptive_engine.yaml:39-42`; `adaptive/strategies/london_breakout_strategy.py:36-39`
**Finding:** The YAML file contains `london_breakout.min_range_pips`, `max_range_pips`,
and `tp_rr` under the `london_breakout:` key. The strategy module never loads this YAML.
All three values are hardcoded constants. Any operator modifying the YAML to tune the
strategy will see no effect. The YAML values are dead configuration.
**Evidence:** No `import yaml`, no config loading, no reference to `adaptive_engine.yaml`
anywhere in `london_breakout_strategy.py`.

---

### H3 — USDJPY Max Spread Inconsistency Between Runner and Scorer

**Severity:** HIGH
**Files:** `scripts/run_portfolio.py:125`; `adaptive/engine/signal_scorer.py:21`
**Finding:** Portfolio runner uses `USDJPY: 1.5` pips as the hard skip threshold.
Signal scorer uses `USDJPY: 2.0` pips as the spread-check threshold. A USDJPY spread
of 1.6 pips passes the scorer but is blocked by the portfolio runner before the scorer
is ever reached. The two limits are independent but inconsistent, creating a dead zone
(1.5–2.0 pips) where scorer would pass but runner blocks. Any test using the scorer
independently would have different results than live portfolio behavior.
**Evidence:** `run_portfolio.py:125`: `"USDJPY": 1.5`; `signal_scorer.py:21`: `"USDJPY": 2.0`.

---

### H4 — breakout_bar Recorded but Never Used (Dead State)

**Severity:** HIGH (dead code — indicates incomplete implementation)
**File:** `adaptive/strategies/london_breakout_strategy.py:114-116`
**Finding:** `breakout_bar = candle` is assigned when a breakout is detected (lines 114, 116).
This variable is never read again. Signal construction uses `candle["close"]` from the
retest bar, not from `breakout_bar`. The breakout bar's time, close, or level are not
referenced anywhere. This suggests a planned feature (e.g., logging the breakout bar
metadata, or using its close as the breakout level reference) that was never completed.
**Evidence:**
```python
breakout_bar = candle   # assigned line 114, 116
# Never referenced again in the function
```

---

### H5 — CircuitBreaker Initialized Without Strategy Config

**Severity:** HIGH
**File:** `scripts/run_portfolio.py:72`
**Finding:** `_breaker = CircuitBreaker()` is called with no config argument. The
circuit_breaker.py docstring shows a per-strategy config example for LondonBreakout
(`max_signals_hour: 3, max_trades_day: 3, max_losses: 4, cooldown_hours: 4`), but
this config is only in the docstring — it is never loaded. The circuit breaker always
uses global defaults: 6 signals/hr, 4 trades/day, 4 losses, 4h cooldown. The example
in the docstring implies someone intended to wire strategy-specific limits but did not.
**Evidence:** `run_portfolio.py:72`: `_breaker = CircuitBreaker()` — no config.

---

### H6 — SHORT Correlation Not Guarded in Adaptive Path

**Severity:** HIGH
**File:** `adaptive/engine/risk_manager.py:35`
**Finding:** `_SAME_DIRECTION_BLOCKED = {"LONG"}` means only LONG+LONG pairs
(EURUSD+GBPUSD) are blocked by the correlation guard. SHORT+SHORT combinations of
EURUSD and GBPUSD are permitted. Since both pairs are highly correlated in downtrends,
two simultaneous SHORT positions create concentrated directional exposure equivalent
to doubled risk, which the guard was designed to prevent.
**Evidence:**
```python
# risk_manager.py:35
_SAME_DIRECTION_BLOCKED = {"LONG"}   # LONG EURUSD + LONG GBPUSD blocked
# SHORT+SHORT is NOT in this set
```

---

## MEDIUM Findings

### M1 — Adapter Overwrites Signal Timestamp With Wall-Clock Time

**Severity:** MEDIUM
**File:** `strategies/adapters/london_breakout_adapter.py:51`
**Finding:** The `Signal` timestamp is set to `datetime.now(timezone.utc).isoformat()`
(wall-clock time of adapter execution), not to `raw.timestamp` (the retest candle's
time). This means the signal timestamp in `core.Signal` objects reflects when the
adapter ran, not when the market event occurred. Journal entries and audit trails will
show the wrong event time. The two times can differ by up to one full tick interval.
**Evidence:** `adapter.py:51`: `timestamp=datetime.now(timezone.utc).isoformat()` while
`raw.timestamp` is available and contains the candle's actual time.

---

### M2 — run_shadow.py Default PAIRS Excludes USDJPY

**Severity:** MEDIUM
**File:** `adaptive/run_shadow.py:58`
**Finding:** `PAIRS = ["EURUSD", "GBPUSD"]` hardcoded at module level. The strategy is
configured for EURUSD, GBPUSD, USDJPY in `adaptive_engine.yaml:6-9` and
`strategy_portfolio.yaml:32`. When using the shadow runner (as opposed to portfolio
runner), USDJPY signals are never generated. The inconsistency is undocumented.
**Evidence:** `run_shadow.py:58`: `PAIRS = ["EURUSD", "GBPUSD"]` — no USDJPY.

---

### M3 — HTF Bias Computation Is a Simplified Heuristic Without Documentation

**Severity:** MEDIUM
**File:** `adaptive/run_shadow.py:223-234`
**Finding:** `_derive_htf_bias()` computes bias as H4 last close vs 20-bar mean with
±0.1% threshold. This is a simple mean-reversion test, not a swing structure analysis
(HH+HL vs LL+LH). CLAUDE.md §2 Signal Chain Phase 2 specifies "HH+HL bullish / LL+LH
bearish (swing_n=3)" as the HTF bias method. The shadow runner implementation is a
simplified proxy. Since `htf_bias` drives 2 of the 10 scorer points for London
Breakout (and is effectively required to pass the 7-point threshold), an incorrect
bias can cause false approvals or false rejections.
**Evidence:** `run_shadow.py:228-229`: `if last > mean * 1.001: return "BULLISH"` — no swing structure logic.

---

### M4 — _PIP_SIZE Duplicated Across Two Files

**Severity:** MEDIUM
**Files:** `adaptive/strategies/london_breakout_strategy.py:25-29`; `strategies/adapters/london_breakout_adapter.py:14`
**Finding:** Pip size lookup tables are defined independently in both files. The
strategy has `_PIP_SIZE = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01}`.
The adapter has `_PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.1}`.
If pip sizes are ever corrected (e.g., a broker uses 0.00001 for 5-decimal EUR/USD),
both files must be updated. The adapter adds XAUUSD which the strategy does not support.
**Evidence:** Two separate dict literals with identical values for the three active pairs.

---

### M5 — Session Hours Duplicated Across Four Locations

**Severity:** MEDIUM
**Files:**
- `london_breakout_strategy.py:31-34` (hardcoded int constants)
- `adaptive_engine.yaml:29-33` (string times)
- `signal_scorer.py:29-30` (int tuple)
- `adaptive/engine/trade_router.py` (implicit in _is_london_bar call chain)
**Finding:** Asian and London session hours are defined as constants in the strategy,
as YAML strings in the config, and as int tuples in the scorer. None of these reads
from a single source. Changing session hours requires updating all four locations.
**Evidence:** LONDON_START_HOUR=6 in strategy; (6,9) in scorer; "06:00"/"09:00" in yaml.

---

### M6 — generate_signals Takes raw_list[-1] Only

**Severity:** MEDIUM
**File:** `strategies/adapters/london_breakout_adapter.py:43`
**Finding:** `raw = raw_list[-1]` — only the last signal is used. The underlying
`generate_signals()` resets `breakout_direction` after emitting, making multiple signals
per call theoretically impossible in current implementation. However, the function
signature (`-> list[AdaptiveSignal]`) implies multiple signals are possible. If the
strategy is ever extended to emit multiple signals per call, the adapter will silently
drop all but the last. This is a latent correctness issue.
**Evidence:** `adapter.py:43`: `raw = raw_list[-1]` — no comment explaining the assumption.

---

### M7 — confidence Formula Not Derived From Config

**Severity:** MEDIUM
**File:** `strategies/adapters/london_breakout_adapter.py:61`
**Finding:** `confidence = min(1.0, rr / 2.0)` uses the magic divisor 2.0.
The comment explains the intent ("1.5R → 0.75, 2R → 1.0") but the value 2.0 has no
config origin. Since TP_RR is always 1.5, confidence is always 0.75 for London Breakout
signals. The formula is effectively a constant. If TP_RR is ever changed, confidence
would change accordingly, but the relationship is implicit.
**Evidence:** `adapter.py:61`: `confidence=min(1.0, rr / 2.0),   # 1.5R → 0.75, 2R → 1.0`

---

### M8 — Regime Map Does Not Allow TRENDING for London Breakout

**Severity:** MEDIUM
**File:** `adaptive/engine/trade_router.py:37`
**Finding:** `_STRATEGY_REGIME_MAP["london_breakout"] = {"BREAKOUT", "RANGING"}`.
A strong directional London open (ADX > 25, ATR expanding) will classify as TRENDING
and cause REGIME_MISMATCH rejection. Asian range breakouts on trend days are often
the strongest setups. The exclusion of TRENDING is conservative but may over-filter
the best trading days. This is a design decision, not a bug, but it is undocumented.
**Evidence:** `trade_router.py:37`: `"london_breakout": {"BREAKOUT", "RANGING"}` — no TRENDING.

---

## LOW Findings

### L1 — Magic Number 2 (pip) in Retest Zone Not Documented

**Severity:** LOW
**File:** `adaptive/strategies/london_breakout_strategy.py:124,154`
**Finding:** The 2-pip lower tolerance in the LONG retest zone (`ah - 2*pip`) and the
2-pip upper tolerance in the SHORT retest zone (`al + 2*pip`) are unexplained magic
numbers. There is no comment, config entry, or documentation for why 2 pips was chosen.
**Evidence:** `strategy.py:124`: `retest_zone_bot = ah - 2 * pip` — bare literal.

---

### L2 — Magic Number 1 (pip) in SL Buffer Not Documented

**Severity:** LOW
**File:** `adaptive/strategies/london_breakout_strategy.py:127,158`
**Finding:** SL is placed 1 pip beyond the Asian range extreme (`al - pip`, `ah + pip`).
The 1-pip buffer is unexplained. No comment, no config entry.
**Evidence:** `strategy.py:127`: `sl = al - pip` — 1× pip with no explanation.

---

### L3 — RETEST_TOLERANCE Name vs Usage Mismatch

**Severity:** LOW
**File:** `adaptive/strategies/london_breakout_strategy.py:40`
**Finding:** `RETEST_TOLERANCE = 0.3` is labeled as "fraction of pip" in a comment
(`# fraction of pip — retest must come back within this`). However, it is only used
as the upper extension of the retest zone (`ah + RETEST_TOLERANCE * pip`), not as a
symmetric tolerance. The 2-pip lower extension uses a different undocumented constant.
The variable name implies symmetric tolerance but implements one-sided extension only.
**Evidence:** `strategy.py:40,123`: `RETEST_TOLERANCE = 0.3`; used only at `ah + 0.3*pip`.

---

### L4 — _utc_hour Returns -1 for Invalid Input, Silently Drops Candles

**Severity:** LOW
**File:** `adaptive/strategies/london_breakout_strategy.py:43-51`
**Finding:** If `candle["time"]` is None, an integer, or an unparseable format,
`_utc_hour` returns -1. Candles with -1 hour are silently excluded from both Asian
and London bar sets. No warning is raised. In a production feed with occasional
malformed timestamps, this could silently corrupt the Asian range or miss London bars.
**Evidence:** `strategy.py:50`: `return -1` — no logging, no exception.

---

### L5 — run_shadow.py Has a MetaAPI SDK Workaround Comment With No Test Coverage

**Severity:** LOW
**File:** `adaptive/run_shadow.py:76-78`
**Finding:** A comment describes a known SDK bug: `wait_synchronized({"timeoutInSeconds":60})`
causes `TypeError` because the SDK expects an `int`, not a `dict`. The workaround
(`await connection.wait_synchronized(60)`) is applied at line 104. No regression test
exists for this workaround. If the SDK is upgraded and the bug is fixed (or the
signature changes again), the workaround could silently break.
**Evidence:** `run_shadow.py:75-78` docstring; `run_shadow.py:104`: `await connection.wait_synchronized(60)`.

---

### L6 — No `__all__` Export in Strategy Package

**Severity:** LOW
**File:** `adaptive/strategies/__init__.py`
**Finding:** The `__init__.py` exports only `AdaptiveSignal`. It does not export
`generate_signals` or provide any `__all__` list. Consumers must import from the full
module path, which is inconsistent with how the adapter handles it (conditional import
inside the method at `adapter.py:29`).
**Evidence:** `__init__.py` has no `__all__` and no strategy function exports.

---

## Summary by Severity

| Severity | Count | Key Issues |
|----------|-------|------------|
| CRITICAL | 3 | News filter stub never blocks; no Phase-0 backtest; risk_per_trade three conflicting values |
| HIGH | 6 | liquidity_swept hardcoded False limits max score; YAML not read; USDJPY spread inconsistency; breakout_bar dead state; CircuitBreaker no config; SHORT correlation unguarded |
| MEDIUM | 8 | Timestamp overwrite; PAIRS missing USDJPY in shadow runner; HTF bias heuristic vs spec; pip dict duplicated; session hours in 4 places; only last signal used; confidence magic number; TRENDING regime excluded |
| LOW | 6 | Undocumented magic pip numbers; RETEST_TOLERANCE naming; silent -1 hour handling; SDK workaround; no __all__ export |
| **Total** | **23** | |
