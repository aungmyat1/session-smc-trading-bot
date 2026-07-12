---
Date: 2026-07-12
Author: PM/Architect audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede
`docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phases 2-4 of the demo-readiness audit requested 2026-07-12. Companion
to `DOCUMENTATION_ALIGNMENT_REPORT.md` and `ARCHITECTURE_REALITY_MAP.md`.
---

# Fastest Path to Demo — Decision Report

## Reframing the objective

The requested objective was "get the SMC trading system running in
controlled DEMO trading with measurable validation evidence." Per
`ARCHITECTURE_REALITY_MAP.md` §1, the *running* half is already true for
ST-A2 (`smc-demo-runner.service`, live on Vantage MT5 demo via MetaAPI since
2026-07-04, stable). The gap is entirely in the **measurable validation
evidence** half, plus two governance/config loose ends that create risk
without adding capability. This report treats "fastest path" as fastest path
to a demo deployment that is both running *and* evidenced/defensible — not
as a from-scratch build.

## Phase 2 summary — trading readiness snapshot

**A. Data readiness.** EURUSD/GBPUSD/XAUUSD historical data present and
validated (`scripts/validate_dataset.py`). GBPUSD 2021-2023 is missing —
blocks walk-forward only, not the current-gate backtest re-run.

**B. Strategy readiness (ST-A2).** Fully coded, not stubbed:
HTF bias (`bias_filter.py`), Asian-range sweep/POI (`sweep_detector.py`),
ATR-displacement confirmation (`displacement_detector.py` — note: this is
NOT CHoCH/BOS/FVG, see below), entry/SL/TP (`entry_engine.py`), risk model
(`demo_risk_manager.py`). One data-quality issue: `config/strategy_portfolio.yaml`'s
description of ST-A2 ("Session sweep + 15M CHoCH + BOS + FVG entry") does not
match the deployed logic — cosmetic/doc bug, not a code bug, but worth fixing
so operators aren't misled about what's actually trading.

**C. Backtest/replay readiness.** Real chronological bar-by-bar replay engine
exists (`scripts/backtest_session_liquidity.py`), reuses the exact production
strategy function (no train/production logic fork). Problems: (1) hardcoded
gate inside the script is the pre-2026-07-01 threshold, not current; (2) no
Sharpe ratio computed anywhere; (3) cost model (`config/costs.json`) is an
explicit unverified placeholder, not measured Vantage spread data; (4) most
recent evidence (`VERDICT_LOG.md`, 2026-06-21, n=169) predates the gate
change and fails it on at least 3 counts (n<200, PF_2x=1.025<1.25, Sharpe
unmeasured); (5) no walk-forward or Monte Carlo evidence exists at all.

**D. Execution readiness.** Strong. MT5/MetaAPI connection, order creation,
position tracking, SL/TP placement, and emergency shutdown are all real,
tested, and independently code-verified (not just documented) as of the
2026-07-05 internal audits. One real open risk: idempotency key is generated
fresh per order call and never checked against existing records — no live
double-order dedup protection (flagged P0, currently low-likelihood).

## 1. Minimum required work before demo trading can be called evidenced

Demo trading is already happening; "minimum required work" here means the
minimum to make the current CLAUDE.md gate (§0.3/§0.6) actually satisfied or
explicitly, deliberately waived by the owner — not to build new
infrastructure:

1. **Capture real Vantage spread data** (`scripts/capture_spreads.py` already
   exists) and populate the empty `vantage_measured` profile in
   `config/costs.json`, replacing the placeholder.
2. **Register a new ST-A2 revalidation trial** in `docs/VERDICT_LOG.md`
   (§0.2/§7 hard rule — pre-register before running) and re-run
   `scripts/backtest_session_liquidity.py` against the current gate
   (n>200, PF>1.25 std+2x, Sharpe>1.2, MaxDD<15%) using the real cost
   profile from step 1. Add Sharpe to `compute_metrics()` — it isn't
   computed today.
3. **Fix `config/validation.yaml`** to match the current gate (currently
   still encodes n≥50/PF>1.0/no-Sharpe) so no tooling silently passes
   strategies against the wrong threshold.
4. **Resolve the LondonBreakout/NYMomentum config landmine**: either flip
   their `execution_mode` back to `shadow` in `config/strategy_portfolio.yaml`
   until they clear replay+backtest per their own `strategy_catalog.yaml`
   requirements, or get explicit owner sign-off to keep them in `demo` mode
   pre-evidence and document that exception. This is a one-line config
   change or a documented decision — not a rebuild.
5. **Fix the idempotency dedup gap** in `execution/trade_manager.py` — check
   the generated idempotency key against existing open positions/journal
   records before placing an order, not just at crash-recovery.
6. **Write one paragraph resolving the freeze-status ambiguity** (see
   `DOCUMENTATION_ALIGNMENT_REPORT.md` §2.1) — does the 2026-06-29/06-30
   SVOS "NOT READY" freeze apply to the System-2 demo runner or not. This
   is a governance decision, zero code.

## 2. What can be postponed

- Consolidating the three broker-client implementations
  (`mt5_connector.py`/`metaapi_client.py`/`mt5_executor.py`) — real debt,
  not urgent since only one is live.
- Resolving `session_smc/`'s ambiguous status (looks like archived nested
  repo copies but not fully import-verified).
- Walk-forward and Monte Carlo studies — valuable, but not required by the
  Phase-3 gate; GBPUSD 2021-2023 data is missing anyway.
- Full `svos/` platform unification (orchestration/governance/monitoring
  backend consolidation) — tracked separately in `docs/svos/CURRENT_STATE.md`,
  does not block the ST-A2 demo runner today.
- `docs/audit/` and root-doc cleanup beyond the two items in
  `DOCUMENTATION_ALIGNMENT_REPORT.md` §3.
- `"New Dashborad"` frontend — disconnected prototype, zero effect on demo
  readiness.

## 3. Features unnecessary before demo evidence closes

New strategies (AdaptiveSMC, VWAPMeanReversion shadow work), `svos/api`,
`svos/notifications`, a new dashboard UI, rehabilitating the unused
`session_smc/` CHoCH+BOS+FVG chain, and any Phase-6/production-approval
scoping (explicitly out of the implementation ceiling per CLAUDE.md §2).

## 4. Top 5 blockers

| # | Blocker | Type | Why it blocks "measurable validation evidence" |
|---|---|---|---|
| 1 | ST-A2 evidence fails current gate (n=169<200, PF_2x=1.025<1.25, no Sharpe, no walk-forward) | Research | This is the literal gap between "running" and "running with evidence" |
| 2 | Cost model is an unverified placeholder, not real Vantage spreads | Research/data | Any re-run without this is not a trustworthy result — would need a second re-run later |
| 3 | LondonBreakout/NYMomentum config allows live demo orders with zero backtest evidence | Governance/config | Real risk exposure disguised as inactive because only ST-A2 happens to be the hardcoded runner today |
| 4 | Idempotency dedup gap in live order placement | Execution/code | Correctness risk on the one path that's actually placing real orders |
| 5 | Freeze-status and doc-authority ambiguity | Governance/docs | Not a code blocker, but blocks confident decision-making — an agent or operator could act on stale "NOT READY" or stale "System 2 unblocked" framing without knowing which is current |

## 5. Estimated effort

| Item | Hours | Complexity | Risk if skipped |
|---|---|---|---|
| Capture real Vantage spreads, populate cost profile | 2-4 | Low (script exists) | Evidence remains untrustworthy |
| Add Sharpe to `compute_metrics()`, re-run ST-A2 backtest under new trial ID | 3-6 | Low-Medium (well-tested engine, just needs the metric + a clean run) | Gate can't be evaluated at all |
| Fix `config/validation.yaml` gate values | <1 | Trivial | Silent wrong-gate passes |
| LondonBreakout/NYMomentum config decision + change | 1-2 | Trivial (config flip) + owner decision time | Unvalidated strategies one guard-flag away from live demo orders |
| Idempotency dedup check in `trade_manager.py` | 3-5 | Low-Medium (needs a persisted lookup, touches live order path — test carefully) | Possible duplicate live orders on retry/race |
| Freeze-status + doc-authority resolution paragraph | 1-2 | Trivial (writing, one owner decision) | Ongoing confusion for future agents/operators |
| **Total to close the evidence gap** | **~11-20 hours** | **Low-Medium overall** | — |

Everything postponed in §2 is materially larger (multi-day to multi-week)
and explicitly not required to satisfy the stated objective.
