# E6_READINESS_AUDIT.md
# E6 Cost Revalidation — Pipeline Readiness Audit
# Audited: 2026-06-24
# Auditor: Phase 2.3 automated checks + integration tests

---

## Audit Verdict: ✅ PIPELINE READY

All pipeline files exist, pass syntax checks, and integration tests pass.
The only blocker is E5 data collection (gate not yet met — see §Phase 2 Gate below).

---

## §1 — Pipeline File Inventory

### Input

| File | Path | Status | Notes |
|---|---|---|---|
| Spread samples | `research/spread_samples.csv` | ✅ EXISTS | 1,840 rows (Day 1 of 5) |
| Costs config | `config/costs.json` | ✅ EXISTS | active_profile = PLACEHOLDER |
| Data EURUSD M15 | `data/historical/EUR_USD_M15.csv` | ✅ EXISTS | 121,086 bars (2021–2026) |
| Data EURUSD H4 | `data/historical/EUR_USD_H4.csv` | ✅ EXISTS | 7,769 bars |
| Data GBPUSD M15 | `data/historical/GBP_USD_M15.csv` | ✅ EXISTS | 79,339 bars (2023–2026) |
| Data GBPUSD H4 | `data/historical/GBP_USD_H4.csv` | ✅ EXISTS | 5,245 bars |

### Step 1 — Spread Analysis

| File | Path | Status | Syntax |
|---|---|---|---|
| analyze_spreads.py | `research/analyze_spreads.py` | ✅ EXISTS | ✅ PASS |
| Output template | `docs/SPREAD_RESEARCH_FINAL_REPORT.md` | ✅ EXISTS | — |

### Step 2 — Cost Model

| File | Path | Status | Syntax |
|---|---|---|---|
| build_cost_model.py | `scripts/build_cost_model.py` | ✅ EXISTS | ✅ PASS |
| Output (created by Step 2) | `research/cost_model.json` | ✅ EXISTS (test run) | — |

### Step 3 — Export Limits

| File | Path | Status | Syntax |
|---|---|---|---|
| export_spread_limits.py | `scripts/export_spread_limits.py` | ✅ EXISTS | ✅ PASS |
| Output YAML | `research/recommended_spread_limits.yaml` | ✅ EXISTS (test run) | — |
| Updates | `config/costs.json` profiles.vantage_measured | ✅ structure verified | null → filled by script |

### Step 4 — Backtest (with measured costs)

| File | Path | Status | Syntax |
|---|---|---|---|
| backtest_session_liquidity.py | `scripts/backtest_session_liquidity.py` | ✅ EXISTS | ✅ PASS |
| `--costs-json` flag | line 660–668 in script | ✅ PRESENT | wired before simulation |
| `_load_costs_from_json()` | lines 622–656 | ✅ PRESENT | mutates SPREAD_PIPS |
| Null-value guard | aborts on null cost | ✅ TESTED | exits with clear error |
| Injection test | SPREAD_PIPS overridden correctly | ✅ TESTED | both symbols verified |

### Pipeline Orchestrator

| File | Path | Status | Executable |
|---|---|---|---|
| run_e6_revalidation.sh | `scripts/run_e6_revalidation.sh` | ✅ EXISTS | ✅ chmod +x |
| Gate pre-check | calls check_phase2_completion.py first | ✅ WIRED | aborts if gate not met |

### Support Scripts

| File | Path | Status | Syntax |
|---|---|---|---|
| check_phase2_completion.py | `scripts/check_phase2_completion.py` | ✅ EXISTS | ✅ PASS |
| spread_status.py | `scripts/spread_status.py` | ✅ EXISTS | — |
| daily_spread_report.py | `scripts/daily_spread_report.py` | ✅ EXISTS | — |

### Reference Documents

| File | Path | Status |
|---|---|---|
| PRE_E6_BASELINE.md | `docs/PRE_E6_BASELINE.md` | ✅ FROZEN — 2026-06-24 |
| E6_RUNBOOK.md | `docs/E6_RUNBOOK.md` | ✅ EXISTS |
| OPS02_REVISED_GATE.md | `docs/OPS02_REVISED_GATE.md` | ✅ EXISTS (owner-approved) |
| E6_COST_REVALIDATION_PLAN.md | `docs/E6_COST_REVALIDATION_PLAN.md` | ✅ EXISTS |
| BACKTEST_COST_REVALIDATION_REPORT.md | `docs/BACKTEST_COST_REVALIDATION_REPORT.md` | ✅ EXISTS (template) |

---

## §2 — Dependency Checks

All Python imports verified on 2026-06-24:

| Dependency | Used by | Status |
|---|---|---|
| `strategy.session_liquidity.session_strategy` | backtest | ✅ importable |
| `research.logger` (BacktestRun, TradeRecord, log_backtest_run) | backtest | ✅ importable |
| `python-dotenv` | capture_spreads | ✅ installed |
| `argparse` | backtest (--costs-json) | ✅ stdlib |
| `csv`, `json`, `statistics`, `math`, `pathlib` | all scripts | ✅ stdlib |
| `metaapi_cloud_sdk` | live bot only | ✅ installed (not used by backtest) |

---

## §3 — Integration Test Results

