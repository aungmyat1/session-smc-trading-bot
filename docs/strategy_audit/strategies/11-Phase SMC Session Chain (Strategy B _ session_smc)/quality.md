# Code Quality — 11-Phase SMC Session Chain (Strategy B / session_smc)

Findings from static audit of `session_smc/` and the test/backtest harness.
Severity: CRITICAL | HIGH | MEDIUM | LOW

---

## Finding Q-01: Phase Classification Result Silently Discarded

**Severity: MEDIUM**

**File:** `confirmation_entry.py:155`
**Code:**
```python
_sess_class = classify_session(session_candles, sess_range, cfg["atr_period"])
```

The session classification (RANGE/TREND/MIXED) is computed, assigned to `_sess_class`,
and never used. The `Signal` dataclass has no `session_class` field. There is no logging
of this value. The comment in the module docstring lists Phase 4 as "Session classification
(informational, not a hard gate)" but the information is entirely lost after computation.

This means:
- ATR is computed twice (once in `classify_session`, once explicitly at line 158).
- The TREND/RANGE distinction that is part of the published trading philosophy (Setup B — Trend
  Pullback, Setup C — Range Fade) has no effect on signal generation.

**Recommendation:** Either expose `session_class` in the `Signal` dataclass for downstream
analytics, or remove the call to avoid the redundant ATR computation.

---

## Finding Q-02: ATR Computed Twice Per Session

**Severity: LOW**

**Files:** `confirmation_entry.py:155` (inside `classify_session`), `confirmation_entry.py:158` (explicit call)

```python
# Line 155 — inside classify_session
_sess_class = classify_session(session_candles, sess_range, cfg["atr_period"])

# Line 158 — explicit re-computation
atr_vals = atr(session_candles, cfg["atr_period"])
```

`classify_session` calls `compute_atr` internally. The result is not returned. Then `atr()`
is called again on the same candles. This is a redundant O(n) computation per session.
For a backtest over 5 years × 2 pairs × 2 sessions/day × ~250 days/year ≈ 5,000 sessions,
this doubles the ATR computation work.

**Recommendation:** Refactor `classify_session` to accept pre-computed ATR values, or
pre-compute ATR once and pass to both functions.

---

## Finding Q-03: PIP Constant Defined in Three Files

**Severity: MEDIUM**

**Files:**
- `confirmation_entry.py:33` — `PIP: float = 0.0001`
- `liquidity_detector.py:14` — `PIP: float = 0.0001`
- `daily_context.py:43` — `PIP = 0.0001`

The pip size is hardcoded as a module-level constant in three separate files. There is no
shared constant module or config key. If additional pairs with different pip sizes (e.g.
USDJPY at 0.01) are added, all three files must be updated independently. Risk of divergence.

**Recommendation:** Define `PIP` in a single `session_smc/constants.py` and import from there,
or make it a parameter in the functions that use it.

---

## Finding Q-04: _UTC Sentinel Duplicated

**Severity: LOW**

**Files:**
- `daily_bias.py:23` — `_UTC = timezone.utc`
- `daily_context.py:44` — `_UTC = timezone.utc`

The `_UTC` sentinel is defined identically in two modules. Minor duplication, no functional
risk, but reinforces the need for a shared constants module.

---

## Finding Q-05: D2 Gate B Uses Session Bar 0 Open Price

**Severity: HIGH**

**File:** `confirmation_entry.py:141`
```python
session_open_price = float(session_candles[0]["open"])
location = classify_location(session_open_price, d2_ctx["pdh"], d2_ctx["pdl"])
```

Gate B classifies the session as premium/discount using the opening price of the very first
bar of the session. In a 20-bar (5-hour) session, the sweep and FVG retest may occur 2–3 hours
after session open. The premium/discount classification at bar 0 may no longer reflect where
price is when the trade fires.

This is a logical inconsistency: the gate is meant to assess whether the current price is in a
favorable zone for the trade direction, but it evaluates the zone at session open, not at the
time of the sweep or entry.

**Comparison:** `replay_6m.py:301–306` applies Gate B per-bar (at each killzone candle), which
is the more defensible implementation. `confirmation_entry.py` applies it only at bar 0.

**Recommendation:** If Gate B is to be retained, evaluate `classify_location` at the sweep bar
or retest bar, not at session bar 0.

---

## Finding Q-06: D2 Gates Default True Despite No Validated Improvement

**Severity: HIGH**

**File:** `confirmation_entry.py:75–81` (DEFAULT_CONFIG)

