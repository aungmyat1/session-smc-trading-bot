# Code Quality Findings: ST-A2 (Session Liquidity Reversal)

Findings are classified: CRITICAL / HIGH / MEDIUM / LOW.
All file:line references are exact locations verified by read.

---

## CRITICAL

### C-01 — risk_percent Discrepancy (Adapter vs Spec)

**File:** strategies/adapters/st_a2_adapter.py:69
**Finding:** `risk_percent=0.25` is hardcoded in ST2Adapter.generate_signal(). RISK_SPEC.md,
CLAUDE.md §4, and SIGNAL_SPEC.md all specify 1% risk per trade. The adapter silently passes
0.25% to the execution layer. If the execution layer uses this value directly for lot sizing,
every position will be 4× undersized (0.25% instead of 1%).
**Classification:** CRITICAL
**Notes:** No comment explaining the 0.25% value. No test that validates this matches the spec.
This will not be caught until live trading (position sizes will be wrong). Not a backtest issue
because the signal chain does not do position sizing.

---

### C-02 — Silent ImportError in Adapter

**File:** strategies/adapters/st_a2_adapter.py:42-43
**Finding:**
```python
except ImportError:
    return None
```
If the session_liquidity package fails to import (missing module, Python path issue, syntax
error in any imported file), the adapter returns None with no log, no alert, and no exception.
The caller (portfolio manager, bot.py) will see a missing signal and may treat it as "no setup
today." A broken import could silently disable the strategy for extended periods.
**Classification:** CRITICAL
**Notes:** There is no fallback logging, no re-raise, and no mechanism to distinguish "no signal
because market conditions" from "no signal because code is broken."

---

### C-03 — atr_map Key Type Mismatch (Potential Silent Miss)

**File:** strategy/session_liquidity/session_strategy.py:84, 165
**Finding:** atr_map is built with `{c["time"]: atr for c, atr in zip(sorted_m15, atrs)}`.
The key is the raw candle["time"] value as-is (may be str or datetime). At line 165:
`atr = atr_map.get(candle["time"])`. If the same candle's time field is the same type and
value at both times, this works. However, if M15 candles have mixed types (some str, some
datetime), some atr lookups will silently return None, causing displacement detection to fail
with 'atr_unavailable' reason. The strategy will produce no signal for those bars without
any error.
**Classification:** CRITICAL
**Notes:** The _utc() normalisation helper is used in other places (classify_session, bias_filter)
but NOT for the atr_map key or the atr_map lookup. This is an inconsistency that could cause
hard-to-diagnose signal misses in live operation.

---

## HIGH

### H-01 — config.yaml Is Not Loaded at Runtime

**File:** strategy/session_liquidity/config.yaml (entire file)
**Finding:** The config.yaml file documents 6 parameters. However, no code in the
session_liquidity package reads this file. session_strategy.py uses DEFAULT_CONFIG (a Python
dict). The YAML is a documentation artifact only. If someone modifies config.yaml expecting
to change live behaviour, nothing changes. If DEFAULT_CONFIG is updated but config.yaml is not
(or vice versa), they will silently diverge.
**Classification:** HIGH
**Notes:** Currently rr=3.0 in both. The operating RR for ST-A2 is 5.0 (per ST_A2_CONFIRMATION.md).
Neither file reflects the confirmed operating value. See H-02.

---

### H-02 — Documented Operating RR (5.0) Does Not Match Code Default (3.0)

**File:** strategy/session_liquidity/session_strategy.py:27; config.yaml:1
**Finding:** DEFAULT_CONFIG["rr"] = 3.0 and config.yaml rr: 3.0. ST_A2_CONFIRMATION.md and
VERDICT_LOG.md document that ST-A2 was confirmed at RR=5.0 ("Operating RR: 5"). The adapter
(st_a2_adapter.py:48) uses DEFAULT_CONFIG as the fallback config if data["config"] is not
supplied. In practice, if a caller does not pass a custom config, the strategy runs at RR=3.0,
which failed Phase-0 (PF_2x=0.954 at RR3, gate is > 1.0). The Phase-0-passing configuration
(RR=5.0) is not the default.
**Classification:** HIGH
**Notes:** A deployment using the defaults will run a configuration that did not pass Phase-0.
The correct default should be rr=5.0 to match the confirmed operating configuration.

---

### H-03 — Timestamp in core.Signal Is Adapter Call Time, Not Bar Time

