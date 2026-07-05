---
Date: 2026-07-05
Status: Investigation complete — no merge, rebase, or push performed
Scope: PR #21 (codex/sys2-first-roadmap → main) vs PR #22 (codex/demo-smoke-test → main)
Owner: Repository governance
Related: PR_AUDIT.md, BRANCH_AUDIT.md, CLEANUP_PLAN.md
---

# PR #21 / PR #22 Integration Report

Read-only analysis using `git diff`, `git merge-tree` (three-way merge
simulation), and `gh pr view/checks`. No merge, rebase, or push was performed.

## Diffstat

| PR | Branch | Commits | Files changed | Diff size |
|---|---|---|---|---|
| #21 | `codex/sys2-first-roadmap` | 1 (`3e6e0d1`) | 5 | +301 / −79 |
| #22 | `codex/demo-smoke-test` | 13 (latest `84731f1`) | 288 | +31,317 / −1,946 |

PR #22 is a large implementation PR (dashboard, execution engine, RBAC,
`svos/*`, extensive docs); PR #21 is a small, focused roadmap/doc amendment.

## Per-file overlap verdict

| File | Verdict | Evidence |
|---|---|---|
| `ARCHITECTURE_STABILIZATION_ROADMAP.md` | **NO CONFLICT** | Content at both branch tips is byte-identical vs `origin/main` — a diff between the two versions is empty |
| `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md` | **NO CONFLICT** | Same — identical final content on both branches |
| `docs/SYSTEM_ARCHITECTURE.md` | **NO CONFLICT** | Same |
| `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md` | **NO CONFLICT** | Same |
| `tests/production/test_system2_demo_readiness.py` | **REAL CONFLICT** | Both PRs add this as a brand-new file with divergent content (PR #21: 158 lines / 3 tests; PR #22: 127 lines / 2 tests) |

For the 4 "no conflict" files, both branches independently arrived at
identical text, so a merge auto-resolves with zero manual work.

## Merge-tree simulation (three-way merge, both directions)

`git merge-tree --write-tree --messages origin/codex/sys2-first-roadmap
origin/codex/demo-smoke-test` (and the reverse) both exit non-zero with:

```
CONFLICT (add/add): Merge conflict in tests/production/test_system2_demo_readiness.py
```

Conflict hunks:

```
<<<<<<< origin/codex/sys2-first-roadmap
from production.api import ProductionReadAPI
from shared.serialization import append_jsonl, write_json
=======
from shared.serialization import append_jsonl
>>>>>>> origin/codex/demo-smoke-test
from shared.strategy_package import build_canonical_package
```

and, near the end of the file:

```
<<<<<<< origin/codex/sys2-first-roadmap
def test_runtime_dashboard_status_is_read_only_and_package_scoped(tmp_path: Path) -> None:
    ... (uses ProductionReadAPI, write_json) ...
    assert "agtrade_broker_writes_enabled 0" in api.metrics()
=======
>>>>>>> origin/codex/demo-smoke-test
```

This is a genuine **add/add** conflict (both branches independently created
the same new test file with different content), not an artifact of merge
direction — confirmed symmetric in both simulated directions.

## CI status

| Check | PR #21 | PR #22 |
|---|---|---|
| CircleCI Pipeline | fail (no CircleCI config in repo — non-required check) | fail (same, non-required) |
| CodeRabbit | pass | pass |
| Documentation and package contracts | pass | pass |
| Quality and architecture | pass | pass |
| **Required CI** | **pass** | **pass** |
| Security and dependencies | pass | pass |
| Tests (integration) | pass | pass |
| Tests (unit) | pass | pass |

`gh pr view --json mergeable,mergeStateStatus`:
- PR #21: `MERGEABLE` / `UNSTABLE` (the only non-green check is the
  non-required CircleCI failure).
- PR #22: `MERGEABLE` / `BLOCKED` — has open, unresolved automated review
  comments (CodeRabbit/Codex bot flagged items, e.g. a dead optimistic-lock
  check noted in `svos/lifecycle/authority.py`) and no human `reviewDecision`
  yet on either PR.

Both PRs are CI-compatible (all required checks green); PR #22 additionally
has outstanding review comments to address before it should merge regardless
of PR #21.

## Recommended merge order: **PR #21 first, then PR #22**

Reasoning:
1. PR #21 is small (5 files, mostly docs + one self-contained test file) and
   easy to fully review — low risk to land first.
2. PR #22 already contains a superset of the shared work — its versions of
   the 4 non-conflicting shared files are identical to PR #21's, and it adds
   far more (dashboard, execution engine, RBAC). It is naturally the branch
   that "absorbs" the smaller one, not the reverse.
3. After PR #21 merges, PR #22 needs exactly **one** conflict resolved on
   rebase: `tests/production/test_system2_demo_readiness.py` (add/add). The
   other 4 shared files auto-merge cleanly since the content is identical.
   Resolution is mechanical: keep PR #22's two tests, re-add PR #21's third
   test (`test_runtime_dashboard_status_is_read_only_and_package_scoped`) and
   its `ProductionReadAPI` / `write_json` imports.
4. Merging in the reverse order (#22 then #21) hits the same single conflict
   on PR #21's side, but PR #21 is small enough that this is comparably easy
   either way — landing the smaller, fully-reviewable PR first is still the
   cleaner default, and keeps the larger PR #22 (still `BLOCKED` on review
   comments) from being the gating item for the roadmap doc update.

## What still needs to happen before either merges (not performed here)

- PR #22: resolve outstanding automated review comments (currently
  `BLOCKED`).
- Whichever PR merges second: resolve the single add/add conflict in
  `tests/production/test_system2_demo_readiness.py` as described above.
- Neither PR was merged, rebased, or pushed as part of this analysis.
