# Missing Features & Roadmap

Date: 2026-07-04
Status: Read-only audit finding — proposes sequencing, does not authorize any implementation
Companion: `IMPLEMENTATION_MATRIX.md`, `TECHNICAL_DEBT.md`, `OBJECTIVE_GAP_ANALYSIS.md`
Relationship to existing plans: this roadmap synthesizes and reprioritizes the still-open
workstreams already tracked in `ARCHITECTURE_STABILIZATION_ROADMAP.md` (WS1-WS8) against findings
from this audit pass. It does not replace that document as the ADR-sequencing authority — it adds
the newly-surfaced items (risk-feedback dead code confirmed still open, doc-sprawl cleanup,
test-coverage gap, LLM pipeline wiring) into one prioritized list.

---

## Part 6 — Prioritized Missing/Incomplete Features

### Critical

| Feature | Difficulty | Risk | Dependencies |
|---|---|---|---|
| Wire `record_result()`/`record_close()` into the live trade-close event path so daily/weekly/monthly loss halts and consecutive-loss halts actually fire (WS2, `ARCHITECTURE_STABILIZATION_ROADMAP.md`) | Medium — needs a real "trade closed" event source, not just a function call fix | High — currently a bot on a losing streak will not self-halt via this mechanism | None blocking; can start immediately |
| Restart-recovery reconciliation in the canonical execution loop (`ExecutionStateStore.recover_incomplete()` never called from `run_portfolio.py`) (WS5) | Medium | High — an ambiguous order across a crash/restart is not resolved before new orders | Should land alongside/after the risk-feedback fix since both touch the same startup path |
| Default-deny broker-write boundary at every layer, not just the CLI entrypoint (WS3, ADR-0012) | Medium | High — a hypothetical alternate caller could still reach a live-mode code path | Independent of the above two |
| Consolidate the two competing execution/order stacks (`execution/trade_manager.py` vs. `production/engine/orders.py`/`positions.py`) — pick one, retire the other | Medium — mostly deletion/import-swap once a decision is made | Medium — dual stacks increase audit surface and risk of the wrong one being modified | Owner decision on which stack is canonical |

### High

| Feature | Difficulty | Risk | Dependencies |
|---|---|---|---|
| Retire one of the two SVOS pipeline orchestrators (`svos/application/pipeline.py` vs. `research/svos/engine.py`+`research/validation/engine.py`) | High — requires confirming feature parity first | Medium — divergent metrics/behavior risk if both keep being edited | Needs a parity audit before deletion |
| Fix `svos/application/pipeline.py`'s VIRTUAL_DEMO evidence recording (7 failing tests in `tests/svos/test_pipeline.py`, currently `--ignore`'d by CI rather than fixed) | Low-Medium | Medium — Phase-5 gate evidence is currently unreliable | None |
| Bring canonical runner (`run_portfolio.py`) up to the recovery/governance wiring level of the legacy runner (`run_st_a2_demo.py`), or reverse the "canonical" designation | Medium | Medium | Depends on the execution-stack consolidation decision above |
| Wire `config/strategy_portfolio.yaml` into whichever runner is actually deployed live, so editing risk config has real effect | Low | Medium — currently a real correctness trap for operators | Depends on which runner is chosen as canonical |
| Expand CI test coverage beyond ~28% of test files, or explicitly document why the excluded dirs are out of scope | Medium | Medium — real regressions (confirmed: 1 failing `tests/core` test) can land on `main` undetected today | None |
| Bandit/security scan coverage of the actual live execution path (`execution/`, `dashboard/`, `scripts/`, `core/`, `bot.py`) | Low | Medium | None |
| Dashboard consolidation (3 backends → 1), fixing the confirmed stale-log and wrong-trades-file bugs | High | Medium — current dashboards are explicitly rated unreliable for live-money decisions even in demo | Needs an owner decision on which backend/frontend combination to keep |
| `core/portfolio_manager.record_close()` wiring so one-per-symbol enforcement doesn't degrade to one-trade-per-symbol-per-day | Low-Medium | Medium | Overlaps with the risk-feedback fix (same "trade closed" event source) |

### Medium

