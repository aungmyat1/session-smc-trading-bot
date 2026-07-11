# SVOS Pipeline Orchestrator Consolidation

Status: RECOMMENDATION — not yet executed. Recorded 2026-07-11 as part of the
P0 production-readiness remediation (ARCH-01). Scope: SVOS research pipeline
orchestration only. Distinct from `docs/systems/system2/PIPELINE_CONSOLIDATION_PLAN.md`,
which covers System 2 (production/demo execution) runner duplication and
explicitly excludes SVOS/research.

## Finding

Three modules were initially suspected to be competing SVOS orchestrators.
Investigation found only two are true duplicates; the third is a shared
dependency of both:

- **`svos/orchestration/service.py` (`SVOSPlatform`)** — not a pipeline
  orchestrator. It's the shared persistence/governance/evidence layer (PG or
  local JSONL) that both runners below call into. Not a candidate for removal.
- **`research/svos/engine.py` (`SVOSRunner`)** — full 9-stage runner matching
  the canonical lifecycle enum in `svos/lifecycle/manager.py` (intake, audit,
  enhancement, replay, backtest, robustness, verification_ready, virtual_demo,
  production_approval). Consumed by `dashboard/pipeline_service.py`,
  `scripts/run_svos_pipeline.py`, `scripts/run_current_strategy_svos.py`,
  `strategy_audit/rules.py`.
- **`svos/application/pipeline.py` (`StrategyPipeline`)** — a narrower 6-phase
  runner (INTAKE→VIRTUAL_DEMO only; missing ENHANCEMENT, REFINEMENT,
  VERIFICATION_READY from the canonical lifecycle). Only reachable via one
  call site: `application/strategy_service.py:svos_main`, the `agtrade
  strategy svos` CLI subcommand. Has dedicated test coverage
  (`tests/svos/test_pipeline.py`, 9 tests) but no dashboard or script usage.

## Recommendation

`SVOSRunner` (`research/svos/engine.py`) is authoritative. It is the phase
superset, matches the lifecycle manager's canonical enum, and is what the
dashboard and primary CLI scripts actually run today. `StrategyPipeline` is
the true duplicate — narrower, less current, single call site.

`SVOSPlatform` is retained under both as the shared evidence/persistence
layer; it is not part of the consolidation decision.

## Migration plan

1. Re-point `application/strategy_service.py:svos_main` to call `SVOSRunner`
   instead of `StrategyPipeline`, preserving the existing CLI flags/output
   contract.
2. Migrate `tests/svos/test_pipeline.py`'s assertions to run against
   `SVOSRunner`'s equivalent stages — port intent, don't delete coverage.
3. Mark `svos/application/pipeline.py` deprecated (docstring, no new
   callers) but leave the file in place for one release cycle.
4. Confirm `tests/svos/test_platform.py` and dashboard SVOS tests stay green
   before and after step 1.
5. After one clean release cycle with no regressions, remove
   `svos/application/pipeline.py` and its dedicated test file in a follow-up
   change.

## Rollback

Revert `svos_main`'s import from `SVOSRunner` back to `StrategyPipeline`.
Zero other code depends on `StrategyPipeline`, so rollback is a single-file
revert with no cascading changes.

## Risk

Medium. Real test coverage exists on the module being deprecated — same
caution class this repo already applies to other dormant-but-tested code
(see `docs/systems/system2/PIPELINE_CONSOLIDATION_PLAN.md`'s treatment of
`bot.py`/`adaptive/run_shadow.py`). Not executed as part of this
remediation pass — P1, queued for explicit approval.