All three D2 gates (`d2_structure_gate`, `d2_location_gate`, `d2_poi_gate`) default to True.
The empirical record shows:
- ST-D2-6M: combined D2 gates removed 68.8% of signals, D2_COMBINED PF_2x = 0.135 vs
  BASELINE PF_2x = 1.909 (VERDICT_LOG)
- TRIAL_ST_A2_D1_001: D1 gates combined removed 100% of signals in a 7-week window.

The module is the primary backtest target for ST-B. Having all three experimental gates default
True means the first run of `scripts/backtest.py` against this module will test the D2-combined
version by default, not the baseline chain. This conflicts with the Phase-0 gate requirement
(which tests the signal chain, not the D2 overlay).

**Recommendation:** Default all three D2 gates to False for the Phase-0 evaluation, matching
how ST-A2 was validated. Add a comment in DEFAULT_CONFIG explaining that D2 gates are
experimental and unvalidated.

---

## Finding Q-07: Signal Return Comment Contradicts Implementation

**Severity: LOW**

**File:** `confirmation_entry.py:108`
```
The signal is based on the MOST RECENT complete sequence found in session_candles.
```

The implementation scans forward and returns the **first** sweep, then the **first** CHoCH
after that sweep, then the **first** BOS, etc. It does not search for the most recent valid
complete sequence — it returns the earliest one that completes. The docstring is misleading.

In practice this matters when multiple sweeps occur in a session. Only the first sweep's chain
is evaluated; a later sweep that also completes the chain would be ignored.

---

## Finding Q-08: d1_poi_filter Stub Uses assert False

**Severity: MEDIUM**

**File:** `daily_context.py:224–228`
```python
if c.get("d1_poi_filter", False):
    assert False, (
        "d1_poi_filter is reserved for TRIAL_ST_A2_D1_POI_001. "
        "Do not enable in TRIAL_ST_A2_D1_001."
    )
```

Using `assert False` as a runtime guard is fragile. In Python, `assert` statements are
removed when running with `-O` (optimize flag). If anyone runs the backtest with `python -O`,
the stub guard is silently bypassed. A proper `raise ValueError(...)` or `raise
NotImplementedError(...)` should be used.

**Recommendation:** Replace `assert False` with `raise NotImplementedError(...)`.

---

## Finding Q-09: No min_sl_pips in DEFAULT_CONFIG

**Severity: HIGH**

**File:** `confirmation_entry.py:60–81` (DEFAULT_CONFIG)

`min_sl_pips` is absent from DEFAULT_CONFIG. This is explicitly documented in
`ST_B_RESEARCH_PLAN.md §E.5` as a known gap. The consequence: signals with SL < 5 pip
(where spread would consume > 20% of 1R) are not rejected by the module.

The corresponding key exists in `strategy/session_liquidity/config.yaml:6` with value 5.0,
and is applied in `scripts/backtest.py` via the same config dict. But for `session_smc/`
standalone use (e.g. future ST-B backtest), a caller must apply this floor externally.

**Recommendation:** Add `"min_sl_pips": 5.0` to DEFAULT_CONFIG with a comment, and apply
the check inside `generate_signal_A` after SL computation (Phase 10).

---

## Finding Q-10: Session Classification RANGE/TREND Thresholds are Magic Numbers

**Severity: LOW**

**File:** `liquidity_detector.py:68,70`
```python
if ratio < 0.5:
    return "RANGE"
if ratio > 0.7:
    return "TREND"
```

The 0.5 and 0.7 thresholds are not documented, not in any config, and have no cited source.
They are not used in any gate (Phase 4 result is discarded per Q-01), so this is currently
low-impact. If Phase 4 is ever made into a hard gate, these thresholds become load-bearing
without any empirical justification.

---

## Finding Q-11: NaN Check Uses Float Identity Trick

**Severity: LOW**

**File:** `structure_detector.py:177`
```python
if atr_val != atr_val:  # NaN
    continue
```

This relies on the IEEE 754 property that NaN != NaN. While technically correct, it is
non-obvious to readers unfamiliar with this idiom. A more readable alternative:
`import math; if math.isnan(atr_val): continue`.

---

## Finding Q-12: daily_context.py Not Used by confirmation_entry.py

**Severity: MEDIUM**

**Files:** `session_smc/daily_context.py`, `session_smc/confirmation_entry.py`

`daily_context.py` provides `DailyContext` dataclass, `build_d1_context()`, and
`apply_d1_gates()` — a cleaner, typed interface over the plain-dict D2 context in
`daily_bias.py`. The module header says "Clean interface for the ST-A2 + D1 context A/B
replay framework."

