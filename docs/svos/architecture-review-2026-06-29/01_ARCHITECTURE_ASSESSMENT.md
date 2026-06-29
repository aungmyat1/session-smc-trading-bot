# Architecture Assessment

## Current shape

The repository is a modular monolith with several partially overlapping
subsystems rather than one layered SVOS application:

```text
dashboard/scripts
  ├─ research/svos + research/validation
  ├─ strategy_validation + strategy_audit
  ├─ simulator + src/backtest
  ├─ execution_validation + execution_simulator + virtual_broker
  ├─ execution + adaptive + strategies
  ├─ core legacy registry/runtime abstractions
  └─ svos integration/control package
       └─ imports legacy core catalog services
```

The import inventory confirms reciprocal top-level dependencies between
`research` and `scripts`, and between `research` and `execution_validation`.
The new `svos` package depends on legacy `core`, so it is not yet the inward,
stable domain center described in the architecture documents.

## Strengths

- Domains such as audit, replay, execution validation, risk, and reporting are
  identifiable and independently testable.
- Dependency injection is used in selected services, including the operational
  API, platform orchestration, and broker abstractions.
- Research calculations are generally separated from broker connectivity.
- The lifecycle and governance models are small enough to become the canonical
  application core.
- Generated artifacts are separated from source and mostly ignored by Git.

## Findings

| ID | Severity | Finding | Technical impact |
|---|---|---|---|
| A-01 | Critical | Dual lifecycle mutation paths | Governance invariants can be bypassed |
| A-02 | High | No authoritative package boundaries | Changes propagate across scripts and domains |
| A-03 | High | Five overlapping validation/audit areas | Divergent rules and duplicate concepts |
| A-04 | High | Embedded repository under `session_smc/` | Duplicate runtime code and ambiguous imports |
| A-05 | High | God modules: research SVOS 1,915 lines; dashboard 842; stage reports 765 | High change risk and weak unit boundaries |
| A-06 | High | Scripts are imported as application services | CLI concerns leak into domain and dashboard |
| A-07 | Medium | Empty target packages (`experiments`, `notifications`, `ui`, `dashboard`) | Architecture claims exceed implementation |
| A-08 | Medium | 84 top-level docs and multiple status sources | Operators cannot reliably identify authority |
| A-09 | Medium | Configuration loaded ad hoc throughout code | Validation/default behavior can diverge |
| A-10 | Medium | Domain models duplicated (`Signal`, orders, trades, stage results) | Adapter and serialization drift |

### A-01 evidence

`research/svos/engine.py` and `research/validation/engine.py` import and call
`core.strategy_registry.promote_strategy_stage()`. That function directly
writes `config/strategy_catalog.yaml`; it does not require evidence, version
lineage, a gate decision, or approval. `svos.registry.transition()` is guarded,
but it is not the only mutation path.

### A-04 evidence

`session_smc/session-smc-trading-bot-replay/session-smc-trading-bot-main/`
contains a second strategy/replay/scripts tree. Additional duplicated session
bot implementations exist beside it. These files are outside `archive` and
some active scripts/tests reference the surrounding `session_smc` domain.

## Target architecture

Use a modular monolith first. Microservices would increase operational burden
without fixing authority or data consistency.

```text
interfaces/
  cli/                 argument parsing only
  http/                authenticated API only
application/
  strategy_service     use cases and transactions
  qualification        stage orchestration
  deployment           controlled handoff
domain/
  strategy             specification/version entities
  lifecycle            stages, policies, decisions
  evidence             artifact/run contracts
ports/
  repositories         persistence protocols
  research             replay/backtest/robustness protocols
  execution            virtual/live execution protocols
adapters/
  postgres             control and metadata repositories
  object_store         immutable artifacts
  duckdb_parquet       analytical data
  broker               MetaAPI/MT5
  legacy               temporary compatibility adapters
```

Dependency rule: interfaces and adapters depend inward; domain imports no
Flask, SQLAlchemy, broker SDK, scripts, or filesystem paths. Enforce this with
an architecture test.

## Recommended decisions

1. Declare `svos` the canonical application namespace, then move its dependency
   from concrete `core` helpers to repository protocols.
2. Make legacy catalog state a read-only compatibility projection.
3. Consolidate `strategy_validation` and the relevant parts of
   `strategy_audit` behind one `StrategyAuditPort`; retain algorithms as
   adapters until parity tests permit deletion.
4. Split `research/svos/engine.py` into stage handlers and a thin orchestrator.
5. Move dashboard subprocess/report logic behind application services.
6. Move the embedded replay repository to `archive` after parity verification.
7. Establish ADRs for lifecycle, persistence, artifact storage, time semantics,
   and quantitative precision.

## Acceptance criteria for architecture readiness

- One public lifecycle mutation API and no direct catalog status writes.
- Dependency tests reject domain-to-interface/adapter imports.
- Every active top-level package has a documented owner and responsibility.
- Legacy paths have removal milestones and parity tests.
- No active nested repository or copied strategy implementation.
- Application services can run without Flask, CLI parsing, or broker SDKs.

