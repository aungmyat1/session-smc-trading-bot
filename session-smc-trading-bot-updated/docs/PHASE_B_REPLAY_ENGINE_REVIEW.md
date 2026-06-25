# PHASE B — REPLAY ENGINE REVIEW
**Date:** 2026-06-25

---

## Engine Option 1: replay_runner.py (bar-by-bar via ForwardTestSimulator)

### Complexity Analysis
```
For each bar i (1..n):
    sim.feed(bar_i)
        → run_strategy(m15[0..i], h4, symbol)  ← full O(n) scan every call
Total: O(n²)
```

**Measured:** Timed out at 480s on 11,199 bars (Jan–Jun 2026 EURUSD M15).
**Root cause:** `ForwardTestSimulator.feed()` calls `run_strategy()` on the full accumulated
history on every bar, rebuilding swing detection, session grouping, and ATR maps each time.

### Decision: REPLACE with batch engine

---

## Engine Option 2: run_strategy() batch call (used in replay_runner.py after fix)

### Complexity Analysis
```
run_strategy(m15_all, h4_all, symbol)
    sorted_m15 = sort(m15_all)             O(n log n)
    atrs = wilder_atr(sorted_m15, 14)     O(n)
    _kz_by_date = group by date           O(n)
    for date in trade_dates:               O(days) ≈ O(n/96)
        for bar in day_bars:              O(bars_per_day) ≈ O(20)
Total: O(n)  — single linear pass
```

**Measured:** Completes in < 3 seconds on 11,199 M15 bars.

### Lookahead equivalence confirmed
Per PHASE_A_AUDIT_CONFIRMATION.md and `compare_with_backtest()`:
- Batch call produces identical signals to bar-by-bar feed
- Causality is guaranteed by chronological date iteration and `[:i]` slice patterns
- No cross-session data access

---

## Engine Option 3: scripts/backtest_session_liquidity.py

The existing 5yr backtest engine (`scripts/backtest_session_liquidity.py`) uses the same
`run_strategy()` call internally, extended with:
- Multi-year date filtering
- Per-year / per-session breakdown tables  
- Research logger (CSV appender)
- Phase-0 gate evaluation across RR variants

**5yr backtest output (run 2026-06-21):** 169 trades, PF_std=1.151, PF_2x=1.025 at RR5 — **PASS**

---

## Decision

```
PHASE D REPLAY ENGINE: run_strategy() batch call (O(n))
  - replay_runner.py updated to use batch mode
  - Equivalent to bar-by-bar (per Phase A audit)
  - Fast enough for any date window
  - Causal: confirmed

5yr CONTEXT ENGINE: scripts/backtest_session_liquidity.py
  - Used for historical context (Phase F)
  - Results: 169 trades, 32% WR, PF_2x=1.025 (PASS)
```

---

## VERDICT: ✅ PASS
Replay engine correctly uses O(n) batch mode. Bar-by-bar mode documented and rejected for performance reasons. Causality of batch mode confirmed.
