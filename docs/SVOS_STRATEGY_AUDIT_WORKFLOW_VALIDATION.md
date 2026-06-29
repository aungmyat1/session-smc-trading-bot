# SVOS Strategy Audit Workflow Validation

Date: 2026-06-28

## Scope

This report validates the current Strategy Audit workflow in the repository
against the attached reference describing how professional quantitative trading
firms gate strategy research before replay and backtesting.

The reference model is:

```text
New Strategy
  ↓
Phase 0 ─ Strategy Audit
  ↓
Phase 1 ─ Strategy Enhancement
  ↓
Phase 2 ─ Historical Replay
  ↓
Phase 3 ─ Backtesting
  ↓
Phase 4 ─ Robustness Tests
  ↓
Phase 5 ─ Demo Trading
  ↓
Phase 6 ─ Production Approval
```

## Executive Verdict

The repository is **substantially aligned in intent** and **partially aligned
in implementation**.

Short version:

- The repo already treats Strategy Audit as a pre-backtest quality gate.
- The repo already includes an Enhancement stage in executable SVOS code.
- The repo already supports stage-by-stage SVOS reports and dashboard display.
- The repo does **not yet fully implement** the reference model's interactive
  AI rule-editor workflow for resolving ambiguities before promotion.
- The new `strategy_validation/` module is closer to the reference model than
  the legacy audit logic embedded in `research/svos/engine.py`.

## Reference-To-Repo Validation

### 1. Pre-backtest audit gate

Reference expectation:

- Strategy logic is audited before replay or backtest.

Repository status:

- Implemented.

Evidence:

- [docs/SVOS_LIFECYCLE_WORKFLOW.md](/home/aungp/session-smc-trading-bot/docs/SVOS_LIFECYCLE_WORKFLOW.md:1)
- [docs/SVOS_STRATEGY_AUDIT_LOOP_REPORT.md](/home/aungp/session-smc-trading-bot/docs/SVOS_STRATEGY_AUDIT_LOOP_REPORT.md:1)
- [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:657)

Assessment:

- Matches the professional workflow.

### 2. Separate Strategy Enhancement phase

Reference expectation:

- After audit, the strategy enters an enhancement/editor stage before replay.

Repository status:

- Implemented in code.
- Not always surfaced consistently in simplified lifecycle summaries.

Evidence:

- [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:673)
- [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:778)
- [docs/SVOS_LIFECYCLE_WORKFLOW.md](/home/aungp/session-smc-trading-bot/docs/SVOS_LIFECYCLE_WORKFLOW.md:64)

Assessment:

- The actual executable SVOS flow is closer to the attached reference than the
  simplified operational pipeline text.

### 3. Rule extraction and machine-readable strategy normalization

Reference expectation:

- Loose strategy text should be converted into structured rules before testing.

Repository status:

- Implemented in two layers.

Evidence:

- Legacy extraction and normalization:
  [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:130)
- New Stage 1 parser and document model:
  [strategy_validation/parser.py](/home/aungp/session-smc-trading-bot/strategy_validation/parser.py:1)
  [strategy_validation/models.py](/home/aungp/session-smc-trading-bot/strategy_validation/models.py:1)

Assessment:

- Matches the reference direction.

### 4. Ambiguity and contradiction auditing

Reference expectation:

- The audit should flag ambiguous rules, missing parameters, undefined filters,
  and contradictions before replay.

Repository status:

- Implemented, especially in the new Stage 1 validation module.

Evidence:

- [strategy_validation/validators/ambiguity_validator.py](/home/aungp/session-smc-trading-bot/strategy_validation/validators/ambiguity_validator.py:1)
- [strategy_validation/validators/completeness_validator.py](/home/aungp/session-smc-trading-bot/strategy_validation/validators/completeness_validator.py:1)
- [strategy_validation/validators/consistency_validator.py](/home/aungp/session-smc-trading-bot/strategy_validation/validators/consistency_validator.py:1)
- [strategy_validation/validators/measurability_validator.py](/home/aungp/session-smc-trading-bot/strategy_validation/validators/measurability_validator.py:1)
- [strategy_validation/validators/risk_validator.py](/home/aungp/session-smc-trading-bot/strategy_validation/validators/risk_validator.py:1)

