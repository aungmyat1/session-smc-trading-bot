# Monitoring Endpoints

Date: 2026-07-02  
Status: Active  
Owner: Platform Operations

| Endpoint | Purpose | Expected consumer |
|---|---|---|
| `GET /api/v1/production/health` | Policy, heartbeat age and deployment-agent health | Load balancer, uptime monitor, operator |
| `POST /api/v1/production/heartbeat` | Authenticated component heartbeat | Production runtime/service timer |
| `GET /metrics` | Prometheus text exposition | Prometheus or compatible scraper |
| `GET /api/v1/strategy-registry` | Versions, supported symbols/brokers, deployments and rollbacks | Operational dashboard |
| `GET /api/v1/deployments` | Deployment history, optionally filtered by `strategy` | Dashboard and audit tooling |
| `GET /api/v1/production/deployments/{id}/status` | Consolidated import/preflight/activation state | Deployment automation |
| `GET /api/status` | Legacy platform health snapshot | Existing control panel |
| `GET /health/demo` | Existing demo runner state | Existing demo monitor |

The health endpoint returns HTTP 503 when the safe construction policy is
violated or a known heartbeat is stale. No heartbeat produces `UNKNOWN`, which
allows installation checks before the runtime is attached. Alert on:

- `agtrade_health == 0`
- `agtrade_live_trading != 0` during disabled rollout
- `agtrade_heartbeat_age_seconds > 120`
- repeated deployment-agent failures or a preflight `BLOCKED` verdict
- broker disconnect, order rejection, or latency threshold breach once those
  runtime metrics are attached
