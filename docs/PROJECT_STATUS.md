# PROJECT_STATUS.md
# Session Trading Bot — Milestone Tracker
# Update after every task. Mark [x] when complete.

---

## Current Task

This file is a manual operational snapshot, not the authoritative strategy
state record.

Authoritative strategy lifecycle and approval state live in:

- `config/strategy_catalog.yaml`
- `docs/SYSTEM_ARCHITECTURE.md`

If this document disagrees with the registry, the registry wins.

**E5 spread capture RUNNING** — `tmux spreads` live since 2026-06-24 06:01 UTC.
Target: ≥5 London + ≥5 NY + ≥7,000 rows. Gate ~2026-06-30.
Monitor: `python3 scripts/spread_status.py`

**E6 package READY** — `bash scripts/run_e6_revalidation.sh` is built and tested.
Run immediately when `python3 scripts/check_phase2_completion.py` exits 0.
See `docs/E6_RUNBOOK.md` for full instructions.

**Gate change (owner-approved 2026-06-24):** 30-day/50-trade demo requirement replaced.
See `docs/OPS02_REVISED_GATE.md`. New sequence: E5 → E6 → E1 (7-day run) → E2/E3/E4.
Fastest path to micro-live: ~14–21 days from capture start.

**Recorded objective:** `docs/PROJECT_OBJECTIVE_FASTEST_PATH.md`

**Live timeline view:** `docs/PROJECT_LIVE_STATUS_TIMELINE.md`

Parallel track: OPS-01 stability run still in progress through 2026-06-28 (see below).

## Strategy Focus

- **Production path:** ST-A2 remains the validated strategy for demo/execution work.
- **Research path:** D2 E3 is isolated behind a holdout gate and must not be treated as a production replacement.
- **Rule:** Only strategies that clear their registered holdout and execution gates may move into the demo path.

---

## Research Infrastructure

The repo is now organized as a quant research platform with a narrow execution
layer. Replay, validation, and backtest paths are kept separate from broker
connectivity, and D2 E3 is treated as a research branch rather than a production
replacement.

The new strategy catalog is the source of truth for lifecycle state and
deployment approval. See `config/strategy_catalog.yaml` and
`docs/QUANT_PLATFORM_ARCHITECTURE.md`.

| ID | Task | Status |
|---|---|---|
| RESEARCH-01 | `research/logger.py` — CSV logging + dataclasses | [x] 29 tests |
| RESEARCH-06 | `research/daily_status_report.py` → `reports/daily_status.md` (CPU/RAM/disk/reconnects) | [x] 2026-06-23 |
| RESEARCH-07 | `docs/ST_A2_OPPORTUNITY_ANALYSIS.md` — segment decomposition | [x] 2026-06-23 |
| RESEARCH-08 | `docs/STRATEGY_PORTFOLIO_ROADMAP.md` — 4-strategy pipeline | [x] 2026-06-23 |
| RESEARCH-09 | `docs/LIVE_CAPITAL_SCALING_PLAN.md` — Demo→$100→$500→$1k→Scale | [x] 2026-06-23 |
| RESEARCH-10 | `research/live_vs_backtest_validator.py` — live execution vs ST-A2 backtest | [x] 2026-06-23 |
| RESEARCH-11 | `docs/QUANT_PLATFORM_ARCHITECTURE.md` — research/execution split and strategy flow | [x] 2026-06-26 |
| RESEARCH-12 | `config/strategy_catalog.yaml` + registry lifecycle helpers | [x] 2026-06-26 |
| RESEARCH-13 | `config/research_queue.yaml` + `scripts/run_research_queue.py` | [x] 2026-06-26 |
| RESEARCH-14 | `config/strategy_change_pipeline.yaml` + blocked promotion stages | [x] 2026-06-26 |
| RESEARCH-15 | Validation gate engine + regression engine + promotion reports | [x] 2026-06-26 |
| RESEARCH-16 | `scripts/run_current_strategy_validation.py` + `scripts/run_current_strategy_svos.py` + catalog-linked strategy spec loading | [x] 2026-06-27 |
| BUG-02 | Telegram parse_mode Markdown on raw heartbeat string → 400 errors | [x] fixed 2026-06-23 |

