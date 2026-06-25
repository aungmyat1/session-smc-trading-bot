# DATA REPORT
**Date:** 2026-06-25 | Period: 2026-01-01 → 2026-06-30

## File Inventory

| File | Total Bars | Replay Bars | Start | End | Dups |
|------|-----------|-------------|-------|-----|------|
| EURUSD_M15 | 121,086 | 11,199 | 2021-06-21 | 2026-06-19 | 0 |
| EURUSD_H1 | 30,274 | 2,800 | 2021-06-21 | 2026-06-19 | 0 |
| EURUSD_H4 | 7,769 | 720 | 2021-06-21 | 2026-06-19 | 0 |
| GBPUSD_M15 | 79,339 | 11,363 | 2023-03-13 | 2026-06-19 | 0 |
| GBPUSD_H1 | 19,818 | 2,841 | 2023-03-14 | 2026-06-19 | 0 |
| GBPUSD_H4 | 5,245 | 727 | 2023-02-01 | 2026-06-19 | 0 |

## XAUUSD
**NOT AVAILABLE** — no historical CSV files found for XAUUSD (any timeframe).
XAUUSD is excluded from this replay. Deployment scope: EURUSD + GBPUSD only.

## H1 Data
H1 candles available for both pairs. ST-A2 strategy uses M15 (entry) + H4 (bias) only.
H1 is available for future strategy extensions but not consumed by the current signal chain.

## Quality
- Zero duplicate timestamps in all files ✅
- Chronologically sorted ✅
- UTC throughout ✅
- No data gaps blocking the replay window ✅

## VERDICT: ✅ PASS
EURUSD + GBPUSD data sufficient for full replay. XAUUSD excluded (no data).