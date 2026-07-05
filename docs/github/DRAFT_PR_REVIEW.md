---
Date: 2026-07-05
Status: Investigation complete — no PR closed
Scope: PR #10 (claude/svos-production-readiness-ycpbcs) and PR #8 (claude/smc-trading-bot-readiness-ds636f), both stale open drafts
Owner: Repository governance
Related: PR_AUDIT.md, BRANCH_AUDIT.md, CLEANUP_PLAN.md
---

# Draft PR Review — #8 and #10

Read-only re-verification. **No PR was closed.**

## Correction to the prior (2026-07-05, earlier session) audit

The earlier PR_AUDIT.md stated `gh pr diff 10` "returns zero changed files."
That was a **misread of a failed command** — `gh pr diff 10` actually fails
with `HTTP 406: diff exceeded maximum number of files (300)`, and its empty
stdout on failure was mistaken for "no diff." The real three-dot diff
(merge-base → PR #10 head), retrieved via `gh api
repos/.../pulls/10/files --paginate`, is **627 files**, not zero. The
underlying conclusion (no unique work) still holds — see below — but it holds
for a different, verified reason, not the one previously stated.

## PR #10 — `claude/svos-production-readiness-ycpbcs`

**Verdict: CONFIRMED NO UNIQUE WORK.**

Of the 627 changed files: 603 exist on both branches but differ in content;
24 are net-new (docs, `replay_validation/`, extra `tests/svos/*.py`). Sampled
the largest and most functionally significant diffs:

- `svos/lifecycle/manager.py`: diff is pure black/isort reformatting — zero
  logic change.
- `svos/deployment/service.py`: **main has 628 lines** (full
  signing/GCS/KMS/artifact-publish implementation); PR #10 has **34 lines** (a
  stub "read-only view"). Main is materially ahead of this PR, not behind it.
- `svos/monitoring/service.py`: functionally equivalent; main's version is a
  refinement (structured incident dicts with severity levels) over PR #10's.
- Governance/orchestration/registry services PR #10 touches all already exist
  on `main` and are exercised by `tests/svos/test_platform.py`; PR #10's extra
  `tests/svos/test_*_service.py` files are unit-test scaffolding for
  capability `main` already covers via integration tests — not new capability.

Everywhere sampled, `main` is equal to or more advanced than PR #10.

**Recommendation: CLOSE.** No unmerged capability found; the ruff/black/isort
hardening pass and RC-hardening work this PR staged in 2026-06-30 has been
independently superseded by subsequent, more complete work on `main`.

## PR #8 — `claude/smc-trading-bot-readiness-ds636f`

**Verdict: NO GENUINELY UNIQUE CAPABILITY, with a caveat.**

226 files changed, still `CONFLICTING`/`DIRTY` against current `main`.
Breakdown: 88 files under `archive/` (repo-reorg noise), 35 `tests/`, 30
`session_smc/`, 28 `scripts/`. The substantive new functionality lives under
`session_smc/{governance,risk,execution,monitoring}/` — and those exact paths
**do not exist on `main`** (main's `session_smc/` only has SMC feature
detectors and an archived runbook). So this isn't a case of identical files
already landed; it's independently reinvented, later, elsewhere.

Capability-level comparison (not path-level):

| PR #8 module | Main's equivalent, later and more complete |
|---|---|
| `session_smc/governance/lifecycle.py` — a competing lifecycle FSM (`research_qualified → verification_ready → execution_qualified → risk_qualified → demo_approved → ... → production_live`) + `governance/registry.py` (JSON store at `data/strategy_registry.json`) | `svos/lifecycle/manager.py` — the canonical, CLAUDE.md §3-declared **sole mutation authority** for lifecycle state, plus `svos/registry/service.py` + `config/strategy_catalog.yaml` |
| `session_smc/risk/qualification.py` (RiskQualificationEngine, guard-scenario simulation) | `strategy_audit/risk.py` (RiskMetricsAuditModule), integrated into the `strategy_audit` pipeline |
| `session_smc/execution/qualification.py` (fill/reject/retry + VT Markets cost-model simulation) | `execution_validation/` package (`engine.py`, `rules.py`, `execution_simulator/broker/virtual_broker.py`), wired to `execution_gate.py` and release lineage — substantially larger |
| `session_smc/monitoring/{health,drift,alerts}.py` | `strategy_audit/monitoring.py` (StrategyDriftAuditModule) + `monitoring/telegram.py` (more mature: async aiohttp, markdown escaping, dedupe) + `svos/monitoring/service.py` |

No file in PR #8 represents a novel idea absent from `main`'s current design
space — every module has a later, independently-built, more mature
counterpart under a different path.

**Governance risk if merged as-is**: PR #8 would reintroduce a second
lifecycle FSM and a second JSON strategy registry running alongside the
canonical `svos/lifecycle/manager.py` — exactly the duplicate-orchestrator
problem CLAUDE.md §9 explicitly warns against ("does it duplicate an existing
module, pipeline, orchestrator, or config system? ... don't add a third").

**Recommendation: CLOSE**, with a one-line note in the closing comment
pointing to `svos/lifecycle/manager.py`, `strategy_audit/`,
`execution_validation/`, and `svos/monitoring/service.py` as the superseding
implementations, so the historical PR record stays traceable.

## Summary

| PR | Unique work found? | Recommendation |
|---|---|---|
| #10 | None | **CLOSE** |
| #8 | None (capability-level; paths differ but are superseded) | **CLOSE** |

No PR was closed as part of this review — both are ready for the owner to
close per CLEANUP_PLAN.md step 2.
