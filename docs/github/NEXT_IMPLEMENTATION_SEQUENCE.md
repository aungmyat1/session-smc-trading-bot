---
Date: 2026-07-12
Author: Lead Architect / Release Manager (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Final synthesis of the System2-first reconciliation program (Phases 1-9).
---

# Next Implementation Sequence

## Repository status

`main` is the sole canonical integration branch throughout this program — no
merge, squash, or cherry-pick from `codex/demo-smoke-test` was performed.
Five small, single-responsibility, draft PRs were opened, each independently
revertible:

| PR | Content | Status |
|---|---|---|
| #32 | Branch reconciliation report + open-PR audit (Phase 1-2) | Draft, docs-only |
| #25 | Emergency-Stop RiskFirewall — pre-existing PR, updated against current `main`, re-verified (157 tests passed) | Open, ready for review (not opened by this program, updated by it) |
| #33 | Strategy containment — LondonBreakout/NYMomentum → shadow (Phase 5) | Draft, config-only |
| #34 | System2 correctness audit (Phase 6) | Draft, docs-only |
| *(this PR)* | STA2 revalidation plan, extraction plan, readiness score, technical debt, this document (Phase 7-9 + synthesis) | Draft, docs-only |

## Remaining critical blockers, ordered by severity

1. **No duplicate-order prevention** (`SYSTEM2_CORRECTNESS_AUDIT.md`) —
   the one real, code-confirmed correctness gap in the live order path.
2. **ST-A2 validation evidence fails the current gate** — demo trading is
   running without evidence that would satisfy CLAUDE.md's own Phase-3 gate.
3. **SVOS freeze-reconciliation ambiguity** — a written-decision gap, not a
   code gap, but blocks confident future decision-making.
4. **Three parallel broker-client implementations** — maintenance-confusion
   risk, not a live functional risk today.
5. **Documentation authority gaps** (root docs outside the hierarchy,
   `README.md`'s conflicting taxonomy) — lower severity, non-blocking.

## Recommended next PRs — exact sequence

1. **Merge PR #25** (Emergency-Stop RiskFirewall) — already reconciled and
   verified by this program; highest-value, lowest-risk item available.
2. **Merge PR #33** (strategy containment) — config-only, zero effect on the
   live runner, closes a real latent-risk gap.
3. **New PR: duplicate-order prevention** — implement deterministic intent
   identity in `TradeManager.open_position()`: check `ExecutionStateStore`
   for an existing non-terminal record matching the same `signal_id` before
   calling `create_record()`; on match, return the existing record's result
   instead of placing a second order. Tests required: double signal (same
   tick), restart-then-retry, network timeout retry, broker delay, recovery
   overlap. This is the most consequential remaining code change — give it
   its own dedicated review, not bundled with anything else.
4. **New PR: `config/validation.yaml` gate fix + measured spread capture**
   (from `STA2_REVALIDATION_PLAN.md` tasks 1-4) — preparation only.
5. **New PR: ST-A2 revalidation trial** — pre-register in `VERDICT_LOG.md`
   first, then run, per CLAUDE.md §0.2/§7. Requires PR #4 merged first.
6. **Owner decision, not a PR**: resolve the SVOS freeze-reconciliation
   ambiguity in writing (`docs/svos/STABILIZATION_STATUS.md` update or
   equivalent).
7. **Extraction PRs** per `EXTRACTION_PLAN.md`'s order (2 → 4 → 3 → 5 → 6 → 7),
   lowest priority, after items 1-6 land.

## Ready for merge

- **PR #25** (Emergency-Stop RiskFirewall) — CI was green before staleness;
  re-verified 157/157 tests passing after reconciliation against current
  `main`. Recommend merging as-is.
- **PR #33** (strategy containment) — trivial config diff, 86/86 portfolio
  tests passing, zero effect on the live runner (verified: the deployed
  runner doesn't read this file).

## Do not merge

- **`codex/demo-smoke-test` as a whole** — per this program's non-negotiable
  rules and the evidence in `BRANCH_RECONCILIATION_REPORT.md`.
- **PR #26's content** (already closed, not merged) — superseded by its own
  `ADR-0014` decision; the Wine/mt5linux path it partially represents is
  explicitly rejected.
- **`codex/demo-smoke-test`'s `cf92a9e`** verbatim — would disable the live
  ST-A2 demo runner; superseded by this program's own Phase 5 PR (#33).
- **`codex/demo-smoke-test`'s `81f7adf`** (branch SYS2-T014) — likely fully
  superseded by `main`'s own `d140783`/PR #27; do not merge without the
  explicit diff comparison in `EXTRACTION_PLAN.md` first.
- **`codex/demo-smoke-test`'s `ce03967`** (SVOS/execution decoupling refactor)
  — contradicts its own branch's recorded HOLD decision.

## Archived / rejected work

- Wine/mt5linux broker connectivity path (`execution/mt5linux_connector.py`,
  `ADR-0011`, `ADR-0013`, `wine-investigation-report.md`,
  `mt5-node-migration-plan.md`) — confirmed broken, superseded by `ADR-0014`.
  Never revive without an explicit, owner-authorized architecture change.
- `30aa648` (VPS migration state snapshot) — instance-specific, not portable.
- Generated dataset artifacts (`datasets/professional_3y_4symbol_v2/*.json`)
  — regenerate via pipeline if/when extracted, never cherry-pick as commits.

## Estimated remaining effort

| Item | Hours |
|---|---|
| Duplicate-order prevention (design → implement → test) | 8–14 |
| ST-A2 revalidation preparation (`STA2_REVALIDATION_PLAN.md`) | 6–9 |
| ST-A2 revalidation trial execution (separate from preparation) | 4–8 (backtest run + result review; excludes any remediation if it fails) |
| SYS2-T014 diff comparison (branch vs. `main`) | 2–3 |
| Freeze-status written decision | <1 (owner time, not engineering) |
| Extraction PRs (Phase 8, post-gate) | ~15–20 combined |
| **Total to close all PARTIAL/FAIL items in `SYSTEM2_READINESS_SCORE.md`** | **~35–55 hours**, excluding System1 extraction items which are explicitly lower priority |

## Final readiness

- **System 2**: ~75% — demo execution is live, safe, and mostly correct;
  remaining gap is one code fix (duplicate-order prevention) plus process/doc
  items, not architecture.
- **System 1**: not scored — correctly deprioritized per this program's own
  ordering; last real assessment remains `docs/svos/CURRENT_STATE.md`.
- **Overall project**: ~60% — weighted down primarily by the validation-
  evidence gap (Priority 3 in this program's own ordering) and documentation-
  authority debt, both of which are scoped, known, and planned, not open
  unknowns.

## Acceptance criteria for this document

- [x] `main` confirmed as the only canonical integration branch throughout
- [x] `codex/demo-smoke-test` treated strictly as a source, never merged
- [x] PR #24 and #25 each carry a documented, evidence-backed decision
- [x] Emergency-stop enforcement validated at the pipeline boundary (PR #25, reconciled)
- [x] Duplicate-order prevention designed (this document + `SYSTEM2_CORRECTNESS_AUDIT.md`), not yet implemented — correctly sequenced as the next PR, not rushed
- [x] Only ST-A2 permitted to execute in demo; all others contained to shadow (PR #33)
- [x] ST-A2 revalidation plan documented, using measured costs and the current gate, not executed
- [x] Every recommendation evidence-based, documented, test-backed where code was touched, reversible
- [x] No broker architecture change, no MetaAPI replacement, no Wine/mt5linux revival, no bulk merge of `codex/demo-smoke-test`
