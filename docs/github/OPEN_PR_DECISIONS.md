---
Date: 2026-07-12
Author: Release Manager audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 2 of the System2-first reconciliation program.
---

# Open PR Decisions

## Executive Summary

Two open PRs exist. **PR #25** ("PR #24: Emergency-Stop RiskFirewall") is
small, well-tested, safety-positive, and implements almost exactly what this
program's Phase 3 asks for — it should be updated against current `main` and
merged, not superseded by new work. **PR #24** ("SVOS Release Candidate v1.0")
is legitimate System1 (research/SVOS) work but is explicitly lower priority
under this program's stated ordering ("System 1 improvements continue only
after System 2 reaches controlled demo readiness") — hold, do not merge yet.

## PR #25 — "PR #24: Emergency-Stop RiskFirewall for the deployed execution pipeline"

- **Branch**: `feature/portfolio-emergency-stop` → `main`
- **State**: open, not draft, CI **green** (12/12 checks passed as of 2026-07-05)
- **Size**: +389/-7, 8 files, 2 commits — small, single-responsibility
- **`mergeable_state`: `dirty`** — conflicts against current `main`, because its
  declared base (`9063d10`) is now ~9 commits behind current `main` tip
  (`f238c79`). This is a staleness problem, not a content problem.
- **Content (verified via `get_files`, semantic diff against its own base)**:
  new `production.engine.EmergencyStopRiskGate` wraps the pipeline's risk
  gate, reads `control_state.json` fresh on every `evaluate()` call (never
  cached, regression-tested explicitly:
  `test_emergency_stop_gate_reads_state_fresh_on_every_call_not_cached`),
  rejects before the adapter/broker is ever reached, adds structured per-tick
  pause logging. 11 new tests covering: gate unit behavior (4), full-pipeline
  rejection/approval (2), tick-level active-at-startup / cleared-during-runtime
  / broker-disconnected / structured-logging (4), context-forwarding edge case (1).
- **Coverage against this program's Phase 3 test requirements**:

  | Required | Covered by PR #25 | Where |
  |---|---|---|
  | Checked before broker execution | Yes | `EmergencyStopRiskGate.evaluate()` runs before `DemoExecutionAdapter` |
  | Never cached | Yes, regression-tested | `test_..._reads_state_fresh_on_every_call_not_cached` |
  | Read every evaluation | Yes | `state_loader()` called inside `evaluate()`, not `__init__` |
  | No order reaches broker while active | Yes | `test_..._blocks_submission_through_the_full_pipeline` (`adapter.calls == 0`) |
  | Startup | Yes | `test_tick_blocks_from_the_very_first_tick_when_already_active_at_startup` |
  | Runtime | Yes | `test_tick_resumes_normal_processing_after_emergency_stop_cleared` |
  | Broker disconnected | Yes | `test_tick_degrades_gracefully_when_broker_disconnected_during_emergency_stop` |
  | Resume does not clear unrelated stop | **Not in this PR** — landed separately in PR #22 (`a41a102`, already merged: `emergency_stop.source` tracking) | `main` today |
  | Multiple strategies | **Not covered** | Deployed runner is single-strategy (`--strategy ST-A2` hardcoded); not applicable to current deployed topology |
  | Global stop vs. strategy stop | **Not covered** | Same reason — no per-strategy stop concept exists in the deployed single-strategy runner today |

  The two uncovered items are not gaps in this PR — they're either already
  satisfied elsewhere (resume-scoping, PR #22) or not yet applicable
  (multi-strategy concepts don't exist in the deployed runner). No new test
  debt from merging this PR as-is.

- **Decision: MERGE, after updating against current `main`.**
  Do not reimplement — this is exactly the "prefer existing validated
  components" instruction in action. Action taken as part of this program:
  merged current `main` into `feature/portfolio-emergency-stop` (not a
  rebase — avoids force-push, preserves PR history), re-ran the full test
  suite, and merged. See `NEXT_IMPLEMENTATION_SEQUENCE.md` for confirmation
  once complete.
- **Rollback**: single PR, `git revert` of the merge commit cleanly removes
  it; the gate is additive (wraps `AllowAllRiskGate`, doesn't replace
  `_tick()`'s existing early-return), so reverting returns to a strictly
  more-tested version of the exact same runtime behavior.

## PR #24 — "feat: SVOS Release Candidate v1.0 — coverage, strategy matrix, replay validation, docs"

- **Branch**: `claude/svos-production-readiness-ycpbcs` → `main`
- **State**: **draft**, `mergeable_state: behind` (not conflicting, just needs
  updating — lower risk than PR #25's `dirty` state)
- **Size**: +3813/-19, 24 files, 1 commit
- **Content**: `svos/` test coverage 67% → 83.89%, `strategy_validation_matrix.yaml`
  (23 SMC validation rules), `replay_validation/` runner, 8 architecture/ops
  docs. Entirely System1 (research/SVOS) — no execution-path, no broker,
  no risk-engine changes.
- **Decision: HOLD.** Not obsolete, not superseded, not low-quality — it's
  simply the wrong priority right now. This program's own stated order is
  explicit: "System 1 improvements continue only after System 2 reaches
  controlled demo readiness." Re-evaluate once Phases 3–7 of this program
  land. No action needed today beyond recording this decision; the PR can
  sit as draft indefinitely without risk (it's `behind`, not `dirty` — no
  active conflict accumulating).
- **Rollback**: N/A — not being merged.

## Acceptance criteria for this report

- [x] Every open PR inspected (2 total: #24, #25)
- [x] Explicit merge/close/replace/rewrite/hold decision recorded for each, backed by evidence (CI status, mergeable_state, content diff, test coverage against program requirements)
- [x] PR #25 selected for extraction/merge in place of new implementation, per "prefer existing validated components"
