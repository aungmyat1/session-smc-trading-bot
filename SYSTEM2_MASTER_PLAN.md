# SYSTEM 2 MASTER PLAN — Production Execution Readiness

- Date: 2026-07-12
- Status: Current master plan for System 2 readiness
- Scope: System 2, the production execution layer. System 1/SVOS appears here
  only as the upstream approval/package handoff.
- Governing authority: `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`.
  If this plan conflicts with that document, the architecture truth wins.
- Safety invariant: this document does not authorize live trading, strategy
  approval, or broker-write configuration changes. `LIVE_TRADING=false` and
  `DEMO_ONLY=true` remain mandatory until the owner explicitly changes them
  after all gates pass.

---

## Executive Summary

System 2 is ready for controlled shadow/disabled rehearsals. It is not ready
for paper execution and not ready for live trading.

Local evidence collected on 2026-07-12:

- `python3 scripts/validate_runtime_config.py` passed.
- `python3 scripts/health_check.py --no-broker --no-db --json` reported
  `READY (shadow mode)`, with warnings for stale runner activity and no restart
  recovery state.
- Focused package/deployment readiness tests passed: `39 passed`.
- ST-B1 historical validation failed and is not approval evidence.
- No strategy currently has Production Approval.

The next work is not to enable more execution. The next work is to close the
remaining System 2 safety gaps, rehearse disabled deployment on the real host,
bind imported packages to the runtime, and prove broker telemetry/recovery
before any paper execution discussion.

---

## Current Readiness Verdict

| Capability | Readiness | Notes |
|---|---|---|
| Runtime configuration safety | PASS locally | Runtime validator passes. |
| Strategy package validation | PASS locally | Package/import/handoff tests pass. |
| Disabled package staging | Partial PASS | Code paths and tests pass; remote rehearsal still required. |
| Shadow-mode health | Conditional PASS | Offline health says shadow-ready but reports stale runner activity and missing recovery state. |
| Broker/data-feed evidence | BLOCKED | Skipped in local run; must be proven against demo broker only. |
| Cloud release/deploy path | BLOCKED | GitHub environments, WIF, GCS, KMS, Secret Manager and host install need proof. |
| Paper execution | BLOCKED | Requires approved package, broker evidence, durable recovery/journal proof and owner approval. |
| Live trading | BLOCKED | Out of scope; requires separate explicit approval after all production gates. |

---

## Non-Negotiable Gates

1. No live trading changes are permitted from this plan.
2. No strategy may be marked current, approved, paper-enabled or demo-enabled
   unless SVOS Production Approval exists and the execution gate is satisfied.
3. A failed strategy validation result, including ST-B1, may not be used as
   approval evidence.
4. Disabled deployment rehearsal must reach `STAGED_DISABLED`; `activated` and
   `live_trading_enabled` must remain false.
5. Every broker-write or activation-class action must retain exact-match
   confirmation-token control where applicable.
6. Broker credentials and tokens stay outside git.

---

## Open Blockers

### Strategy and Governance

- No catalog strategy is approved for release.
- ST-B1 failed historical validation: PF, Sharpe and MaxDD failed at standard
  and 2x cost stress, and 0/6 walk-forward windows passed.
- ST-A2 remains legacy/deferred from the SVOS perspective unless revalidated
  through the current gate.

### Local System 2 Safety

- Offline health reports stale runner activity.
- Offline health reports no restart recovery state.
- Phase 1 local safety issues from risk-register rows #15, #17, #19, #20 and
  #21 were fixed on 2026-07-12 with regression coverage.

### Runtime and Execution

- Imported packages are not yet fully bound to an executable production runtime
  with immutable package identity visible at signal/order time.
- Execution contracts remain split across existing order/trade/demo executor
  surfaces and need one normalized behavior for success, rejection, timeout and
  recovery.
- Broker latency, rejection, slippage, stale-feed and close-event telemetry need
  retained evidence from the actual demo path.

### Infrastructure

- GitHub protected environments and required variables need owner-side
  provisioning/proof.
- GCP Workload Identity, GCS, KMS, Secret Manager, IAM and production-host
  installation need a disabled rehearsal.
- Backup/restore, rollback, restart and network-partition drills are not yet
  complete.

---

## Target Architecture

System 2 remains deliberately simple:

```text
Approved Strategy Package
  -> package import + checksum/signature preflight
  -> STAGED_DISABLED runtime binding
  -> permission/risk/position gates
  -> execution manager
  -> broker adapter
  -> trade journal + execution state + telemetry
  -> dashboard/alerts/reconciliation
```

The production runtime must not audit, optimize, backtest or approve
strategies. It only stages, verifies, observes and executes approved packages
inside the allowed mode.

---

## Implementation Plan

### Phase 1 — Close Local Safety Gaps

Status: completed for in-repo fixes on 2026-07-12.

Tasks:

