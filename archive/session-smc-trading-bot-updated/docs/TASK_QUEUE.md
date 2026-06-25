# TASK_QUEUE.md
# Development Task Queue
# Update PROJECT_STATUS.md after each task completes

---

## Strategy A — Session Liquidity Reversal

### SA-01 — Asian Session Builder
**File:** `strategy/session_liquidity/session_builder.py`
**Deliverable:** `AsianRange` dataclass + `build_asian_range(candles_m15, trade_date)` function
**Test:** `tests/session_liquidity/test_session_builder.py`
- Verify: high/low from 18:00–01:45 EST only
- Verify: < 4 bars → returns None
- Verify: weekend bars not included in range
- Verify: DST transition handled (use 2024-03-10 and 2024-11-03)

---

### SA-02 — HTF Bias Filter
**File:** `strategy/session_liquidity/bias_filter.py`
**Deliverable:** `htf_bias(candles_4h, before_dt, swing_n=2)` → `'bullish'|'bearish'|'neutral'`
**Test:** `tests/session_liquidity/test_bias_filter.py`
- Verify: HH+HL → bullish
- Verify: LL+LH → bearish
- Verify: mixed → neutral
- Verify: `before_dt` cutoff excludes future 4H bar (lookahead)
- Verify: < 10 bars → neutral

---

### SA-03 — Killzone Filter
**File:** `strategy/session_liquidity/session_builder.py` (add to it) or inline in `session_strategy.py`
**Deliverable:** `classify_session(dt_utc)` → `'london'|'new_york'|None`
**Test:** `tests/session_liquidity/test_session_builder.py` (add cases)
- Verify: 07:00 UTC (winter) → london
- Verify: 10:00 UTC (winter) → None (exclusive upper bound)
- Verify: 12:00 UTC (winter) → new_york
- Verify: 15:00 UTC (winter) → None
- Verify: DST (summer): 06:00 UTC → london

---

### SA-04 — Sweep Detector
**File:** `strategy/session_liquidity/sweep_detector.py`
**Deliverable:** `Sweep` dataclass + `detect_sweep(candle, bar_idx, asian_range, direction)` → `Sweep|None`
**Test:** `tests/session_liquidity/test_sweep_detector.py`
- Verify: low < asian_low AND close > asian_low → bullish sweep
- Verify: high > asian_high AND close < asian_high → bearish sweep
- Verify: close ≤ asian_low (no snap back) → None
- Verify: wick only, closes below level → None

---

### SA-05 — Displacement Detector
**File:** `strategy/session_liquidity/displacement_detector.py`
**Deliverable:** `wilder_atr(candles, period=14)` + `Displacement` dataclass + `detect_displacement(candle, bar_idx, atr, direction, mult=1.2)` → `Displacement|None`
**Test:** `tests/session_liquidity/test_displacement_detector.py`
- Verify: body > 1.2×ATR AND close in upper 25% → bullish displacement
- Verify: body > 1.2×ATR AND close in lower 25% → bearish displacement
- Verify: body just below threshold → None
- Verify: close in wrong quartile → None
- Verify: NaN ATR (early bars) → None
- Verify: Wilder's seed at index 14 (not index 13)

---

### SA-06 — Entry Engine
**File:** `strategy/session_liquidity/entry_engine.py`
**Deliverable:** `Signal` dataclass + `build_signal(candle, sweep, displacement, asian_range, session, rr, sl_buffer_pips)` → `Signal|None`
**Test:** `tests/session_liquidity/test_entry_engine.py`
- Verify: long signal: entry=close, sl=sweep_low-buffer, tp=entry+RR×dist
- Verify: short signal: entry=close, sl=sweep_high+buffer, tp=entry-RR×dist
- Verify: sl_dist ≤ 0 → None (degenerate)
- Verify: sl_pips computed correctly

---

### SA-07 — Strategy Orchestrator
**File:** `strategy/session_liquidity/session_strategy.py`
**Deliverable:** `run_strategy(candles_m15, candles_4h, symbol, config)` → `list[Signal]`
**Test:** `tests/session_liquidity/test_session_strategy.py`
- Verify: full bullish signal fires (complete synthetic dataset)
- Verify: full bearish signal fires
- Verify: neutral 4H bias → no signal
- Verify: asian range too small → no signal
- Verify: no displacement → no signal (sweep only)
- Verify: one-trade-per-session gate (second signal in same session blocked)
- Verify: pending sweep times out after 4 bars

---

### SA-08 — Backtest Validation
**File:** `scripts/backtest_session_liquidity.py`
**Deliverable:** CLI script producing RR comparison table + per-year + per-session breakdown
**Audit:** Generate `LOOKAHEAD_AUDIT.md`, `PERFORMANCE_AUDIT.md`
**Gate:** Trades ≥ 100 AND PF > 1.0 at std AND 2× spread

---

## Data Pipeline

### DP-01 — Fetch Historical Data
**Script:** `scripts/fetch_data.py`
**Status:** COMPLETE — Dukascopy bi5 async download, M15+H1+H4 for EURUSD+GBPUSD
**Output:** `data/historical/EUR_USD_M15.csv`, `EUR_USD_H4.csv`, `GBP_USD_M15.csv`, `GBP_USD_H4.csv`

### DP-02 — Data Audit
**Script:** `scripts/data_audit.py`
**Status:** COMPLETE — generates `DATA_AUDIT.md`
**Gate:** missing < 0.1%, duplicates = 0, price errors = 0, coverage ≥ 4.5yr

---

## Strategy B — SMC (BLOCKED until Strategy A passes)

### SB-01 — Swing Detector       [COMPLETE — session_smc/swing_detector.py]
### SB-02 — Structure Detector   [COMPLETE — session_smc/structure_detector.py]
### SB-03 — Liquidity Detector   [COMPLETE — session_smc/liquidity_detector.py]
### SB-04 — POI Detector         [COMPLETE — session_smc/poi_detector.py]
### SB-05 — Confirmation Entry   [COMPLETE — session_smc/confirmation_entry.py]
### SB-06 — SMC Backtest         [PENDING — blocked on data download + Strategy A gate]

---

## Deployment (BLOCKED until Strategy A passes)

### DEP-01 — Demo deployment (MetaAPI demo account)
### DEP-02 — 30-day paper trade
### DEP-03 — Micro live ($200, 0.5% risk)