| Feature | Difficulty | Risk | Dependencies |
|---|---|---|---|
| Wire `svos/application/refinement.py` (LLM drafting) into `svos/application/pipeline.py` as a real REFINEMENT phase, with test coverage | Medium | Low — advisory-only by design, human-acceptance gated | Add `openai` to requirements; document `DEEPSEEK_API_KEY` in `.env.example` first |
| Consolidate the 5+ independent PF/metrics implementations into one canonical metrics library | High | Medium — risk of divergent PF numbers between gate and ad-hoc scripts | Needs a parity/regression test suite before consolidation |
| Node-separate Postgres onto VPS 2 per the target deployment topology | High (real infra work) | Medium | GCP provisioning decisions, VPS 2 RAM upgrade (currently 955 MiB, below the 8 GB gate) |
| Root-level report sprawl cleanup — archive/delete superseded scorecards, add a "Root Reports" tier to `DOC_AUTHORITY.md` | Low | Low — but real reader-misleading risk today | Owner sign-off on which reports are canonical |
| Real-world rollout of strategy packaging/signing (GCS bucket/KMS provisioning, IAM, remote host rollout, rehearsals) — per `docs/architecture/remaining_real_world_rollout_tasks.md` | High (real infra + cost) | Medium | Owner-level cloud spend/IAM decisions |
| Scheduled/automated Postgres backup job (currently manual-only) | Low | Low-Medium | None |
| Fix `agent/` vs `agents/` naming collision | Low | Low | None |
| Prune the 156 MB nested duplicate inside `New Dashborad/` | Low | Low | None |

### Low

| Feature | Difficulty | Risk | Dependencies |
|---|---|---|---|
| Delete/gitignore stray files (`scratch_deepseek_test.py`, `backtest_output_d2_holdout/`, `backtest_output_d2_optimized/`) | Low | Low | None |
| Delete-candidate empty local data dumps (`research_engine/`, `research_sweep/`) | Low | Low | Confirm truly unused first (already confirmed 0 imports in this audit) |
| Centralized log aggregation (ELK/Loki/CloudWatch) | Medium | Low at current single-host scale | Only matters once multi-host |
| MFA / per-user rotatable auth tokens for the dashboard | Medium | Low for a single-operator deployment | Only matters at multi-operator scale |

---

## Part 7 — Phased Roadmap

### Phase 1 — Safety-Critical Correctness (land first, blocks trusting demo results)
**Objectives**: make the existing demo deployment's safety mechanisms actually work as documented.
**Tasks**:
- Wire trade-close events into `record_result()` and `record_close()` (both risk-halt and
  position-release paths use the same missing signal — fix together).
- Wire `ExecutionStateStore.recover_incomplete()` into the canonical runner's startup path.
- Correct the circuit breaker's hardcoded `won=True` at open-time to reflect real outcomes at close.
**Dependencies**: none blocking; can start immediately; touches `scripts/run_portfolio.py`,
`execution/demo_risk_manager.py`, `core/portfolio_manager.py`.
**Deliverables**: a demo bot that actually halts on a real losing streak and safely recovers from
a crash mid-order.
**Acceptance criteria**: a test that forces a losing streak past the configured threshold and
asserts the bot halts; a test that simulates a crash during `SUBMISSION_PENDING` and asserts
recovery resolves it before the next order; `core/portfolio_manager` shows a symbol released after
its position closes.

