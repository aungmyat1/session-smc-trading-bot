# Dashboard Boundary

Date: 2026-07-01
Status: current-state audit and target split

## Current State

Current dashboard ownership is mixed.

Active dashboard-related surfaces:

- `dashboard/app.py`
- `dashboard/live_app.py`
- `dashboard/status_server.py`
- `New Dashborad/`
- `svos/api/service.py`

Current problems:

- production runtime views and SVOS/governance views are mixed
- backends depend on local files and in-process services
- Flask and FastAPI surfaces coexist without one clean system boundary
- prototype React dashboard is oriented toward validation workflows, not production operations

## Production Dashboard Should Show

The Production dashboard is an external operator surface. It observes the
simple execution machine but is not part of the Production trading-engine
responsibility chain defined by the Original Truth.

- live positions
- open and historical orders
- broker connection state
- runtime health
- risk and exposure
- emergency controls
- alerts and incidents

## SVOS Dashboard Should Show

- experiments
- validation results
- replay and backtest evidence
- robustness results
- strategy ranking
- registry status
- approval workflow

## Recommended Split

### Production dashboard

Backend owner:

- `production/api/`
- production runtime services

Data sources:

- production engine state
- deployment state
- runtime risk and execution services

### SVOS dashboard

Backend owner:

- `svos/`
- SVOS registry/governance/report services

Data sources:

- strategy registry
- evidence
- validation reports
- approval and deployment metadata

## Current Reuse Recommendation

From the existing dashboard assessment:

- reuse selected UI patterns
- do not reuse the current backend architecture as the production live backend
- preserve only presentation components where helpful

## Migration Note

Do not attempt to make one dashboard serve both systems long term.

The correct target is:

- one production operations dashboard
- one SVOS research/governance dashboard
