# Developer Handbook

Date: 2026-06-28
Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Engineering
Authority: Level 5 — Development Standards
Related: index.md, DOC_AUTHORITY.md, SYSTEM_ARCHITECTURE.md, AGENT_RULES.md

This handbook is the repository-level implementation constitution for AI agents
and human contributors.

It converts existing repo norms into a concise build standard that can be
reused across implementation tasks.

Primary references:

- `docs/AGENT_RULES.md`
- `CLAUDE.md`
- `README.md`
- `docs/SYSTEM_ARCHITECTURE.md`

If this handbook conflicts with a stricter safety or lifecycle rule elsewhere,
the stricter rule wins.

## Runtime Baseline

- Python version: `3.12`
- Dependency policy: no unnecessary new dependencies
- Time handling: UTC internally; convert only at clearly defined boundaries
- Trading safety: never introduce lookahead bias
- Secrets policy: no secrets committed to the repository

## Architecture Principles

- Keep research, execution, risk, governance, and monitoring concerns separate.
- Prefer explicit contracts over implicit coupling.
- Do not move lifecycle semantics into ad hoc scripts when they belong in
  documented architecture or config.
- Keep stage meanings aligned with `docs/SYSTEM_ARCHITECTURE.md`.
- Favor deterministic behavior for validation and reporting code.

## Coding Standards

- Type hints are expected for public functions and dataclasses.
- Public APIs should have docstrings when behavior is not obvious.
- Keep functions focused and side effects explicit.
- Avoid duplicated business logic across modules.
- Prefer dependency injection or parameterized collaborators over hidden global
  state.
- Add comments only where they save the reader real effort.
- Preserve existing naming patterns unless there is a strong reason to change
  them.

## Testing Standards

- Every behavior change should be covered by tests.
- Add or update unit tests near the touched module area.
- Backtest, replay, and validation logic should be tested for deterministic
  behavior when feasible.
- Fixes for bugs should include a regression test.
- If a change cannot be tested locally, document the gap clearly in the task
  closeout.

## Specification Standards

Before implementation, define:

- module or feature name
- responsibility boundaries
- inputs and outputs
- public API
- acceptance criteria
- test plan
- non-goals

Use `docs/templates/implementation_spec_template.md` when the task is larger
than a one-file bug fix.

## Change Control

- New architecture or lifecycle changes require a doc-level design update.
- Public API changes should be intentional and called out in the task summary.
- Do not mix unrelated refactors into bug-fix work.
- Keep task scope narrow enough to review confidently.

## Review Checklist

Before treating work as complete, verify:

- code matches the agreed spec
- repository hard rules are still satisfied
- tests for the changed behavior exist and pass
- documentation is updated when operators or downstream callers would be
  affected
- no accidental architecture drift was introduced

## Prompting Guidance For AI Executors

Prefer prompts with:

- one clear module or behavior target
- an explicit API contract
- acceptance criteria
- boundaries on what must not change

Example:

```text
Implement `RuleValidator` according to the attached spec.
Do not change the public API.
Add tests for the listed acceptance criteria.
Do not redesign adjacent modules.
```

Avoid prompts with:

```text
Build my trading platform.
```

## Task Sizing Guidance

Good task size:

- one module
- one validator
- one report enhancement
- one CLI improvement
- one tightly scoped refactor

Task is too large if it requires:

- inventing architecture during implementation
- changing multiple subsystem contracts at once
- mixing lifecycle redesign with code generation

## Documentation Artifacts

Use these artifact types consistently:

- architecture reference: `docs/SYSTEM_ARCHITECTURE.md`
- repo/runtime change record: `docs/CHANGE_CONTROL_SYSTEM.md` + `reports/change_control/`
- implementation status: `docs/IMPLEMENTATION_STATUS.md`
- operator workflow: `docs/OPERATING_MANUAL.md`
- task contract: `docs/templates/implementation_spec_template.md`
- module-local tests: `tests/`

## Final Rule

Thinking is expensive. Repetition is cheap.

Spend reasoning effort on architecture, contracts, and review quality. Keep
implementation work narrow, testable, and obedient to the frozen spec.

## CI/CD Standards
(Status: Active baseline — update when gates change)

- Python version: 3.12
- Test runner: pytest
- Coverage: enforced for `svos` via pytest-cov baseline
- Type checking: mypy is configured and run in CI
- Linting: Ruff is configured and run in CI
- Dependency locking: runtime and development lock files exist
- CI pipeline: GitHub Actions runs tests, mypy, Ruff, migration SQL compile, secret checks, and whitespace checks

Priority:
- keep CI gate outputs aligned with generated readiness reports
- tighten type/lint scope over time instead of reporting stale “not configured” guidance
