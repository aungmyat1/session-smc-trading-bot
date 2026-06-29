# SVOS Strategy Audit Gap Closure Plan

Date: 2026-06-28

## Objective

Close the remaining gaps between the current repository implementation and the
professional Strategy Validation Operating System workflow validated in
[docs/SVOS_STRATEGY_AUDIT_WORKFLOW_VALIDATION.md](/home/aungp/session-smc-trading-bot/docs/SVOS_STRATEGY_AUDIT_WORKFLOW_VALIDATION.md:1).

The target is not to invent a new workflow. The target is to make the current
repo fully behave like a professional research gate:

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

## Current Gaps

From the validation report, the remaining gaps are:

1. The audit engine is split between the legacy audit logic in
   `research/svos/engine.py` and the newer `strategy_validation/` module.
2. The AI enhancement stage is recommendation-based, not a true interactive
   clarification/editor loop.
3. Strategy input ingestion is still mostly markdown/text oriented.
4. Lifecycle documentation is not yet fully consistent about the presence of
   `Strategy Enhancement`.
5. The main SVOS runner does not yet use `strategy_validation/` as the
   canonical Stage 0 audit engine.

## Guiding Principle

Do not add another strategy-audit subsystem.

Instead:

- promote `strategy_validation/` into the canonical specification-quality layer
- reduce the legacy audit code in `research/svos/engine.py` to orchestration
- make Enhancement the structured bridge between failed audit findings and a
  replay-ready rulebook

## Workstreams

### Workstream 1: Canonicalize Stage 0 Audit

Goal:

- Make `strategy_validation/` the single source of truth for specification
  validation before replay.

Implementation steps:

1. Introduce an adapter from `strategy_validation.ValidationReport` to the
   legacy `StageResult` shape used by `SVOSRunner`.
2. Replace the current `StrategyAuditEngine.audit()` call inside
   `SVOSRunner.run_pipeline()` with the adapter-backed `strategy_validation`
   pipeline.
3. Preserve stage report output shape so downstream dashboard and report tools
   do not break.

Primary files:

- [strategy_validation/pipeline/strategy_validation_pipeline.py](/home/aungp/session-smc-trading-bot/strategy_validation/pipeline/strategy_validation_pipeline.py:1)
- [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:645)

Definition of done:

- `SVOSRunner` uses `strategy_validation/` for audit decisions
- audit findings, readiness decision, and recommendations appear in
  `01_audit.json` and `01_audit.md`
- no duplicate audit logic remains authoritative

### Workstream 2: Build A Real Enhancement Editor

Goal:

- Upgrade `Strategy Enhancement` from static recommendations into a proper
  clarification/editor workflow.

Implementation steps:

1. Add a question-generation layer that turns failed validator findings into
   explicit resolution prompts.
2. Add an enhancement session model with:
   - original rule
   - unresolved question
   - selected answer
   - revised wording
   - reason
3. Support deterministic resolution templates for common institutional concepts:
   - BOS
   - CHOCH
   - FVG validity window
   - sweep timeout
   - order block definition
   - cancellation rules
4. Persist enhancement outputs as explicit stage artifacts.

Primary files to add or extend:

- `strategy_validation/ai/question_engine.py`
- `strategy_validation/ai/editor_engine.py`
- [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:778)

Definition of done:

- `02_enhancement` contains structured clarifications, not only suggestions
- unresolved critical questions block replay
- resolved answers produce a revised machine-readable spec

### Workstream 3: Add Multi-Format Strategy Intake

Goal:

- Accept the kinds of input described in the professional workflow:
  markdown, plain text, PDF, Word, and screenshots.

Implementation steps:

1. Extend intake to detect input type and normalize it into extracted text.
2. Add document adapters for:
   - `.md`
   - `.txt`
   - `.pdf`
   - `.docx`
3. Add image OCR ingestion for screenshots as a best-effort preprocessing step.
4. Track extraction confidence in intake metadata.

Primary files to add:

- `strategy_validation/intake/loaders.py`
- `strategy_validation/intake/ocr.py`
- `strategy_validation/intake/extractors.py`

Definition of done:

- intake metadata records source type and extraction confidence
- non-text input can still produce a `StrategyDocument`
- failed extraction blocks audit cleanly with actionable findings

### Workstream 4: Tighten Structured Audit Outputs

Goal:

- Match the reference-style outputs more explicitly.

Implementation steps:

