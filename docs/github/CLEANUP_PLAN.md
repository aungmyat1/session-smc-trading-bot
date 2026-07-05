---
Date: 2026-07-05
Status: Proposed — awaiting owner confirmation; no step below has been executed
Scope: Recommended cleanup actions arising from PR_AUDIT.md and BRANCH_AUDIT.md
Owner: Repository governance
Related: PR_AUDIT.md, BRANCH_AUDIT.md
---

# GitHub Cleanup Plan

This is a **proposal only**. Per the audit constraints, nothing here has been
executed — no branch deleted, no PR closed, no history rewritten, no force
push, no production code changed. The owner (or an explicitly-instructed
follow-up session) chooses which rows to execute and when.

## Guardrails carried into every step below

- No `--force`/`--force-with-lease` pushes.
- No rewriting of merged PR history.
- No production code touched — every action here is PR/branch metadata or
  local git housekeeping.
- Every "DELETE BRANCH" below is on a branch already confirmed (in
  BRANCH_AUDIT.md) to have zero unique, unlanded content.

## Recommended order

Ordered to resolve sequencing risk first (roadmap-doc overlap), then close out
stale/superseded work, then automated bumps, then pure housekeeping.

### 1. Resolve the PR #21 / #22 sequencing risk (do first, before anything else merges)

Both are legitimate, active, currently-mergeable PRs that touch the same 5
roadmap/doc/test files. Recommended sequence:
1. Merge whichever is closer to done first (owner's call — #21 is a smaller,
   5-file doc/roadmap PR; #22 is a 136-file implementation PR).
2. Immediately after, rebase the other PR's branch on the new `main` and
   resolve any conflicts in `ARCHITECTURE_STABILIZATION_ROADMAP.md`,
   `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`, `docs/SYSTEM_ARCHITECTURE.md`,
   `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`, and
   `tests/production/test_system2_demo_readiness.py` before merging it.
3. No action needed if the owner instead decides to merge only one and close
   the other as redundant — but PR_AUDIT.md found no evidence they are
   redundant (roadmap doc vs. implementation), so this plan defaults to
   merging both.

### 2. Close superseded stale drafts

| PR | Action | Pre-condition |
|---|---|---|
| #10 | `CLOSE` | Zero net file diff vs `main` already confirmed; safe to close without review |
| #8 | `CLOSE` | Recommend one human skim first (226 files, real conflicts) to confirm nothing unique before closing |

### 3. Review and merge/close automated dependency bumps

PRs #12–#16 (Dependabot, all → `develop`). All show a mixed `FAILURE`/`SUCCESS`
check set. Before merging any of them:
1. Open one representative failing job (e.g. PR #16's `Testing Agent` / `test`
   jobs) and confirm the failure is pre-existing on `develop` / unrelated to
   the version bump, not caused by it.
2. If confirmed pre-existing: `MERGE` all five (they're independent action
   version bumps, low risk).
3. If any failure is caused by the bump itself: `NEEDS REVIEW` that one PR
   specifically, merge the rest.
4. Separately (process fix, not a PR action): sync `develop` with `main`
   (currently 5 commits behind) so future Dependabot PRs aren't based on stale
   `develop`, or repoint `dependabot.yml`'s `target-branch` at `main` if
   `develop` is no longer the intended integration branch.

### 4. Delete branches with content already on `main` (GitHub, after their PRs are closed/merged)

| Branch | Wait for |
|---|---|
| `codex/project-readiness-v1` | Already merged (#19) — delete now |
| `codex/original-truth` | Already merged (#17) — delete now |
| `codex/sys2-first-roadmap` | Delete after PR #21 merges (step 1) |
| `claude/svos-production-readiness-ycpbcs` | Delete after PR #10 is closed (step 2) |
| `claude/smc-trading-bot-readiness-ds636f` | Delete after PR #8 is closed (step 2) |

`architecture/separate-svos-production` (#11) and
`claude/project-review-latest-changes-0hp3ui` (#7) are already deleted on
`origin` by GitHub's auto-delete-on-merge — no GitHub action needed for these
two.

### 5. Delete the orphan branch

`circleci-project-setup` — no PR, no salvageable content (would delete ~209
files if ever opened as a PR). Delete on `origin`.

### 6. Local git housekeeping (this checkout only — no GitHub API calls)

```
git worktree remove /tmp/session-smc-pr7
git branch -D pr-7
git branch -D architecture/separate-svos-production
git branch -D codex/local-main-pre-sync-20260702-1508
# after step 4 confirms the remote branches are gone:
git branch -D codex/original-truth
git branch -D codex/project-readiness-v1
```
Also resolve the local-`main`-ahead-of-`origin/main`-by-14-commits anomaly
(BRANCH_AUDIT.md) — confirm intent, then `git push origin main` or reset local
`main` to `origin/main`, whichever matches what the owner actually wants on
`origin`.

## What this plan deliberately does NOT touch

- `main`, `develop` (kept — still wired into CI/Dependabot).
- Any merged PR's history (#1–#7, #9, #11, #17–#20).
- Any production code, config, or `.env`.
