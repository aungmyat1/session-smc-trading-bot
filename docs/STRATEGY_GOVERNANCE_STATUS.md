---
title: Strategy Governance Status
purpose: Single source-of-truth reconciliation of declared config state vs SVOS lifecycle registry state, evidence, and promotion eligibility, per strategy
owner: Platform Governance
status: living document — regenerate after any registry/config change
last_verified: 2026-07-11 (updated same day by TASK-1-DAYTRADING-GOV — DayTradingManeuvers catalog/registry sync, see Summary #6; and TASK-GROUP-3-DTM-TRACKING — deferred-adapter tracking entry, see Summary #8)
---

# Strategy Governance Status

This document reconciles three independent state sources that exist for every
strategy in this repo — `config/strategy_portfolio.yaml` (runtime enable/mode),
`config/strategy_catalog.yaml` (a second, older approval-status field set), and
the authoritative SVOS lifecycle registry (`data/svos/registry/<name>/state.json`,
mutated only by `svos/lifecycle/manager.py`) — plus the evidence trail in
`docs/VERDICT_LOG.md`. Gate reference: n>200 AND net PF>1.25 AND Sharpe>1.2 AND
MaxDD<15% at BOTH standard and 2× spread stress, effective 2026-07-01
(`CLAUDE.md` §0.6/§7).

No lifecycle stage or registry state was mutated to produce this document. All
findings below are read-only observations.

## Summary — flagged issues (read this first)

1. **Corrected finding — the 5-strategy portfolio config is not a governance gap.**
   All five `config/strategy_portfolio.yaml` entries (ST-A2, LondonBreakout,
   NYMomentum, AdaptiveSMC, VWAPMeanReversion) are `enabled: false` /
   `execution_mode: shadow`. This is consistent with the fact that none of them
   holds catalog approval or has reached a stage beyond VIRTUAL_DEMO. Prior
   memory describing this as "five strategies running in tiered demo/shadow" is
   stale — as of commit `cf92a9e` (2026-07-11, today), this was already
   corrected by the repo owner: the portfolio was flipped from `enabled: true /
   execution_mode: demo` for ST-A2/LondonBreakout/NYMomentum to
   `enabled: false / shadow` across the board. Treat any doc still describing
   the old enabled state as superseded.

2. **`SMCOrderBlockFVGSession` governance gap (VERDICT_LOG.md:290-296) is now
   STALE, not current.** VERDICT_LOG.md's 2026-07-01 entry says this strategy
   (registry stage `INTAKE`, `approved: false`) "is currently running in
   live-demo shadow/dry-run form via `smc-demo-runner.service` against real
   market data." Investigation (`docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`,
   2026-07-04) found the service was actually **crash-looping on an argparse
   error** (`--strategy SMCOrderBlockFVGSession` is not a registered
   `ADAPTER_TYPES` choice) and exiting in <1s before any market data fetch or
   broker connection — i.e. it was never actually generating live signals, the
   VERDICT_LOG description was inaccurate even at the time it was written. The
   wrapper (`deploy/gcp-vm1/run_smc_demo.sh`) was subsequently repointed to
   `--strategy ST-A2` (confirmed live in the current file). **VERDICT_LOG.md
   should be corrected/appended to reflect this** — it currently misstates
   what was actually deployed. This is a documentation-accuracy issue for the
   VERDICT_LOG owner, not something this doc resolves unilaterally.

3. **As of today (`cf92a9e`), the replacement target (ST-A2) is itself now
   blocked at runtime**, closing the loop: `scripts/run_st_a2_demo.py` gained a
   `StrategyExecutionGuard` startup check that reads `config/strategy_catalog.yaml`
   and refuses to run any strategy without `approved: true` for the target
   environment. `logs/strategy_demo_state.json` (last write 2026-07-11T10:30Z)
   shows `execution_status: blocked`, `reason_code: DEPLOYMENT_NOT_APPROVED`,
   `catalog_status: DEFERRED_REVALIDATION`. **Net effect: no strategy is
   currently generating live-demo signals anywhere on `gcp-vm1` as of this
   writing** — `smc-demo-runner.service` is running but its process exits
   immediately with `PermissionError` on every restart cycle (still
   `Restart=always`, so it is still consuming a restart-loop resource, just no
   longer silently mis-attributed to the wrong strategy).

