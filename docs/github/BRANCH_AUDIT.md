---
Date: 2026-07-05
Status: Audit — informational, no destructive actions taken
Scope: All local branches/worktrees in this checkout + all branches on `origin`
Owner: Repository governance
Related: PR_AUDIT.md, CLEANUP_PLAN.md
---

# Branch Audit

Read-only audit. No branch was deleted, renamed, or force-pushed in producing
this report. "Merged" is determined from the GitHub PR's `mergedAt` field, not
from `git merge-base --is-ancestor`, because this repo's merged PRs are
squash-merged — the original branch SHA is never a literal ancestor of `main`
even though its content has landed.

## Anomaly found first (not a branch-cleanup item, flagging for awareness)

Local `main` (`d8fdb88`) is **14 commits ahead of `origin/main`** in this
checkout — i.e. there are local-only commits on `main` that were never pushed.
Cross-referencing the messages, these are the same commits already present on
`codex/demo-smoke-test` (this checkout's current branch), so no work is at risk
of loss, but local `main` and `origin/main` have diverged. No action taken;
flagged for the owner — recommend `git push origin main` (or resetting local
`main` to track `origin/main`) once confirmed intentional. This is a local-repo
hygiene issue, not a GitHub artifact, so it does not appear in the cleanup plan.

## Branches on `origin` (GitHub)

| Branch | Last commit | Associated PR | Merged? | Unique vs `main` | Category | Recommendation |
|---|---|---|---|---|---|---|
| `main` | 2026-07-03 | — | — | — | Default/protected | KEEP |
| `develop` | 2026-07-01 | — | — | 0 ahead / 5 behind `main` | Fully contained in `main`; CI target for `develop`-scoped triggers and Dependabot base branch | **NEEDS REVIEW** — not an orphan (still wired into `.github/workflows/ci.yml` and `.github/dependabot.yml` `target-branch: develop`), but it is stale relative to `main` by 5 commits. Recommend the owner periodically fast-forward/merge `main` → `develop` (or repoint Dependabot at `main`) so dependency-bump PRs aren't based on a lagging branch. No deletion recommended. |
| `codex/demo-smoke-test` | 2026-07-05 | #20 (merged), #22 (open) | Partially (see PR audit) | 16 ahead / 0 behind | Active | KEEP — actively developed, PR #22 open |
| `codex/sys2-first-roadmap` | 2026-07-03 | #21 (open) | No | 1 ahead / 0 behind | Active | KEEP until #21 merges, then DELETE BRANCH |
| `codex/project-readiness-v1` | 2026-07-02 | #19 (merged) | Yes | 5 ahead / 2 behind (squash merge, so not a git ancestor) | Merged, content landed | **DELETE BRANCH** |
| `codex/original-truth` | 2026-07-02 | #17 (merged) | Yes | 3 ahead / 4 behind (squash merge) | Merged, content landed | **DELETE BRANCH** |
| `architecture/separate-svos-production` | 2026-07-02 | #11 (merged) | Yes | — | Merged; **remote already deleted by GitHub** | N/A on GitHub — see local-only leftover below |
| `circleci-project-setup` | 2026-07-03 | none | No | 1 ahead / 1 behind, but diff vs `main` touches 209 files / −29,478 lines (near-total repo deletion) | **Orphan branch** — auto-created by the CircleCI GitHub App's "Set Up Project" flow from a very old repo snapshot; no PR was ever opened against it | **DELETE BRANCH** — has no salvageable content; opening a PR from it would attempt to delete almost the entire current repo |
| `dependabot/github_actions/develop/actions/upload-artifact-7` | 2026-07-02 | #16 (open) | No | — | Automated | See PR_AUDIT #16 — NEEDS REVIEW, then MERGE or DELETE BRANCH (GitHub auto-deletes on merge/close) |
| `dependabot/github_actions/develop/actions/checkout-7` | 2026-07-02 | #15 (open) | No | — | Automated | Same as above (#15) |
| `dependabot/github_actions/develop/github/codeql-action-4` | 2026-07-02 | #14 (open) | No | — | Automated | Same as above (#14) |
| `dependabot/github_actions/develop/dorny/test-reporter-3` | 2026-07-02 | #13 (open) | No | — | Automated | Same as above (#13) |
| `dependabot/github_actions/develop/actions/setup-python-6` | 2026-07-02 | #12 (open) | No | — | Automated | Same as above (#12) |
| `claude/svos-production-readiness-ycpbcs` | 2026-06-30 | #10 (draft, open) | No | 8 ahead / 29 behind | Stale draft, `CONFLICTING`, zero net diff vs `main` | **DELETE BRANCH** after PR #10 is closed |
| `claude/smc-trading-bot-readiness-ds636f` | 2026-06-28 | #8 (draft, open) | No | 3 ahead / 49 behind | Stale draft, `CONFLICTING` | **DELETE BRANCH** after PR #8 is closed (pending human skim, see PR_AUDIT) |

Branches referenced by earlier, already-merged PRs (#1–#7, #9, #18) are **not
present on `origin`** — GitHub already auto-deleted them on merge. No action
needed.

## Local-only branches / worktrees in this checkout

These exist only in this local clone (not on `origin`) and are separate from
the GitHub cleanup surface, but are included per the "audit every local
branch" requirement:

| Local branch | Worktree | Tracks | Status | Recommendation |
|---|---|---|---|---|
| `architecture/separate-svos-production` | — | `origin/...` (gone — remote deleted after merge) | Stale leftover from merged PR #11 | **DELETE (local)** — safe, content is on `main` |
| `pr-7` | `/tmp/session-smc-pr7` | `origin/claude/project-review-latest-changes-0hp3ui` (gone — remote deleted after merge) | Stale leftover worktree from merged PR #7 | **DELETE (local)** — run `git worktree remove /tmp/session-smc-pr7` then delete the branch; safe, content is on `main` |
| `codex/local-main-pre-sync-20260702-1508` | — | none (never pushed) | Manual pre-merge snapshot dated 2026-07-02; diff vs current `main` touches 297 files / −36,856 lines — fully superseded. Its two unique commits ("Implement unified dashboard operations center", "Fix PR review blockers for proxy CSRF and broker gating") match content that landed via PR #18/#19 under different (squashed) SHAs; orphan snapshot, no PR, no remote | **DELETE (local)** |
| `codex/sys2-first-roadmap` | `/tmp/session-smc-sys2-roadmap` | `origin/codex/sys2-first-roadmap` (active, PR #21 open) | Active | KEEP until PR #21 merges |
| `codex/demo-smoke-test` | (this checkout) | `origin/codex/demo-smoke-test`, ahead 2 | Active (current branch) | KEEP |
| `codex/original-truth` | — | `origin/codex/original-truth` | Merged via PR #17 | DELETE (local) once remote is deleted |
| `codex/project-readiness-v1` | — | `origin/codex/project-readiness-v1` | Merged via PR #19 | DELETE (local) once remote is deleted |
| `main` | (implicit) | `origin/main`, ahead 14 (see anomaly above) | Diverged, unpushed | Push or resync — not a deletion candidate |

## Detection summary (requirement §3)

- **Duplicate PRs**: none.
- **Superseded PRs**: #8, #10 (see PR_AUDIT.md).
- **Abandoned branches**: `circleci-project-setup` (no PR, orphan snapshot),
  `codex/local-main-pre-sync-20260702-1508` (local-only, superseded snapshot).
- **Stale draft PRs**: #8, #10.
- **Branches already merged** (safe to delete): `architecture/separate-svos-production`
  (remote already gone; local leftover remains), `codex/original-truth`,
  `codex/project-readiness-v1`, and — once #21 merges —
  `codex/sys2-first-roadmap`.
- **Branches with no unique commits relative to `main`**: `develop` (0 ahead),
  and effectively PR #10's branch (0-file net diff, though technically 8
  commits ahead by SHA due to the conflict/rebase state).
- **Orphan branches**: `circleci-project-setup`.

## Verification (requirement §4)

- **No active implementation depends on any branch marked for deletion.**
  Checked: `.github/workflows/*.yml` only reference `main`/`develop` and glob
  patterns (`feature/**`, `hotfix/**`, `release/**`) — no hardcoded reference to
  any specific branch slated for deletion. `.github/dependabot.yml` references
  `develop` only (kept). No script or config in the repo references
  `session-smc-pr7`, `session-smc-sys2-roadmap`, or any of the other
  branch names verbatim. **Confirmed clear.**
- **No open PR conflicts with the current architecture roadmap.** PR #21 and
  #22 both touch `ARCHITECTURE_STABILIZATION_ROADMAP.md` and related roadmap
  docs — not a content conflict today (both `MERGEABLE` against `main`
  individually) but a **sequencing** concern: merge one, then rebase the other.
  See CLEANUP_PLAN.md. No other open PR touches roadmap docs.
- **No documentation references deleted branches.** `docs/migration/baseline.md`
  and `docs/migration/database_inventory.md` name
  `architecture/separate-svos-production` as the historical migration branch —
  this is accurate historical record of a merged PR, not a live dependency, and
  needs no edit. No other doc references any branch recommended for deletion.
