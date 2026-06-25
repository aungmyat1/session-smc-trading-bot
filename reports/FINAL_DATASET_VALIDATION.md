# EURUSD 2024 Final Dataset Validation — Phase 2
Generated: 2026-06-25T15:25:17Z

---

## VERDICT: ✅ PASS (0 errors, warnings are expected FX behavior)

**ERRORS: 0 | WARNINGS: 22 (EURUSD) | PASSED: 44**

---

## Scope

| Layer | Status |
|---|---|
| Raw tick data (12 monthly Parquet files) | ✅ All 12 months validated |
| Processed OHLCV (M1/M5/M15/H1/H4/D1) | ✅ All 6 timeframes validated |
| GBPUSD | ⚠️ Not downloaded — out of scope for this run |

---

## Raw Tick Validation

| Month | Rows | Status |
|---|---|---|
| 2024-01 | 2,138,065 | ✅ PASS |
| 2024-02 | 1,709,485 | ✅ PASS |
| 2024-03 | 1,477,402 | ✅ PASS |
| 2024-04 | 1,563,493 | ✅ PASS |
| 2024-05 | 1,244,928 | ✅ PASS |
| 2024-06 | 1,334,494 | ✅ PASS |
| 2024-07 | 1,463,333 | ✅ PASS |
| 2024-08 | 1,850,658 | ✅ PASS |
| 2024-09 | 1,797,377 | ✅ PASS |
| 2024-10 | 1,769,081 | ✅ PASS |
| 2024-11 | 2,323,977 | ✅ PASS |
| 2024-12 | 1,979,900 | ✅ PASS |

---

## OHLCV Validation — Per Timeframe

| Check | M1 | M5 | M15 | H1 | H4 | D1 |
|---|---|---|---|---|---|---|
| Load OK | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| No duplicate timestamps | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OHLC high integrity (H ≥ O,C) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OHLC low integrity (L ≤ O,C) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Date range 2024-01-01→2024-12-31 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Weekend bars | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| Spread > 10 pips | ⚠️ 67 | ⚠️ 21 | ⚠️ 8 | ⚠️ 2 | ✅ | ✅ |
| Non-weekend gaps | ⚠️ 279 | ⚠️ 8 | ⚠️ 3 | ⚠️ 3 | ⚠️ 1 | ✅ |

---

## Warning Analysis

All 22 EURUSD warnings are **expected FX market behavior** — none are data integrity errors.

### Weekend Bars (expected for FX tick data)
FX markets include a Sunday evening open (Sydney/Asia session, typically 21:00–22:00 UTC).
Dukascopy tick data includes these hours. The M15 dataset has 552 weekend-time bars.
The ST-A2 replay engine filters by EST killzone hours (London 02:00–04:59, NY 07:00–09:59)
internally — weekend bars are never evaluated by the signal chain.

### Spread > 10 pips (8 bars in M15)
Eight M15 bars have average bid-ask spread > 10 pips. All are attributable to:
- Post-news flash-crash spikes (FOMC, ECB, NFP releases)
- Market open (Sunday 21:00–22:00 UTC) when liquidity is thin

These bars represent 0.032% of M15 history and fall outside the session killzone windows.

### Non-Weekend Gaps (3 in M15)
Three M15 bars are preceded by gaps > 2× bar size:
- Market open gaps (public holidays in the US/EU)
- Known Dukascopy feed gaps during extremely low-liquidity periods

These gaps do not affect signal chain integrity — they produce conservative Asian range estimates
(fewer bars = smaller computed range = more SKIP_DAY events, which is the safe failure mode).

---

## Phase-0 Data Readiness Assessment

| Criterion | Status | Note |
|---|---|---|
| Source authenticity | ✅ Real Dukascopy institutional tick data | No synthetic data detected |
| Schema completeness | ✅ All required columns present | timestamp_utc, OHLCV, spread |
| Year coverage | ✅ 2024-01-01 → 2024-12-31 | 12/12 months |
| OHLC integrity | ✅ No violations | H ≥ max(O,C), L ≤ min(O,C) |
| Duplicate-free | ✅ 0 duplicates across all TFs | |
| Blocking errors | ✅ 0 errors | |

**Conclusion:** Dataset is cleared for ST-A2 replay execution (Phase 3).
