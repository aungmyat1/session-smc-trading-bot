# E6_EXECUTION_CHECKLIST.md
# Gate-Day Execution Checklist — ST-A2 Cost Revalidation
# Complete every item in order before running E6.

---

## Pre-E6 Checks

- [ ] `python3 scripts/check_phase2_completion.py` exits 0 (READY_FOR_COST_REVALIDATION)
- [ ] `python3 scripts/spread_status.py` shows HEALTHY and sample age < 5 min
- [ ] Stop spread collector: `tmux kill-session -t spreads`
- [ ] Confirm `research/spread_samples.csv` is no longer growing (final row count stable)
- [ ] `config/costs.json` active_profile = `PLACEHOLDER_vt_markets_assumption` (not yet vantage_measured)
- [ ] `docs/BACKTEST_RESULTS.md` run ID is a baseline run (20260621T100458-183aaa or 20260621T102303-daefa9)
- [ ] `docs/PRE_E6_BASELINE.md` is unchanged — do not modify
- [ ] OPS-01 stability run complete (through 2026-06-28)
- [ ] `git status` — no uncommitted changes to strategy code, risk params, or entry/exit logic
- [ ] Bot session is running normally (`tmux ls` shows `bot`) — do not stop it

---

## E6 Execution Sequence

Run in this exact order. Do not reorder.

```bash
# Step 1 — Gate confirmation (must exit 0)
python3 scripts/check_phase2_completion.py

# Step 2 — Build cost model from frozen samples
python3 scripts/build_cost_model.py

# Step 3 — Freeze dataset (immutable snapshot + SHA256)
python3 scripts/freeze_phase2_dataset.py

# Step 4 — Verify snapshot is complete
#   Open research/e6_dataset_snapshot/dataset_manifest.json
#   Confirm: collection_complete = true
#   Confirm: london_sessions >= 5, ny_sessions >= 5
#   Confirm: active_profile = PLACEHOLDER_vt_markets_assumption

# Step 5 — Run E6 pipeline (gate → analyze → model → export → backtest)
bash scripts/run_e6_revalidation.sh

# Step 6 — Compare results to baseline
python3 scripts/compare_e6_to_baseline.py
```

---

## Post-E6 Actions

- [ ] Read `docs/BACKTEST_RESULTS.md` — note PF_2x at RR=5
- [ ] Read `docs/E6_COMPARISON_REPORT.md` — note IMPROVED / UNCHANGED / DEGRADED for each metric
- [ ] Check trade count is still 169 (must be unchanged — see E6_DECISION_MATRIX.md §integrity)
- [ ] Apply decision matrix (`docs/E6_DECISION_MATRIX.md`):
  - PF_2x ≥ 1.05 → ✅ PASS — proceed to E1–E4
  - PF_2x 1.00–1.05 → ⚠️ REVIEW — proceed with GBPUSD monitoring
  - PF_2x < 1.00 → ❌ REJECT — stop, write ST_A3_RECOVERY_OPTIONS.md
- [ ] Populate `docs/BACKTEST_COST_REVALIDATION_REPORT.md` from BACKTEST_RESULTS.md
- [ ] Check `docs/E6_PAIR_ANALYSIS.md` — note EURUSD and GBPUSD individual PF_2x
- [ ] Check `docs/E6_SESSION_ANALYSIS.md` — note London and NY session PF
- [ ] Add E6 sub-entry to `docs/VERDICT_LOG.md` under ST-A2
- [ ] If PASS or REVIEW: proceed to E1 (enable LIVE_TRADING=true, start 7-day execution gate)

---

## Do Not

- Do not re-run the backtest with different parameters to improve the result
- Do not modify strategy code, entries, exits, or risk settings
- Do not stop the bot session during E6 (it does not use the backtest data files)
- Do not change LIVE_TRADING — owner only

---

*E6_EXECUTION_CHECKLIST.md | Written 2026-06-24 | Use on gate day ~2026-06-30*
