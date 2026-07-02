# Demo-First Unified Trading Operations Center

## Goal

Extend the unified SVOS and trading dashboard from a two-view MVP into a demo-first operations center that keeps all trading authority in the existing Python control plane while exposing the additional operational views needed for readiness, validation, deployment, and incident handling.

## Product Shape

Serve a single React application at `/new-dashboard/` with six route-level surfaces:

- `/new-dashboard/overview`
- `/new-dashboard/live`
- `/new-dashboard/pipeline`
- `/new-dashboard/positions`
- `/new-dashboard/svos`
- `/new-dashboard/health`

The dashboard remains polling-based for the current implementation. Live execution data refreshes every three seconds. SVOS, governance, readiness, incident, and report data refresh every fifteen seconds.

## Core Principles

- Keep all mutation authority in `dashboard/app.py`.
- Preserve `DEMO_ONLY=true` and `LIVE_TRADING=false` as the operational default.
- Keep deployment, preflight, import, activation, rollback, emergency-stop, and report workflows backend-authoritative.
- Treat stale, missing, degraded, or unauthenticated states explicitly in the UI.
- Defer advanced realtime streaming, scaling, and execution analytics until stable demo validation is complete.

## Required Surfaces

### 1. Overview

- Readiness gates from infrastructure through demo-first qualification.
- Recommendation badge and current operational blockers.
- Approved package verification from strategy registry and release metadata.
- Deployment timeline from recorded deployment history.
- Operational report center with inline report viewer.
- Incident inbox with acknowledgement for `incident_operator` and `admin`.

### 2. Live

- High-level execution health, risk, broker, and emergency state.
- Existing guarded controls for emergency stop and admin-only clear.
- No new authority beyond the existing backend actions.

### 3. Pipeline

- Strategy pipeline selector.
- Latest SVOS pipeline run summary and stage status.
- Deployment creation, import, preflight, activate, and rollback workflows.
- Package verification checklist.
- Validation report viewer for indexed SVOS artifacts.

### 4. Positions

- Dedicated open position and pending-order management.
- Close, protect, and cancel controls with audit reasons.
- Trade Decision Inspector using recent trade history and matching live exposure.
- Execution and risk context beside position actions.

### 5. SVOS

- Strategy inventory and lifecycle status.
- Strategy comparison matrix across stage, version, evidence, and deployment readiness.
- Readiness and governance visibility.
- Report generation, review, and validation report viewer.

### 6. Health

- Broker, execution, runtime, and policy telemetry.
- Production heartbeat and policy guardrails.
- Monitoring, database, runner, and risk subsystem state.
- Audit timeline and readiness-policy cross-checks.

## API Usage

The operations center composes existing endpoints instead of introducing new control authority:

- `GET /api/session/me`
- `GET /api/live-dashboard`
- `GET /api/new-dashboard/overview`
- `GET /api/new-dashboard/strategies`
- `GET /api/new-dashboard/strategies/<strategy_id>/pipeline-report`
- `GET /api/new-dashboard/reports`
- `GET /api/governance`
- `GET /api/platform/readiness`
- `GET /api/rgm`
- `GET /api/smo`
- `GET /api/reports/latest`
- `GET /api/reports/<report_id>`
- `GET /api/v1/strategy-registry`
- `GET /api/v1/deployments`
- `GET /api/v1/production/health`

Existing mutation endpoints remain authoritative for:

- position close
- position protect
- order cancel
- incident acknowledgement
- emergency stop
- emergency stop clear
- deployment create
- deployment import
- deployment preflight
- deployment activate
- deployment rollback
- report review
- report generation

## Deferred Until Post-Stable-Demo

- WebSocket streaming as the primary transport
- horizontal scaling and Redis fan-out
- multi-host streaming topology
- historical replay inside the dashboard runtime
- advanced slippage and latency distributions
- MAE/MFE and execution-quality analytics expansion
- production-profit optimization surfaces

## Validation Standard

Implementation is considered valid when:

- the React app builds into `New Dashborad/dist`
- Flask serves nested SPA routes under `/new-dashboard/...`
- session/auth tests pass
- operator controls remain role-gated and stale-data guarded
- the UI shows explicit degraded states rather than synthetic placeholders
- the dashboard does not introduce any path that enables `LIVE_TRADING`
