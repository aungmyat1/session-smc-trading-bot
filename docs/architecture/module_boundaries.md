# Module Boundaries

Date: 2026-07-02
Status: enforced migration contract

## Dependency direction

```text
agtrade / dashboards
        |
        v
application orchestration
   |                 |
   v                 v
production          svos
   |                 |
   +-------> shared <+
   |                 |
   +--> infrastructure <---+
```

`shared` contains pure contracts and business logic. `infrastructure` contains
replaceable external-system adapters such as GCS and KMS. Neither bounded
application may import the other.

## Production boundary

Production owns broker connectivity, execution permission, orders, risk,
positions, runtime health, deployment import, and live-status projection.
Production must not import replay, optimization, research, strategy audit,
strategy validation, datasets, or `svos`.

During migration, `production.engine` is the stable facade over legacy
`execution` modules. Moving those implementations is deferred until callers
use the facade, which preserves public APIs and trading behavior.

## SVOS boundary

SVOS owns intake, replay, simulation, backtest, robustness, optimization,
validation, evidence, approval, packaging, registry, and research reports.
SVOS must not import live broker connectors, production order/position
managers, or production runtime services. Simulation adapters are allowed.

## Shared boundary

Shared code must be deterministic and side-effect free at import time. It may
not depend on Production, SVOS, dashboards, databases, or broker adapters.

## Infrastructure boundary

Infrastructure adapters may depend on external SDKs and network protocols but
contain no strategy, research, risk, or execution policy. Credentials are
provided at runtime; secrets are never package content.

## Compatibility policy

Legacy paths remain as thin re-exports until all active consumers migrate.
Compatibility modules contain no new behavior and are removed only after an
import scan and regression suite show no callers.

## Enforcement

`tests/architecture/test_package_boundaries.py` parses imports and rejects
cross-boundary dependencies. Any temporary exception must be narrow, named,
documented here, and paired with a removal stage in `migration_plan.md`.
