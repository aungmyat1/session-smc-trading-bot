# SVOS Strategy Audit Workflow Validation

Date: 2026-06-28


This report validates the current Strategy Audit workflow in the repository
against the attached reference describing how professional quantitative trading

The reference model is:
Evidence:

- [SVOS_LIFECYCLE_WORKFLOW.md](SVOS_LIFECYCLE_WORKFLOW.md)
- [SVOS_STRATEGY_AUDIT_LOOP_REPORT.md](SVOS_STRATEGY_AUDIT_LOOP_REPORT.md)
- [../research/svos/engine.py](../research/svos/engine.py)
  ↓
Phase 1 ─ Strategy Enhancement
  ↓
Phase 2 ─ Historical Replay
  ↓
  ↓
Phase 4 ─ Robustness
  ↓
Phase 6 ─ Virtual Demo Trading
  ↓
Evidence:

- [../research/svos/engine.py](../research/svos/engine.py)
- [../research/svos/engine.py](../research/svos/engine.py)
- [SVOS_LIFECYCLE_WORKFLOW.md](SVOS_LIFECYCLE_WORKFLOW.md)
The repository is **substantially aligned in intent** and **partially aligned
in implementation**.

Short version:

- The repo already includes an Enhancement stage in executable SVOS code.
- The repo already supports stage-by-stage SVOS reports and dashboard display.
- The repo does **not yet fully implement** the reference model's interactive
- The new `strategy_validation/` module is closer to the reference model than
  the legacy audit logic embedded in `research/svos/engine.py`.
Evidence:

- [../research/svos/engine.py](../research/svos/engine.py)
- [../strategy_validation/parser.py](../strategy_validation/parser.py)
- [../strategy_validation/models.py](../strategy_validation/models.py)
Reference expectation:

- Strategy logic is audited before replay or backtest.

Repository status:
- Implemented.

Evidence:

- [SVOS_STRATEGY_AUDIT_LOOP_REPORT.md](SVOS_STRATEGY_AUDIT_LOOP_REPORT.md)
- [../research/svos/engine.py](../research/svos/engine.py)
Evidence:

- [../strategy_validation/validators/ambiguity_validator.py](../strategy_validation/validators/ambiguity_validator.py)
- [../strategy_validation/validators/completeness_validator.py](../strategy_validation/validators/completeness_validator.py)
- [../strategy_validation/validators/consistency_validator.py](../strategy_validation/validators/consistency_validator.py)
- [../strategy_validation/validators/measurability_validator.py](../strategy_validation/validators/measurability_validator.py)
- [../strategy_validation/validators/risk_validator.py](../strategy_validation/validators/risk_validator.py)
Reference expectation:

- After audit, the strategy enters an enhancement/editor stage before replay.

Repository status:
- Implemented in code.
- Not always surfaced consistently in simplified lifecycle summaries.

Evidence:

- [../research/svos/engine.py](../research/svos/engine.py)
- [SVOS_LIFECYCLE_WORKFLOW.md](SVOS_LIFECYCLE_WORKFLOW.md)

Evidence:

- [../research/svos/engine.py](../research/svos/engine.py)
- [SVOS_LIFECYCLE_WORKFLOW.md](SVOS_LIFECYCLE_WORKFLOW.md)
- [../strategy_validation/ai/improvement_engine.py](../strategy_validation/ai/improvement_engine.py)
### 3. Rule extraction and machine-readable strategy normalization

Reference expectation:

- Loose strategy text should be converted into structured rules before testing.
Repository status:

- Implemented in two layers.
Evidence:

Evidence:

- [../research/svos/engine.py](../research/svos/engine.py)
- [SVOS_LIFECYCLE_WORKFLOW.md](SVOS_LIFECYCLE_WORKFLOW.md)
- [../dashboard/app.py](../dashboard/app.py)
- [../dashboard/index.html](../dashboard/index.html)
Assessment:

- Matches the reference direction.

### 4. Ambiguity and contradiction auditing

Reference expectation:

  and contradictions before replay.

Repository status:


Evidence:

Evidence:
- Strong alignment.
-- [../strategy_validation/validators/ambiguity_validator.py](../strategy_validation/validators/ambiguity_validator.py)
-- [../strategy_validation/validators/completeness_validator.py](../strategy_validation/validators/completeness_validator.py)
-- [../strategy_validation/validators/consistency_validator.py](../strategy_validation/validators/consistency_validator.py)
-- [../strategy_validation/validators/measurability_validator.py](../strategy_validation/validators/measurability_validator.py)
-- [../strategy_validation/validators/risk_validator.py](../strategy_validation/validators/risk_validator.py)

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
  [../research/svos/engine.py](../research/svos/engine.py)
- The repo explicitly documents that AI edits are outside the deterministic
  pipeline:
  [SVOS_LIFECYCLE_WORKFLOW.md](SVOS_LIFECYCLE_WORKFLOW.md)
- The new improvement engine is deterministic recommendation aggregation, not a
  live interactive editor:
  [../strategy_validation/ai/improvement_engine.py](../strategy_validation/ai/improvement_engine.py)

Assessment:

Reference expectation:

- Every research stage should produce reviewable evidence before promotion.
- Implemented.

Evidence:

  [../research/svos/engine.py](../research/svos/engine.py)
- Stage workflow docs:
  [SVOS_LIFECYCLE_WORKFLOW.md](SVOS_LIFECYCLE_WORKFLOW.md)
Assessment:

- Strong alignment.

## Overall Alignment Rating
|---|---|
| Pre-backtest strategy audit | Aligned |
| Strategy enhancement phase | Aligned in code |

## Practical Conclusion

The attached workflow is a valid professional benchmark, and the repository is
already moving in that direction.

The current repo should be described as:

- professionally valid in research-gate philosophy
- operationally usable today
- not yet fully complete as an interactive AI-first rule editing system
```text
Strategy Intake
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

Use the following checklist to validate the workflow in the repo directly.
### A. Check the documented workflow

Review:


What to confirm:

- stage reports are part of the operational model

### B. Check the executable SVOS stage order

- [../research/svos/engine.py](../research/svos/engine.py)

What to confirm in `SVOSRunner.run_pipeline()`:
- replay, backtest, robustness, verification-ready, virtual-demo, and
  production-approval run in sequence

### C. Check audit logic

Inspect:

- [../research/svos/engine.py](../research/svos/engine.py)
- [../strategy_validation/validators](../strategy_validation/validators)

- ambiguous rules are flagged
- contradictory rules are flagged

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

- [../strategy_validation/cli.py](../strategy_validation/cli.py)
- [../strategy_validation/pipeline/strategy_validation_pipeline.py](../strategy_validation/pipeline/strategy_validation_pipeline.py)

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

- [../scripts/run_current_strategy_svos.py](../scripts/run_current_strategy_svos.py)

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

- [../dashboard/app.py](../dashboard/app.py)
- [../dashboard/index.html](../dashboard/index.html)

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

- [../tests/strategy_validation/test_pipeline.py](../tests/strategy_validation/test_pipeline.py)
- [../tests/test_dashboard_app.py](../tests/test_dashboard_app.py)

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