---

## Strategy A — Session Liquidity Reversal

| ID | Task | Status |
|---|---|---|
| SA-01 | Session Builder (`session_builder.py`) | [x] 29 tests |
| SA-02 | HTF Bias Filter (`bias_filter.py`) | [x] 28 tests |
| SA-03 | Killzone Filter (in `session_builder.py`) | [x] merged into SA-01 |
| SA-04 | Sweep Detector (`sweep_detector.py`) | [x] 40 tests |
| SA-05 | Displacement Detector (`displacement_detector.py`) | [x] 49 tests |
| SA-06 | Entry Engine (`entry_engine.py`) | [x] 64 tests |
| SA-07 | Strategy Orchestrator (`session_strategy.py`) | [x] 44 tests |
| SA-08 | Backtest + Validation | [x] `scripts/backtest_session_liquidity.py` — 49 tests |
| SA-09 | Phase-1 Experiments   | [x] `scripts/run_experiments.py` — 34 tests. See EXPERIMENT_RESULTS.md |
| SA-10 | ST-A2 Implementation  | [x] min_sl_pips=5.0 enforced + 8 new tests. See ST_A2_CONFIRMATION.md |

**Gate:** Trades ≥ 100, PF > 1.0 at std AND 2× spread
**ST-A result:** ❌ FAIL — 181 trades, Net PF(std)=1.126, Net PF(2×)=0.965 at RR=5
**ST-A2 result:** ✅ PASS — 169 trades, Net PF(std)=1.151, Net PF(2×)=1.025 at RR=5
**Run ID:** 20260621T100458-183aaa | Phase-0 gate cleared

---

## Data Pipeline

| ID | Task | Status |
|---|---|---|
| DP-01 | `scripts/fetch_data.py` — Dukascopy async download | [x] |
| DP-02 | `scripts/data_audit.py` — DATA_AUDIT.md generation | [x] |
| DP-03 | 3-year Dukascopy archive complete | [x] EURUSD ✅ GBPUSD ✅ XAUUSD ✅ (2023-07 → 2026-06 raw coverage complete) |
| DP-04 | Data audit passed | [x] Dataset validation PASS; processed M1/M5/M15/H1/H4/D1 built for all three symbols |

---

## Strategy B — Full SMC Session Reversal

**EXP05 result (2026-06-24):** FAIL — no variant cleared all 4 gates. Best: Variant B (NY only,
PF_2x=1.562, WR=41.2%, n=51). D=2/29 (6.9%) confirms CHoCH+BOS gate is viable but near-zero
at displacement-close entry. ST-A2 gate passed → ST-B research track UNLOCKED.
See `research/EXP05_*.md` and `docs/VERDICT_LOG.md` EXP05 section.

Research plan: `docs/ST_B_RESEARCH_PLAN.md`

| ID | Task | Status |
|---|---|---|
| SB-01 | Swing Detector | [x] `session_smc/swing_detector.py` — 127 tests pass |
| SB-02 | Structure Detector | [x] `session_smc/structure_detector.py` |
| SB-03 | Liquidity Detector | [x] `session_smc/liquidity_detector.py` |
| SB-04 | POI Detector | [x] `session_smc/poi_detector.py` |
| SB-05 | Confirmation Entry | [x] `session_smc/confirmation_entry.py` — `generate_signal_A()` full 11-phase chain |
| STB-01 | Backtest Orchestrator | [ ] `scripts/backtest_stb.py` — session slicing + generate_signal_A() → Signal list |
| STB-02 | Partial-Close Simulator | [ ] TP1=75%@4R + SL→BE + TP2=25%@5R logic |
| STB-03 | Metrics Report | [ ] PF_std/PF_2x/WR/DD, per-symbol/session/year → `docs/STB_PHASE0_RESULTS.md` |
| STB-04 | Phase-0 Run + Gate | [ ] 5yr backtest → VERDICT_LOG.md ST-B entry |
| STB-05 | Sensitivity (conditional) | [ ] only if STB-04 FAIL and a targeted fix exists |

