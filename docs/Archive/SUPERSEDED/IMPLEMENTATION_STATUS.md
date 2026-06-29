# Current Implementation Plan

Date: 2026-06-28

> **Superseded 2026-06-29.** Retained as historical implementation context.
> Current work is governed by
> `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md` and is
> sequenced by `docs/svos/architecture-review-2026-06-29/06_UPGRADE_ROADMAP.md`.

## Purpose

This document defines what should be implemented now for `SVOS`.

`SVOS` is not just a backtester.

It is a research and verification system whose job is to take:

- a new trade idea
- or a new strategy specification

and turn it into either:

- a production-approved strategy
- or a rejected strategy that must return to refinement

## Core Function

The main function of `SVOS` is the failure loop.

This is the essential behavior:

- fail in `Strategy Intake` -> correct the source specification or ingestion payload
- fail in `Strategy Audit` -> fix the specification
- fail in `Strategy Enhancement` -> resolve unanswered rule questions and regenerate the rulebook
- fail in `Historical Replay` -> fix the logic interpretation
- fail in `Backtest` -> improve logic or filters
- fail in `Robustness` -> simplify or retune
- fail in `Verification Ready` -> close research-stage gaps before demo promotion
- fail in `Virtual Demo Trading` -> analyze execution drift and return to research

That means `SVOS` is not just a linear pipeline.

It is a controlled refinement engine that keeps improving or rejecting a
strategy until it is genuinely ready for production approval.

## Target Workflow

```text
Strategy Intake
      │
      ▼
Strategy Audit
      │
      ├── FAIL -> AI edits specification -> Audit again
      ▼
Strategy Enhancement
      │
      ├── FAIL -> Resolve unresolved rule questions -> Enhance again
      ▼
Historical Replay
      │
      ├── FAIL -> Refine rules -> Replay again
      ▼
Backtest
      │
      ├── FAIL -> Improve logic or filters -> Backtest again
      ▼
Robustness
      │
      ├── FAIL -> Adjust parameters or simplify rules -> Retest
      ▼
Verification Ready
      │
      ├── FAIL -> Resolve research-stage gaps -> Return to research
      ▼
Virtual Demo Trading
      │
      ├── FAIL -> Analyze live drift -> Return to research
      ▼
Production Approval
```

This is the current operational pipeline in the repository.

## Implementation Priorities

### Phase 0. Strategy Audit

Purpose:

- understand the strategy before testing it
- convert rules into objective, machine-checkable logic
- block ambiguous or contradictory specifications

What this stage should do:

- rule extraction from strategy text
- ambiguity detection
- contradiction detection
- missing-parameter detection
- data-availability checks
- execution-conflict detection
- audit summary and readiness verdict

Desired output:

- structured rulebook
- audit findings
- pass/fail readiness decision

Current implementation position:

- canonical validation engine exists in `strategy_validation/`
- SVOS runner already uses the validation engine for audit-stage decisions
- structured enhancement artifacts exist

Remaining implementation focus:

- make the fail-loop explicit and operator-friendly
- ensure audit findings map cleanly into revision actions
- prioritize unresolved ambiguity as a hard block before replay

### Phase 1. Strategy Enhancement

Purpose:

- refine failed strategies immediately after audit
- let AI propose corrections before testing begins

What this stage should do:

- ask targeted clarification questions
- rewrite ambiguous rules
- propose parameter defaults only when justified
- emit a revised strategy specification candidate

Desired output:

- cleaner rulebook
- revision suggestions
- explicit unresolved questions

Current implementation position:

- structured clarification plan and rewrite snippets already exist

Remaining implementation focus:

- persist answers
- produce a revised spec artifact cleanly
- loop directly back into audit until readiness is achieved

### Phase 2. Historical Replay

Purpose:

- verify that strategy behavior makes sense candle by candle
- validate logic interpretation before profitability claims

What this stage should do:

- replay historical candles one step at a time
- verify event sequencing
- verify session logic
- verify entry/exit timing
- detect missing or spurious signals

Desired output:

- replay report
- logic findings
- pass/fail replay verdict

Current implementation position:

- replay capability exists in the current workflow

Remaining implementation focus:

- strengthen replay diagnostics around why a strategy failed
- make replay failure feed directly into rule refinement

### Phase 3. Backtest

Purpose:

- test statistical profitability only after rules are clear

What this stage should do:

- run strategy on historical data
- evaluate profitability and cost sensitivity
- produce statistical evidence

Desired output:

- trade count
- profit factor
- expectancy
- drawdown and distribution evidence
- pass/fail backtest verdict

Current implementation position:

- backtest tooling exists

Remaining implementation focus:

- keep this stage downstream of audit and replay
- make failed backtests route into logic/filter improvement, not blind retesting

### Phase 4. Robustness

Purpose:

- reject fragile or overfit strategies
- verify stability across different assumptions and conditions

Core robustness modules to support:

- walk-forward testing
- parameter stability
- regime analysis
- execution cost sensitivity
- distribution stress tests where appropriate

Desired output:

- robustness report
- fragility findings
- stable/fragile verdict

Current implementation position:

