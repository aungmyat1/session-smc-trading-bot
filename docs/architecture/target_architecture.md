# Target Architecture

Date: 2026-07-01
Status: proposed migration target

## Objective

Split the repository into three explicit ownership layers:

1. Production Trading Engine
2. SVOS Strategy Validation Operating System
3. Shared Trading Libraries

Core rule:

- SVOS discovers, validates, and approves strategies
- Production imports approved strategy artifacts and executes them
- Shared contains reusable contracts and pure business logic only

## Logical System Model

```text
                    SVOS Platform
                   Research / Validation

      Strategy Research
      Historical Replay
      Backtesting
      Optimization
      Monte Carlo
      Robustness Testing
      AI Strategy Improvement
      Validation Reports
      Strategy Registry

                 |
                 | versioned strategy artifact
                 v

             Production VM
           Live Trading Engine

      Market Connection
      Strategy Runtime
      Risk Engine
      Execution Engine
      Position Manager
      Portfolio
      Monitoring
      Dashboard
      Alerts
```

## Target Repository Ownership

```text
shared/
  models/
  strategy_api/
  market_data/
  indicators/
  risk_models/
  schemas/
  serialization/
  configuration/

application/
  research_service.py
  strategy_service.py
  execution_service.py
  deployment_service.py
  monitoring_service.py

production/
  engine/
    strategy_runtime/
    execution/
    risk/
    portfolio/
    orders/
    broker/
  monitoring/
  dashboard/
  api/
  deployment/

svos/
  research/
  replay/
  experiments/
  optimization/
  validation/
  robustness/
  datasets/
  ai/
  reports/
  registry/
```

## Dependency Rules

Allowed:

- `application -> shared`
- `application -> production`
- `application -> svos`
- `production -> shared`
- `svos -> shared`

Not allowed:

- `production -> svos.replay`
- `production -> svos.optimization`
- `production -> research experiments`
- `svos -> broker execution`
- `svos -> live order router`
- `svos -> live position manager`

## Runtime Contracts

### Production

Production responsibilities only:

- import approved strategy artifacts
- run strategy runtime
- enforce risk
- execute orders
- manage positions
- publish health and status

### SVOS

SVOS responsibilities only:

- strategy creation and intake
- replay and validation
- optimization and robustness
- approval workflow
- strategy artifact creation
- registry and deployment packaging

### Shared

Shared responsibilities only:

- contracts
- immutable models
- schemas
- market and indicator primitives
- serialization
- pure risk math

## Deployment Model

```text
Research/SVOS Node
  -> validate strategy
  -> create artifact
  -> register version
  -> approve deployment

Production Node(s)
  -> pull/import artifact
  -> run preflight checks
  -> activate strategy runtime
  -> report health and deployment status
```

## Success Conditions

- Production contains no research code
- SVOS contains no live broker execution
- Shared is dependency-clean and reusable
- Strategies move between systems as versioned artifacts
- Dashboards are separated by system ownership
- Multiple production instances can consume the same approved artifact
