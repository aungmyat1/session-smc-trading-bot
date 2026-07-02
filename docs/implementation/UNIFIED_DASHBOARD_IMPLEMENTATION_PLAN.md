# Unified SVOS and Trading Operations Dashboard

## Summary

Replace the simulated dashboard backend with the existing Python control plane while retaining the combined React interface. Deliver a production MVP with two views—Live Operations and SVOS Research—served at `/new-dashboard/`, using three-second polling and authenticated operational controls.

The dashboard may operate against an already authorized live environment, but it cannot enable `LIVE_TRADING` or bypass lifecycle, deployment, preflight, risk, or emergency-stop gates.

## Implementation Changes

### React dashboard

- Make `New Dashborad/Two system on one Dashboard` the source for the production dashboard and configure Vite to build into `New Dashborad/dist` with base path `/new-dashboard/`.
- Replace `SocketContext` with an abortable polling data provider:
  - Fetch `/api/live-dashboard` every three seconds.
  - Fetch SVOS registry, validation, deployment, readiness, reports, governance, and health data on page entry and every 15 seconds.
  - Retain the last valid snapshot during temporary failures.
  - Mark data stale after ten seconds and disable all mutations while stale, unauthenticated, broker-disconnected, or already pending.
- Replace simulated `LiveDashboardState` with typed adapters for the existing Python responses. Components must render explicit unavailable states rather than fabricated values.
- Keep two primary navigation areas:
  - **Live Operations:** account/equity, positions, orders, market watch/chart, execution, risk, broker/system health, history, and emergency state.
  - **SVOS Research:** strategy registry, validation stages, evidence/reports, readiness, deployment progression, and approved packages.
- Implement controls only for existing authoritative workflows:
  - Close or protect a position.
  - Cancel a pending order.
  - Emergency stop and admin-only clear.
  - Deployment import, preflight, activation, and rollback.
  - Report review/generation where the user's role permits it.
- Require confirmation dialogs with reason fields for destructive operations. Emergency-stop confirmation must use the backend's required tokens.
- Remove UI actions backed only by the simulation server, including arbitrary pause/resume, analytics reset, risk-setting mutation, broker reconnect, and direct strategy activation.
- Remove Gemini requirements from this dashboard MVP and exclude `server.ts`, Express, WebSocket, and simulation state from production scripts and dependencies.

### Python APIs and authentication

- Continue serving the built React application from `dashboard/app.py`; retain the existing API and audit-log authorities.
- Add `GET /api/session/me`, returning authenticated actor, mapped role, permitted actions, trading mode, demo/live flags, and whether data mutations are currently allowed.
- Extend authentication to support a trusted reverse-proxy identity:
  - Flask binds only to loopback.
  - Nginx strips all incoming identity/role headers.
  - oauth2-proxy authenticates through OIDC and supplies the verified email.
  - Nginx maps verified emails/groups through an explicit deployment allowlist to `research_operator`, `incident_operator`, `risk_operator`, or `admin`.
  - Nginx injects an internal shared-secret header; Flask accepts proxy identity only when that secret matches.
  - Preserve bearer-token authentication for existing CLI/automation compatibility.
- Use same-origin secure cookies through oauth2-proxy and reject mutating requests without a valid same-origin/CSRF header.
- Keep all current backend validation, role checks, audit records, package verification, preflight checks, and live-environment guards authoritative. The frontend must never infer authorization.
- Normalize API errors to include `error`, optional `code`, and `fetched_at`; do not hide broker or control failures behind successful HTTP responses.
- Add a lightweight aggregate SVOS read endpoint only if existing calls cannot populate the view efficiently; it must compose existing services and introduce no new lifecycle authority.

### Deployment and operation

- Add deployment templates for Nginx, oauth2-proxy, environment variables, role mapping, and systemd services without provisioning external cloud resources.
- Expose only Nginx over TLS/private networking; keep Flask and oauth2-proxy listeners private.
- Document OIDC client configuration, secret placement, token rotation, allowed users/groups, build commands, service startup, health checks, and rollback to the previous dashboard assets.
- Preserve `DEMO_ONLY=true` and `LIVE_TRADING=false` as defaults. Real-money enablement remains an external, explicitly authorized operational procedure.
- Build assets before backend deployment, retain the prior `dist` directory as a rollback artifact, restart only the dashboard service, and verify the trading runtime remains uninterrupted.

## Public Interfaces

- New: `GET /api/session/me`.
- Existing read endpoints remain compatible, particularly `/api/live-dashboard`, strategy registry/validation, deployments, production health, readiness, governance, and reports.
- Existing mutation endpoints remain authoritative; no `/api/action` or simulated `/api/live/*` routes are introduced.
- Frontend types mirror backend payloads and use nullable fields for unavailable broker, SVOS, or analytics data.
- Polling requests use `AbortController`, prevent overlapping calls, and append no-cache timestamps where needed.

## Test Plan

- Frontend unit tests cover payload adapters, unavailable fields, stale-state handling, role-based controls, confirmation dialogs, mutation errors, and polling cleanup.
- Frontend integration tests cover both views using recorded Python API fixtures; assert that no simulated prices, trades, health, or analytics appear.
- Backend tests cover `/api/session/me`, proxy-secret validation, stripped/spoofed header rejection, role mapping, bearer compatibility, CSRF/origin checks, and audit attribution.
- Control tests verify close/protect/cancel, deployment progression, rollback, emergency stop, and admin-only clear under allowed and forbidden roles.
- Safety tests verify controls are disabled on stale data, lost authentication, broker uncertainty, duplicate submission, and failed preflight.
- Build test runs TypeScript checking and the production Vite build, then verifies Flask serves the SPA and nested routes from `/new-dashboard/`.
- Acceptance smoke test runs in demo mode through oauth2-proxy, exercises one authorized non-destructive workflow and emergency-stop confirmation, confirms audit records, and verifies the dashboard cannot modify `LIVE_TRADING`.

## Assumptions

- Production MVP uses polling, not WebSocket or SSE.
- OAuth2 Proxy and Nginx are the authentication boundary; OIDC provider-specific credentials are supplied during deployment.
- VPS 1 hosts the dashboard and execution control plane; SVOS remains isolated on the research node.
- Current Python services and persisted artifacts remain the system of record.
- “Live-capable controls” means controls may operate when the environment was independently authorized for live trading; it does not authorize this implementation to enable live trading.