**File:** strategies/adapters/st_a2_adapter.py:68
**Finding:**
```python
timestamp=datetime.now(timezone.utc).isoformat(),
```
The canonical core.Signal timestamp is set to the wall-clock time when the adapter is called,
not the displacement candle's bar-close timestamp (raw.timestamp). This means:
- The signal timestamp in the execution layer does not correspond to the bar that generated it.
- In replay scenarios, the timestamp will reflect replay runtime, not the historical bar time.
- Journal entries keyed on Signal.timestamp will be misleading.
The original Signal dataclass (entry_engine.py) carries the correct bar-close timestamp in
Signal.timestamp; it is available as raw.timestamp but is not forwarded.
**Classification:** HIGH

---

### H-04 — m15 Minimum (50 bars) Is Undocumented Magic Number

**File:** strategies/adapters/st_a2_adapter.py:50
**Finding:** `if len(m15) < 50: return None`. The number 50 has no documented basis.
ATR(14) warm-up requires only 15 bars (indices 0..14). The STRATEGY_A_SESSION.md and SIGNAL_SPEC.md
do not mention a 50-bar minimum. This threshold silently blocks the strategy from producing
signals on short datasets and will cause unexpected None returns in unit tests or short replay
windows without explanation.
**Classification:** HIGH

---

### H-05 — Only Last Signal Returned by Adapter

**File:** strategies/adapters/st_a2_adapter.py:57
**Finding:** `raw = raw_signals[-1]` — the adapter returns only the last signal from run_strategy.
run_strategy may return multiple signals (one per session per day, across many days, if called
with a multi-day candle batch). Signals for earlier sessions/days are silently discarded. If the
caller intends to process all signals (e.g., for replay or multi-day analysis), they must call
run_strategy directly; the adapter is lossy.
**Classification:** HIGH
**Notes:** For a live bot calling the adapter with the last 200 candles, only the most recent
signal is wanted, so this is intentional in that context. But the behaviour is undocumented and
will surprise callers running batch analysis through the adapter.

---

## MEDIUM

### M-01 — config.yaml and DEFAULT_CONFIG Are Maintained Separately (Duplicate State)

**File:** strategy/session_liquidity/config.yaml (all 11 lines); session_strategy.py:26-37
**Finding:** All 6 configurable parameters appear in both places with identical values. There is
no mechanism to ensure they stay in sync. Any future parameter change requires updating two files.
This is a maintenance hazard: the YAML may mislead a developer into thinking it is the live config.
**Classification:** MEDIUM

---

### M-02 — _parse_utc Duplicated Across Three Modules

**File:**
- strategy/session_liquidity/session_builder.py:32-36
- strategy/session_liquidity/bias_filter.py:30-34
- strategy/session_liquidity/session_strategy.py:201-204 (named _utc)

**Finding:** Three near-identical implementations of ISO-string-to-UTC-datetime parsing. Logic is
the same: isinstance check, then fromisoformat with Z→+00:00 substitution. The session_strategy.py
version is named _utc instead of _parse_utc. If the parsing logic needs to change (e.g., to handle
a new timestamp format), all three must be updated.
**Classification:** MEDIUM

---

### M-03 — htf_bias Called on Every Killzone Bar Including When Pending Sweep Exists

**File:** strategy/session_liquidity/session_strategy.py:135
**Finding:** htf_bias() is called unconditionally for every killzone bar regardless of whether a
sweep is pending. When displacement is being searched (pending is not None), the bias result from
htf_bias is computed but never used (the pending branch at line 155 does not check bias). This is
wasted computation on every bar in the pending state, which is up to sweep_timeout_bars (4) bars
per sweep event.
**Classification:** MEDIUM
**Notes:** Not a correctness issue. Performance impact is negligible in Python for typical dataset
sizes. Wasted computation grows proportionally with the number of days with pending sweeps.

---

### M-04 — max_sl_pips Not Implemented

**File:** RISK_SPEC.md (specification only); entry_engine.py (missing check)
**Finding:** RISK_SPEC.md specifies a maximum SL of 50 pips ("reject if wider — degenerate setup").
Neither build_signal() nor the post-signal filter in session_strategy.py checks for an upper bound
on risk_pips. Wide-wick sweeps (e.g., 40+ pip sweeps on GBPUSD during high-volatility events) will
produce signals. The VERDICT_LOG.md confirms max DD is 18.72R across 5yr backtest, so this has not
been catastrophic in practice, but the spec is unimplemented.
**Classification:** MEDIUM

