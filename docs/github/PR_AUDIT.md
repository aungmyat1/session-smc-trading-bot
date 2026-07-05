---
Date: 2026-07-05
Status: Audit — informational, no destructive actions taken
Scope: All 22 pull requests on `aungmyat1/session-smc-trading-bot` (read-only audit)
Owner: Repository governance
Related: BRANCH_AUDIT.md, CLEANUP_PLAN.md
---

# GitHub Pull Request Audit

Read-only audit of every PR (open, merged, draft) as of 2026-07-05. No PRs were
closed, merged, or modified in producing this report. Recommendations only —
see `CLEANUP_PLAN.md` for the proposed execution order.

## Legend

- **Superseded**: a later PR/commit on `main` independently delivers the same
  or greater scope, making this PR's unique value ~0.
- Recommendation values: `KEEP` (leave as-is) · `CLOSE` (no code action, close
  PR only) · `ARCHIVE` (documentation retained, branch/PR closed) ·
  `DELETE BRANCH` · `MERGE` · `NEEDS REVIEW` (human judgment required before
  acting).

## Table

| # | Title (from PR) | State | Branch → Base | Created | Last update | Purpose | Superseded? | Recommendation |
|---|---|---|---|---|---|---|---|---|
| 22 | Restart recovery, canonical execution pipeline, Postgres ops recording, VPS stabilization, dashboard integration (System 2 demo) | OPEN | `codex/demo-smoke-test` → `main` | 2026-07-04 | 2026-07-05 | Active in-flight hardening of the System 2 demo execution stack; CI green, mergeable | No | **KEEP** (active work; merge when ready) |
| 21 | Prioritize System 2 stabilization roadmap (first delivery gate) | OPEN | `codex/sys2-first-roadmap` → `main` | 2026-07-03 | 2026-07-03 | Roadmap/doc amendment making System 2 demo readiness the explicit first gate | No | **KEEP** — touches 5 files, 4 of which overlap with PR #22's file set (`ARCHITECTURE_STABILIZATION_ROADMAP.md`, `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`, `tests/production/test_system2_demo_readiness.py`). Both are individually mergeable now, but whichever merges **second** will need a rebase. See CLEANUP_PLAN §sequencing. |
| 20 | Consolidate canonical System 2 production runtime, signed packages, fail-closed risk/order/position services | MERGED (2026-07-03) | `codex/demo-smoke-test` → `main` | 2026-07-02 | 2026-07-03 | Predecessor sprint on the same branch, later reused for PR #22 | N/A (merged) | **KEEP** (merged history) — branch was reused for #22, not stale |
| 19 | Strategy intake, deterministic historical replay, signed approval packages, demo readiness gates | MERGED (2026-07-02) | `codex/project-readiness-v1` → `main` | 2026-07-02 | 2026-07-02 | Delivered | N/A (merged) | **KEEP** (merged history) / **DELETE BRANCH** (fully landed, no unique commits remain to preserve) |
| 18 | Unified dashboard operations center (six-surface dashboard) | MERGED (2026-07-02) | `codex/unified-dashboard-operations-center` → `main` | 2026-07-02 | 2026-07-02 | Delivered | N/A (merged) | **KEEP** (merged history); remote branch already auto-deleted by GitHub |
| 17 | Record owner's original two-system architecture as canonical truth | MERGED (2026-07-02) | `codex/original-truth` → `main` | 2026-07-02 | 2026-07-02 | Delivered | N/A (merged) | **KEEP** (merged history) / **DELETE BRANCH** |
| 16 | Bump `actions/upload-artifact` 4→7 | OPEN | `dependabot/.../upload-artifact-7` → `develop` | 2026-07-02 | 2026-07-02 | Automated dependency bump | No | **NEEDS REVIEW** — CI shows a mix of `FAILURE`/`SUCCESS` checks (Docs Lint, Testing Agent, `test` jobs fail); failures look pre-existing/repo-wide rather than caused by this bump, but must be confirmed before merge. Also see BRANCH_AUDIT.md note on `develop` being 5 commits behind `main`. |
| 15 | Bump `actions/checkout` 4→7 | OPEN | `dependabot/.../checkout-7` → `develop` | 2026-07-02 | 2026-07-02 | Automated dependency bump | No | **NEEDS REVIEW** (same CI-failure caveat as #16) |
| 14 | Bump `github/codeql-action` 3→4 | OPEN | `dependabot/.../codeql-action-4` → `develop` | 2026-07-02 | 2026-07-02 | Automated dependency bump | No | **NEEDS REVIEW** (same caveat) |
| 13 | Bump `dorny/test-reporter` 1→3 | OPEN | `dependabot/.../test-reporter-3` → `develop` | 2026-07-02 | 2026-07-02 | Automated dependency bump | No | **NEEDS REVIEW** (same caveat) |
| 12 | Bump `actions/setup-python` 5→6 | OPEN | `dependabot/.../setup-python-6` → `develop` | 2026-07-02 | 2026-07-02 | Automated dependency bump | No | **NEEDS REVIEW** (same caveat) |
| 11 | Separate Production Trading Engine and SVOS platform (signed packages, registry history) | MERGED (2026-07-02) | `architecture/separate-svos-production` → `main` | 2026-07-01 | 2026-07-02 | Delivered | N/A (merged) | **KEEP** (merged history) / **DELETE BRANCH** — remote already gone; a stale local copy remains (see BRANCH_AUDIT.md). Referenced by name in `docs/migration/baseline.md` and `docs/migration/database_inventory.md` as a historical migration-record pointer — those references are accurate history, not a functional dependency, and need no edit. |
| 10 | Ruff/black/isort across 128 files; SVOS Release Candidate v1.0 hardening (9 phases) | **DRAFT, OPEN** | `claude/svos-production-readiness-ycpbcs` → `main` | 2026-06-30 | 2026-06-30 (5 days stale) | Code-quality/RC hardening pass | **Likely yes** | **CLOSE** — `gh pr diff 10` now returns **zero changed files** against current `main` and GitHub reports `mergeStateStatus: DIRTY` / `mergeable: CONFLICTING`. The formatting/hardening work this PR staged has no remaining net diff — its value has already been absorbed or overtaken by later commits (e.g. `84731f1 Fix CI failures: ruff unused imports...`). Recommend closing with a comment pointing to the superseding work; do not merge as-is (conflicting, empty diff). |
| 9 | Consolidate governance/lifecycle stabilization roadmap; fail-closed legacy mutation; bearer-auth dashboard mutations | MERGED (2026-06-29) | `codex/stabilize-governance-persistence` → `main` | 2026-06-29 | 2026-06-29 | Delivered | N/A (merged) | **KEEP** (merged history); branch already cleaned up (not present locally or remotely) |
| 8 | Add governance/risk-qualification/execution-qualification/monitoring layers on top of existing SVOS | **DRAFT, OPEN** | `claude/smc-trading-bot-readiness-ds636f` → `main` | 2026-06-28 | 2026-06-28 (7 days stale) | Governance/qualification layer proposal | **Likely yes** | **CLOSE** — predates and overlaps with PR #9 (governance/lifecycle stabilization, merged 2026-06-29), PR #11 (architecture separation, merged), and PR #19/#20/#22 (readiness + canonical execution, merged/in-flight). GitHub reports `mergeStateStatus: DIRTY` / `mergeable: CONFLICTING` against current `main` (226 files, real conflicts). Recommend a human skim for any not-yet-landed idea before closing, then close. |
| 7 | Fix `.env.example` typo; make SVOS/EVF subprocess timeout configurable; dashboard status indicator fix | MERGED (2026-06-28) | `claude/project-review-latest-changes-0hp3ui` → `main` | 2026-06-28 | 2026-06-28 | Delivered | N/A (merged) | **KEEP** (merged history) / **DELETE BRANCH** — remote already gone; a stale local worktree branch `pr-7` remains checked out at `/tmp/session-smc-pr7` (see BRANCH_AUDIT.md) |
| 6 | Add `dashboard/app.py` Flask API + `dashboard/index.html` control panel | MERGED (2026-06-27) | `claude/svos-evf-dashboard-panels-btnxch` → `main` | 2026-06-27 | 2026-06-28 | Delivered | N/A (merged) | **KEEP** (merged history); branch already cleaned up |
| 5 | Research execution engine foundation (features, signals, replay, research DB) | MERGED (2026-06-27) | `feature/research-execution-engine` → `main` | 2026-06-27 | 2026-06-27 | Delivered | N/A (merged) | **KEEP** (merged history); branch already cleaned up |
| 4 | Strategy audit docs updated for split workstreams | MERGED (2026-06-27) | `docs/strategy-audit-updates` → `main` | 2026-06-27 | 2026-06-27 | Delivered | N/A (merged) | **KEEP** (merged history); branch already cleaned up |
| 3 | Adaptive/demo trading stack — XAUUSD, VWAP mean reversion, health checks | MERGED (2026-06-27) | `review/live-adaptive-stack` → `main` | 2026-06-27 | 2026-06-27 | Delivered | N/A (merged) | **KEEP** (merged history); branch already cleaned up |
| 2 | Strategy Validation Operating System (SVOS) orchestration layer + audit engine | MERGED (2026-06-27) | `codex/svos-stage-gate` → `main` | 2026-06-27 | 2026-06-28 | Delivered | N/A (merged) | **KEEP** (merged history); branch already cleaned up |
| 1 | Wire archive prototype to `session_smc/` signal chain; add `pipeline/` deterministic Phase-0 backtest | MERGED (2026-06-26) | `claude/database-architecture-explanation-0kz3cd` → `main` | 2026-06-26 | 2026-06-28 | Delivered | N/A (merged) | **KEEP** (merged history); branch already cleaned up |

## Notes on detection criteria (requirement §3)

- **Duplicate PRs**: none found. No two open/draft PRs target the same feature with
  identical scope. PR #21 and #22 overlap on files but are complementary (roadmap
  doc vs. implementation), not duplicates.
- **Superseded PRs**: #8 and #10 — both stale drafts pre-dating governance/readiness
  work that has since merged (#9, #11, #19, #20/#22), both now `CONFLICTING`
  against `main`, #10 has a zero-file net diff.
- **Stale draft PRs**: #8 (7 days, no update since open) and #10 (5 days, no update
  since open) — see above.
- **Abandoned branches**: none of the currently-open PR branches show >7 days with
  zero commit activity beyond #8/#10 already covered.
