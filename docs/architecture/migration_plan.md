# Migration Plan

Date: 2026-07-01
Status: architecture migration roadmap

## Principles

- do not rewrite validated strategy logic
- prefer extraction over replacement
- keep legacy wrappers during migration
- separate ownership before optimizing internals
- preserve existing SVOS workflows until replacement is proven

## Stage Order

### Stage 1

Audit and documentation only.

Deliverables:

- current architecture assessment
- ownership inventory
- dependency graph
- target architecture definition
- boundary risks

### Stage 2

Create structural boundaries without moving behavior.

Actions:

- add `shared/`, `application/`, and `production/` package roots
- add import-boundary architecture tests
- map existing files to destination ownership
- keep compatibility wrappers in place

### Stage 3

Extract shared contracts.

Priority extraction set:

- strategy contracts
- signal models
- market/bar data contracts
- serialization helpers
- pure risk math
- shared configuration models

### Stage 4

Create application service layer.

Service targets:

- `application/research_service.py`
- `application/strategy_service.py`
- `application/execution_service.py`
- `application/deployment_service.py`
- `application/monitoring_service.py`

Goal:

- `agtrade` calls application services
- scripts become wrappers or are retired

### Stage 5

Establish production engine boundary.

Actions:

- move runtime components behind `production/engine`
- isolate broker, execution, orders, risk, portfolio, strategy runtime
- add tests preventing production import of SVOS and research packages

### Stage 6

Consolidate SVOS ownership.

Actions:

- absorb replay, robustness, validation, and execution-qualification logic into explicit SVOS subpackages
- leave compatibility import bridges where needed

### Stage 7

Implement strategy artifact and registry system.

Actions:

- define versioned package layout
- create artifact manifest schema
- store validation and deployment history
- add deployment import workflow

### Stage 8

Separate deployment and scaling model.

Actions:

- formalize SVOS node versus production node
- support multiple production consumers of approved artifacts
- align dashboard/API contracts to system boundaries

## First Extraction Priorities

1. Shared contracts from `core/`
2. Application services around `agtrade`
3. Production wrapper around `execution/` and `strategies/`
4. SVOS consolidation around `svos/`, `strategy_validation/`, `strategy_audit/`, and `execution_validation/`
5. Dashboard split

## Compatibility Strategy

- keep existing scripts as wrappers
- maintain current SVOS workflow commands
- preserve current test suite
- add new architecture tests before moving high-risk runtime code

## Exit Criteria

- production-only modules contain no research imports
- SVOS modules contain no live broker imports
- strategy deployment uses artifacts, not manual code copying
- dashboards are separated by ownership and data source