---

### M-05 — Session Module Reference Name Mismatch (SA vs SA numbers)

**File:** strategy/session_liquidity/*.py (all module docstrings)
**Finding:** Modules are labeled SA-01 through SA-07 in their docstrings (SA-01 = session_builder,
SA-02 = bias_filter, SA-04 = sweep_detector, SA-05 = displacement_detector, SA-06 = entry_engine,
SA-07 = session_strategy). SA-03 is missing (no module with that designation). This may be an
intentional gap (a module was planned and not built, or was merged into another) or a labeling error.
The gap is unexplained.
**Classification:** MEDIUM (documentation inconsistency; no runtime impact)

---

### M-06 — Signal.timestamp Fallback to datetime.now in entry_engine

**File:** strategy/session_liquidity/entry_engine.py:143-152
**Finding:**
```python
raw_time = candle.get("time")
if raw_time is None:
    timestamp = datetime.now(_UTC)
```
If candle["time"] is missing or unparseable, the signal timestamp defaults to the current wall-clock
time. In backtest replay, this would assign the replay run time to historical signals, corrupting any
time-based analysis. The fallback is silent (no log, no error).
**Classification:** MEDIUM

---

## LOW

### L-01 — _VALID_SESSIONS Frozenset Is Redundant with classify_session Output

**File:** strategy/session_liquidity/entry_engine.py:21
**Finding:** `_VALID_SESSIONS = frozenset({"london", "new_york"})` mirrors the exact return values of
classify_session(). If classify_session's session labels change, entry_engine.py must be updated
independently. A shared constant (imported from session_builder) would be more maintainable.
**Classification:** LOW

---

### L-02 — debug Parameter Returns Different Type (tuple vs list)

**File:** strategy/session_liquidity/session_strategy.py:46
**Finding:** The return type annotation is `list[Signal] | tuple[list[Signal], list[dict]]`.
When debug=False (default), returns list. When debug=True, returns tuple. Callers must either
always check the type or always pass debug=False. The adapter (st_a2_adapter.py:53) calls
run_strategy without debug=True and destructures the result as a list, which is correct. But
type-checking tools will flag the union return type as ambiguous.
**Classification:** LOW

---

### L-03 — No __all__ Exports in Package __init__.py

**File:** strategy/session_liquidity/__init__.py (referenced in STRATEGY_A_SESSION.md as
re-exporting Signal and run_strategy; content not verified)
**Finding:** STRATEGY_A_SESSION.md documents that __init__.py "re-exports Signal, run_strategy"
but the file contents were not audited. If __all__ is absent, star imports would pull in all names.
**Classification:** LOW

---

### L-04 — reason String in entry_engine Contains Non-ASCII Character (≤)

**File:** strategy/session_liquidity/displacement_detector.py:172
**Finding:**
```python
reason=f"body({body:.5f}) ≤ {mult}×ATR({threshold:.5f})",
```
The '≤' and '×' characters are non-ASCII Unicode. In environments where logs are written to
ASCII-encoded files or terminals without UTF-8 support, these characters may corrupt log output or
raise UnicodeEncodeError. Low risk in modern environments but not portable.
**Classification:** LOW

---

### L-05 — SIGNAL_SPEC.md Describes a Different Signal Chain Than What Is Implemented

**File:** docs/SIGNAL_SPEC.md (strategy ID "SESSION_SMC_A"), docs/STRATEGY_A_SESSION.md
**Finding:** SIGNAL_SPEC.md describes the full 11-phase chain from CLAUDE.md §2 (4H+1H bias,
session range build, 15M CHoCH, 15M BOS, displacement FVG, FVG retest entry). The implemented
code (session_strategy.py / session_liquidity/) implements only Phases 1-6: Asian range, 4H bias,
killzone filter, range filter, sweep, and displacement. There is no CHoCH, no BOS, no FVG in the
ST-A2 implementation. SIGNAL_SPEC.md describes an aspirational or future design, not ST-A2.
This discrepancy can mislead a reader into thinking more confirmation logic is in place than
actually exists.
**Classification:** LOW (documentation only; runtime behaviour is correctly described in
STRATEGY_A_SESSION.md, but the two spec docs are inconsistent)
