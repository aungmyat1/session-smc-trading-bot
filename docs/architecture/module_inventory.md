# Module Ownership Inventory

Date: 2026-07-01
Scope: active repository packages and operational module roots

Classification rule:

- `Production` = live/demo runtime, broker, order, risk, position, monitoring, production dashboard
- `SVOS` = research, replay, validation, robustness, evidence, governance, registry
- `Shared` = reusable contracts, schemas, models, pure business logic
- `Shared/Application` = orchestration or control surfaces that coordinate bounded subsystems
- `Legacy/Transitional` = active but should be migrated behind a boundary
- `Archive` = historical only

No active module below is left unclassified.

## Inventory

| Module | Owner | Current status | Notes |
| --- | --- | --- | --- |
| `agtrade/` | Shared/Application | Active | Canonical CLI surface; should remain the operator control layer |
| `core/` | Shared -> Production candidate | Transitional | Contains shared domain contracts plus runtime-specific portfolio and registry behavior |
| `execution/` | Production | Active | Broker, execution state, permission, trade and order runtime |
| `monitoring/` | Production | Active | Runtime alerting and logging helpers |
| `strategies/` | Production | Active | Runtime adapters and strategy integration |
| `strategy/` | SVOS | Active | Research strategy logic used in replay/backtest workflows |
| `session_smc/` | Legacy/Transitional | Partially used | Historical strategy/replay code with overlap against newer strategy packages |
| `adaptive/` | Legacy/Transitional | Partially used | Older adaptive runtime/research stack |
| `svos/` | SVOS | Active | Core lifecycle, governance, registry, orchestration, reporting |
| `research/` | SVOS | Active | Validation, robustness, queue, lineage, SVOS bridge |
| `strategy_validation/` | SVOS | Active | Pre-replay specification validation |
| `strategy_audit/` | SVOS | Active | Strategy audit framework |
| `execution_validation/` | SVOS | Active | Execution qualification and replay bridge |
| `execution_simulator/` | SVOS | Active | Virtual broker, fill, risk, replay simulator |
| `virtual_broker/` | Shared -> SVOS support candidate | Transitional | Simulation primitives reusable by validation |
| `db/` | Shared/Application | Active | Cross-boundary persistence layer; needs later split into production and SVOS adapters |
| `research_db/` | SVOS | Partially used | Research-only storage helpers and datasets |
| `pipeline/` | SVOS | Partially used | Legacy research feature/replay pipeline |
| `src/` | SVOS | Partially used | Legacy research engine implementation |
| `dashboard/` | Mixed; split required | Active | Currently mixes production runtime status, operator control, and SVOS report/control surfaces |
| `data/` | Shared infrastructure | Active | Mixed runtime and research artifact/data storage; should be partitioned by ownership |
| `models/` | Shared | Active | Low-level domain models |
| `schemas/` | Shared | Active | JSON schema contracts |
| `scripts/` | Shared/Application | Active | Orchestration surface spanning production, SVOS, and migration wrappers |
| `deploy/` | Shared/Application | Active | Deployment manifests and operational environment docs |
| `tests/architecture/` | Shared/Application | Active | Architecture enforcement tests |
| `tests/execution/` | Production | Active | Production runtime coverage |
| `tests/svos/` | SVOS | Active | SVOS pipeline coverage |
| `tests/research_engine/` | SVOS | Active | Research engine coverage |
| `tests/database/` | Shared/Application | Active | Persistence and control-plane contracts |
| `New Dashborad/` | SVOS UI prototype | Transitional | Validation workstation UI, not production live dashboard |
| `archive/` | Archive | Inactive | Historical only |

## Ownership By Concern

### Production

- `execution/`
- `monitoring/`
- `strategies/`
- production-facing subset of `core/`
- production-facing subset of `dashboard/`
- production runtime scripts

### SVOS

- `svos/`
- `research/`
- `strategy_validation/`
- `strategy_audit/`
- `execution_validation/`
- `execution_simulator/`
- `strategy/`
- research pipeline scripts and reports

### Shared

- contracts in `core/`
- `models/`
- `schemas/`
- configuration models and serialization helpers
- pure simulation and market primitives

## Immediate Migration Mapping

### Source candidates for future `shared/`

- `core/base_strategy.py`
- `core/signal.py`
- `core/broker_interface.py`
- `models/`
- `schemas/`
- pure risk/math helpers from `execution/` and simulation code

### Source candidates for future `production/`

- `execution/`
- runtime portions of `core/`
- `strategies/`
- `monitoring/`
- live/demo dashboard and production status APIs

### Source candidates for future `svos/` consolidation

- existing `svos/`
- `strategy_validation/`
- `strategy_audit/`
- `research/validation`
- `research/robustness`
- `execution_validation/`
- `execution_simulator/`
- `pipeline/` and `src/` where still needed
