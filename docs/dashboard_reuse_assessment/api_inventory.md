# API Inventory

## Summary

The active dashboard API surface is the Flask application in `dashboard/app.py`.

The React app also has a historical Express mock API in `New Dashborad/server.ts`. That mock API is useful only as prototype context and should not be reused.

No WebSocket endpoints were found.

## Active Flask REST Endpoints

| Method | URL | Purpose | Request | Response | Dependencies | Reuse |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/status` | top-level system summary | none | system, strategy, EVF, trade count, risk, governance, monitoring, emergency status | health checks, reports, control state, trade logs, SVOS snapshots | Replace with production status aggregator |
| `GET` | `/api/svos` | SVOS strategy and stage summary | none | strategy list, current report, stage reports, canonical run | YAML catalog, SVOS reports | Keep separate from live dashboard |
| `POST` | `/api/svos/run` | trigger SVOS run | confirm token, strategy | status, returncode, output | subprocess, audit log | Do not reuse in live dashboard |
| `GET` | `/api/evf` | EVF validation summary | none | validation metrics and checks | EVF report JSON | Optional support screen only |
| `POST` | `/api/evf/run` | trigger EVF run | confirm token, strategy, payload path | status, returncode, output | subprocess, audit log | Do not reuse in live dashboard core |
| `GET` | `/api/trades` | recent trades and summary stats | none | stats + recent trades | local journal JSONL | Replace with production order/trade service |
| `GET` | `/api/demo-runner` | runtime/demo runner state | none | runner payload | local JSON state | Replace with production execution/broker service |
| `GET` | `/api/platform` | operational API overview | none | combined platform snapshot | `SVOSOperationalAPI` | Keep only for SVOS side |
| `GET` | `/api/platform/registry` | registry snapshot | none | registry detail | `SVOSOperationalAPI` | Keep only for SVOS side |
| `GET` | `/api/platform/strategies/<strategy>` | strategy snapshot | none | strategy detail | `SVOSOperationalAPI` | Keep only for SVOS side |
| `GET` | `/api/platform/readiness` | readiness reports + persistence | none | production readiness, testing, quality, stabilization, persistence | local report JSON + SVOS platform | Keep only for SVOS side |
| `GET` | `/api/new-dashboard/overview` | React SPA overview payload | none | overview + readiness + latest reports | SVOS API + local reports | Replace with production live overview API |
| `GET` | `/api/new-dashboard/strategies` | list strategy overlays | none | list of React strategy objects | strategy overlay service | Do not reuse for live ops |
| `POST` | `/api/new-dashboard/strategies` | create strategy overlay | body with strategy spec | created strategy | strategy overlay service, audit log | Do not reuse |
| `GET` | `/api/new-dashboard/strategies/<strategy_id>` | get strategy overlay | none | strategy detail | strategy overlay service | Do not reuse |
| `PUT` | `/api/new-dashboard/strategies/<strategy_id>` | patch strategy overlay | JSON patch | updated strategy | strategy overlay service | Do not reuse |
| `POST` | `/api/new-dashboard/strategies/<strategy_id>/promote` | move lifecycle stage forward | none | updated strategy | strategy overlay service, audit log | Do not reuse |
| `POST` | `/api/new-dashboard/strategies/<strategy_id>/demote` | move lifecycle stage backward | target stage, comments | updated strategy | strategy overlay service, audit log | Do not reuse |
| `POST` | `/api/new-dashboard/gemini/parse` | parse trading idea into strategy spec | `{text}` | parsed JSON strategy proposal | Gemini service | Do not reuse |
| `POST` | `/api/new-dashboard/gemini/explain-failure` | AI explanation of losing trades | `{trades}` | diagnosis JSON | Gemini service | Optional analyst tool, not live core |
| `GET` | `/api/new-dashboard/strategies/<strategy_id>/pipeline-report` | fetch pipeline report | none | pipeline report | strategy overlay service + SVOS reports | Do not reuse |
| `GET` | `/api/new-dashboard/reports` | list reports for SPA | none | report index | report service | Partial reuse |
| `GET` | `/api/rgm` | risk qualification summary | none | risk, portfolio, emergency stop, breaches | local health checks, control state | Replace with production risk/portfolio service |
| `GET` | `/api/governance` | governance summary | none | approval, promotion map, architecture | YAML + docs | Keep separate from live dashboard |
| `GET` | `/api/smo` | monitoring and incidents | none | runner, db, risk, incidents, audit, emergency state | health checks, logs, audit log, control state | Replace with production monitoring API |
| `GET` | `/api/reports` | report index | none | report index | report service | Partial reuse |
| `GET` | `/api/reports/latest` | latest report pointers | none | latest reports + recommendation badge + review map | report service, control state | Partial reuse |
| `GET` | `/api/reports/<report_id>` | read report content | optional query `reviewed=1` rejected on GET | report detail + content | filesystem | Partial reuse |
| `POST` | `/api/reports/<report_id>/review` | mark report reviewed | authenticated POST | reviewed_at | control state, audit log | Partial reuse |
| `POST` | `/api/reports/generate` | generate report type | `{type}` | artifacts + latest | local script generator | Do not reuse backend |
| `POST` | `/api/reports/generate/all` | generate all reports | none | artifacts + latest | local script generator | Do not reuse backend |
| `POST` | `/api/incidents/ack` | acknowledge incident | `{incident_id}` | reviewed_at | control state, audit log | Replace with production incident service |
| `POST` | `/api/emergency-stop` | set emergency stop state | confirm token, reason | emergency stop state | control state, audit log | Replace with production kill-switch API |
| `POST` | `/api/emergency-stop/clear` | clear emergency stop | confirm token, reason | emergency stop state | control state, audit log | Replace with production kill-switch API |

## Static Routes

| Method | URL | Purpose |
| --- | --- | --- |
| `GET` | `/` | redirects to `/new-dashboard/` |
| `GET` | `/legacy` | serves legacy dashboard HTML |
| `GET` | `/new-dashboard/` | serves React SPA shell |
| `GET` | `/new-dashboard/<path>` | serves built assets or SPA fallback |

## Historical Express Prototype API

Located in [New Dashborad/server.ts](../../New%20Dashborad/server.ts:166).

| Method | URL | Purpose | Reuse |
| --- | --- | --- | --- |
| `GET` | `/api/strategies` | list in-memory strategies | No |
| `GET` | `/api/strategies/:id` | get strategy | No |
| `POST` | `/api/strategies` | create strategy | No |
| `PUT` | `/api/strategies/:id` | update strategy | No |
| `DELETE` | `/api/strategies/:id` | delete strategy | No |
| `POST` | `/api/gemini/parse` | Gemini parsing | No |
| `POST` | `/api/strategies/:id/promote` | stage promotion | No |
| `POST` | `/api/strategies/:id/demote` | stage demotion | No |
| `POST` | `/api/gemini/explain-failure` | AI diagnosis | No |

Why not reusable:

- in-memory store with JSON backup
- mock market data and mock backtester
- prototype-only domain model
- not connected to production services

## Authentication Notes

Protected Flask endpoints use:

- `Authorization: Bearer <token>`
- `X-SVOS-Actor`
- `X-SVOS-Role`

Protection is inconsistent:

- many read endpoints are open
- `/api/new-dashboard/strategies` mutations are currently unauthenticated

This is not acceptable for a production live trading dashboard.

## WebSocket Audit

No WebSocket routes or socket server implementations were found in:

- Flask backend
- legacy HTML frontend
- React frontend
- Express prototype server

Realtime behavior today:

- 30-second polling in the legacy page
- local simulation intervals in React components

Production implication:

- websocket or server-sent-event architecture must be added through the production FastAPI backend for prices, positions, orders, execution events, alerts, and heartbeat updates
