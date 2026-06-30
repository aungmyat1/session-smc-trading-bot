# Technical Debt

## High-Impact Issues

### 1. Mixed dashboard generations in one repo

- Legacy HTML dashboard and React SPA both exist
- a third backend model also exists in Express prototype form
- this creates architectural ambiguity and raises maintenance cost

Impact:

- unclear source of truth
- duplicate UI concepts
- duplicated API semantics

### 2. Tight filesystem coupling

The active Flask backend reads from:

- YAML catalogs
- local JSON reports
- JSONL journals
- Markdown reports
- local logs
- local control-state files

Impact:

- not deployable as a stateless production UI backend
- hard to scale
- hard to secure
- hard to make consistent under concurrent updates

### 3. SVOS and live-ops concerns are mixed

The legacy dashboard combines:

- SVOS governance
- EVF evidence
- monitoring
- trade journal
- runtime controls

Impact:

- violates the desired separation between validation dashboard and live trading dashboard
- makes reuse harder because domain boundaries are blurred

### 4. No realtime transport

- no websocket support
- no SSE
- only 30-second polling in legacy UI
- local simulation timers in React UI

Impact:

- unsuitable for live positions, executions, connectivity, and alerts

### 5. Inconsistent authentication

- mutating Flask endpoints use bearer token and actor/role headers
- many read endpoints are open
- `/api/new-dashboard/*` mutations lack the same protection
- frontend has no auth/session model

Impact:

- not safe for live account operations
- not suitable for industrial access control

### 6. Prototype-only React backend assumptions

The React app originated with:

- mock market data
- mock backtester
- strategy validation workflow
- local interval simulation

Impact:

- much of the semantics are wrong for a live dashboard even if the UI looks polished

## Medium-Impact Issues

### 7. No frontend API abstraction

- components call `fetch()` directly
- no shared client
- no typed domain adapters
- no central error handling

Impact:

- harder migration to FastAPI contracts
- brittle for auth, retries, and streaming

### 8. No route-based SPA information architecture

- React app uses internal tab state rather than real routes

Impact:

- weak deep linking
- limited navigation patterns
- poor fit for larger operational surfaces

### 9. Local control-state as operational truth

- emergency stop and acknowledgements are stored in a local JSON file

Impact:

- unsafe for multi-user or multi-instance deployment
- weak audit guarantees

### 10. Subprocess-triggered actions

- SVOS and EVF runs are started from dashboard endpoints

Impact:

- operational coupling
- long-running tasks mixed into UI server
- wrong model for production live dashboard responsibilities

### 11. Report generation inside dashboard backend

- report generation is triggered directly by the dashboard server

Impact:

- backend coupling to local scripts
- runtime unpredictability
- hard to scale

## Low-Impact / Hygiene Issues

### 12. Directory naming inconsistency

- `New Dashborad` directory is misspelled

Impact:

- signals prototype quality
- increases friction in tooling and documentation

### 13. Committed build and dependency artifacts

- built `dist/` and `node_modules/` content exist under the React app directory

Impact:

- noisy repository
- increases risk of stale assets

### 14. Duplicate API concepts across Flask and Express

- strategy CRUD and Gemini endpoints exist in both historical Express and active Flask forms

Impact:

- confusion
- documentation drift
- accidental maintenance burden

### 15. Browser alerts and inline outputs for operator feedback

- React uses `alert()`
- legacy uses text areas/output boxes instead of richer notification model

Impact:

- weak operator UX
- poor fit for critical operational events

## Security and Operational Risks

- insufficient auth coverage on dashboard read/write surfaces
- local file-backed state instead of centrally governed service state
- no explicit separation between research controls and live operations
- no streaming architecture for urgent events
- backend endpoints can trigger local scripts and mutate local files

## Debt Priority

### Must address before production reuse

- mixed concern boundary between SVOS and live ops
- filesystem coupling
- lack of realtime transport
- auth gaps
- local control-state model
- lack of proper backend/service abstraction

### Can be addressed during migration

- route structure
- notification UX
- directory cleanup
- removal of obsolete Express prototype and committed artifacts