4. **`ST-A2` internal inconsistency — `current_stage` vs `legacy_status`
   disagree.** `data/svos/registry/ST-A2/state.json`: `current_stage: DRAFT`
   but `legacy_status: DEFERRED_REVALIDATION`. DRAFT is the very first
   lifecycle stage; DEFERRED_REVALIDATION is a terminal/paused status implying
   the strategy previously passed Phase-0 and was later pulled back for
   revalidation. These two fields describe incompatible strategy histories in
   the same record. **Flagged for the lifecycle manager owner to resolve — not
   resolved here** (`svos/lifecycle/manager.py` is the only mutation
   authority per `CLAUDE.md` §3).

5. **Catalog vs registry stage-model mismatch (structural, not just one row).**
   `config/strategy_catalog.yaml`'s `status:` field uses a different, looser
   vocabulary (`research`, `replay`, `shadow`, `draft`, `DEFERRED_REVALIDATION`)
   than the registry's canonical `current_stage` enum (`DRAFT → INTAKE → AUDIT →
   HISTORICAL_REPLAY → ... `). They are not the same taxonomy and do not
   1:1 map cleanly (e.g. catalog `shadow` corresponds to registry stages as
   different as `AUDIT`, `VIRTUAL_DEMO`). This matches the CLAUDE.md §9
   vocabulary-conflict warning ("a third numbering scheme is an authority
   conflict, not a style choice") — the catalog's `status` field is a legacy
   holdover and should either be deprecated in favor of reading the registry
   directly, or mechanically derived from it, not maintained by hand in
   parallel. See per-row mismatches below.

6. **RESOLVED 2026-07-11 (TASK-1-DAYTRADING-GOV) — `DayTradingManeuvers` catalog
   gap closed.** Previously this strategy had a registry record
   (`data/svos/registry/DayTradingManeuvers/state.json`, `current_stage: INTAKE`)
   but no `config/strategy_catalog.yaml` entry, and `legacy_status` disagreed
   with the catalog (`shadow` vs the now-added `draft`). Fixed by (a) adding a
   `DayTradingManeuvers` entry to `config/strategy_catalog.yaml` (`status: draft`,
   `svos_stage: INTAKE`, `approved: false`, `execution_allowed: false`,
   `current: false`) matching the `SMCOrderBlockFVGSession` pattern, and (b)
   recording a new registry version via `StrategyRegistryService.record_version`
   (the sanctioned API — `svos/lifecycle/manager.py` governs stage vocabulary,
   `svos/registry/service.py` is the persistence layer that uses it; no file was
   hand-edited) so `legacy_status` now reads `draft`, consistent with the
   catalog. `current_stage` was intentionally left at `INTAKE` — this task is
   registration, not promotion.
   **Still open, unchanged by this task:** `DayTradingManeuvers` is still not
   present in `strategy_portfolio.yaml` (same as `SMCOrderBlockFVGSession`), and
   `scripts/run_portfolio.py`'s wiring is dead code today — the import of
   `strategies.adapters.day_trading_maneuvers_adapter.DayTradingManeuversAdapter`
   is wrapped in `try/except ImportError` and the module does not exist, so the
   adapter resolves to `None` and is skipped at registration time; the strategy
   is also absent from `_STRATEGY_MAP` (the dict that actually drives per-tick
   signal generation), so `_NEEDS_DTM_DATA` never triggers. No systemd unit runs
   `run_portfolio.py` (confirmed absent in `deploy/gcp-vm1/systemd/`). Net: no
   live or demo signal path currently executes for this strategy anywhere.

7. **Per-row catalog/registry `status` disagreements** (see table): LondonBreakout
   (catalog `research` vs registry `HISTORICAL_REPLAY`), NYMomentum (catalog
   `replay` vs registry `HISTORICAL_REPLAY` — same meaning, different spelling),
   VWAPMeanReversion and VWAPBreakout (catalog `shadow` vs registry
   `VIRTUAL_DEMO` — registry is two stages ahead of what the catalog records).
   No VERDICT_LOG evidence trail was found justifying VWAPMeanReversion's or
   VWAPBreakout's advancement to VIRTUAL_DEMO (Phase 5) — flagged as an
   evidence-gap, not just a labeling mismatch.

8. **TRACKED / DEFERRED (2026-07-11, TASK-GROUP-3-DTM-TRACKING) —
   `DayTradingManeuvers` adapter implementation.** This is the explicit tracking
   entry for the follow-up work item Flag 6 identified but did not implement.
   No code was written for this task; it is tracking-only.
   - **Current state:** `DayTradingManeuvers` is registered in SVOS governance
     (`config/strategy_catalog.yaml` + `data/svos/registry/DayTradingManeuvers/state.json`,
     `svos_stage: INTAKE`, `approved: false`, `execution_allowed: false`,
     `current: false`). It has no adapter module — `strategies/adapters/day_trading_maneuvers_adapter.py`
     does not exist. `scripts/run_portfolio.py` (lines ~80-93) contains a dead
     `try/except ImportError` stub that swallows the missing import and sets
     `DayTradingManeuversAdapter = None`, so the strategy is silently skipped at
     registration time and is absent from `_STRATEGY_MAP`; `_NEEDS_DTM_DATA`
     (line 224) never triggers as a result. No live or demo signal path
     currently executes for this strategy anywhere.
   - **What's needed to close this item:** (a) implement
     `strategies/adapters/day_trading_maneuvers_adapter.py` (a
     `DayTradingManeuversAdapter` class matching the pattern of the other
     entries in `strategies/adapters/`), and (b) wire it into `_STRATEGY_MAP`
     in `scripts/run_portfolio.py`, replacing the dead stub import. Neither is
     done by this tracking entry.
   - **Why deferred:** PM decision (2026-07-11) — ST-A2 revalidation (see Flag 1
     summary and the ST-A2 table row) is the current priority; `DayTradingManeuvers`
     is at `INTAKE` (earliest lifecycle stage, Phase 0 not started) and building
     an execution adapter ahead of any Phase 0-5 evidence would front-run the
     governed pipeline order (`CLAUDE.md` §2/§9) for no near-term benefit.
   - **What would unblock it:** an explicit PM/governance decision to
     prioritize this adapter work, made independently of — and not implied by
     — this tracking entry's existence. Until then, no adapter code should be
     written for this strategy.
   - Out of scope for this entry (unchanged): the adapter module itself,
     `scripts/run_portfolio.py` wiring, and any change to `execution_allowed`
     or the registry lifecycle stage (mutation authority remains
     `svos/lifecycle/manager.py` only).

## Strategy status table

| Strategy | Portfolio config (`strategy_portfolio.yaml`) | Registry `current_stage` | Registry `legacy_status` | Catalog `status` / `approved` | Most recent evidence (VERDICT_LOG.md) | Current gate (n>200, PF>1.25, Sharpe>1.2, DD<15%, std+2x) | Promotion eligibility |
|---|---|---|---|---|---|---|---|
| **ST-A2** | `enabled: false`, `execution_mode: shadow` (was `true`/`demo` until today's `cf92a9e`) | `DRAFT` | `DEFERRED_REVALIDATION` (internally inconsistent — see Flag 4) | `status: DEFERRED_REVALIDATION`, `approved: false`, `phase0_result: PASS (PF_2x=1.025, n=169) — preserved, not current` | ST-A2, 2026-06-21: n=169, PF_std=1.151, PF_2x=1.025 — PASS under **old** pre-2026-07-01 gate (n≥50, PF>1.0) only. Does not meet current gate (needs n>200, PF>1.25, Sharpe, DD evidence not computed under new gate). | **FAIL current gate** — n=169 < 200; PF_2x=1.025 < 1.25; Sharpe/DD not evaluated under new methodology | Blocked. Per `CLAUDE.md` §0.6, must re-enter at INTAKE and re-earn all evidence under the current gate; DRAFT/DEFERRED_REVALIDATION inconsistency must be resolved first |
| **LondonBreakout** | `enabled: false`, `execution_mode: shadow` | `HISTORICAL_REPLAY` | `research` | `status: research`, `approved: false`, requirements all `pending` | None found | Not evaluated — no backtest run yet | Blocked pending Phase-3 backtest; currently mid-Phase-2 (Historical Replay) |
| **NYMomentum** | `enabled: false`, `execution_mode: shadow` | `HISTORICAL_REPLAY` | `replay` (consistent w/ registry, different spelling) | `status: replay`, `approved: false`, requirements all `pending` | None found | Not evaluated | Blocked pending Phase-3 backtest; currently mid-Phase-2 |
| **AdaptiveSMC** | `enabled: false`, `execution_mode: shadow` | `AUDIT` | `research` | `status: research`, `approved: false`, requirements all `pending` | None found | Not evaluated | Blocked; earliest stage of the shadow-configured group, needs to clear Audit → Replay → Backtest |
| **VWAPMeanReversion** | `enabled: false`, `execution_mode: shadow` | `VIRTUAL_DEMO` | `shadow` | `status: shadow`, `approved: false`, requirements all `pending` | None found | Not evaluated — no PF/Sharpe/DD evidence located despite reaching Phase-5 stage | **Evidence gap flagged**: registry stage implies Phase 0–4 all passed, but no corresponding VERDICT_LOG entries exist to substantiate it. Do not treat VIRTUAL_DEMO stage alone as evidence of a gate pass |
| **VWAPBreakout** | Not present in `strategy_portfolio.yaml` | `VIRTUAL_DEMO` | `shadow` | `status: shadow`, `approved: false`, requirements all `pending` | None found | Not evaluated — same evidence gap as VWAPMeanReversion | Same evidence-gap flag; additionally has no portfolio config entry at all, so its `enabled` state is undefined |
| **D2E3** | Not present in `strategy_portfolio.yaml` | `AUDIT` | `research` | `status: research`, `approved: false`, requirements all `pending` | ST-D2-E3-OPT holdout (2026-06-26): Gross PF=0.875 (no raw edge outside search window), WR collapsed 51.6%→39.4% in-sample→holdout — **FAIL** (overfitting). ST-D2-E3-OPT2: pre-registered, "Holdout results: PENDING" | **FAIL** (ST-D2-E3-OPT variant) / not yet run (OPT2 variant) | Blocked; the evaluated variant failed outright, successor variant's evidence is still pending |
| **SMCOrderBlockFVGSession** | Not present in `strategy_portfolio.yaml` | `INTAKE` | `draft` (consistent) | `status: draft`, `svos_stage: INTAKE`, `approved: false`, requirements all `pending` | VERDICT_LOG.md:290-296, 2026-07-01: "governance gap" entry — now stale, see Flag 2 | Not evaluated — earliest possible stage | Blocked at INTAKE (Phase 0 not started); deployment wrapper previously mis-targeted this strategy (fixed — now points at ST-A2), no adapter registered in `ADAPTER_TYPES`, one pre-existing failing unit test (`test_generates_long_signal_on_retrace`) |
| **DayTradingManeuvers** | Not present in `strategy_portfolio.yaml` | `INTAKE` | `draft` (consistent as of 2026-07-11, see Summary #6) | `status: draft`, `svos_stage: INTAKE`, `approved: false`, `execution_allowed: false`, requirements all `pending` (added 2026-07-11, TASK-1-DAYTRADING-GOV) | None found | Not evaluated | Blocked at INTAKE (Phase 0 not started). Promotion requires, in order: (1) Phase-0 Strategy Audit PASS (intake validation + logic/lookahead review, `svos_stage: AUDIT`); (2) accepted Phase-1 spec refinement if audit returns FIX; (3) Phase-2 Historical Replay PASS with zero-lookahead trade log; (4) Phase-3 Backtest PASS at current gate — n>200, net PF>1.25, Sharpe>1.2, MaxDD<15% at BOTH standard and 2× spread stress (`CLAUDE.md` §0.6/§7); (5) Phase-4 Robustness (walk-forward, Monte Carlo, parameter stability, regime, cost sensitivity); (6) Phase-5 Offline Virtual Demo PASS with no drift vs backtest. Each stage transition must go through `svos/lifecycle/manager.py`/`StrategyRegistryService.transition` with a governance decision — no direct edits. Additionally, before any of this strategy's code can execute even in shadow mode, `strategies/adapters/day_trading_maneuvers_adapter.py` must actually be implemented (it does not exist today) and the strategy must be added to `_STRATEGY_MAP` in `scripts/run_portfolio.py` — both are separate follow-up work items, not part of this registration task |

## Evidence sources checked

- `config/strategy_portfolio.yaml`, `config/strategy_catalog.yaml`
- `data/svos/registry/*/state.json`, `*/versions.jsonl`, `*/transitions.jsonl`
- `docs/VERDICT_LOG.md` (full file)
- `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`
- `deploy/gcp-vm1/systemd/smc-demo-runner.service`, `deploy/gcp-vm1/run_smc_demo.sh`
- `scripts/run_st_a2_demo.py`, `scripts/validate_runtime_config.py`
- `logs/strategy_demo_state.json` (live runtime governance decision snapshot)
- `GOVERNANCE_BASELINE_REPORT.md` (2026-07-11, same-day baseline correction)
- `svos/application/adapter_dispatch.py`, `strategies/adapters/*`
- Git history: `cf92a9e` (today's portfolio/runtime-guard change)
- `svos/registry/service.py` (`StrategyRegistryService`), exercised directly via
  `record_version()` for TASK-1-DAYTRADING-GOV (2026-07-11) — read back via
  `get_strategy_record()` and `scripts/registry_audit.py`

## What this document does not do

- Does not mutate any registry `state.json` or catalog `status`/`approved`
  field. All mutation must go through `svos/lifecycle/manager.py`.
- Does not correct `docs/VERDICT_LOG.md` — Flag 2 is a recommendation for its
  owner, not an edit made here.
- Does not resolve the ST-A2 `DRAFT`/`DEFERRED_REVALIDATION` inconsistency
  (Flag 4) — flagged for the lifecycle manager owner.
