# System Health Baseline

Date: 2026-07-01
Status: Read-only audit finding — no fixes applied
Scope: Phase 6 of the deployment-topology validation audit

## pytest

Full-suite run (`.venv/bin/python -m pytest -q`) **crashes during collection**, exit code 139
(segmentation fault). This is a pre-existing, already-documented condition
(`docs/migration/current_test_status.md`, dated 2026-07-01) — not something this audit
introduced or is fixing.

- Passed: 0 in the full-suite invocation (execution never starts).
- Failed / skipped / total collected: unknown — collection does not complete.
- **Root cause (documented):** a native segfault triggered by `pd.Timedelta(minutes=1)`
  constructed at module import time in `scripts/validate_dataset.py:52-58`, reproduced with a
  standalone pandas import + the same call. Implicated versions: `pandas==3.0.4`,
  `numpy==2.5.0`, `pyarrow==24.0.0`.
- **Workaround subset** (excludes the crashing module):
  `pytest -q tests/architecture tests/svos tests/test_demo_execution_safety.py
  tests/test_broker_interface_and_gate.py tests/execution
  tests/scripts/test_validate_runtime_config.py` → **171 passed**, 72.12% coverage (exceeds the
  67% threshold). This subset covers lifecycle authority, SVOS behavior, execution guards,
  broker interface, and runtime config — it is not a substitute for a full-suite green
  baseline.

## Known issues already documented in the repo

- `docs/migration/current_test_status.md`: the pandas segfault above, explicitly marked "do not
  fix during Phase 0; isolate as separate remediation."
- mypy (`svos/lifecycle`, `svos/shared` scope per `pyproject.toml`): 2 pre-existing errors in
  `svos/experiments/manager.py:205,207` (a method named `list` shadowing the builtin, and a
  resulting non-iterable inference) — documented as baseline defects, not new regressions.
- No deprecated-dependency warnings found documented in `docs/` or the lock files.

## CI status

`.github/workflows/` contains four workflows:

- `ci.yml` ("stabilization-gates"): full pytest gate (currently failing due to the segfault
  above), mypy type-check on the canonical lifecycle modules, ruff lint on the stabilization
  boundary, Alembic migration compile check (no live credentials), committed-secrets check,
  whitespace/diff-check.
- `testing.yml`: custom Testing Agent workflow.
- `quality.yml`: custom Quality Agent + docs-lint job.
- `approval.yml`: Production Approval Gate (deployment-facing workflow; not exercised by this
  audit).

Recent CI history on `main` (last 5 runs): 3 failures, 2 cancellations — consistent with the
pytest segfault blocking the `test` job.

## Bottom line

The platform's known-issue list is small and already tracked: one blocking pandas segfault
(collection-time, isolated to `scripts/validate_dataset.py`'s import-time `pd.Timedelta` call)
and two minor pre-existing mypy errors. Neither is new information from this audit — both were
already documented as of 2026-07-01, prior to this pass. No fixes were applied.
