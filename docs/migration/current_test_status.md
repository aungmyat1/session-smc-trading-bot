# Architecture Migration Current Test Status

Date: 2026-07-01
Status: Observed
Version: 1.0
Owner: Engineering
Authority: Level 7 — Migration Evidence
Related: baseline.md, safety_state.md, ../../.github/workflows/ci.yml

## Full Automated Test Command

```bash
.venv/bin/python -m pytest -q
```

Result: **CRASHED during collection** with exit code `139`.

- Passed: `0` in the full invocation; test execution never began.
- Failed assertions: `0`; collection did not complete.
- Skipped: unknown; collection did not complete.
- Total collected: unknown; collection did not complete.

The crash occurred while importing `tests/test_validate_dataset.py`. The direct
trigger is construction of `pd.Timedelta(minutes=1)` at module import in
`scripts/validate_dataset.py`. A standalone pandas import plus the same
`pd.Timedelta` call reproduces the native segmentation fault.

Locked numerical/data versions at baseline:

- `numpy==2.5.0`
- `pandas==3.0.4`
- `pyarrow==24.0.0`

### Pandas Segmentation Fault

Issue:
A pandas-related native segmentation fault prevents full test collection.

Status:
Existing before architecture migration changes.

Impact:
The canonical CI pytest gate cannot currently produce a complete pass/fail/skip
count in this environment. Dataset validation and any path constructing the
affected pandas time delta are suspect until dependency compatibility is
isolated.

Action:
Do not fix during Phase 0. Isolate as a separate remediation before relying on a
full-suite green baseline.

## Focused Safety and Boundary Tests

Command:

```bash
.venv/bin/python -m pytest -q \
  tests/architecture tests/svos tests/test_demo_execution_safety.py \
  tests/test_broker_interface_and_gate.py tests/execution \
  tests/scripts/test_validate_runtime_config.py
```

Result: **171 passed**, coverage `72.12%`, required threshold `67%` reached.

This verifies the exercised lifecycle authority, SVOS application behavior,
offline virtual demo, execution guards, broker interface, and runtime-config
safety paths. It does not replace the failed full-suite gate.

Dashboard-focused execution produced **48 passing assertions**. That subset
command exited non-zero only because global coverage was `36.70%`, below the
repository-wide `67%` threshold when most SVOS tests were intentionally absent.

## Type Checking

Command:

```bash
.venv/bin/python -m mypy
```

Result: **failed with 2 errors** in one module:

- `svos/experiments/manager.py:205`: `ExperimentManager.list` is resolved as a
  function rather than the built-in generic `list` type.
- `svos/experiments/manager.py:207`: the resulting inferred type is reported as
  non-iterable.

These failures existed at baseline and were not corrected in Phase 0.

## Lint

The exact stabilization-boundary Ruff command from CI passed with:

```text
All checks passed!
```

## Runtime Configuration Check

Command:

```bash
.venv/bin/python scripts/validate_runtime_config.py --root .
```

Result: **PASS**.

## Baseline Test Verdict

The repository is not fully green. Focused architecture and safety behavior is
well covered and passing, but the canonical full test and mypy gates fail before
the migration begins. Phase 1 must preserve these as baseline defects rather
than attributing them to separation work.