Assessment:

- Strong alignment.

### 5. Interactive AI clarification/editor loop

Reference expectation:

- AI should actively ask rule-resolution questions such as:
  - what defines BOS
  - how long FVG remains valid
  - how many sweeps are allowed

Repository status:

- Partially implemented.

Evidence:

- The legacy audit stores clarifying questions:
  [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:474)
- The repo explicitly documents that AI edits are outside the deterministic
  pipeline:
  [docs/SVOS_LIFECYCLE_WORKFLOW.md](/home/aungp/session-smc-trading-bot/docs/SVOS_LIFECYCLE_WORKFLOW.md:81)
- The new improvement engine is deterministic recommendation aggregation, not a
  live interactive editor:
  [strategy_validation/ai/improvement_engine.py](/home/aungp/session-smc-trading-bot/strategy_validation/ai/improvement_engine.py:1)

Assessment:

- This is the biggest gap versus the attached professional workflow.

### 6. Audit outputs and stage reports

Reference expectation:

- Every research stage should produce reviewable evidence before promotion.

Repository status:

- Implemented.

Evidence:

- Stage report writing:
  [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:1289)
- Stage workflow docs:
  [docs/SVOS_LIFECYCLE_WORKFLOW.md](/home/aungp/session-smc-trading-bot/docs/SVOS_LIFECYCLE_WORKFLOW.md:61)
- Dashboard stage-report surfacing:
  [dashboard/app.py](/home/aungp/session-smc-trading-bot/dashboard/app.py:69)
  [dashboard/index.html](/home/aungp/session-smc-trading-bot/dashboard/index.html:616)

Assessment:

- Strong alignment.

## Overall Alignment Rating

| Area | Status |
|---|---|
| Pre-backtest strategy audit | Aligned |
| Strategy enhancement phase | Aligned in code |
| Structured rule extraction | Aligned |
| Ambiguity and contradiction checks | Aligned |
| Interactive AI rule editor | Partial |
| Multi-stage evidence and reports | Aligned |
| Input support for PDF/Word/screenshots | Partial |

## Practical Conclusion

The attached workflow is a valid professional benchmark, and the repository is
already moving in that direction.

The current repo should be described as:

- professionally valid in research-gate philosophy
- operationally usable today
- not yet fully complete as an interactive AI-first rule editing system

The most accurate current implementation sequence is:

```text
Strategy Intake
  ↓
Strategy Audit
  ↓
Strategy Enhancement
  ↓
Historical Replay
  ↓
Backtest
  ↓
Robustness
  ↓
Verification Ready
  ↓
Virtual Demo Trading
  ↓
Production Approval
```

## How To Check The Implementation

Use the following checklist to validate the workflow in the repo directly.

### A. Check the documented workflow

Review:

- [docs/SVOS_LIFECYCLE_WORKFLOW.md](/home/aungp/session-smc-trading-bot/docs/SVOS_LIFECYCLE_WORKFLOW.md:1)
- [docs/SYSTEM_ARCHITECTURE.md](/home/aungp/session-smc-trading-bot/docs/SYSTEM_ARCHITECTURE.md:1)
- [docs/STRATEGY_VALIDATION_ENGINE.md](/home/aungp/session-smc-trading-bot/docs/STRATEGY_VALIDATION_ENGINE.md:1)
- [docs/SVOS_STRATEGY_AUDIT_LOOP_REPORT.md](/home/aungp/session-smc-trading-bot/docs/SVOS_STRATEGY_AUDIT_LOOP_REPORT.md:1)

What to confirm:

