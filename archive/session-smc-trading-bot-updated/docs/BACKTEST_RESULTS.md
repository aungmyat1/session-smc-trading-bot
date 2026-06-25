# BACKTEST_RESULTS.md
# Strategy A — Session Liquidity Reversal — Phase-0 Gate
# Run: 20260621T102303-daefa9  |  Date: 2026-06-21T10:23:03Z

---

## Summary Table
(ranked by Net PF std, then Trade Count)

| RR | Trades | Win% | Avg R | Gross PF | Net PF (std) | Net PF (2×) | Max DD (R) | Verdict |
|---|---|---|---|---|---|---|---|---|
| 5 | 169 | 32.0% | 0.108 | 1.299 | 1.151 | 1.025 | 18.72 | **PASS** |
| 4 | 169 | 32.5% | 0.106 | 1.299 | 1.149 | 1.022 | 16.72 | **PASS** |
| 3 | 169 | 34.3% | 0.054 | 1.225 | 1.078 | 0.954 | 11.18 | FAIL |
| 2 | 169 | 38.5% | 0.002 | 1.152 | 1.003 | 0.877 | 11.57 | FAIL |

---

## Phase-0 Gate
Condition: Trades ≥ 100 AND Net PF (std) > 1.0 AND Net PF (2×) > 1.0

| RR | Trades | Net PF (std) | Net PF (2×) | Gate |
|---|---|---|---|---|
| 2 | 169 | 1.003 | 0.877 | ❌ FAIL |
| 3 | 169 | 1.078 | 0.954 | ❌ FAIL |
| 4 | 169 | 1.149 | 1.022 | ✅ PASS |
| 5 | 169 | 1.151 | 1.025 | ✅ PASS |

### FINAL VERDICT: ✅ PASS — demo trading unlocked (subject to Phase-1 paper trade)

---

## Per-Symbol Breakdown (RR 5)

### EURUSD

| Metric | Standard | 2× Stress |
|---|---|---|
| Trades | 105 | 105 |
| Win Rate | 29.5% | 29.5% |
| Avg R | 0.044 | -0.045 |
| Net PF | 1.059 | 0.945 |
| Max DD | 14.00R | 18.20R |
| Total R | 4.61 | -4.67 |

### GBPUSD

| Metric | Standard | 2× Stress |
|---|---|---|
| Trades | 64 | 64 |
| Win Rate | 35.9% | 34.4% |
| Avg R | 0.214 | 0.124 |
| Net PF | 1.313 | 1.168 |
| Max DD | 9.70R | 11.02R |
| Total R | 13.67 | 7.96 |

## Per-Year Breakdown (combined, RR 5, standard spread)

| Year | Trades | Win% | Net PF |
|---|---|---|---|
| 2021 | 15 | 26.7% | 0.830 ⚠ |
| 2022 | 25 | 36.0% | 1.416 |
| 2023 | 48 | 27.1% | 0.878 ⚠ |
| 2024 | 20 | 40.0% | 1.659 |
| 2025 | 43 | 27.9% | 0.886 ⚠ |
| 2026 | 18 | 44.4% | 2.182 |

## Per-Session Breakdown (combined, RR 5, standard spread)

| Session | Trades | Win% | Net PF |
|---|---|---|---|
| london | 118 | 28.0% | 0.949 |
| new_york | 51 | 41.2% | 1.731 |

---

*Data: 2026-06-21T10:23:03Z*