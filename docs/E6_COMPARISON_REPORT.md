# E6_COMPARISON_REPORT.md
# ST-A2 — E6 vs PRE_E6_BASELINE Comparison
# Status: TEMPLATE — populated automatically by scripts/compare_e6_to_baseline.py
# Prerequisite: bash scripts/run_e6_revalidation.sh must complete first

---

## How to Generate This Report

After E6 pipeline completes:

```bash
python3 scripts/compare_e6_to_baseline.py
```

The script reads `docs/BACKTEST_RESULTS.md` (updated by E6), compares against
the locked baseline, and overwrites this file with populated results.

If E6 has not yet been run, the script exits with:
```
[INFO] BACKTEST_RESULTS.md still contains baseline run (20260621T102303-daefa9).
       E6 has not yet been executed.
```

---

## Run Identity

| Field | Baseline | E6 |
|---|---|---|
| Run ID | `20260621T100458-183aaa` | *pending E6 run* |
| Cost profile | PLACEHOLDER_vt_markets_assumption | vantage_measured |
| EURUSD cost (std) | 1.4 pip | *measured* |
| GBPUSD cost (std) | 1.8 pip | *measured* |
| Generated | 2026-06-21 | *pending* |

---

## Metric Comparison (RR 5, Combined EURUSD + GBPUSD)

| Metric | Baseline | E6 | Delta | Direction |
|---|---|---|---|---|
| Trade count | 169 | *pending* | — | *pending* |
| Win rate | 32.0% | *pending* | — | *pending* |
| Gross PF | 1.299 | *pending* | — | *pending* |
| Net PF (std) | 1.151 | *pending* | — | *pending* |
| Net PF (2×) | **1.025** | *pending* | — | *pending* |
| Expectancy | 0.108R | *pending* | — | *pending* |
| Max DD | 18.72R | *pending* | — | *pending* |

---

## Overall E6 Verdict

*Pending — run `python3 scripts/compare_e6_to_baseline.py` after E6 completes.*

See decision rules: `docs/E6_DECISION_MATRIX.md`

---

## Integrity Check

Trade count and win rate must be identical to baseline — costs affect P&L only,
not signal generation. Any change here indicates a pipeline error.

| Check | Expected | Actual | Status |
|---|---|---|---|
| Trade count unchanged | 169 | *pending* | *pending* |
| Win rate stable | 32.0% | *pending* | *pending* |

---

*E6_COMPARISON_REPORT.md | Template | Auto-populated by scripts/compare_e6_to_baseline.py*
