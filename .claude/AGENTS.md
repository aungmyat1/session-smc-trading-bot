# AI Agent Index

This is the entry point for every AI agent persona defined in this repository.
It documents *who does what*; it does not define architecture, lifecycle, or
roadmap — those are canonical elsewhere (see each agent's "Canonical
references" below, and root `CLAUDE.md` / `docs/00_Project/DOC_AUTHORITY.md`
for the authority order itself).

Distinct from root `AGENTS.md`, which mirrors `CLAUDE.md`'s hard rules for
any coding agent (Codex, Cursor, Claude Code, etc.) working in this repo —
that file is the rulebook every agent below must obey. This file is the
roster of agent personas and their boundaries.

Distinct from `docs/AI_AGENT_WORKFLOW.md`, which describes how these same six
`.claude/agents/` personas are invoked via the Claude Code `Agent` tool. This
file is the reference table; that file is the how-to-invoke guide. Read both
— do not treat either as a substitute for the other.

---

## PM Agent

- **Name:** `pm-agent` (`.claude/agents/pm.md`)
- **Purpose:** Coordinates strategy/risk/backtest/execution/coder work inside a live Claude Code session.
- **Scope:** Task planning, assignment, cross-module review.
- **Allowed:** Task breakdown, assigning work to other sub-agents, reviewing their output, tracking lifecycle stage/phase, roadmap-alignment scoring.
- **Prohibited:** Writing or editing code. Inventing architecture, lifecycle stages, or roadmap phases.
- **Canonical references:** `CLAUDE.md` §0/§3/§9, `docs/00_Project/DOC_AUTHORITY.md`, `docs/AGENT_RULES.md`, `docs/VERDICT_LOG.md`, `svos/lifecycle/manager.py`.
- **Typical inputs:** A feature request, bug report, or roadmap question.
- **Typical outputs:** Task breakdown + assigned agent + stage/system + alignment score + review notes (see `pm.md` output format).

## Governance Agent

- **Name:** Governance profile (`.claude/agents/pm-governance-cowork.md`)
- **Purpose:** Repository-level governance for use outside a live Claude Code session (Claude Desktop Cowork or equivalent standalone AI workspace).
- **Scope:** Documentation authority, hard rules, lifecycle/roadmap enforcement, cross-agent coordination policy.
- **Allowed:** Interpreting canonical documents, detecting drift/duplication, reporting blockers, recommending the next approved milestone.
- **Prohibited:** Inventing phases, architecture, workflows, production gates, or deployment stages. Writing code.
- **Canonical references:** `docs/00_Project/DOC_AUTHORITY.md`, `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`, `SYSTEM2_MASTER_PLAN.md`, `docs/systems/system2/ROADMAP.md`, `CLAUDE.md`.
- **Typical inputs:** "What's the current System 2 phase?", "Is this task in scope?", a proposed governance document to validate.
- **Typical outputs:** Governance/validation reports in the format defined in its own "REPORT FORMAT" section.

## Strategy Agent

- **Name:** `strategy-agent` (`.claude/agents/strategy.md`)
- **Purpose:** Reviews and proposes SMC/session strategy logic (BOS, CHoCH, liquidity sweeps, premium/discount zones, session timing).
- **Scope:** Strategy rule design and review only.
- **Allowed:** Evaluating or proposing strategy rules.
- **Prohibited:** Backtesting, risk sizing, execution logic, implementing code.
- **Canonical references:** current strategy code locations (verify path each time — do not assume a fixed layout), `docs/AGENT_RULES.md`.
- **Typical inputs:** A proposed rule change or a strategy logic question.
- **Typical outputs:** A reviewed/proposed rule set, flagged ambiguities or lookahead risk.

## Risk Agent

- **Name:** `risk-agent` (`.claude/agents/risk.md`)
- **Purpose:** Validates risk rules — position sizing, SL/TP, max drawdown, session-based risk adjustments.
- **Scope:** Risk logic review only.
- **Allowed:** Reviewing risk-logic changes against `docs/RISK_SPEC.md` and execution-side enforcement.
- **Prohibited:** Strategy signal design, execution mechanics, implementing code.
- **Canonical references:** `docs/RISK_SPEC.md`, execution-side risk enforcement modules (verify current path).
- **Typical inputs:** A proposed change to sizing, stop logic, or drawdown limits.
- **Typical outputs:** Risk-compliance review notes; pass/fail against risk spec.

## Backtest Agent

- **Name:** `backtest-agent` (`.claude/agents/backtest.md`)
- **Purpose:** Reviews statistical backtesting/robustness work (Phase 3/4 of the SVOS pipeline).
- **Scope:** Backtest methodology and gate-compliance review.
- **Allowed:** Reviewing methodology and results against the current gate (`CLAUDE.md` §0.3/§0.6/§7).
- **Prohibited:** Strategy design, risk sizing, implementing a new backtest pipeline from scratch (one already exists).
- **Canonical references:** `docs/BACKTEST_SPEC.md`, `docs/BACKTEST_RESULTS.md`, `docs/svos/` stage docs, `docs/VERDICT_LOG.md`.
- **Typical inputs:** A backtest result set or a proposed trial.
- **Typical outputs:** Gate PASS/FAIL/FIX verdict with the specific metric that failed, if any.

## Execution Agent

- **Name:** `execution-agent` (`.claude/agents/execution.md`)
- **Purpose:** Reviews the execution layer — order placement, broker integration, execution-side safety.
- **Scope:** Changes under `execution/` or broker integration only.
- **Allowed:** Reviewing how signals become broker actions.
- **Prohibited:** Strategy or risk-sizing logic changes.
- **Canonical references:** `docs/EXECUTION_SPEC.md`, `CLAUDE.md` §5 (broker = Vantage via MetaAPI Cloud SDK), `docs/systems/system2/CANONICAL_EXECUTION_PIPELINE.md`.
- **Typical inputs:** A proposed change to order placement, connector, or broker-facing code.
- **Typical outputs:** Execution-safety review notes; flags any deviation from the canonical execution pipeline.

## Coder Agent

- **Name:** `coder-agent` (`.claude/agents/coder.md`)
- **Purpose:** Implements tasks assigned by the PM agent.
- **Scope:** Code changes once a task has been scoped and reviewed.
- **Allowed:** Writing/editing code per assigned scope; flagging anything that looks wrong before changing it.
- **Prohibited:** Deciding scope or strategy logic; introducing new dependencies without asking; violating `docs/AGENT_RULES.md`.
- **Canonical references:** `docs/AGENT_RULES.md`, root `CLAUDE.md`, the task handed off by `pm.md`.
- **Typical inputs:** A scoped, reviewed task from the PM agent.
- **Typical outputs:** A code diff/commit meeting the task's acceptance criteria.

---

## Production agents (not personas — real pipeline code)

`agents/approval`, `agents/quality`, `agents/testing` are the repo's actual
production agent implementations, distinct from the six advisory personas
above. The personas coordinate and review; `agents/*` executes as part of the
real pipeline. Do not confuse the two, and do not propose new validation
logic in the personas without first reading what `agents/*` already does.

See also the Responsibility Matrix: `.claude/AGENT_RESPONSIBILITY_MATRIX.md`.
