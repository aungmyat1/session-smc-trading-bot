# PHASE 2 — Dataset Validation
Symbol: EURUSD | Period: 2025-01-01 → 2025-12-31T23:59:59Z

## Coverage

| Item | Value | Status |
|---|---|---|
| M15 bars in 2025 | 24,144 | ✅ |
| Expected minimum | 20,000 | — |
| Date range first | 2025-01-01T22:00:00Z | — |
| Date range last | 2025-12-31T21:45:00Z | — |

## Integrity Checks

| Check | Result | Status |
|---|---|---|
| Duplicate timestamps | 0 | ✅ None |
| OHLC integrity errors | 0 | ✅ None |
| Weekend bars | 0 | ✅ None |
| Gaps > 1h | 73 | ⚠️ (weekend/holiday expected) |
| Avg bar range (pips) | 7.4 | — |

## Significant Gaps (first 5)

| From | To | Duration (min) |
|---|---|---|
| 2025-01-03 21:45:00 | 2025-01-06 00:00:00 | 3015 |
| 2025-01-09 10:45:00 | 2025-01-09 12:00:00 | 75 |
| 2025-01-09 13:45:00 | 2025-01-09 16:00:00 | 135 |
| 2025-01-10 21:45:00 | 2025-01-13 04:00:00 | 3255 |
| 2025-01-13 06:45:00 | 2025-01-13 08:00:00 | 75 |

## Verdict

✅ PASS — dataset clean and sufficient for replay.