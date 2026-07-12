# System 2 Readiness Implementation Plan

Date: 2026-07-12
Status: Draft implementation plan
Scope: Production execution system readiness; live trading remains disabled.

## Current Readiness

System 2 is ready for controlled shadow/disabled rehearsals, not paper execution
and not live trading.

Local evidence:

- `python3 scripts/validate_runtime_config.py` passes.
- `python3 scripts/health_check.py --no-broker --no-db --json` reports
  `READY (shadow mode)`.
- Focused package/deployment readiness tests pass:
  `39 passed`.

Blocking evidence:

- No strategy currently has Production Approval.
- Offline health check shows stale runner activity and no restart recovery
  state.
- Broker, database, data-feed, cloud IAM, GCS, KMS, Secret Manager and remote
  host checks were not exercised in the local offline run.
- Production runtime still needs package-bound executable strategy binding and
  unified execution contract proof.
- Risk-register rows #15, #17, #19, #20 and #21 were resolved on 2026-07-12
  with regression coverage.

## Readiness Verdict

| Capability | Readiness | Notes |
|---|---|---|
| Disabled package staging | Partial PASS | Local tests pass; remote rehearsal still required. |
| Strategy package validation | PASS locally | Package CLI/import tests pass. |
| Runtime config safety | PASS locally | Config validator passes. |
| Shadow mode health | Conditional PASS | Offline health says shadow-ready, with WARNs. |
| Paper execution | BLOCKED | Needs broker, DB, recovery, telemetry and approved package evidence. |
| Live trading | BLOCKED | Out of scope until explicit owner approval and all gates pass. |

## Implementation Plan

### Phase 1 — Close Local System 2 Safety Gaps

Status: completed for in-repo fixes on 2026-07-12.

1. Completed: `last_tick_at` is passed to `scripts/vps_health_check.sh` Python
   via argv.
2. Completed: `vps-health-check.service` no longer loads dashboard secrets.
3. Completed: System 2 operational JSON endpoints require authentication.
4. Completed: stale-tick thresholds are aligned at 180s.
5. Completed: invalid `strategy-release` GitHub CLI action reference removed.
6. Completed: regression tests added.
7. Completed: focused System 2 tests and config validation rerun.

Exit criteria:

- Focused readiness tests pass: 26 passed.
- Risk-register rows for the fixed items are updated with evidence.

### Phase 2 — Remote Disabled Deployment Rehearsal

1. Provision/verify GitHub environments:
   `strategy-release`, `paper`, `production-disabled`.
2. Configure required reviewer protections and branch/tag restrictions.
3. Provision/verify GCP Workload Identity, GCS bucket, KMS key version, Secret
   Manager references, IAM roles and production VM metadata.
4. Install the deployment poller on the target host under a non-login
   `agtrade` service account.
5. Run a fake approved-package disabled deployment rehearsal.

Exit criteria:

- Deployment reaches `STAGED_DISABLED`.
- `LIVE_TRADING=false` and `DEMO_ONLY=true` are verified on-host.
- Health, heartbeat and metrics endpoints are reachable locally on the host.

### Phase 3 — Production Runtime Binding

1. Bind imported strategy package metadata to the production runtime without
   copying research code into System 2.
2. Normalize the execution contract across `order_manager.py`,
   `trade_manager.py`, and `vantage_demo_executor.py`, or add a shim that gives
   them one consistent interface.
3. Prove one-position-per-symbol, max-open-position, daily-loss and duplicate
   order protections through tests.

Exit criteria:

- Package identity, checksum and signature remain traceable at runtime.
- Runtime can load a staged-disabled package and produce shadow-only signals.
- Execution contract tests cover success, rejection, timeout and recovery.

### Phase 4 — Broker and Telemetry Evidence

1. Run broker connectivity checks in demo mode only.
2. Add metrics/alerts for:
   - broker connection state;
   - tick freshness;
   - order latency;
   - order rejection;
   - slippage;
   - close-event feedback;
   - reconciliation status.
3. Prove periodic reconciliation clears or escalates non-terminal execution
   records mid-session.

Exit criteria:

- Broker/data-feed checks pass without live trading.
- Health and dashboard report the same freshness status.
- Reconciliation evidence is retained.

### Phase 5 — Paper Execution Gate

1. Use only a strategy with valid Production Approval.
2. Stage the approved package disabled.
3. Enable paper/demo execution only after owner approval and exact required
   environment settings are verified.
4. Run a minimum observation window with retained journal, broker, telemetry
   and reconciliation evidence.

Exit criteria:

- No critical execution failures.
- Journal, broker state and recovery store reconcile.
- Daily/weekly/monthly risk limits are proven from real close events.

## Non-Actions

- Do not enable live trading.
- Do not mark any unapproved strategy current or approved.
- Do not tune strategy parameters as part of System 2 readiness.
- Do not use ST-B1 as approval evidence; its real-data validation is BLOCKED
  by Dukascopy 403/no reachable EURUSD/GBPUSD H1+M15 data, not failed.