1. Add roll-up counters to the validation report:
   - ambiguous rule count
   - missing parameter count
   - contradiction count
   - undefined filter count
   - execution conflict count
2. Surface these counters in markdown, HTML, and dashboard outputs.
3. Distinguish between:
   - fatal blockers
   - revision-required issues
   - improvement-only recommendations

Primary files:

- [strategy_validation/models.py](/home/aungp/session-smc-trading-bot/strategy_validation/models.py:1)
- [strategy_validation/reports/report_generator.py](/home/aungp/session-smc-trading-bot/strategy_validation/reports/report_generator.py:1)
- [dashboard/index.html](/home/aungp/session-smc-trading-bot/dashboard/index.html:1)

Definition of done:

- audit reports read like professional rule-audit summaries
- counts appear consistently in JSON, markdown, and dashboard surfaces

### Workstream 5: Standardize Lifecycle Documentation

Goal:

- Remove ambiguity between the simplified “current operational pipeline” text
  and the actual executable stage sequence.

Implementation steps:

1. Update current-state docs so they consistently include:
   `Strategy Intake -> Strategy Audit -> Strategy Enhancement -> Historical Replay`
2. Mark older simplified diagrams as historical or shorthand if retained.
3. Ensure dashboard labels match docs and code.

Primary files:

- [docs/SYSTEM_ARCHITECTURE.md](/home/aungp/session-smc-trading-bot/docs/SYSTEM_ARCHITECTURE.md:1)
- [docs/SVOS_LIFECYCLE_WORKFLOW.md](/home/aungp/session-smc-trading-bot/docs/SVOS_LIFECYCLE_WORKFLOW.md:1)
- [dashboard/index.html](/home/aungp/session-smc-trading-bot/dashboard/index.html:1)

Definition of done:

- docs, code, and dashboard show the same stage sequence

## Recommended Delivery Order

### Phase A: Convergence

Build first:

1. Canonicalize Stage 0 audit on `strategy_validation/`
2. Standardize lifecycle docs
3. Tighten structured audit outputs

Why first:

- this reduces architectural duplication before adding more features

### Phase B: Interactive Enhancement

Build next:

1. question engine
2. enhancement session model
3. structured edited-spec output

Why next:

- this is the most important workflow gap relative to the professional model

### Phase C: Input Expansion

Build after:

1. PDF/DOCX/image intake
2. extraction confidence and OCR failure handling

Why later:

- valuable, but not required to make the core workflow professionally valid

## Verification Plan

### Code verification

Inspect:

- [research/svos/engine.py](/home/aungp/session-smc-trading-bot/research/svos/engine.py:645)
- [strategy_validation/pipeline/strategy_validation_pipeline.py](/home/aungp/session-smc-trading-bot/strategy_validation/pipeline/strategy_validation_pipeline.py:1)

Confirm:

- only one audit engine is authoritative
- enhancement produces structured clarified rules

### Report verification

Inspect:

- `reports/current_strategy_svos/<strategy>/stages/01_audit.md`
- `reports/current_strategy_svos/<strategy>/stages/02_enhancement.md`

Confirm:

- audit findings are traceable
- enhancement answers unresolved rule questions explicitly

### Dashboard verification

Confirm in the SVOS panel:

- stage reports exist for intake, audit, enhancement, replay, and later stages
- audit/enhancement reports render as markdown
- report cards expose stage-specific evidence, not only generic “latest” reports

### Test verification

Extend tests for:

- validator-to-stage adapter behavior
- enhancement question generation
- edited spec persistence
- multi-format intake
- dashboard surfacing of audit counters and enhancement details

Primary test files:

- [tests/strategy_validation/test_pipeline.py](/home/aungp/session-smc-trading-bot/tests/strategy_validation/test_pipeline.py:1)
- [tests/test_dashboard_app.py](/home/aungp/session-smc-trading-bot/tests/test_dashboard_app.py:1)

## Success Criteria

The gap is closed when:

1. A raw strategy document is ingested into a normalized strategy document.
2. Audit results come from the canonical `strategy_validation/` engine.
3. Failed audit findings generate structured clarification questions.
4. Enhancement resolves those questions into a revised, machine-readable spec.
5. Replay is blocked until critical specification issues are resolved.
6. Stage reports and dashboard surfaces show the evidence for each step.

## Final Recommendation

The best next engineering move is:

`Make strategy_validation the canonical audit engine, then build a structured enhancement editor on top of it.`

That gives the repo the biggest professional-workflow upgrade with the least
architectural churn.
