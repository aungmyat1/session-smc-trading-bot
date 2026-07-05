---
Date: 2026-07-05
Status: Investigation complete — informational, no push/reset performed
Scope: Local `main` branch in this checkout (`/home/aungp/session-smc-trading-bot`), 14 commits ahead of `origin/main`
Owner: Repository governance
Related: PR_AUDIT.md, BRANCH_AUDIT.md, CLEANUP_PLAN.md
---

# Local `main` Audit — 14 Unpushed Commits

This is a read-only investigation. No `git push`, `git reset`, or history change
was performed. Findings below are based on tree-identity checks (`git rev-parse
<sha>^{tree}`) and ancestry checks (`git merge-base --is-ancestor`) against
`origin/main` and `origin/codex/demo-smoke-test`.

## Headline finding

**None of the 14 commits represent commits at risk of loss, and none should be
pushed directly to `origin/main`.** Local `main`'s branch pointer was advanced
locally (almost certainly via a local `checkout main && merge
codex/demo-smoke-test`-style operation in a prior session) to match a point
partway through the `codex/demo-smoke-test` branch's history, but that
advance was never pushed to `origin/main`. All 14 commits are fully accounted
for by two already-known GitHub artifacts:

- **11 of the 14** are the exact content that PR #20 already squash-merged
  into `origin/main` (commit `71cb8e1`, "Complete disabled System 2 execution
  platform (#20)"). Tree-identity check: `c9203a1^{tree}` (the last of these
  11) is byte-identical to `71cb8e1^{tree}` on `origin/main`. These commits
  are **superseded** — their content already lives on `origin/main`, just
  under a different (squashed) SHA.
- **The remaining 3** are already pushed to `origin/codex/demo-smoke-test` and
  are part of the currently **open PR #22**. They are not missing or at risk;
  they're sitting in the normal PR-review pipeline.

Pushing local `main` straight to `origin/main` would (a) be redundant for the
first 11 (content already merged) and (b) for the last 3, would push
**unreviewed, not-yet-approved PR #22 content directly to `main`, bypassing
CI and review** — a governance violation, not just a hygiene issue. **Do not
push local `main` to `origin/main` under any circumstance until PR #22 is
reviewed and merged through the normal process.**

## Commit-by-commit classification

| # | SHA | Date (UTC) | Message | Classification | Evidence |
|---|---|---|---|---|---|
| 1 | `b5b5e2d` | 2026-07-02 22:51 | Document demo runtime integration readiness | **SUPERSEDED** | Part of the 11-commit run whose final tree (`c9203a1`) matches `origin/main`'s `71cb8e1` (PR #20, merged) |
| 2 | `e0cdab1` | 2026-07-02 22:52 | Begin demo smoke test sprint | **SUPERSEDED** | Same run |
| 3 | `81fa2ab` | 2026-07-02 22:57 | Add deterministic demo package smoke fixture | **SUPERSEDED** | Same run |
| 4 | `6306f59` | 2026-07-03 15:08 | Add AGENTS.md mirroring CLAUDE.md governing rules for non-Claude agents | **SUPERSEDED** | Same run |
| 5 | `5df1853` | 2026-07-03 15:31 | Merge branch 'main' into codex/demo-smoke-test | **SUPERSEDED** (merge commit, no unique content) | Same run |
| 6 | `4d2e84b` | 2026-07-03 16:27 | docs: record ADR-0002 through ADR-0004 implementation status | **SUPERSEDED** | Same run |
| 7 | `a11ae8a` | 2026-07-03 16:27 | test: verify canonical package and runtime handoff | **SUPERSEDED** | Same run |
| 8 | `959b27e` | 2026-07-03 16:28 | docs: add demo smoke test readiness report | **SUPERSEDED** | Same run |
| 9 | `e009d5f` | 2026-07-03 18:29 | Complete disabled System 2 execution platform | **SUPERSEDED** | Same run |
| 10 | `d8e0a59` | 2026-07-03 18:35 | Use static operations queries | **SUPERSEDED** | Same run |
| 11 | `c9203a1` | 2026-07-03 18:42 | Address execution safety review findings | **SUPERSEDED** | Tree-identical to `origin/main` HEAD `71cb8e1` — confirmed via `git rev-parse c9203a1^{tree}` == `git rev-parse 71cb8e1^{tree}` |
| 12 | `7fcf673` | 2026-07-04 20:16 | Stabilize System 2 execution platform and integrate live dashboard | **PR-TRACKED (do not push)** | Confirmed present on `origin/codex/demo-smoke-test`; part of open PR #22's diff |
| 13 | `e896b1c` | 2026-07-04 20:29 | Merge remote-tracking branch 'origin/main' into codex/demo-smoke-test | **PR-TRACKED (do not push)**, merge commit, no unique content | Same |
| 14 | `d8fdb88` | 2026-07-04 20:30 | Re-remove dead Production Platform v2 cluster resurrected by main merge | **PR-TRACKED (do not push)** — this is local `main`'s current tip | Confirmed present on `origin/codex/demo-smoke-test` |

None of the 14 fall into "Push to main" (would bypass review) or
"Experimental" (all are accounted-for, intentional work already tracked by a
merged or open PR) in isolation. "Move to another branch" is moot for
commits 12–14 — they are already on `origin/codex/demo-smoke-test`, pushed.

## Recommended resolution (no action taken — awaiting approval)

1. **Do nothing destructive.** No content is unique or at risk.
2. Once PR #22 merges through the normal process, local `main` will be
   trivially resynced: `git checkout main && git reset --hard origin/main`
   (safe at that point, since local `main`'s content will be a strict subset
   of what just landed) — **or**, if the owner prefers to preserve the exact
   local ref state until then, simply leave local `main` alone; it is not
   blocking anything and nothing will be lost either way.
3. Do **not** `git push origin main` from this checkout before PR #22 merges.
4. This finding does not change any PR_AUDIT.md or BRANCH_AUDIT.md
   recommendation — it only confirms the local `main` divergence is benign
   bookkeeping, not an unpushed-work risk.
