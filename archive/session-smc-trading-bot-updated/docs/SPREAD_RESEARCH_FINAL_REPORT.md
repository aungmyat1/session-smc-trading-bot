# SPREAD_RESEARCH_FINAL_REPORT.md
# Vantage Spread Research — Final Report
# Status: POPULATED — generated 2026-06-24T12:11:03Z
# Source: research/spread_samples.csv

---

## 1 — Collection Summary

| Field | Value |
|---|---|
| Collection start | 2026-06-24 05:57:48 UTC |
| Collection end   | 2026-06-24 11:12:04 UTC |
| London sessions  | 1/5 |
| NY sessions      | 1/5 |
| Total rows       | 1,840 |
| Poll interval    | ~30 s (target) |
| Symbol dropouts  | see Section 2 |

---

## 2 — Sample Counts by Symbol and Session

| Symbol | Session | n | Notes |
|---|---|---|---|
| AUDUSD | london | 330 | killzone |
| AUDUSD | new_york | 24 | killzone |
| AUDUSD | off | 106 | off-session |
| EURUSD | london | 330 | killzone |
| EURUSD | new_york | 24 | killzone |
| EURUSD | off | 106 | off-session |
| GBPUSD | london | 330 | killzone |
| GBPUSD | new_york | 24 | killzone |
| GBPUSD | off | 106 | off-session |
| USDJPY | london | 330 | killzone |
| USDJPY | new_york | 24 | killzone |
| USDJPY | off | 106 | off-session |

---

## 3 — Average Spread by Symbol and Session

| Symbol | Session | Avg (pip) | Median (pip) | P95 (pip) | Min | Max |
|---|---|---|---|---|---|---|
| AUDUSD | london | 1.46 | 1.50 | 1.50 | 1.40 | 1.60 |
| AUDUSD | new_york | 1.48 | 1.50 | 1.50 | 1.40 | 1.60 |
| EURUSD | london | 1.35 | 1.30 | 1.40 | 1.30 | 1.40 |
| EURUSD | new_york | 1.35 | 1.35 | 1.40 | 1.30 | 1.40 |
| GBPUSD | london | 1.55 | 1.60 | 1.60 | 1.50 | 1.80 |
| GBPUSD | new_york | 1.56 | 1.60 | 1.60 | 1.50 | 1.60 |
| USDJPY | london | 1.85 | 1.90 | 1.90 | 1.80 | 1.90 |
| USDJPY | new_york | 1.88 | 1.90 | 1.90 | 1.80 | 2.00 |

---

## 4 — Hourly Breakdown Within Sessions (EURUSD and GBPUSD)

### EURUSD — London

| Hour UTC | n | Avg | Median | Max |
|---|---|---|---|---|
| 06:xx | 113 | 1.35 | 1.40 | 1.40 |
| 07:xx | 115 | 1.35 | 1.30 | 1.40 |
| 08:xx | 102 | 1.35 | 1.30 | 1.40 |

### EURUSD — New York

| Hour UTC | n | Avg | Median | Max |
|---|---|---|---|---|
| 11:xx | 24 | 1.35 | 1.35 | 1.40 |
| 12:xx | 0 | — | — | — |
| 13:xx | 0 | — | — | — |

### GBPUSD — London

| Hour UTC | n | Avg | Median | Max |
|---|---|---|---|---|
| 06:xx | 113 | 1.56 | 1.60 | 1.80 |
| 07:xx | 115 | 1.55 | 1.60 | 1.80 |
| 08:xx | 102 | 1.55 | 1.50 | 1.70 |

### GBPUSD — New York

| Hour UTC | n | Avg | Median | Max |
|---|---|---|---|---|
| 11:xx | 24 | 1.56 | 1.60 | 1.60 |
| 12:xx | 0 | — | — | — |
| 13:xx | 0 | — | — | — |

---

## 5 — Recommended Standard and Stress-2× Costs

Methodology: combined killzone average (london + new_york), P95 rounded
up to next 0.05 pip = standard. Standard × 2 = stress.

| Symbol | KZ avg (pip) | KZ P95 (pip) | Recommended standard | Recommended stress 2× | vs Placeholder |
|---|---|---|---|---|---|
| EURUSD | 1.35 | 1.40 | 1.40 pip | 2.80 pip | +0.00 vs 1.4 |
| GBPUSD | 1.55 | 1.60 | 1.60 pip | 3.20 pip | -0.20 vs 1.8 |

---

## 6 — Comparison Against Placeholder Assumptions

| Symbol | Measured KZ avg | Placeholder std | Delta | Delta % |
|---|---|---|---|---|
| EURUSD | 1.35 | 1.40 | -0.05 | -3.7% |
| GBPUSD | 1.55 | 1.80 | -0.25 | -13.7% |

---

## 7 — Preliminary Trend

From `research/SPREAD_CAPTURE_INTERIM.md` (1 London session, 2026-06-24):

| Symbol | Preliminary avg | Placeholder | Signal |
|---|---|---|---|
| EURUSD | 1.35 pip | 1.40 pip | Lower |
| GBPUSD | 1.55 pip | 1.80 pip | Lower |

This report supersedes the preliminary reading with 1,840 rows.

---

## 8 — Estimated Impact on ST-A2 PF_2x

| Metric | Placeholder costs | Direction |
|---|---|---|
| PF_std  | 1.151 | See BACKTEST_RESULTS.md post-E6 run |
| PF_2x   | 1.025 | See BACKTEST_RESULTS.md post-E6 run |

Run `python3 scripts/backtest_session_liquidity.py --costs-json config/costs.json`
after export_spread_limits.py updates the active_profile.

---

## 9 — Conclusion and Recommendation

See `docs/BACKTEST_COST_REVALIDATION_REPORT.md` for the E6 verdict
(populated after the backtest re-run with measured costs).

*Generated: 2026-06-24T12:11:03Z*