**Status — 2026-07-04**: all three tasks landed, in `scripts/run_st_a2_demo.py` (the deployed
runner) rather than `run_portfolio.py` (undeployed, no systemd unit — fixing it was correctly
out of scope; see `SYSTEM2_MASTER_PLAN.md` Phase 2's canonical-runner decision). Evidence:
`tests/scripts/test_run_st_a2_demo_close_detection.py`, `tests/execution/test_startup_recovery.py`,
`tests/scripts/test_run_st_a2_demo_e2e_recovery.py`. `SYSTEM2_MASTER_PLAN.md` is the authoritative
detail record for this fix; this entry is a status pointer, not a duplicate.

### Phase 2 — Execution-Path Consolidation
**Objectives**: eliminate the competing execution/order stacks and canonical/legacy inversion so
there is exactly one trusted path.
**Tasks**:
- Decide and document which stack is canonical: `execution/trade_manager.py` (currently live) or
  `production/engine/orders.py`/`positions.py` (currently unused).
- Port any wiring gaps (governance guard, permission service, recovery) from
  `scripts/run_st_a2_demo.py` into `scripts/run_portfolio.py`, or formally re-designate which
  script is canonical.
- Retire the losing stack/script rather than leaving it as parallel dead code.
**Dependencies**: Phase 1 (both touch the same runner startup path).
**Deliverables**: one execution stack, one canonical runner with full governance/recovery wiring.
**Acceptance criteria**: `grep` confirms zero production imports of the retired stack; the
canonical runner's test suite covers the same governance/recovery cases the legacy runner's did.

### Phase 3 — SVOS Pipeline Unification & Test Coverage
**Objectives**: retire duplicate SVOS orchestrators, fix the Phase-5 evidence gap, and close the
CI coverage gap.
**Tasks**:
- Parity-audit `svos/application/pipeline.py` vs. `research/svos/engine.py` +
  `research/validation/engine.py`; retire the losing one.
- Fix VIRTUAL_DEMO evidence recording so `tests/svos/test_pipeline.py` passes without being
  excluded from CI.
- Expand `ci.yml`'s test-path selection to cover currently-excluded directories (`tests/core` at
  minimum, given its known live failure) or explicitly document the exclusion rationale per directory.
- Add `openai` to `requirements.in`/`requirements.lock`; document `DEEPSEEK_API_KEY` in `.env.example`.
**Dependencies**: none blocking Phase 3 start; independent of Phases 1-2.
**Deliverables**: one SVOS orchestrator, a green `tests/svos/test_pipeline.py` inside CI, wider CI coverage.
**Acceptance criteria**: only one orchestrator remains importable; CI's `tests` job includes the
previously-excluded file with a pass; dependency manifests match the venv's actual installed packages.

### Phase 4 — Governance & Documentation Hygiene
**Objectives**: bring the document corpus and root-level report sprawl under
`docs/00_Project/DOC_AUTHORITY.md`'s governance, and consolidate the dashboard.
**Tasks**:
- Archive or delete superseded root-level reports (starting with `PROJECT_READINESS_SCORECARD.md`);
  add a "Root Reports" tier to `DOC_AUTHORITY.md`.
- Resolve the ~67 broken links / ~98 missing file refs the doc-readiness scanner reports.
- Decide and execute dashboard consolidation (3 backends → 1); fix the confirmed stale-log and
  wrong-trades-file bugs as part of the same work, not separately.
- Rename `agent/` to remove the naming collision with `agents/`; prune the `New Dashborad/` nested duplicate.
**Dependencies**: independent of Phases 1-3; can run in parallel by a different owner/agent.
**Deliverables**: a document tree fully compliant with `DOC_AUTHORITY.md`; one dashboard backend.
**Acceptance criteria**: `scripts/lint_docs.py` reports zero broken links; a single dashboard
process serves both research and trading views with freshness indicators on every widget.

### Phase 5 — Real-World Infrastructure Rollout (owner-gated, out of pure-code scope)
**Objectives**: execute the already-designed but not-yet-provisioned infrastructure: node
separation, real cloud signing, backup automation, DR rehearsal.
**Tasks**:
- Provision GCS bucket/KMS key/IAM for real package signing; run one end-to-end signed rollout rehearsal.
- Cut Postgres control-plane data over to VPS 2 (after upgrading its RAM past the 8 GB gate).
- Schedule the existing backup CLI via cron/systemd timer.
- Execute and document a DR restore rehearsal.
**Dependencies**: owner-level cloud spend/IAM decisions; Phases 1-3 should land first so what's
being rolled out is already safety-correct.
**Deliverables**: a node-separated, backed-up, rehearsed deployment — still demo-only, no live capital.
**Acceptance criteria**: a real signed package verified end-to-end against a provisioned KMS key;
a documented, timestamped restore-rehearsal report; a scheduled backup job with a logged successful run.

**Explicitly out of scope for all 5 phases**: enabling `LIVE_TRADING=true` or `DEMO_ONLY=false`.
That remains gated behind Production Approval (`CLAUDE.md` §0.1), which requires a strategy to
clear the tightened Phase-3 gate first — none currently does.