---

## Spread Cost Validation

| ID | Task | Status |
|---|---|---|
| OPS-02A | `scripts/capture_spreads.py` — 4 pairs, DST-aware, USDJPY pip fix, reconnect | [x] 2026-06-24 |
| OPS-02A | `config/costs.json` — placeholder + vantage_measured template | [x] 2026-06-24 |
| OPS-02A | `tests/test_capture_spreads.py` — 51 tests (session, pip, csv, agg, summary, reconnect) | [x] 51 tests |
| OPS-02A | `docs/SPREAD_CAPTURE_PLAN.md` — tmux command, runtime, interpretation guide, update procedure | [x] 2026-06-24 |
| E5 (OPS-02A) | Live capture run — ≥5 London + ≥5 NY + ≥7,000 rows | [~] RUNNING — Day 1/5. Gate ~2026-06-30 |
| E5 (OPS-02A) | `scripts/spread_status.py` — daily monitoring one-liner | [x] 2026-06-24 |
| E5 (OPS-02A) | `scripts/daily_spread_report.py` — verbose daily report | [x] 2026-06-24 |
| E5 (OPS-02A) | `scripts/check_phase2_completion.py` — gate check (exit 0=ready) | [x] 2026-06-24 |
| E5 (OPS-02A) | `research/SPREAD_CAPTURE_INTERIM.md` — 1-session preliminary findings | [x] 2026-06-24 |
| E5 (OPS-02A) | `docs/PHASE22_COLLECTION_HEALTH.md` — full health audit + risks | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/E6_COST_REVALIDATION_PLAN.md` — methodology + decision table | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/SPREAD_RESEARCH_FINAL_REPORT.md` — template (populate post-gate) | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/BACKTEST_COST_REVALIDATION_REPORT.md` — template (populate post-E6) | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/DEMO_GATE_DECISION.md` — template (populate post-E1–E4) | [x] 2026-06-24 |
| E6 (OPS-02A) | `research/analyze_spreads.py` — populates SPREAD_RESEARCH_FINAL_REPORT.md | [x] 2026-06-24 |
| E6 (OPS-02A) | `scripts/build_cost_model.py` — avg/median/P90/P95/P99 per symbol/session → `research/cost_model.json` | [x] 2026-06-24 |
| E6 (OPS-02A) | `scripts/export_spread_limits.py` — P95+margin → `research/recommended_spread_limits.yaml` + updates `config/costs.json` | [x] 2026-06-24 |
| E6 (OPS-02A) | `scripts/backtest_session_liquidity.py --costs-json` — argparse cost injection (no change to logic) | [x] 2026-06-24 |
| E6 (OPS-02A) | `scripts/run_e6_revalidation.sh` — full 5-step pipeline (gate → analyze → model → export → backtest) | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/E6_RUNBOOK.md` — operator guide: preconditions, steps, validation, decision matrix | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/PRE_E6_BASELINE.md` — locked baseline snapshot (run 20260621T100458-183aaa) | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/E6_READINESS_AUDIT.md` — full pipeline audit (all checks PASS, gate CLOSED) | [x] 2026-06-24 |
| E6 (OPS-02A) | `scripts/compare_e6_to_baseline.py` — post-E6 comparison utility → `docs/E6_COMPARISON_REPORT.md` | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/E6_COMPARISON_REPORT.md` — template (auto-populated by compare script) | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/E6_PAIR_ANALYSIS.md` — EURUSD / GBPUSD viability template (populate post-E6) | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/E6_SESSION_ANALYSIS.md` — London / NY contribution template (populate post-E6) | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/E6_DECISION_MATRIX.md` — PF_2x → PASS/REVIEW/REJECT rules with rationale | [x] 2026-06-24 |
| E6 (OPS-02A) | `scripts/freeze_phase2_dataset.py` — immutable snapshot (SHA256 + manifest) → `research/e6_dataset_snapshot/` | [x] 2026-06-24 |
| E6 (OPS-02A) | `docs/E6_DATASET_FREEZE.md` — freeze purpose, usage, integrity verification | [x] 2026-06-24 |
| E6 (OPS-02A) | Run E6 pipeline → fill `vantage_measured` + rerun ST-A2 → PF_2x decision | [ ] BLOCKED on E5 (gate ~2026-06-30) |

---

## Deployment

| ID | Task | Status |
|---|---|---|
| DEP-00 | Forward Test Simulator | [x] 43/43 tests. No lookahead. See FORWARD_TEST_VALIDATION.md |
| DEP-01 | Demo deployment (execution layer) | [x] 66 tests. See DEPLOYMENT_READINESS.md. Needs .env credentials to start |
| DEP-02 | Demo bot connection | [~] bot running since 2026-06-21T18:26 UTC (LIVE_TRADING=false) |
| OPS-01 | Operational stability (7-day) | [~] bot running ✅ Day-0/1/2 PASS. 7-day run through 2026-06-28. See OPS01_* docs |
| OPS-01A | Process startup + health check | [x] 9/9 health checks PASS. Day-0 baseline captured. |
| OPS-02 | Demo-trading gate — REVISED | [x] `docs/OPS02_REVISED_GATE.md` — owner-approved 2026-06-24 (replaces 30+50 requirement) |
| OPS-02/E1 | 7-day runtime (LIVE_TRADING=true) | [ ] BLOCKED on E5+E6+OPS-01 |
| OPS-02/E2 | ≥1 signal validated | [ ] BLOCKED on E1 |
| OPS-02/E3 | ≥1 order lifecycle (fill or valid reject) | [ ] BLOCKED on E1 |
| OPS-02/E4 | Manual restart test (Day 2–3 of E1) | [ ] BLOCKED on E1 |
| OPS-03 | Live trade analytics | [x] `research/live_trade_analyzer.py` — daily + weekly JSON summaries |
| RESEARCH-05 | Execution quality analytics | [x] `research/execution_analyzer.py` — 8 metrics, 50 tests, daily + weekly JSON |
| BUG-01 | MetaAPI RPC hang → heartbeat freeze | [x] `_rpc()` 30s timeout, `reconnect()`, 10-min watchdog task — 19 tests |
| DEP-03 | Micro-live ($1,000 Vantage, 0.25% risk) | [ ] BLOCKED on OPS-02/E1–E4; first 20 trades = validation period |

---

## Backtest Results Log

| Trial | Pairs | RR | Trades | PF (std) | PF (2×) | Verdict |
|---|---|---|---|---|---|---|
| ST-A  | EUR+GBP | RR5 | 181 | 1.126 | 0.965 | **FAIL** — 2× stress. Run: 20260621T060745-f6ac57 |
| ST-A2 | EUR+GBP | RR5 | 169 | 1.151 | 1.025 | **PASS** ✅ — Run: 20260621T100458-183aaa |

---

## Known Issues / Blockers

1. **E5 spread capture RUNNING (Day 1/5)** — `tmux spreads` live since 2026-06-24 06:01 UTC.
   Preliminary: EURUSD 1.35pip, GBPUSD 1.56pip at London (vs 1.40/1.80 placeholder) — both lower.
   Projected PF_2x ~1.035 (vs 1.025 at placeholder). Gate met ~2026-06-30.
   Monitor daily: `python3 scripts/spread_status.py`

2. **E6 blocked on E5** — do not update `config/costs.json` until 5 London + 5 NY sessions.
   Decision table in `docs/OPS02_REVISED_GATE.md`.

3. **Historical dataset complete** — raw ticks and processed timeframes for EURUSD, GBPUSD, and XAUUSD are now built and validated for the 2023-07 → 2026-06 window. Current validation report: `reports/dataset_validation_report.md`.

---

## Test Suite Health

```
session_smc/        127/127 passing
session_liquidity/  262/262 passing  (SA-01…SA-07 + SA-10 min_sl_pips)
research/            29/29  passing  (RESEARCH-01)
backtest/            49/49  passing  (SA-08)
experiments/         34/34  passing  (SA-09)
forward_test/        43/43  passing  (DEP-00)
execution/           66/66  passing  (DEP-01: metaapi_client, position_sizer, trade_logger, order_manager)
ops/                 21/21  passing  (OPS-01: safety, dedup, heartbeat, state persistence, logging)
research/            50/50  passing  (RESEARCH-05: execution quality metrics)
execution/bug01      19/19  passing  (BUG-01: RPC timeout, reconnect, watchdog)
scripts/             51/51  passing  (OPS-02A: capture_spreads — session, pip, csv, agg, summary, reconnect)
total               751/751
```

---

## Next Steps (in order)

1. [x] [SA-01] `session_builder.py` + tests
2. [x] [SA-02] `bias_filter.py` + tests
3. [x] [SA-03] `classify_session()` merged into SA-01
4. [x] [SA-04] `sweep_detector.py` + tests
5. [x] [SA-05] Build `displacement_detector.py` + tests
6. [x] [SA-06] Build `entry_engine.py` + tests
7. [x] [SA-07] Build `session_strategy.py` + tests
8. [x] [SA-08] Build backtest + run on 5yr data  ← See BACKTEST_RESULTS.md
9. [x] [SA-09] Phase-1 experiments  ← See EXPERIMENT_RESULTS.md
10. [x] Register ST-A2 trial in VERDICT_LOG.md — EXP-01 ≥5pip, PASS
11. [x] Implement ST-A2 filter — `min_sl_pips: 5.0` in DEFAULT_CONFIG + post-signal gate
12. [x] Production backtest confirms ST-A2 — n=169, PF_2x=1.025 ✅ See ST_A2_CONFIRMATION.md
13. [x] [DEP-00] Forward Test Simulator — no lookahead, 43/43 tests. See FORWARD_TEST_VALIDATION.md
14. [x] [DEP-01] Execution layer — MetaAPIClient, OrderManager, PositionSizer, TradeLogger, bot.py. 66 tests. See DEPLOYMENT_READINESS.md
15. [x] [DEP-02] Connection validated — Vantage MT5 Demo synced. 30/30 checks. See DEP_02_CONNECTION_REPORT.md
16. [x] [OPS-01] Operational stability layer — pre-flight, reconnect, heartbeat, safety tests. 21 tests. See OPS01_* docs
17. [x] [OPS-01A] Process startup — tmux run, log rotation, health_check.py 9/9 PASS, Day-0 baseline
18. [ ] [OPS-01] 7-day stability run — complete 2026-06-28, fill daily reports
19. [x] [OPS-02] Revised demo gate — docs/OPS02_REVISED_GATE.md (owner-approved 2026-06-24)
20. [x] [OPS-03] Live trade analytics — research/live_trade_analyzer.py; daily + weekly JSON
21. [x] [RESEARCH-05] Execution quality analytics — research/execution_analyzer.py; 50 tests; 8 metrics
22. [ ] [E5] Spread capture — CONFIRM-SPREAD-CAPTURE → ≥5 London + ≥5 NY sessions
23. [ ] [E6] Cost revalidation — vantage_measured → ST-A2 rerun → PF_2x gate
24. [ ] [E1–E4] 7-day execution gate (LIVE_TRADING=true) — after E5+E6+OPS-01 pass
25. [ ] [DEP-03] Micro-live $1k Vantage, 0.25% risk — after E1–E4 pass
