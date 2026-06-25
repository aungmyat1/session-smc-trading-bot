# PHASE 8 — Comparison Report
New replay: EURUSD 2025 (12 months) vs Phase-0 Baseline

## Prior Results Available

| Source | Location | Status |
|---|---|---|
| ST-A2 Phase-0 (5yr) | `docs/VERDICT_LOG.md` | ✅ Found |
| ST-D2-6M baseline | `docs/VERDICT_LOG.md` | ✅ Found |
| ST-A2 Confirmation | `docs/ST_A2_CONFIRMATION.md` | ✅ Found |

## Comparison Table

| Metric | Phase-0 Baseline (5yr, EUR+GBP) | 2025 EURUSD Replay (1yr) |
|---|---|---|
| Period | 2021-06-21 → 2026-06-19 (5yr, EUR+GBP combined) | 2025 EURUSD only |
| Trades (n) | 169 (combined) | 16 |
| Win Rate | 32.0% | 31.2% |
| PF (std) | 1.151 | 1.067 |
| PF (2×) | 1.025 | 0.948 |
| Max DD | 18.72R | 6.89R |

## Important Caveats on Comparison

1. **Phase-0 baseline = EUR+GBP combined, 5yr.** The 2025 replay covers EURUSD only, 1yr.
   A 1yr EURUSD-only slice is not directly comparable to the 5yr combined baseline.
2. **Expected n per year EURUSD only:** 5yr had ~169 combined; EURUSD ~60% historically
   → ~20–30 EURUSD signals/year expected.
3. **2025 n=16:** within expected range.

## ST-D2-6M Baseline (closest comparable)

From VERDICT_LOG.md ST-D2-6M (2026-01 → 2026-06, EURUSD + GBPUSD):
- EURUSD BASELINE 6mo: n=6, PF_std=1.804, PF_2x=1.560
- GBPUSD BASELINE 6mo: n=10, PF_std=2.587, PF_2x=2.204
- Combined 6mo: n=16, PF_std=2.224, PF_2x=1.909

The 6-month 2026 window showed strong PF with n=16 combined.
2025 full-year EURUSD-only replay provides a different window.