---
Date: 2026-07-05
Status: Audit complete
Scope: CI/CD configuration health — main and develop
Owner: Repository governance
Related: docs/audit/DEPENDENCY_UPDATE_PLAN.md, .github/workflows/, .github/dependabot.yml
---

# CI/CD Health Report

## Mandatory workflow coverage (`main`, `.github/workflows/ci.yml`)

| Requirement | Status | Where |
|---|---|---|
| Lint | **Implemented** | `quality` job — `ruff check` (application/production/shared/svos/infrastructure + release scripts + `tests/architecture`) + `mypy` (scoped to `svos/lifecycle`, `shared/models`, `shared/serialization`) |
| Unit tests | **Implemented, with a gap** | `tests` job, `unit` matrix leg — `tests/production tests/svos tests/execution` (`test_pipeline.py` explicitly ignored). **`tests/core/*` and `tests/test_status_server.py` are never run on `main`'s CI** — not in either the `unit` or `integration` matrix path. |
| Integration tests | **Implemented** | `tests` job, `integration` matrix leg — `tests/database tests/integration` + CLI/dashboard tests |
| Coverage threshold | **Configured but not enforced by CI** | `pyproject.toml` sets `--cov=svos --cov-fail-under=67` as a pytest default, but the CI `tests` job runs with `-o addopts=''`, explicitly disabling it. The gate only fires if someone runs bare `pytest` locally. |
| Security / dependency scanning | **Implemented** | `security` job — `pip_audit` against `requirements.lock` (4 CVE waivers, justified inline given live trading is disabled) + `bandit` static scan + a secret-pattern grep. Dependabot also runs weekly (pip + github-actions). |
| Docker build/publish | **Missing** | No Dockerfile anywhere in the repo; `deploy-production.yml` deploys via `gcloud compute ssh` to a persistent VM/venv, not a container. |

A synthetic `required` job (`needs: [quality, tests, security, docs-and-package]`, `if: always()`) is what surfaces as the **"Required CI"** check — the only status check branch protection actually requires (`required_approving_review_count: 0`). `deploy-production.yml` and `strategy-release.yml` are `workflow_dispatch`-only, not part of PR gating.

## CircleCI

Confirmed: no `.circleci/config.yml` exists anywhere on `main`. "CircleCI Pipeline" is a live GitHub App check-suite integration that fires on every push/PR regardless of a config file's existence, always reporting "No configuration was found." It is **not** in the required-checks list — PRs merge clean with it red (confirmed on PR #21 and #22).

**Recommendation: leave it as cosmetic noise for now, but it should eventually be disabled properly.** Disabling it isn't reachable via `gh api` — there's no repo-scoped endpoint to remove a third-party GitHub App's check-suite subscription. It requires either revoking the CircleCI GitHub App's repository access (GitHub → Settings → Integrations → GitHub Apps, needs repo-admin) or removing the project from CircleCI's own project list at circleci.com. Both are outside this audit's reach — flagging as an action item for whoever holds admin access, not a migration plan, since there's nothing to migrate (no config ever existed to port to Actions).

## `develop` branch CI — materially worse than previously understood

`develop`'s workflows have **diverged from `main`'s, not just gone stale**:
- `main`'s `ci.yml` is `develop`'s `stabilization-gates.yml` — renamed, and rewritten against a `db/`/`data/`/`adaptive/` directory layout that doesn't match `main`'s current `application/production/shared/svos` layout.
- Three extra workflow files exist only on `develop` (`approval.yml`, `quality.yml`, `testing.yml`) — a parallel "Testing/Quality/Approval Agent" CI system (`scripts/run_testing_agent.py`) not present on `main` at all.

**Root causes of `develop`'s 3 failing checks (confirmed from actual run logs, not assumed):**
1. **"Docs Lint" job**: `ModuleNotFoundError: No module named 'yaml'` — this job runs `lint_docs.py` right after `setup-python` with **no pip-install step at all**. Trivial fix: add a `pip install -r requirements-dev.lock` step before the script runs.
2. **`stabilization-gates` / `test` job**: bare `pytest -q` with no path scoping (unlike `main`'s `ci.yml`) sweeps in `tests/core/test_smc_ob_fvg_session_adapter.py` and `tests/core/test_st_a2_adapter.py` (both need `smartmoneyconcepts`, present in **neither** `main`'s nor `develop`'s lock file) plus `tests/test_status_server.py` (needs `fastapi`, present in `main`'s lock but missing from `develop`'s stale lock) → 3 **collection errors**, not real test failures. Real fix: add `smartmoneyconcepts` to the dependency set and regenerate the hashed lock (not a one-line YAML edit), refresh `develop`'s lock to include `fastapi`, or scope this job's pytest paths the way `main`'s `ci.yml` already does.
3. **"Testing Agent" job**: surfaces the same 3 collection errors through its own custom JUnit reporting.

`main`'s own `ci.yml` sidesteps all of this by never pointing pytest at `tests/core/` or `tests/test_status_server.py` — which is itself the unit-test coverage gap noted above.

## `develop` vs `main` sync

Not just "5 commits behind" — currently a different pipeline generation. `.github/dependabot.yml` targets `develop` for both `pip` and `github-actions` ecosystems, but `develop`'s lock file and workflow layout predate `main`'s current structure by enough that treating `develop`'s CI state as representative of `main`'s is invalid.

**Recommendation:** either (a) fast-forward/merge `main` into `develop` and retire the divergent workflow files in favor of `main`'s, or (b) if `develop` is meant to keep its own separate Agent-based CI system intentionally, decide that explicitly and stop treating its failures as blocking for Dependabot bumps that target `main`-equivalent code. Given `develop` currently has no unique commits ahead of `main` (per the earlier `BRANCH_AUDIT.md`), option (a) is the lower-risk path.
