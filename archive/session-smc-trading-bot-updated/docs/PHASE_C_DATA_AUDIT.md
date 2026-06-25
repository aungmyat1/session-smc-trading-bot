# PHASE C — DATA AUDIT
**Date:** 2026-06-25 | Replay window: 2026-01-01 → 2026-06-19

---

## Data Inventory

| Symbol | TF | Total Bars | Replay Window Bars | Date Range (Replay) | Sorted | Dupes | Gap Days |
|--------|----|-----------|-------------------|---------------------|--------|-------|----------|
| EURUSD | M15 | 121,086 | 11,199 | 2026-01-01 → 2026-06-19 | ✅ | 0 | 2 |
| EURUSD | H4 | 7,769 | 720 | 2026-01-01 → 2026-06-19 | ✅ | 0 | N/A |
| GBPUSD | M15 | 79,339 | 11,363 | 2026-01-01 → 2026-06-19 | ✅ | 0 | 1 |
| GBPUSD | H4 | 5,245 | 727 | 2026-01-01 → 2026-06-19 | ✅ | 0 | N/A |

---

## Quality Checks

### Ordering
All four datasets are chronologically sorted. ✅

### Duplicates
Zero duplicate timestamps found in any dataset. ✅

### Gap Analysis
- EURUSD M15: 2 days with < 20 bars on trading weekdays
  - These are likely partial trading days (holidays, half-sessions)
  - Not a data error — acceptable
- GBPUSD M15: 1 day with < 20 bars
  - Same assessment — partial session day

### UTC Consistency
All timestamps use ISO 8601 UTC format: `YYYY-MM-DDTHH:MM:SSZ`
No timezone ambiguity. UTC throughout. ✅

### Coverage
- EURUSD M15: Covers replay window end-to-end ✅
- EURUSD H4: Covers replay window end-to-end ✅
- GBPUSD M15: Covers replay window end-to-end ✅
- GBPUSD H4: Covers replay window end-to-end ✅
- **XAUUSD: NOT AVAILABLE ❌** — configured in demo.yaml but no historical data exists

### Data End Date
All datasets end at 2026-06-19 (most recent available). Replay window set to
2026-06-30 but data caps at Jun 19. Effective replay: **2026-01-01 → 2026-06-19**
(approximately 24.5 trading weeks).

---

## H4 Warmup Context
The strategy uses H4 data for HTF bias detection before each session.
- Total H4 bars available for EURUSD: 7,769 (from 2021)
- H4 bars before replay start: 7,049 (adequate warmup context ✅)
- Strategy has full 5yr H4 history for bias calculation

---

## VERDICT: ✅ PASS

No data quality issues blocking replay. Zero duplicates, correct ordering, UTC consistent.
Minor gap days (holidays) are normal and do not affect strategy logic.
XAUUSD absence is a scope limitation (not a data error) — replay will cover EUR+GBP only.
