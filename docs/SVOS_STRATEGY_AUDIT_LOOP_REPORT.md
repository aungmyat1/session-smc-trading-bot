# SVOS Strategy Audit Feedback Loop Report

Date: 2026-06-28

## Scope

This report explains the SVOS lifecycle branch:

```text
Strategy Audit
      │
      ├── FAIL → AI edits specification → Audit again
```

It describes the operational purpose of the loop, what a failure means, what
the AI revision step is allowed to do, and the expected outputs before the
strategy can proceed to Historical Replay.

## Purpose

The Strategy Audit stage is the specification-quality gate in SVOS.

Its job is not to judge profitability.

Its job is to determine whether the strategy specification is:

- complete
- objective
- measurable
- internally consistent
- risk-defined
- testable by another reviewer or by code

If the specification fails here, the strategy must not proceed to replay,
backtest, or later validation stages.

## Operational Meaning Of The Branch

### 1. Strategy Audit

SVOS reviews the written strategy definition and checks whether the strategy can
be translated into deterministic logic.

Typical review questions:

- Are the required fields present?
- Are entry and exit rules explicit?
- Are risk controls documented?
- Are institutional concepts defined precisely?
- Can two reviewers identify the same trades?
- Can the rules be coded without hidden assumptions?

### 2. FAIL

A fail means the strategy specification is not ready for research validation.

Typical failure causes:

- missing required fields such as stop loss, take profit, or session
- subjective wording such as "strong trend" or "good momentum"
- contradictory instructions such as mutually exclusive session rules
- undefined institutional concepts
- missing cancellation or invalidation logic
- incomplete risk controls
- rules that cannot be converted into code deterministically

At this point the failure is a documentation and logic-quality failure, not a
performance failure.

### 3. AI Edits Specification

This step exists to improve the written specification without changing the core
trading idea.

Allowed changes:

- rewrite subjective phrases into measurable language
- add missing field definitions
- normalize terminology across sections
- clarify rule order and cancellation logic
- convert informal risk language into explicit controls
- surface unresolved conflicts for human review

Not allowed:

- invent a new strategy idea
- change the intended market thesis
- optimize the strategy for profitability
- insert unverified trading rules that were not implied by the original design

In the current repository, this step is conceptually part of the lifecycle but
is not automatically executed inside the SVOS pipeline itself. It is a human or
agent action outside the deterministic stage runner.

### 4. Audit Again

After the revised specification is produced, the Strategy Audit is rerun on the
updated text.

The rerun checks whether the prior failures have been resolved and whether the
new version is now:

- complete enough for replay
- still faithful to the original intent
- free of contradictions introduced during editing
- reproducible under the same validation rules

This loop repeats until the specification reaches an acceptable readiness state
or is rejected as too incomplete to rehabilitate safely.

## Expected Inputs

The audit loop expects a canonical strategy specification that includes, at
minimum:

- strategy name
- instrument or instruments
- market
- timeframe
- session
- direction
- entry rules
- exit rules
- stop loss
- take profit
- risk model
- position sizing

Additional fields such as news rules, daily loss limits, and maximum drawdown
improve audit quality and reduce revision cycles.

## Expected Outputs

The Strategy Audit should produce structured findings and recommendations.

Expected outputs include:

- validator name
- score
- status
- findings
- recommendations
- readiness decision

Under the new Stage 1 implementation in `strategy_validation/`, the resulting
readiness decisions are:

- `READY_FOR_REPLAY`
- `REQUIRES_REVISION`
- `INCOMPLETE`
- `REJECTED`

## Why This Loop Matters

Without this branch, SVOS would allow weak strategy text to enter replay and
backtest stages where failures would be harder to interpret.

The loop protects the research pipeline by catching specification errors early:

- before historical evidence is polluted by ambiguous rules
- before backtest results are trusted on a faulty implementation
- before later stages spend time on a strategy that is not yet codable

This makes the audit stage a quality gate and a cost-control mechanism.

## Governance Interpretation

The correct governance interpretation is:

- Audit fail does not mean the strategy has no edge.
- Audit fail means the strategy is not yet defined well enough to evaluate.
- AI revision is a clarity-improvement step, not a profitability-improvement step.
- Re-audit is mandatory after any material specification change.

## Current Repository Alignment

This workflow is already referenced in:

- [docs/SVOS_LIFECYCLE_WORKFLOW.md](/home/aungp/session-smc-trading-bot/docs/SVOS_LIFECYCLE_WORKFLOW.md:1)
- [docs/SVOS_EVF_USER_MANUAL.md](/home/aungp/session-smc-trading-bot/docs/SVOS_EVF_USER_MANUAL.md:1)
- [docs/SYSTEM_ARCHITECTURE.md](/home/aungp/session-smc-trading-bot/docs/SYSTEM_ARCHITECTURE.md:1)
- [docs/STRATEGY_VALIDATION_ENGINE.md](/home/aungp/session-smc-trading-bot/docs/STRATEGY_VALIDATION_ENGINE.md:1)

The executable Stage 1 implementation that supports this loop now lives in:

- [strategy_validation](/home/aungp/session-smc-trading-bot/strategy_validation)

## Conclusion

The branch

```text
Strategy Audit
      │
      ├── FAIL → AI edits specification → Audit again
```

is the mechanism that keeps SVOS from evaluating unclear strategies as though
they were fully defined systems.

Its purpose is to improve specification quality until the strategy is objective,
traceable, and ready for Historical Replay.
