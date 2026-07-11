# Governance Baseline Report

Date: 2026-07-11
Status: Baseline
Owner: Platform Governance

## Executive Decision

Automated trading deployment is **not demo-ready**.

The repository now has a single practical approval source of truth:
`config/strategy_catalog.yaml`. The portfolio configuration has been aligned to
that source by disabling every strategy because no catalog strategy is approved.

No live trading was enabled, no broker credentials were modified, and no systemd
services were started.

## Approved Strategies

None.

`config/strategy_catalog.yaml` currently records:

- `current_strategy: null`
- ST-A2: `DEFERRED_REVALIDATION`, `approved: false`, `current: false`
- LondonBreakout: `approved: false`
- NYMomentum: `approved: false`
- AdaptiveSMC: `approved: false`
- VWAPMeanReversion: `approved: false`
- SMCOrderBlockFVGSession: `approved: false`
- D2E3: `approved: false`

## Active Strategy

None.

There is no catalog-approved current strategy and no strategy with an authorized
deployment target.

## Portfolio Status

`config/strategy_portfolio.yaml` is now aligned to the catalog:

| Strategy | Enabled | Mode | Governance status |
|---|---:|---|---|
| ST-A2 | false | shadow | blocked, not approved |
| LondonBreakout | false | shadow | blocked, not approved |
| NYMomentum | false | shadow | blocked, not approved |
| AdaptiveSMC | false | shadow | blocked, not approved |
| VWAPMeanReversion | false | shadow | blocked, not approved |

## Runtime Guard

The deployed runner now performs a startup governance check before opening the
broker connection. Any strategy not approved for the requested environment
raises `PermissionError` and writes a blocked runner state.

`scripts/validate_runtime_config.py` also checks enabled portfolio entries
against the catalog and fails if an unapproved strategy is enabled for
`demo`, `demo_validation`, or `live`.

## ST-A2 Package Record

Created:

- `docs/strategies/ST-A2 Approved Strategy Package/strategy_spec.md`
- `docs/strategies/ST-A2 Approved Strategy Package/validation_report.md`
- `docs/strategies/ST-A2 Approved Strategy Package/replay_results.md`
- `docs/strategies/ST-A2 Approved Strategy Package/risk_parameters.yaml`
- `docs/strategies/ST-A2 Approved Strategy Package/execution_constraints.yaml`
- `docs/strategies/ST-A2 Approved Strategy Package/approval_record.md`

Despite the requested directory name, the package records **DENIED / BLOCKED**.
It does not grant approval.

## Validation Results

### Runtime Config

Command:

```bash
python3 scripts/validate_runtime_config.py
```

Result:

```text
PASS: runtime configuration is valid
```

### Pytest

Plain system `pytest` could not start because the system Python environment does
not load the `pytest-cov` plugin required by `pytest.ini`.

The repo virtualenv has the required plugin, so the full suite was run with:

```bash
.venv/bin/pytest
```

Result:

```text
11 failed, 1755 passed, 4 skipped, 5 warnings in 86.79s
coverage: 81.61%, required 67%
```

Failing tests:

- `tests/core/test_smc_ob_fvg_session_adapter.py::TestSMCOrderBlockFVGSessionAdapter::test_generates_long_signal_on_retrace`
- `tests/database/test_db_preflight.py::test_preflight_fails_closed_when_env_missing`
- `tests/database/test_db_preflight.py::test_preflight_cli_returns_one_on_not_ready`
- `tests/svos/test_pipeline.py::test_pipeline_full_pass_all_six_phases`
- `tests/svos/test_pipeline.py::test_pipeline_full_pass_writes_approval_package`
- `tests/svos/test_pipeline.py::test_pipeline_approval_package_has_all_evidence_ids`
- `tests/svos/test_pipeline.py::test_pipeline_all_phases_have_report_artifacts`
- `tests/svos/test_pipeline.py::test_pipeline_evidence_summary_covers_all_phases`
- `tests/svos/test_pipeline.py::test_pipeline_result_to_dict_is_json_serializable`
- `tests/svos/test_pipeline.py::test_pipeline_platform_evidence_covers_all_passed_stages`
- `tests/test_capture_spreads.py::TestReconnectIfNeeded::test_not_connected_reconnect_fails`

## Documentation Debt

Command:

```bash
python3 scripts/lint_docs.py
```

Result:

- Dead links: PASS
- Header compliance warnings: 268 files
- Orphan docs: 5 files

Remaining orphan docs:

- `docs/governance/AGENT_DIRECTORY.md`
- `docs/governance/COMMAND_REFERENCE.md`
- `docs/governance/GOVERNANCE-GAP-ANALYSIS.md`
- `docs/governance/PHASE-6A-6B-GOVERNANCE-AUDIT.md`
- `docs/governance/PM-OPERATING-SYSTEM-PHASE6.md`

## Recommendation On Demo Readiness

Do **not** start Vantage demo trading.

Demo readiness remains blocked until:

1. At least one strategy has current catalog approval backed by qualifying SVOS
   evidence.
2. The full test suite is green.
3. The remaining governance documentation debt is either fixed or explicitly
   accepted by the owner.
4. The runtime uses only catalog-approved strategy deployment state.