1. Completed: `scripts/vps_health_check.sh` passes `last_tick_at` via argv.
2. Completed: `vps-health-check.service` no longer loads dashboard secrets.
3. Completed: System 2 operational JSON endpoints require authentication.
4. Completed: health-check/dashboard stale-tick thresholds are aligned at 180s.
5. Completed: the invalid `strategy-release` GitHub CLI action was removed.
6. Completed: regression tests cover the above.
7. Completed: `docs/operations/risk-register.md` records the evidence.

Exit criteria:

- Focused System 2 tests pass: 26 passed.
- Runtime config validator passes.
- Risk-register rows are updated.

### Phase 2 — Remote Disabled Deployment Rehearsal

Priority: after Phase 1.

Tasks:

1. Configure GitHub environments:
   `strategy-release`, `paper`, `production-disabled`.
2. Apply required reviewer and trusted-branch/tag protections.
3. Set and verify required release variables:
   `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_RELEASE_SERVICE_ACCOUNT`,
   `SVOS_KMS_KEY_VERSION`, `SVOS_GCS_BUCKET`.
4. Provision/verify WIF, GCS, KMS, Secret Manager, IAM and production VM access.
5. Install the deployment poller on the target host under a non-login
   `agtrade` service account.
6. Run a fake approved-package disabled deployment rehearsal.

Exit criteria:

- Deployment status is `STAGED_DISABLED`.
- On-host policy confirms `LIVE_TRADING=false` and `DEMO_ONLY=true`.
- Health, heartbeat and `/metrics` are reachable locally on the host.
- Rollback record can be created without mutating package bytes.

### Phase 3 — Runtime Package Binding

Priority: after disabled rehearsal proves the deployment path.

Tasks:

1. Bind imported package metadata to runtime signal/order records:
   package ID, strategy ID, version, checksum and signature verification result.
2. Ensure runtime strategy loading uses verified package identity rather than
   ungoverned config defaults.
3. Normalize execution behavior across order placement paths:
   success, broker rejection, ambiguous timeout, retry, recovery and terminal
   failure.
4. Prove one-position-per-symbol, max-open-position, duplicate-order and daily
   loss controls in tests.

Exit criteria:

- A staged-disabled package can produce shadow-only signals with immutable
  package identity in journal/telemetry.
- No broker write can occur from an unapproved package.
- Execution contract tests pass for success, rejection, timeout and recovery.

### Phase 4 — Broker, Recovery and Telemetry Evidence

Priority: before paper execution.

Tasks:

1. Run broker connectivity and data-feed checks in demo mode only.
2. Add or verify telemetry for:
   - broker connection state;
   - tick freshness;
   - order latency;
   - broker rejection;
   - slippage;
   - close-event feedback;
   - reconciliation status;
   - non-terminal execution records.
3. Prove periodic reconciliation resolves or escalates non-terminal execution
   records mid-session.
4. Reconcile journal, broker state and execution-state store after a controlled
   restart drill.

Exit criteria:

- Broker/data-feed checks pass without live trading.
- Health and dashboard report the same freshness status.
- Reconciliation evidence is retained.
- Restart drill leaves no unexplained open, orphaned or non-terminal records.

### Phase 5 — Paper Execution Gate

Priority: only after Phases 1-4 pass and a strategy has Production Approval.

Tasks:

1. Use only an approved strategy package.
2. Stage the package disabled.
3. Verify exact environment policy and owner approval.
4. Enable paper/demo execution only; never live.
5. Run a minimum observation window with retained broker, journal, telemetry,
   risk and reconciliation evidence.

Exit criteria:

- No critical execution failures.
- Journal, broker and execution-state records reconcile.
- Risk limits are proven from real close events.
- Operator runbook covers pause, emergency stop, restart, rollback and
  recovery.

---

## Current Test Commands

Use these as the local readiness smoke set:

```bash
python3 scripts/validate_runtime_config.py
python3 scripts/health_check.py --no-broker --no-db --json
python3 -m pytest -o addopts='' \
  tests/production/test_system2_demo_readiness.py \
  tests/production/test_deployment_agent.py \
  tests/production/test_deployment_importer.py \
  tests/integration/test_canonical_package_handoff.py \
  tests/portfolio/test_strategy_package_cli.py \
  tests/portfolio/test_demo_smoke_test.py \
  tests/test_execution_validation_example_payload.py \
  tests/test_validate_strategy_package.py \
  tests/shared/test_strategy_package.py -q
```

The last recorded local run produced `39 passed`.

---

## Operator Rules

- Treat offline `READY (shadow mode)` as a narrow result, not paper readiness.
- Broker, DB and data-feed skips are blockers for paper evidence.
- Do not deploy ST-B1; it failed validation.
- Do not silently resolve registry/config mismatches by editing YAML directly.
- Do not bypass confirmation tokens for broker-write or activation-class
  actions.
- Preserve all failed validation and rehearsal evidence.

---

## References

- `docs/operations/system2_readiness_implementation_plan.md`
- `docs/operations/production_readiness_report.md`
- `docs/operations/current_operational_status.md`
- `docs/operations/deployment_runbook.md`
- `docs/operations/risk-register.md`
- `docs/operations/monitoring_endpoints.md`
- `docs/VERDICT_LOG.md`
