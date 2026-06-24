# BACKTEST_COST_REVALIDATION_REPORT.md
# ST-A2 Backtest — Cost Revalidation Run
# Status: TEMPLATE — populate after E6 revalidation backtest completes
# Prerequisite: SPREAD_RESEARCH_FINAL_REPORT.md populated AND config/costs.json updated

---

## Run Metadata

<!-- Populate after E6 run -->

| Field | Value |
|---|---|
| Run ID | |
| Date | |
| Backtest script | `scripts/backtest_session_liquidity.py` |
| Cost profile used | `vantage_measured` |
| EURUSD cost (std/2×) | / pip |
| GBPUSD cost (std/2×) | / pip |
| Strategy | ST-A2 (min_sl_pips=5.0, RR=5) |
| Data | EURUSD (4.9yr) + GBPUSD (3.3yr) |

---

## Results vs Phase-0 Baseline

<!-- Populate after E6 run -->

| Metric | Phase-0 (placeholder) | E6 (measured costs) | Change |
|---|---|---|---|
| Trade count | 169 | | |
| Win rate | 32.0% | | |
| Gross PF | 1.299 | | |
| Net PF (std) | 1.151 | | |
| Net PF (2×) | **1.025** | | |
| Max DD | 18.72R | | |
| Phase-0 gate | ✅ PASS | | |

---

## Per-Symbol Results (E6 run)

<!-- Populate after E6 run -->

| Symbol | Trades | Win% | Net PF (std) | Net PF (2×) | Max DD |
|---|---|---|---|---|---|
| EURUSD | | | | | |
| GBPUSD | | | | | |
| Combined | | | | | |

---

## Per-Session Results (E6 run)

<!-- Populate after E6 run -->

| Session | Trades | Win% | Net PF (std) |
|---|---|---|---|
| london | | | |
| new_york | | | |

---

## Gate Assessment

<!-- Populate after E6 run -->

| Gate | Condition | Result | Status |
|---|---|---|---|
| Trade count | ≥ 100 | | |
| Net PF (std) | > 1.0 | | |
| Net PF (2×) | > 1.0 | | |
| E6 Gate | All three | | |

---

## E6 Decision

<!-- Populate after E6 run — apply decision table from OPS02_REVISED_GATE.md -->

| PF_2x band | Action |
|---|---|
| ≥ 1.05 | Continue to E1–E4 execution gate |
| 1.00–1.05 | Continue to E1–E4, thin margin — monitor GBPUSD |
| < 1.00 | STOP — prepare ST_A3_RECOVERY_OPTIONS.md |

**E6 verdict:** <!-- PENDING -->

---

## VERDICT_LOG.md Sub-Entry

<!-- Add to docs/VERDICT_LOG.md under ST-A2 after E6 run — not a new trial -->

```
ST-A2 (E6 revalidation) | <date> | Same signal spec as ST-A2 (run 20260621T100458-183aaa).
Cost profile changed from PLACEHOLDER_vt_markets_assumption to vantage_measured
(EURUSD std=X.XX / GBPUSD std=X.XX, measured 2026-06-24 to 2026-06-30).
Results: n=169, PF_std=X.XXX, PF_2x=X.XXX | PASS / FAIL
```

---

*BACKTEST_COST_REVALIDATION_REPORT.md | Template | Populate after E6 — ~2026-06-30*