- audit happens before replay
- enhancement exists between audit and replay
- stage reports are part of the operational model

### B. Check the executable SVOS stage order

Inspect:

- [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:645)

What to confirm in `SVOSRunner.run_pipeline()`:

- `intake` runs first
- `audit` runs second
- `_enhance(audit)` runs before replay
- replay, backtest, robustness, verification-ready, virtual-demo, and
  production-approval run in sequence

### C. Check audit logic

Inspect:

- [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:389)
- [strategy_validation/validators](/home/aungp/session-smc-trading-bot/strategy_validation/validators)

What to confirm:

- missing fields are detected
- ambiguous rules are flagged
- contradictory rules are flagged
- risk controls are validated
- readiness decisions are generated

### D. Check the new Stage 1 validator module

Run:

```bash
python3 -m strategy_validation.cli \
  --spec "docs/strategy_audit/strategies/ST-A2 (Session Liquidity Reversal)/strategy_spec.md"
```

What to confirm:

- a structured report is written under `reports/strategy_validation/<strategy>/`
- outputs include JSON, Markdown, HTML, and audit log
- the readiness decision reflects specification quality rather than profitability

Relevant files:

- [strategy_validation/cli.py](/home/aungp/session-smc-trading-bot/strategy_validation/cli.py:1)
- [strategy_validation/pipeline/strategy_validation_pipeline.py](/home/aungp/session-smc-trading-bot/strategy_validation/pipeline/strategy_validation_pipeline.py:1)

### E. Check the SVOS orchestration entrypoint

Run:

```bash
python3 scripts/run_current_strategy_svos.py --strategy ST-A2 --stop-after audit
```

or:

```bash
python3 scripts/run_current_strategy_svos.py --strategy ST-A2 --stop-after enhancement
```

What to confirm:

- stage progress is printed
- the run stops at the selected boundary
- stage report artifacts are written

Relevant file:

- [scripts/run_current_strategy_svos.py](/home/aungp/session-smc-trading-bot/scripts/run_current_strategy_svos.py:1)

### F. Check stage report artifacts on disk

Inspect:

- `reports/current_strategy_svos/<strategy>/stages/index.json`
- `reports/current_strategy_svos/<strategy>/stages/01_audit.md`
- `reports/current_strategy_svos/<strategy>/stages/02_enhancement.md`
- `reports/current_strategy_svos/<strategy>/stages/03_replay.md`

What to confirm:

- each completed stage writes both `.json` and `.md` evidence
- `index.json` tracks stage status and order

### G. Check dashboard implementation

Inspect:

- [dashboard/app.py](/home/aungp/session-smc-trading-bot/dashboard/app.py:69)
- [dashboard/index.html](/home/aungp/session-smc-trading-bot/dashboard/index.html:616)

What to confirm:

- `/api/svos` returns stage report metadata
- the dashboard stage list matches the current operational pipeline
- each stage can open its related report
- reports render as formatted markdown in the dashboard

### H. Check tests

Run:

```bash
pytest -q tests/strategy_validation/test_pipeline.py tests/test_dashboard_app.py
```

What to confirm:

- strategy validation tests pass
- dashboard report exposure tests pass
- stage report viewing tests pass

Relevant tests:

- [tests/strategy_validation/test_pipeline.py](/home/aungp/session-smc-trading-bot/tests/strategy_validation/test_pipeline.py:1)
- [tests/test_dashboard_app.py](/home/aungp/session-smc-trading-bot/tests/test_dashboard_app.py:1)

## Recommended Next Steps

To match the attached workflow more completely, the highest-value upgrades are:

1. Add an interactive clarification layer that asks unresolved rule questions
   before replay.
2. Expand document ingestion beyond markdown/text into PDF, DOCX, and image
   extraction.
3. Make `strategy_validation/` the canonical audit engine used directly by the
   main SVOS runner.
4. Standardize lifecycle docs so they consistently show `Strategy Enhancement`
   between Audit and Replay.
