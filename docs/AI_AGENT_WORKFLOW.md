---
Status: Authoritative (for agent-role definitions only — not architecture)
Version: 1.0
Updated: 2026-07-06
Owner: Platform Architecture
Authority: Level 7 — Module documentation (per docs/00_Project/DOC_AUTHORITY.md)
Related: docs/AGENT_RULES.md, docs/00_Project/DOC_AUTHORITY.md, CLAUDE.md
---

# AI Agent Workflow

This document describes the reviewer/planner sub-agents defined under
`.claude/agents/` (`pm`, `strategy`, `risk`, `backtest`, `execution`, `coder`).
It does **not** define a new lifecycle, phase taxonomy, or architecture claim —
for those, see root `CLAUDE.md` §2/§3 and `docs/00_Project/DOC_AUTHORITY.md`.

## What these agents are

Prompt-level personas for the Claude Code `Agent` tool, used to parallelize
review across strategy, risk, backtest, and execution concerns before the
coder agent implements a change. They are advisory/planning roles, not new
code.

They are distinct from — and must not duplicate — the repo's real production
agent implementations already in `agents/` (`agents/approval`, `agents/quality`,
`agents/testing`), which run as part of the actual pipeline. The `.claude/agents/`
personas coordinate and review; `agents/*` executes.

## Lifecycle reference (do not re-derive elsewhere)

Use the canonical SVOS lifecycle only:
`DRAFT → INTAKE → AUDIT → REFINEMENT → HISTORICAL_REPLAY → STATISTICAL_VALIDATION
→ ROBUSTNESS_VALIDATION → VERIFICATION_READY → VIRTUAL_DEMO → EXECUTION_VALIDATION
→ PAPER_TRADING → LIVE_DEMO → PRODUCTION_CANDIDATE → PRODUCTION → MONITORING
→ REVALIDATION → RETIRED` (`svos/lifecycle/manager.py` is the sole mutation authority).

Current implementation ceiling: VIRTUAL_DEMO. No agent above may plan or build
toward PRODUCTION.

## How to use

Invoke via the `Agent` tool with `subagent_type` set to `pm-agent`,
`strategy-agent`, `risk-agent`, `backtest-agent`, `execution-agent`, or
`coder-agent`. Route non-trivial tasks through `pm-agent` first; it assigns
work to the others and reviews their output before anything is implemented.

## End-to-end task workflow

The standard path a non-trivial task follows through the agent ecosystem
above (see `.claude/AGENTS.md` for per-agent scope, `.claude/AGENT_RESPONSIBILITY_MATRIX.md`
for ownership boundaries). This describes coordination order only — it does
not redefine the SVOS lifecycle or the System 2 roadmap referenced above.

1. **Bootstrap** — start from repo root; nothing here overrides `CLAUDE.md`.
2. **Load authoritative documents** — `CLAUDE.md`, `docs/00_Project/DOC_AUTHORITY.md`,
   `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`, `docs/AGENT_RULES.md`,
   `docs/VERDICT_LOG.md`.
3. **PM analyzes** — `pm-agent` (or, outside a live session, the
   `pm-governance-cowork.md` governance profile) determines which system/stage
   owns the task and checks for duplication per `.claude/agents/pm.md`
   "Before assigning any task."
4. **PM generates backlog** — prioritized, scoped to the current canonical
   phase (System 1 enum or System 2's `SYSTEM2_MASTER_PLAN.md` phase).
5. **PM assigns implementation** — routes to the matching domain agent
   (`strategy-agent` / `risk-agent` / `backtest-agent` / `execution-agent`)
   for review, then to `coder-agent` for implementation.
6. **Coder implements** — per the assigned, reviewed scope only; flags
   anything that looks wrong before changing it.
7. **Reviewer validates** — the domain agent that owns the touched area
   reviews the diff against its own scope (see the matrix's "Reviews" column).
8. **Documentation updated** — as part of the same task, not a separate pass;
   the domain reviewer checks this before sign-off.
9. **Tests pass** — `coder-agent` writes/runs tests for the task; `backtest-agent`
   separately checks gate compliance if the change touches backtest/robustness
   results.
10. **Merge** — a human/operator action; no agent above merges or deploys
    (see the matrix's "Deployment" column and `CLAUDE.md` §4 CONFIRM tokens).
