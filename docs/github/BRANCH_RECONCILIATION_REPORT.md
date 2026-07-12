---
Date: 2026-07-12
Author: Lead Architect / Release Manager audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 1 of the System2-first reconciliation program.
---

# Branch Reconciliation Report — `main` vs `codex/demo-smoke-test`

## Executive Summary

`codex/demo-smoke-test` is **not** a clean feature branch — it is a long-running
integration branch whose earlier content (everything through the merge-base)
has already reached `main` via three separate, previously-merged PRs (#20,
#22, and the fork-point commit shared with PR #23). What remains genuinely
unmerged is a **16-commit frontier** dated 2026-07-07 through 2026-07-11,
produced after PR #26 ("Phase 5B.5: Architecture Approval") was **closed
without merging** (confirmed by file-presence: none of PR #26's files —
`ADR-0011` through `ADR-0014`, `PHASE-5B5-ARCHITECTURE-APPROVAL.md`,
`wine-investigation-report.md` — exist on `main` today, despite the PR API
reporting a `merged_at` timestamp; file-presence is the more reliable signal
and is what this report relies on throughout).

**Verdict: this branch must not be merged as a unit.** Its unmerged frontier
mixes real System2 safety value (strategy governance checks, a confirmed
`trade_manager.py` defect writeup), pure System1 research (professional
dataset v2, ST-A2 freezing), one-off VPS operational history that shouldn't
land on `main` at all, and one governance commit that — if adopted verbatim —
would **disable the live ST-A2 demo runner**, directly contradicting this
program's Priority 1 (protect existing demo execution). Each item needs
individual extraction, not a bulk merge. See `EXTRACTION_PLAN.md` for the
one-PR-per-feature sequencing.

## Method

`git log origin/main..origin/codex/demo-smoke-test --oneline` (42 commits) was
walked commit-by-commit. For each: read the commit message, and for the
higher-risk/higher-value items, read the actual diff (`git show <sha>`).
Cross-referenced against `main`'s own history and PR bodies (#20, #22, #23,
#26) to determine already-merged status by **content match**, not by trusting
the GitHub API's `merged` flag alone (which disagreed with file-presence
ground truth for PR #26 — flagged explicitly below).

## Classification key

- **Already merged** — content is on `main` today (verified by file/feature presence), different SHA due to squash-merge.
- **Superseded** — `main` independently implemented equivalent functionality via a different PR.
- **System2 Safety** — execution/risk/recovery correctness or safety property.
- **System2 Feature** — execution-layer capability, non-safety.
- **System1 Research** — strategy research, datasets, backtesting, validation tooling.
- **Infrastructure** — deployment, CI, VPS ops, tooling.
- **Documentation** — docs/reports with no code change.
- **Generated artifacts** — datasets, manifests, checksums — do not belong in git history as commits to cherry-pick.
- **Reject** — should never land on `main`.

## Commit-by-commit inventory

| # | SHA | Date | Summary | Class | Dependency | Risk | Recommended action |
|---|---|---|---|---|---|---|---|
| 1 | `bca39b6` | 07-11 | ST-A2 strategy freezing + trade ledger generation (`research/st_a2_freeze.py`, 505 lines) | System1 Research | None declared | Low (research-only, no execution path) | Extract later, after System2 gate — review for lifecycle-authority conflicts with `svos/lifecycle/manager.py` first |
| 2 | `b351f84` | 07-11 | Strategy optimization diagnostics config + doc | System1 Research | None | Low | Extract later |
| 3 | `6a689fd` | 07-11 | Dataset validation/reporting script enhancements | System1 Research | None | Low | Extract later |
| 4 | `c575dfe` | 07-11 | Professional dataset v2 processing scripts + tests | System1 Research | #3, #5 | Low | Extract later |
| 5 | `38c7635` | 07-11 | Professional dataset download/processing scripts | System1 Research | None | Low (new scripts, no existing-path changes) | Extract later |
| 6 | `dbc8071` | 07-11 | Orchestrator dependency map + regression tests for strategy registry/bot reconciliation | Infrastructure / Documentation | None | Low, additive docs+tests | **Extract soon** — directly informs the known dual-orchestrator debt (`docs/svos/CURRENT_STATE.md`) |
| 7 | `cf92a9e` | 07-11 | Governance checks disabling unapproved strategies | **System2 Safety (mixed)** | `config/strategy_catalog.yaml` semantics | **High** — as written, sets `ST-A2: enabled: false`, which would stop the live demo runner | **Do not adopt verbatim.** The LondonBreakout/NYMomentum/AdaptiveSMC/VWAPMeanReversion containment logic is correct and reusable; the ST-A2 disable contradicts Priority 1. Extract the non-ST-A2 portion only (see Phase 5 of this program). Also introduces a `docs/.../ST-A2 Approved Strategy Package/` directory with `approval_record.md` etc. while `strategy_catalog.yaml` shows ST-A2 unapproved — needs explicit review before extraction to confirm it's a template/scaffold, not a false approval claim. |
| 8 | `30aa648` | 07-10 | Preserve VPS migration state before teardown | Infrastructure | None | N/A — historical/instance-specific | **Reject** — one-off operational snapshot, not reusable code |
| 9 | `81f7adf` | 07-07 | Periodic runtime reconciliation for pending executions (SYS2-T014) | **Superseded** | — | Needs diff comparison | `main` has its own independent SYS2-T014 implementation (`d140783`, PR #27, merged directly to `main` the same week). Do not merge this version without first diffing against `main`'s — high risk of two incompatible reconciliation implementations coexisting silently. Flagged for Phase 8 comparison, not blind adoption. |
| 10 | `92432467` | 07-07 | Docs: risk #13, unauthenticated System2 endpoints | Documentation | None | Low | Extract — cheap, valuable risk-register entry if not already tracked on `main` |
| 11 | `c2bf23c` | 07-07 | Docs: PR #26 CodeRabbit findings tracked as debt | Documentation | PR #26 (unmerged) | Low, but references unmerged context | Low priority — re-file directly if the underlying findings still apply |
| 12 | `49b29ca` | 07-07 | Merge commit (remote-tracking → branch) | N/A | — | — | No action — merge scaffolding only |
| 13 | `8694a5a` | 07-07 | **Docs: confirms `trade_manager.py` defect** — `BROKER_ACKNOWLEDGED` records never advance, `RECOVERY_PENDING` only clears at startup | Documentation (records a System2 Safety finding) | `execution-record-nonterminal-investigation.md` (not separately committed in this range — referenced, not included) | N/A for the doc itself; the **underlying defect is high-risk** | **High-value input to Phase 6 correctness audit** (this report's sibling, `SYSTEM2_CORRECTNESS_AUDIT.md`) — extract the finding regardless of whether the referenced investigation doc itself is recovered |
| 14 | `6f39a77` | 07-07 | Merge commit (`main` → branch) | N/A | — | — | No action |
| 15 | `faed6d1` | 07-07 | Docs: Phase 5B.5 architecture approval report | Documentation | ADR-0013/0014 (unmerged) | Low | Extract as historical governance record once ADR-0011–0014 disposition is decided (see Phase 9 — several of those ADRs describe a path this program's rules explicitly forbid) |
| 16 | `ce03967` | 07-07 | Refactor: decouple execution from SVOS, add approved package contract | System2 Feature (refactor) | Wide — touches execution/SVOS boundary | **High** — refactor, not additive | **Reject for now.** PHASE-5B5's own recorded decision was "HOLD on ExecutionService implementation pending FIX API access confirmation" — adopting this refactor would contradict that branch's own governance gate, not just this program's "no unrelated refactoring" rule. |
| 17–31 | `0f8f729` … `7fcf673` | 07-04 – 07-05 | Full PR #22 commit range (Real-Time Operations Layer, RBAC, dashboard, close-reconciliation fixes, emergency-stop resume-scoping fix, Gai dashboard SPA serving) | **Already merged** | — | None | No action — content-verified present on `main` (PR #22, merged 2026-07-05T12:43:33Z; corroborated by matching file sets and matching PR-body prose found in `docs/systems/system2/STATUS.md` on `main`) |
| 32–41 | `c9203a1` … `b5b5e2d` | 07-02 – 07-03 | Full PR #20 commit range (canonical execution pipeline, signed package v2, risk/order/position services, recovery, Postgres ops persistence) | **Already merged** | — | None | No action — content-verified present on `main` (PR #20, merged 2026-07-03T18:43:26Z) |
| 42 | `893de10` | 07-05 | Repository stabilization: reorganize root docs (#23) | **Already merged** | — | None | This commit **is the merge-base** (`main`'s `9063d10` is the squashed form of this exact commit/PR). No action. |

Note on rows 17–41: individually enumerating all ~25 commits in the PR #20/#22
ranges was skipped after content-matching the first and last commit of each
range against `main`'s file set and each PR's own body text (both matched
exactly) — re-deriving per-commit detail for already-merged content would not
change any recommendation and burns review budget better spent on the
16-commit unmerged frontier (rows 1–16), which is where all actionable risk
and value actually lives.

## Cross-cutting findings

1. **PR #26's `merged` status is unreliable.** The GitHub API returned a
   `merged_at` timestamp for PR #26 despite `state: closed` and `merged:
   false`, and despite none of its files existing on `main`. Treat
   file-presence, not API flags, as ground truth for any future reconciliation
   work on this repo.
2. **Two independent SYS2-T014 implementations may exist** (`main`'s `d140783`
   vs. this branch's `81f7adf`). Not yet diffed line-by-line — flagged as a
   required check before any further execution-layer work, since silently
   having two reconciliation implementations is exactly the kind of
   duplication this program exists to prevent.
3. **The branch's own CLAUDE.md is stale relative to its own ADR-0014** —
   still describes mt5linux as "replacing" MetaAPI. Not extracted, per this
   program's explicit prohibition on reviving the Wine/mt5linux path.

## Rejected work (Phase 9)

- **Wine/mt5linux path**: `execution/mt5linux_connector.py`, `ADR-0011`,
  `ADR-0013`, `docs/audit/wine-investigation-report.md`, `docs/operations/mt5-node-migration-plan.md`.
  Confirmed broken (`could not load kernel32.dll`) and explicitly superseded
  by that same branch's own `ADR-0014` decision to stay on MetaAPI. Never
  extract without an explicit owner-authorized architecture change.
- **`30aa648`** (VPS migration state snapshot) — instance-specific, not portable.
- **`ce03967`** (SVOS/execution decoupling refactor) — contradicts its own
  branch's HOLD decision; out of scope regardless.
- **Generated dataset artifacts** (`datasets/professional_3y_4symbol_v2/manifest.json`,
  `checksums.json` — 247–621 lines each): do not belong in `git log` as
  reconciliation targets; if the professional-dataset pipeline is extracted
  later (System1, post-gate), regenerate these, don't cherry-pick them.

## Acceptance criteria for this report

- [x] Every commit in the 42-commit range classified into exactly one category
- [x] SHA, summary, dependency, risk, and recommended action recorded per commit (individually for the unmerged frontier; range-level for content-verified already-merged spans)
- [x] No merge, cherry-pick, or code change performed by this report
