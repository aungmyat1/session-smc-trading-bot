# Runtime Boundary Migration Summary

## Suggested PR Title

`Refactor runtime boundaries into shared, application, and production engine layers`

## PR Summary

This change separates the repository's mixed runtime and research boundaries into explicit architectural layers while preserving current behavior.

### What changed

- Added a new `application/` layer for CLI-facing orchestration
- Added a real `shared/` layer for cross-boundary contracts and pure helpers
- Added a `production/engine` facade as the public runtime boundary
- Kept legacy import paths working through compatibility re-exports
- Migrated active callers away from legacy shared and runtime imports
- Added architecture tests to enforce the new ownership boundaries

### Key structural additions

#### `application/`

- `admin_service.py`
- `research_service.py`
- `strategy_service.py`

#### `shared/`

- `strategy_api/`
- `models/`
- `serialization/`
- `configuration/`

#### `production/engine/`

- runtime inventory facade
- runtime services facade

### Behavioral intent

This does not introduce a new runtime behavior model. It reorganizes import boundaries so:

- `agtrade` depends on `application`
- production-facing code depends on `production.engine`
- shared contracts and helpers live under `shared`
- `execution/` increasingly acts as implementation detail
- legacy modules remain as compatibility shims where needed

### Compatibility preserved

Legacy modules still work via re-export paths, including:

- `core.signal`
- `svos.shared.models`
- `svos.shared.support`

### Validation

Validated with targeted compile and regression runs throughout the migration.

Verified during migration:

- targeted regression suites passing
- architecture boundary tests passing
- `git diff --check` clean before commit

### Known environment limitation

Some adapter-related tests require `smartmoneyconcepts`, which is not installed in the current shell, so those specific tests were not runnable here. This is an existing environment dependency issue, not introduced by this change.

### Why this matters

This change turns the architecture plan into enforceable code boundaries and creates a safer path for:

- further SVOS / production separation
- future production API layering
- reducing direct dependencies on legacy top-level modules
- incremental extraction without destabilizing the runtime

## Migration Changelog

- Added `application` service layer for CLI orchestration
- Added `shared` packages for:
  - strategy signal contract
  - shared records/models
  - serialization helpers
  - configuration helpers
- Added `production.engine` facade for:
  - `ExecutionStateStore`
  - `TradingPermissionService`
  - `StrategyExecutionGuard`
  - `TradeManager`
  - managed position magic constant
- Migrated active callers from:
  - `core.signal` -> `shared.strategy_api`
  - `svos.shared.*` -> `shared.models` / `shared.serialization`
  - direct `execution.*` runtime service imports -> `production.engine`
- Added architecture tests preventing regression to legacy import paths
- Preserved backward compatibility through legacy module re-exports
