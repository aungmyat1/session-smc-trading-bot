# Agent Directory

Status: Index only — consolidates what already exists in `.claude/agents/`
into one browsable table. Adds no new policy; each row links to its
authoritative source file, which remains the source of truth. See
`docs/governance/GOVERNANCE-GAP-ANALYSIS.md` for why this is an index and
not a rebuild.

| Agent | Purpose | Owned scope | Tools | Allowed | Forbidden |
|---|---|---|---|---|---|
| [`pm`](../../.claude/agents/pm.md) | Interactive planning, task orchestration, cross-module review, coordinates the 5 specialist agents below | Whole repo (coordination only) | Read, Grep, Glob, Bash | Plan, assign, review, approve | Never writes production code itself |
| [`pm-governance-cowork`](../../.claude/agents/pm-governance-cowork.md) | Governance policy layer for standalone/cowork sessions — hard rules, doc-authority order, lifecycle enforcement | Whole repo (policy only) | N/A (policy doc, not an invokable agent) | Interpret and enforce existing canon | Never invents phases, architecture, workflows, or gates |
| [`strategy-agent`](../../.claude/agents/strategy.md) | Reviews/proposes SMC/session strategy logic (BOS, CHoCH, liquidity sweeps, premium/discount zones, session timing) | Strategy design | Read, Grep, Glob | Evaluate/design strategy rules | Backtesting, risk sizing, execution |
| [`risk-agent`](../../.claude/agents/risk.md) | Validates risk rules — position sizing, SL/TP, max drawdown, session-based risk adjustments | Risk logic | Read, Grep, Glob | Review risk logic changes | Strategy design, execution mechanics |
| [`backtest-agent`](../../.claude/agents/backtest.md) | Reviews/validates statistical backtesting/robustness work (SVOS Phase 3/4) | Backtest methodology, gate compliance | Read, Grep, Glob, Bash | Review backtest results/methodology | Strategy design, risk sizing |
| [`execution-agent`](../../.claude/agents/execution.md) | Reviews the execution layer — order placement, broker integration, execution-side safety | `execution/`, broker integration | Read, Grep, Glob, Bash | Review execution/broker changes | Strategy or backtest logic |
| [`coder-agent`](../../.claude/agents/coder.md) | Implements tasks assigned by PM once scoped and reviewed | Whole repo (implementation only, task-scoped) | Read, Edit, Write, Grep, Glob, Bash | Write code for an already-scoped task | Planning, architecture decisions |

## Not yet created (proposed, not approved)

See `docs/governance/GOVERNANCE-GAP-ANALYSIS.md`'s hierarchy-expansion
section — Architecture, Infrastructure, Security, QA/Test, Documentation,
and Release agents were requested but not created this pass; awaiting a
decision on whether each is worth the added coordination overhead versus
folding into the existing 6.

## Reporting format (shared by all agents)

Per `.claude/agents/pm-governance-cowork.md`'s "REPORT FORMAT" section —
every agent reports:
```
Status
System (1 / 2 / Shared)
Stage/Phase
Priority
Alignment Score (0-100)
Architecture Impact
Documentation Impact
Implementation Risk
Completed
Remaining
Blockers
Recommendations
Next Sprint
Files Affected
Documents Referenced
```
This is not restated per-agent — each agent file inherits it from the
governance policy layer rather than redefining it.
