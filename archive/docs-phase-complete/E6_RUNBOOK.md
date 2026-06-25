# E6_RUNBOOK.md
# E6 Cost Revalidation — Operator Runbook
# Session Liquidity Bot (ST-A2)
# Written: 2026-06-24

---

## Purpose

E6 replaces the Phase-0 placeholder spread costs (assumed VT Markets standard)
with measured Vantage Standard STP killzone-hour costs.

ST-A2 passed Phase-0 at PF_2x = 1.025 — a 0.025 margin over the gate.
The entire verdict rests on whether the cost assumption was accurate.
E6 confirms or refutes it with real data.

---

## Preconditions

Run `scripts/check_phase2_completion.py` before anything else.
All three items must be satisfied:

| Check | Requirement | Command |
|---|---|---|
| London sessions | ≥ 5 | `python3 scripts/check_phase2_completion.py` |
| NY sessions | ≥ 5 | (same) |
| Total rows | ≥ 7,000 | (same) |
| OPS-01 stability run | Complete by 2026-06-28 | `cat docs/OPS01_DAILY_REPORT.md` |

If `check_phase2_completion.py` exits non-zero, do not proceed.

---

## Execution

From the repo root:

```bash
bash scripts/run_e6_revalidation.sh
```

This runs all 5 steps in sequence and prints next actions on completion.

---

## Pipeline Steps (what the shell script does)

| Step | Script | Output |
|---|---|---|
| 0 | `scripts/check_phase2_completion.py` | exits 0 or aborts |
| 1 | `research/analyze_spreads.py` | `docs/SPREAD_RESEARCH_FINAL_REPORT.md` |
| 2 | `scripts/build_cost_model.py` | `research/cost_model.json` |
| 3 | `scripts/export_spread_limits.py` | `research/recommended_spread_limits.yaml` + `config/costs.json` |
| 4 | `scripts/backtest_session_liquidity.py --costs-json config/costs.json` | `docs/BACKTEST_RESULTS.md` |

---

## Validation (what to check in BACKTEST_RESULTS.md)

Open `docs/BACKTEST_RESULTS.md` after the pipeline completes. Focus on RR=5.

| Metric | Phase-0 baseline | Expected direction | Flag if |
|---|---|---|---|
| Trade count | 169 | Equal | Changes by > 2 (costs don't affect signals) |
| Net PF (std) | 1.151 | Higher if measured < placeholder | Any drop |
| Net PF (2×) | **1.025** | Higher if measured < placeholder | Drops below 1.00 |
| Win rate | 32.0% | Unchanged | Changes (should be identical) |
| Max DD | 18.72R | Approximately same | Changes by > 2R |

**Trade count must not change.** Costs affect P&L but not signal generation.
If trade count changes, something is wrong — stop and investigate.

---

## E6 Decision Matrix

Apply after reading PF_2x from `docs/BACKTEST_RESULTS.md` at RR=5.

| PF_2x result | Decision | Next action |
|---|---|---|
| ≥ 1.05 | ✅ **PASS** — margin comfortable | Proceed to E1–E4 execution gate |
| 1.00–1.05 | ⚠️ **REVIEW** — thin margin | Proceed to E1–E4; monitor GBPUSD spread during E1 live run |
| < 1.00 | ❌ **REJECT** — no edge at measured cost | STOP. Write `docs/ST_A3_RECOVERY_OPTIONS.md`. Do not proceed to demo. |

Full decision table with rationale: `docs/OPS02_REVISED_GATE.md §E6`.

---

## What Changes / What Does Not

### Changes after E6

| Item | Change |
|---|---|
| `config/costs.json` | `active_profile` → `vantage_measured`; `profiles.vantage_measured` filled |
| `docs/BACKTEST_RESULTS.md` | Overwritten with E6 run results |
| `research/backtest_runs.csv` | New row appended (E6 run) |
| `research/trades.csv` | New rows appended (E6 trade log) |
| `research/cost_model.json` | Created |
| `research/recommended_spread_limits.yaml` | Created |
| `docs/SPREAD_RESEARCH_FINAL_REPORT.md` | Populated from template |

### Does NOT change

| Item | Why |
|---|---|
| Strategy code (`session_strategy.py`, `bias_filter.py`, `entry_engine.py`, …) | Signal logic is unchanged |
| Risk parameters (`sl_pips`, `rr`, `daily_loss`, `drawdown`) | Not a new trial |
| `LIVE_TRADING` flag | Owner-only |
| `.env` credentials | Not touched |
| Trial ID in VERDICT_LOG.md | ST-A2 is the same trial — cost update is a sub-entry, not a new row |

---

## Post-E6 Actions

### If PASS (PF_2x ≥ 1.00)

1. Populate `docs/BACKTEST_COST_REVALIDATION_REPORT.md` with results from `docs/BACKTEST_RESULTS.md`
2. Add E6 sub-entry to `docs/VERDICT_LOG.md` under ST-A2 (template at bottom of `BACKTEST_COST_REVALIDATION_REPORT.md`)
3. Proceed to E1: enable `LIVE_TRADING=true` in `.env` and start the 7-day execution gate

### If REJECT (PF_2x < 1.00)

1. Do NOT proceed to demo or live
2. Write `docs/ST_A3_RECOVERY_OPTIONS.md` — options include:
   - Tighter cost filter (only trade when spread < 1.2 pip)
   - Session restriction (London only, which historically has tighter spreads)
   - Raw account switch (Vantage Raw ECN: ~0.7–0.9 pip all-in)
   - Strategy revision → new trial ST-A3

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `[BLOCKED] Phase 2 collection not yet complete` | Gate not met | Wait for 5+5 sessions |
| `[ERROR] vantage_measured has null costs` | export_spread_limits.py not run or failed | Re-run Step 3 manually |
| `[ERROR] Symbol 'EURUSD' not in profile` | costs.json corrupted | Restore from git: `git checkout config/costs.json`, re-run pipeline |
| Trade count changes | Bug in cost injection | Check that `--costs-json` was passed; costs don't affect signal generation |
| `ModuleNotFoundError` | Wrong working directory | Run from repo root: `cd ~/session-smc-trading-bot` |

---

*E6_RUNBOOK.md | Written: 2026-06-24 | Do not run until check_phase2_completion.py exits 0*
