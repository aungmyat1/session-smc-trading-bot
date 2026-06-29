# SVOS Coding Rules
# Python 3.12 — apply these standards to all new code.

---

## Style

- Type hints required on all function signatures.
- Dataclasses with `frozen=True, slots=True` for value objects (TransitionCommand pattern).
- `@dataclass(frozen=True, slots=True)` not Pydantic for internal domain objects.
- Pydantic only for: API request/response bodies, JSON schema validation.
- No mutable default arguments.
- Raise specific exceptions, not bare `Exception`.

---

## Naming Conventions

- Strategy identity: always `strategy_id: str` (the catalog slug, e.g. "london-breakout")
- Stage names: always use canonical enum names from `svos/lifecycle/manager.py`
  (`DRAFT`, `INTAKE`, `AUDIT`, etc.). Never use "Phase N" without citing the source.
- Evidence trust: `QUALIFYING_REAL | SYNTHETIC | LEGACY_IMPORTED | INVALIDATED`
- File naming: `snake_case.py` modules, `PascalCase` classes, `UPPER_CASE` constants

---

## Error Handling

- Use the existing error hierarchy:
  - `ControlPlaneError` → base for persistence errors
  - `ControlPlaneConflict` → stale revision (retry with fresh revision)
  - `ControlPlaneEvidenceError` → absent/stale/non-qualifying evidence
  - `GovernanceGateError` → policy violation
  - `DirectCatalogMutationError` → attempted YAML write (never catch; always fatal)

- Fail closed: if a required resource is unavailable, raise — do not return a default.
- Never swallow exceptions in governance code paths.

---

## Database Rules

- Use `db/control_plane.py` for lifecycle mutations (not raw SQLAlchemy sessions).
- Use `db/evidence_repository.py` for evidence CRUD.
- Use `db/connection.py` for session management.
- Never write to `config/strategy_catalog.yaml` in application code.
- Never use SQLite in governance code paths (SQLite is demo/test only).
- Alembic owns all schema changes. Never `CREATE TABLE` in application code.

---

## Testing Rules

- Unit tests: `tests/unit/<package>/test_<module>.py`
- Integration tests: `tests/database/test_<name>.py` (require real DB, mark with `pytest.mark.integration`)
- Architecture tests: `tests/architecture/` — AST scans, import checks; do not skip
- No mocking of the lifecycle authority or governance service in integration tests
- Fixtures for test strategies: use a fixed strategy_id like `"test-strategy-a"` — never `"ST-A2"`
- `@pytest.mark.skip` requires a comment explaining exactly when the skip will be removed

---

## Pipeline Dispatch Pattern

When adding a new strategy to the pipeline:

```python
# In strategies/adapters/__init__.py
SIGNAL_DISPATCH: dict[str, Callable] = {
    "st-a2": generate_signal_A,           # legacy
    "london-breakout": generate_signal_lb,
    "ny-momentum": generate_signal_ny,
}

def get_signal_fn_for_strategy(strategy_id: str) -> Callable:
    fn = SIGNAL_DISPATCH.get(strategy_id)
    if fn is None:
        raise ValueError(f"No signal function registered for strategy: {strategy_id!r}")
    return fn
```

Never: `if strategy_id == "ST-A2": use_signal_A(); elif ...`

---

## Import Order

```python
# 1. stdlib
import os
import json
from dataclasses import dataclass
from typing import Optional

# 2. third-party
import sqlalchemy
from pydantic import BaseModel

# 3. project — domain first, then application, then adapters
from svos.lifecycle.manager import StrategyLifecycleManager
from svos.governance.service import GovernanceService
from db.control_plane import PostgresControlPlane
```

Domain code (`svos/domain/`) must not import from `db/`, `dashboard/`, `execution/`, or any broker SDK.
