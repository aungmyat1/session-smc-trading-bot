---
Date: 2026-07-12
Author: Release Manager audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 8 of the System2-first reconciliation program.
---

# Extraction Plan — Recovering Valuable Work from `codex/demo-smoke-test`

## Executive Summary

Of the 16-commit unmerged frontier identified in `BRANCH_RECONCILIATION_REPORT.md`,
seven items carry extractable value. Each becomes its own single-responsibility
PR, opened only after Phases 3–7 of this program land (System2 safety/evidence
work takes priority per the stated program order). None are extracted as a
bulk merge or cherry-pick chain — each needs independent review against
current `main`, which has moved substantially since the branch's fork point.

## Current State

`codex/demo-smoke-test` cannot be merged directly (per this program's
non-negotiable rules). Its valuable content must be re-created as scoped PRs
sourced from — but not identical to — the branch's commits, since several
commits (see Rejected section) must not be adopted verbatim.

## Extraction candidates, one PR each

| # | Source commit(s) | Feature | System | Pre-req before extraction |
|---|---|---|---|---|
| 1 | `cf92a9e` (partial) | Strategy governance checks — the non-ST-A2 containment logic | System2 Safety | **Superseded by this program's own Phase 5 PR** (`claude/strategy-containment`) — do not re-extract, would duplicate |
| 2 | `dbc8071` | Orchestrator dependency map + regression tests for strategy registry/bot reconciliation | Infrastructure | None — low risk, additive docs+tests. Directly informs the known dual-orchestrator debt (`docs/svos/CURRENT_STATE.md`) |
| 3 | `81f7adf` | Periodic runtime reconciliation (SYS2-T014, branch version) | System2 Safety | **Diff line-by-line against `main`'s own SYS2-T014 (PR #27, `d140783`) first.** `SYSTEM2_CORRECTNESS_AUDIT.md` confirms `main`'s version already resolves the underlying defect — this is likely fully superseded, not merely overlapping. Do not extract without that diff confirming otherwise. |
| 4 | `92432467` | Risk register entry (risk #13, unauthenticated System2 endpoints) | Documentation | Check whether `docs/operations/risk-register.md` on `main` already covers this (PR #22 added RBAC to those endpoints — the risk may already be closed, not just documented) |
| 5 | `bca39b6` | ST-A2 strategy freezing + trade ledger generation (`research/st_a2_freeze.py`) | System1 Research | Review for conflicts with `svos/lifecycle/manager.py`'s own state machine before extraction — "freezing" a strategy's parameters is adjacent to lifecycle authority, which `DOC_AUTHORITY.md` reserves exclusively to that module |
| 6 | `c575dfe`, `38c7635`, `6a689fd` | Professional dataset v2 pipeline + validation/reporting scripts | System1 Research | Hold until System2 gate (Phases 3–7) passes, per this program's explicit priority order. Do not extract generated artifacts (`datasets/professional_3y_4symbol_v2/*.json`) — regenerate via the pipeline instead of committing manifests |
| 7 | `b351f84` | Strategy optimization diagnostics config + doc | System1 Research | Same hold as #6; low value, low urgency |

## Evidence

Each row's "pre-req" column is the evidence gate — no extraction proceeds
without satisfying it. Rows 3–4 in particular could otherwise silently
re-introduce the exact duplication this program exists to prevent (two
reconciliation implementations, or a stale risk-register entry claiming an
already-fixed gap is still open).

## Risk

- Extracting row 3 without the diff check is the single highest-risk item in
  this plan — it could reintroduce a since-superseded reconciliation
  implementation alongside the current one.
- Extracting rows 5–7 before the System2 gate passes would violate this
  program's own stated priority order (System1 continues only after System2
  reaches controlled demo readiness) — sequencing error, not a correctness
  risk, but still a rule this program must not break.

## Recommendation

Extraction order: **2 → 4 → 3 → 5 → 6 → 7**, i.e. the cheapest, lowest-risk,
purely-additive items first (orchestrator dependency map, risk register
check), then the one item requiring careful comparison (SYS2-T014 diff),
then System1 items only after the System2 gate closes.

## Priority

Low relative to Phases 3–7 — none of these items are required for demo
readiness or evidence-gap closure. Sequenced last deliberately.

## Estimated effort

| Item | Hours |
|---|---|
| #2 Orchestrator dependency map | 1–2 (review + adapt to current `main`) |
| #4 Risk register check | <1 |
| #3 SYS2-T014 diff + decision | 2–3 (comparison work, likely concludes "reject, already superseded") |
| #5 ST-A2 freezing (System1, post-gate) | 3–5 |
| #6/#7 Dataset v2 + diagnostics (System1, post-gate) | 8–12 combined |

## Rollback

Each extraction is its own PR — revertible independently, no cross-PR
dependencies by design.

## Dependencies

- Phases 3–7 must land first (System2-first priority).
- Item #3 depends on completing its diff-comparison sub-task before any
  code is written.

## Acceptance criteria

- [x] One PR per feature, not a bulk merge
- [x] Every extraction candidate has an explicit pre-req/evidence gate
- [x] No generated dataset artifacts proposed for direct commit
