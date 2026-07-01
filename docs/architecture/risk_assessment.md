# Architecture Risk Assessment

Date: 2026-07-01
Scope: migration risks for Production / SVOS / Shared separation

## Highest Risks

### 1. Boundary breakage during extraction

Risk:

- moving runtime code into production ownership may break current scripts and dashboards

Mitigation:

- preserve wrappers
- move behind application services first
- add import-boundary tests before file relocation

### 2. Strategy behavior drift

Risk:

- strategy code exists in multiple representations
- careless consolidation could alter validated logic

Mitigation:

- do not rewrite validated strategy logic
- extract contracts, not behavior
- add parity tests around strategy outputs before moves

### 3. Persistence split risk

Risk:

- current system uses JSON, JSONL, SQLite, and PostgreSQL together

Mitigation:

- inventory all state stores before extraction
- isolate persistence adapters per boundary
- preserve existing file-backed compatibility until new adapters are proven

### 4. Dashboard coupling risk

Risk:

- dashboards currently depend on local files, runtime internals, and SVOS control/reporting flows

Mitigation:

- separate dashboard ownership in docs first
- keep UI and backend migration independent
- move toward typed API contracts

## Medium Risks

### 5. Orchestration duplication

Risk:

- multiple SVOS orchestration paths create inconsistent behavior during migration

Mitigation:

- standardize application services above existing implementations
- retire duplicate paths only after parity

### 6. Global catalog coupling

Risk:

- `config/strategy_catalog.yaml` is a hidden shared control point

Mitigation:

- treat it as a projection during migration
- move authority into registry + control-plane services

## Lower Risks

### 7. Shared contract extraction

Risk:

- low, if limited to pure models and schemas

Mitigation:

- start with immutable contracts and helpers

## Recommended Safety Gates

Before each structural migration:

- run `pytest`
- run architecture import-boundary tests
- verify wrapper compatibility
- verify no strategy output regressions for moved code
- verify dashboards still start against current data sources if touched