Tests run on 2026-06-24 against live data (1 London session, 1,840 rows):

| Test | Result | Notes |
|---|---|---|
| `analyze_spreads.py` dry run | ✅ PASS | writes SPREAD_RESEARCH_FINAL_REPORT.md, exits 0 |
| `build_cost_model.py` dry run | ✅ PASS | writes cost_model.json with correct stats |
| `export_spread_limits.py` dry run | ✅ PASS | writes YAML, updates costs.json correctly |
| null-cost guard in backtest | ✅ PASS | SystemExit on null values, clear error message |
| filled-cost injection in backtest | ✅ PASS | SPREAD_PIPS overridden correctly for both symbols |
| `compare_e6_to_baseline.py` pre-guard | ✅ PASS | exits 1 with clear message when E6 not yet run |
| Shell script bash syntax check | ✅ PASS | `bash -n` passes |
| `check_phase2_completion.py` gate check | ✅ PASS (gate CLOSED) | exits 1, correct output |

**Note:** `config/costs.json` was temporarily mutated during dry-run testing and restored to `active_profile = PLACEHOLDER_vt_markets_assumption` with `vantage_measured` = null values. Confirmed restored.

---

## §4 — costs.json State Verification

Current state (correct pre-E6 state):

```
active_profile: PLACEHOLDER_vt_markets_assumption
profiles.vantage_measured.EURUSD.standard: null   ← will be filled by export_spread_limits.py
profiles.vantage_measured.EURUSD.stress2x: null
profiles.vantage_measured.GBPUSD.standard: null
profiles.vantage_measured.GBPUSD.stress2x: null
```

**Do not touch costs.json** until `run_e6_revalidation.sh` is launched.

---

## §5 — Phase 2 Gate Status

As of 2026-06-24 12:10 UTC:

| Requirement | Have | Need | Status |
|---|---|---|---|
| London sessions | 1 | 5 | ⏳ 4 more |
| NY sessions | 1 | 5 | ⏳ 4 more |
| Total rows | 1,840 | 7,000 | ⏳ 5,160 more |

**Gate expected: ~2026-06-30 14:00 UTC**

Collection is running: `tmux spreads` active.
Check anytime: `python3 scripts/spread_status.py`
Gate check: `python3 scripts/check_phase2_completion.py`

---

## §6 — Identified Failure Points

| Risk | Severity | Mitigation |
|---|---|---|
| `tmux spreads` session dies (OOM, reboot) | HIGH — data gap | Manual relaunch. Check daily. |
| MetaAPI disconnection during killzone | MEDIUM — killzone data lost (observed once 2026-06-24 09:01 UTC, off-session, no data lost) | Check `spread_status.py` each morning; relaunch if sample age >10 min during session |
| costs.json corrupted by partial run | LOW | Restore via `git checkout config/costs.json`; re-run pipeline |
| BACKTEST_RESULTS.md overwritten by non-E6 run | LOW | Pipeline uses `--costs-json` flag — easy to detect by run ID |
| GBPUSD data gap (3.3yr vs 4.9yr EUR) | KNOWN | Documented in DATA_AUDIT.md. Does not affect E6 (same data as Phase-0) |
| Weekend gap in spread collection | CERTAIN (acceptable) | Expected. Collection resumes Monday. No weekend market. |

**No blocking failure points identified.** All risks have mitigations.

---

## §7 — E6 Execution Checklist (run on 2026-06-30)

Before running `bash scripts/run_e6_revalidation.sh`:

- [ ] `python3 scripts/check_phase2_completion.py` exits 0
- [ ] `python3 scripts/spread_status.py` shows HEALTHY
- [ ] `tmux ls` shows `spreads` session exists
- [ ] `config/costs.json` active_profile = PLACEHOLDER (will be flipped by pipeline)
- [ ] `docs/BACKTEST_RESULTS.md` run ID = baseline run (not yet overwritten)
- [ ] OPS-01 stability run complete (through 2026-06-28)
- [ ] No open positions in demo bot (check bot logs)

After E6 completes:

- [ ] `python3 scripts/compare_e6_to_baseline.py` — read verdict
- [ ] Populate `docs/BACKTEST_COST_REVALIDATION_REPORT.md`
- [ ] Add sub-entry to `docs/VERDICT_LOG.md` under ST-A2
- [ ] Apply decision matrix in `docs/E6_DECISION_MATRIX.md`

---

## §8 — Summary

| Category | Status |
|---|---|
| All pipeline files exist | ✅ YES |
| All paths valid | ✅ YES |
| All scripts pass syntax | ✅ YES |
| Shell script executable | ✅ YES |
| No missing dependencies | ✅ YES |
| Cost injection tested | ✅ PASS |
| Null-guard tested | ✅ PASS |
| Gate pre-check wired | ✅ YES |
| costs.json in correct pre-E6 state | ✅ YES |
| Baseline frozen | ✅ PRE_E6_BASELINE.md locked |
| **E6 gate open** | ❌ NO — collection ongoing (gate ~2026-06-30) |

**Recommendation: Continue collecting spread data. Run E6 on 2026-06-30 after gate opens.**

---

*E6_READINESS_AUDIT.md | Audited 2026-06-24 | Re-audit on gate day before running pipeline*
