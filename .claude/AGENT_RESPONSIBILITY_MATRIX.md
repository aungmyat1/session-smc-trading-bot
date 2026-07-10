# Agent Responsibility Matrix

Companion to `.claude/AGENTS.md`. One primary owner per column where a real
overlap existed; ✓ = performs this activity for its own scope, — = does not.

| Agent | Plans | Codes | Reviews | Docs | Tests | Deployment |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PM Agent (`pm.md`) | ✓ (primary) | — | ✓ | — | — | — |
| Governance Agent (`pm-governance-cowork.md`) | — | — | ✓ (compliance only) | ✓ (primary, authority order) | — | — |
| Strategy Agent | ✓ (rule design) | — | ✓ (strategy logic only) | — | — | — |
| Risk Agent | — | — | ✓ (risk logic only) | — | — | — |
| Backtest Agent | — | — | ✓ (methodology/gate) | — | ✓ (gate compliance, not authoring) | — |
| Execution Agent | — | — | ✓ (execution layer only) | — | — | — |
| Coder Agent | — | ✓ (primary) | — | — | ✓ (writes tests for assigned task) | — |

## Notes on overlap

- **Plans:** PM Agent is the sole planner across modules. Strategy Agent
  "plans" only in the narrow sense of proposing rule changes within its own
  domain — it does not plan tasks, assignment, or sequencing; that stays
  with PM Agent.
- **Reviews:** every review-capable agent reviews only its own domain
  (strategy / risk / backtest / execution). PM Agent's review is
  cross-module coordination review, not a second opinion inside any one
  domain — it does not re-review what a domain agent already reviewed.
  Governance Agent's review is compliance-against-canonical-docs only, not
  code or methodology review.
- **Docs:** no agent owns documentation broadly. Governance Agent owns the
  documentation-authority *order* and flags drift; it does not author
  feature docs. Updating a spec doc (e.g. `docs/RISK_SPEC.md`) after a code
  change is the Coder Agent's job as part of the assigned task, reviewed by
  the matching domain agent.
- **Tests:** Coder Agent writes tests for the task it implements. Backtest
  Agent checks gate-compliance of *results*, which is a review activity, not
  test authorship — it does not write test code.
- **Deployment:** no agent in this table owns deployment. Deployment is a
  human/operator action gated by the CONFIRM-token rules in `CLAUDE.md` §4
  and the System 2 production-readiness checklist in `SYSTEM2_MASTER_PLAN.md`
  — intentionally outside every agent's allowed responsibilities.

No agent has overlapping primary ownership of the same cell. Where two
agents both show ✓ in "Reviews," their scopes are domain-partitioned (see
`.claude/AGENTS.md` "Prohibited" fields per agent), not duplicated.