However, `confirmation_entry.py` imports from `daily_bias.py` directly (line 30), not from
`daily_context.py`. The two D1/D2 gate implementations are therefore:

1. `confirmation_entry.py` uses `daily_bias.build_daily_context()` → plain dict gates
   (D2 protocol, `d2_structure_gate` etc.)
2. `scripts/replay_st_a2_d1.py` uses `daily_context.apply_d1_gates()` → typed DailyContext
   gates (D1 protocol, `d1_bias_filter` etc.)

These are parallel but separate implementations of essentially the same gate logic with
different naming conventions. The gate logic (structure alignment, premium/discount location)
is duplicated across:
- `confirmation_entry.py:131–146`
- `daily_context.py:207–228`
- `replay_6m.py:281–316`

**Recommendation:** Choose one canonical gate implementation. If `daily_context.py` is the
target interface, update `confirmation_entry.py` to use it.

---

## Finding Q-13: No Execution Adapter for session_smc/

**Severity: CRITICAL**

**Related file:** `strategies/adapters/st_a2_adapter.py` (exists for ST-A2; no equivalent for session_smc)

The `session_smc/` chain is a standalone module with no portfolio adapter. It cannot be
connected to `scripts/run_portfolio.py` or any live trading infrastructure without writing
an adapter. All account-level risk controls (daily loss, drawdown, position limits) are
unenforced until an adapter exists.

This is documented in ST_B_RESEARCH_PLAN.md §B.3 ("No execution adapter") but is also a
quality risk: the module is production-grade code (passing 127 tests) with no path to
production use without additional scaffolding.

---

## Finding Q-14: backtest.py Simulates Full Close at TP1 — Contradicts Spec

**Severity: MEDIUM**

**File:** `scripts/backtest.py:231–258` (`_simulate_trade`)

The backtest exits the full position at TP1. The spec (CLAUDE.md §4, SIGNAL_SPEC.md) defines
a partial-close model: 75% at TP1 (4R) and 25% runner to TP2 (5R) or session end. The
`Signal` dataclass includes `tp1` and `tp2` fields, but the backtest ignores `tp2`.

This means the ST-B Phase-0 result (when run) will not actually test the specified exit model.
The backtest produces PF/WR for a full-close-at-TP1 strategy, not for the specified
partial-close strategy.

**Recommendation:** Implement partial-close simulation in a new `scripts/backtest_stb.py`
as planned in ST_B_RESEARCH_PLAN.md §STB-02. Do not use `scripts/backtest.py` for ST-B
Phase-0.

---

## Finding Q-15: Minimum Closed Days Threshold is Magic Number

**Severity: LOW**

**File:** `daily_bias.py:95`
```python
if len(closed) < 2:
    return None
```

Requiring at least 2 closed daily bars is reasonable (need at least 2 for PDH/PDL and some
structure), but `2` is not a named constant or config key. If the daily structure computation
is changed to require more bars, this literal must be found and updated.

---

## Summary Table

| ID | Severity | File | Line | Category |
|---|---|---|---|---|
| Q-01 | MEDIUM | confirmation_entry.py | 155 | Dead code (result discarded) |
| Q-02 | LOW | confirmation_entry.py | 155, 158 | Duplicate computation |
| Q-03 | MEDIUM | confirmation_entry.py:33, liquidity_detector.py:14, daily_context.py:43 | — | Duplicated constant |
| Q-04 | LOW | daily_bias.py:23, daily_context.py:44 | — | Duplicated constant |
| Q-05 | HIGH | confirmation_entry.py | 141 | Logic inconsistency (stale price for location gate) |
| Q-06 | HIGH | confirmation_entry.py | 75–81 | Unvalidated gates default True |
| Q-07 | LOW | confirmation_entry.py | 108 | Misleading docstring |
| Q-08 | MEDIUM | daily_context.py | 224 | Fragile assert False guard |
| Q-09 | HIGH | confirmation_entry.py | 60–81 | Missing min_sl_pips risk gate |
| Q-10 | LOW | liquidity_detector.py | 68, 70 | Magic number thresholds |
| Q-11 | LOW | structure_detector.py | 177 | Non-obvious NaN check idiom |
| Q-12 | MEDIUM | daily_context.py, confirmation_entry.py | — | Duplicated gate logic, unused typed interface |
| Q-13 | CRITICAL | (missing file) | — | No execution adapter |
| Q-14 | MEDIUM | scripts/backtest.py | 231–258 | Backtest exit model contradicts spec |
| Q-15 | LOW | daily_bias.py | 95 | Magic number minimum days |
