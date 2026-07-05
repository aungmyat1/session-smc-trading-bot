---
Date: 2026-07-05
Status: No open Dependabot PRs to act on — plan for when they reappear
Scope: Dependency maintenance (GitHub Actions + pip, per .github/dependabot.yml)
Owner: Repository governance
Related: docs/github/DEPENDABOT_REVIEW.md, docs/audit/CI_CD_HEALTH_REPORT.md
---

# Dependency Update Plan

## Current state: nothing open

All 5 Dependabot PRs that existed at the start of this stabilization pass (#12–16, GitHub Actions version bumps against `develop`) were **manually closed by the repo owner** (`aungmyat1`) on 2026-07-05T10:32:27Z — confirmed via the GitHub issue timeline (`event: closed`, `actor: aungmyat1`), not an automated or Dependabot-initiated closure. Dependabot's own follow-up comment on each ("I won't notify you again about this release... reopen if you change your mind") confirms this was a deliberate manual action, not a bug or a side effect of this session's work. There is nothing to review, run tests against, or merge right now.

## What was already established about these 5 (docs/github/DEPENDABOT_REVIEW.md, still valid if reopened)

All 5 were security-labeled, single-line version-string bumps (`actions/checkout` 4→7, `actions/setup-python` 5→6, `actions/upload-artifact` 4→7, `github/codeql-action` 3→4, `dorny/test-reporter` 1→3) with no breaking API/input changes for this repo's usage — the only common thread across release notes was the GitHub-hosted-runner Node 20→24 migration, handled transparently. Their CI failures were entirely pre-existing on `develop` itself (missing `pyyaml`, 3 collection errors — see `docs/audit/CI_CD_HEALTH_REPORT.md`), not caused by the bumps.

## Plan for when they reappear

Dependabot will regenerate these PRs on its next scheduled run (weekly, per `.github/dependabot.yml`) unless the repo owner explicitly told it to stop via an `ignore` comment (the timeline shows no such comment — only the standard "won't notify again for *this* release" default, which still allows a future version bump to open a new PR).

1. **Fix `develop`'s CI first** (see `docs/audit/CI_CD_HEALTH_REPORT.md`) — add the missing `pyyaml` install step and resolve the `smartmoneyconcepts`/`fastapi` lock-file gaps causing the 3 collection errors. Merging dependency PRs against a base branch with pre-existing red checks makes it impossible to tell a real regression from known noise.
2. **Re-verify no breaking change** at merge time — release notes can change between now and whenever Dependabot reopens these; don't assume the prior review still holds verbatim, re-check in ~30 seconds via `gh pr diff <n>` (single-line version bumps are easy to re-confirm).
3. **Merge individually**, not as a batch — each is an independent action-version bump; a batch merge makes it harder to bisect if one specific bump does cause a CI regression.
4. **After merging all 5 (or whichever reappear):** consider whether `develop` should remain the Dependabot target branch at all, given it's now confirmed to be a different pipeline generation from `main` (see CI/CD Health Report) — either keep `develop` current going forward or repoint `dependabot.yml`'s `target-branch` at `main`.

## pip ecosystem

`.github/dependabot.yml` also configures weekly `pip` scans against `develop` — no open PRs from that ecosystem existed at the time of this audit. Same guidance applies: fix `develop`'s CI before merging anything from it, since a red base branch makes any pip-bump PR's own CI result unreadable.