- robustness stage exists in the current workflow

Remaining implementation focus:

- make robustness failures produce specific correction guidance
- route failures to simplification, retuning, or rule changes

### Phase 5. Verification Ready + Virtual Demo Trading

Purpose:

- validate the strategy in live demo market conditions
- detect drift between research behavior and execution behavior

What this stage should do:

- run the validated strategy on Vantage demo
- verify signal lifecycle
- verify order lifecycle
- verify reconnect/restart safety
- detect live drift and execution mismatch

Desired output:

- virtual-demo execution evidence
- drift findings
- PASS/FAIL Virtual Demo Trading verdict

Current implementation position:

- execution layer exists
- demo bot is deployed
- current operational gating depends on spread capture, cost revalidation, and
  execution checks

Remaining implementation focus:

- make Virtual Demo Trading failure explicitly route back into research analysis
- keep the bot simple, stable, and well-instrumented

Implemented report contract:

- every run writes six canonical JSON reports and six matching Markdown reports
- immutable artifacts are stored under
  `reports/svos/<strategy-id>/<version>/<run-id>/`
- internal intake and enhancement evidence is included in `Strategy Audit`
- internal verification-ready evidence is carried into `Virtual Demo Trading`
- reports use `PASS`, `FAIL`, `BLOCKED`, `IN_PROGRESS`, and `NOT_RUN`
- downstream stages become `BLOCKED` after a failed or blocked hard gate
- the append-only SVOS registry records report hashes and strategy versions
- the shared JSON contract is `svos/reports/stage_report.schema.json`
- `scripts/run_svos_sample.py` provides an isolated six-stage PASS verification
  without changing the active catalog or requesting live promotion

Minimum delivery timeline for this reporting and lifecycle consolidation:

| Period | Target |
|---|---|
| Days 1-2 | lifecycle and report contracts |
| Days 3-5 | immutable storage, indexing, and version identity |
| Days 6-8 | audit, replay, and backtest integration |
| Days 9-11 | robustness, verification-ready handoff, virtual demo drift, and approval integration |
| Days 12-13 | blocked-stage handling and dashboard report access |
| Days 14-15 | regression tests and end-to-end acceptance |

### Phase 6. Production Approval

Purpose:

- approve only strategies that have survived the full fail-loop

What this stage should do:

- review audit, enhancement, replay, backtest, robustness, verification-ready, and Virtual Demo Trading evidence
- approve or reject live promotion

Desired output:

- production approval decision
- approval artifact
- rationale for deployment or rejection

Current implementation position:

- partial registry/config-driven approval logic already exists

Remaining implementation focus:

- keep approval evidence-based and simple
- avoid broad governance-system expansion unless the direct workflow needs it

## Audit Modules To Prioritize

The next valuable implementation work should strengthen the audit layer above
the existing data, replay, simulator, and execution components.

Priority audit modules:

### 1. Rule Audit

Checks:

- session timing
- sweep/BOS/CHOCH sequencing
- FVG/OB logic
- entry timing
- stop placement
- take-profit logic
- position sizing
- risk-limit compliance

### 2. Market Data Audit

Checks:

- missing candles
- duplicate bars
- weekend leakage
- spread anomalies
- timestamp ordering
- session-boundary correctness

### 3. Statistical Audit

Checks:

- profit factor
- expectancy
- payoff ratio
- drawdown
- trade distribution
- edge consistency

### 4. Regime Audit

Checks:

- trending vs ranging
- high vs low volatility
- session segmentation
- seasonal and time-window segmentation

### 5. Parameter Stability Audit

Checks:

- plateau behavior instead of sharp peaks
- sensitivity across parameter ranges

### 6. Walk-Forward / Robustness Audit

Checks:

- rolling validation
- out-of-sample behavior
- stability under changed conditions

## Simple Bot Principle

The trading bot should remain simple.

It should do these things well:

- run approved strategy logic
- place or simulate trades safely
- log signals and order lifecycle clearly
- survive reconnects and restarts
- respect risk controls

It should not grow into a larger control plane unless that becomes necessary
for the direct SVOS-to-demo/live path.

## Active Work Right Now

The current operational work remains:

1. finish `E5` spread capture
2. run `E6` cost revalidation
3. complete `E1-E4` execution gate
4. continue Virtual Demo Trading only if evidence holds
5. allow controlled live approval only after Virtual Demo Trading evidence is acceptable

## In Scope

- fail-loop clarity
- audit quality
- replay correctness
- backtest correctness
- robustness diagnostics
- Virtual Demo Trading drift analysis
- simple Vantage demo/live bot
- execution reliability

## Out Of Scope For Now

- broad EVF/RGM/Governance/SMO expansion
- major architecture separation not needed for the current fail-loop
- multi-strategy platform growth
- dashboard/control-plane expansion that does not directly improve the current
  research-to-demo/live workflow

## References

- `docs/CURRENT_SCOPE.md`
- `docs/PROJECT_OBJECTIVE_FASTEST_PATH.md`
- `docs/PROJECT_LIVE_STATUS_TIMELINE.md`
- `config/strategy_catalog.yaml`
