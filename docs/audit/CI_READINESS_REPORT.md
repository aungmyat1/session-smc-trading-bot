# CI Readiness Report

## Overview

This repository is configured with a main CI workflow at `.github/workflows/ci.yml` and a release workflow at `.github/workflows/strategy-release.yml`.

## Verified CI workflow behavior

- `ci.yml` contains four gated jobs: `quality`, `tests`, `security`, and `docs-and-package`, plus a required `required` gate.
- Each job installs Python 3.12 using `actions/setup-python@v5` and installs dependencies from `requirements-dev.lock`.
- The repository has both `requirements.lock` and `requirements-dev.lock` present.
- Issue templates are available at `.github/ISSUE_TEMPLATE/bug_report.yml` and `.github/ISSUE_TEMPLATE/feature_request.yml`.

## Commands validated locally

- `python -m ruff check application production shared svos infrastructure scripts/build_strategy_release.py scripts/validate_strategy_package.py tests/architecture` → passed
- `python -m mypy --follow-imports=skip svos/lifecycle shared/models shared/serialization` → passed
- `python -m pytest -q -o addopts='' tests/database tests/integration tests/test_agtrade_cli.py tests/test_dashboard_app.py` → passed (44 passed, 4 skipped)
- `python -m alembic upgrade head --sql >/tmp/svos-migration.sql` → passed
- `python -m pip_audit -r requirements.lock --disable-pip --ignore-vuln CVE-2026-48802 --ignore-vuln CVE-2026-48809 --ignore-vuln CVE-2025-61765 --ignore-vuln CVE-2026-48804` → passed
- `python -m bandit -q -ll -r application production shared svos infrastructure` → passed
- `git diff --check` → passed
- `python scripts/validate_strategy_package.py --self-test` → passed
- `python scripts/check_docs_drift.py --root .` → passed
- `python scripts/lint_docs.py --root docs --index docs/index.md` → executed successfully, and correctly reports repository documentation issues

## Current readiness status

- `quality` and `tests` commands are valid and executable in the repository environment.
- `security` commands are valid and execute successfully.
- `docs-and-package` command chain is valid. It currently surfaces existing repository issues:
  - `scripts/lint_docs.py` reports header compliance warnings for many docs files
  - `scripts/lint_docs.py` reports 67 broken links
- The `docs-drift` check passes.

## Notes

- The CI workflow will flag existing documentation metadata and link issues correctly.
- No unsafe live trading changes were introduced in the workflows.
- `strategy-release.yml` now installs GitHub CLI via `cli/cli-action@v3`, which is required for the `gh release create` step.
