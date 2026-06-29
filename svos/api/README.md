# svos/api — SVOS Operational API

Date: 2026-06-29
Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform Architecture
Authority: Level 6 — Module Documentation
Related: docs/svos/CORE_ARCHITECTURE.md, docs/ISOP_CONTROL_PANEL.md

## Purpose

This package provides a read-oriented operational facade over the SVOS core
services. It is consumed by the dashboard and monitoring systems to query
strategy state, evidence, and lifecycle information without directly accessing
internal service layers.

## Architecture

`SVOSOperationalAPI` is a thin composition class. It does not own any state or
persistence of its own. On construction it instantiates three sub-services
(`SVOSPlatform`, `DeploymentStatusService`, `MonitoringStatusService`) and
accepts two callable factories from the caller for control state and latest
reports. This keeps the API layer free of direct I/O: callers inject the I/O
providers.

```
SVOSOperationalAPI
  ├── SVOSPlatform          (svos/orchestration/service.py)
  │     ├── StrategyLifecycleManager
  │     ├── StrategyRegistryService
  │     ├── StandardizedReportService
  │     └── GovernanceService
  ├── DeploymentStatusService   (svos/deployment/service.py)
  ├── MonitoringStatusService   (svos/monitoring/service.py)
  ├── latest_reports_factory    (injected callable → dict)
  └── control_state_factory     (injected callable → dict)
```

All query paths call `self.platform.bootstrap()` first. `bootstrap()` iterates
the strategy catalog and calls `registry.ensure_strategy(name)` for each entry,
guaranteeing that the in-memory registry is consistent with the catalog YAML
before any data is returned.

## Service Contract

The public API surface exposed by `SVOSOperationalAPI`:

### `overview() -> dict[str, Any]`

Returns a single aggregated snapshot of the entire platform state. Calls
`bootstrap()`, then merges results from all four sub-services plus the two
injected factories. The returned dict contains the following top-level keys:

| Key | Source | Content |
|-----|--------|---------|
| `current_strategy` | `core.strategy_registry.get_current_strategy_name` | Name of the active strategy as declared in the catalog, or empty string |
| `registry` | `SVOSPlatform.registry.summary()` | Full strategy registry snapshot |
| `deployment` | `DeploymentStatusService.status()` | Deployment state for all known strategies |
| `monitoring` | `MonitoringStatusService.snapshot()` | Live monitoring health snapshot |
| `reports` | `latest_reports_factory()` | Latest report artifacts per strategy/stage |
| `emergency_stop` | `control_state_factory()["emergency_stop"]` | Emergency stop flag and metadata |
| `service_status` | composed | Fixed `"ONLINE"` for research/validation/governance/deployment; monitoring status from the monitoring snapshot |

The `service_status.research`, `service_status.validation`, `service_status.governance`,
and `service_status.deployment` values are hardcoded to `"ONLINE"`. They are
not derived from live health checks. Only `service_status.monitoring` reflects
a live value (from the monitoring snapshot's `monitoring_status` key).

### `registry_snapshot() -> dict[str, Any]`

Returns the registry summary only. Calls `bootstrap()` then delegates to
`self.platform.registry.summary()`. Use this when you need strategy list and
stage information without the cost of fetching deployment, monitoring, and
report data.

### `strategy_snapshot(strategy: str) -> dict[str, Any]`

Returns the full detail record for a single named strategy. Calls `bootstrap()`
then delegates to `self.platform.strategy_summary(strategy)`. The returned
structure is defined by `StrategyRegistryService.strategy_summary` and includes
lifecycle stage, evidence records, version history, and transition log.

## Authentication

No authentication layer is present in this package. `SVOSOperationalAPI` and
its methods carry no token validation, API key checking, or access control.
Authentication is the responsibility of the caller (e.g., the Flask dashboard
layer that wraps this API).

**Note:** The architecture review found that the Flask dashboard binds to
`0.0.0.0` and the API security is a HIGH-risk finding. See:
`docs/svos/architecture-review-2026-06-29/05_RISK_ASSESSMENT.md`

## Read-Only vs Mutating Operations

The `api` package is designed as a read-oriented facade. All three public
methods (`overview`, `registry_snapshot`, `strategy_snapshot`) are queries
only. No method in this package writes to the registry, mutates lifecycle
stage, records evidence, or places orders.

Lifecycle mutations must go through `svos/governance/service.py`, not through
this API. Evidence recording goes through `SVOSPlatform.record_report_evidence`
in `svos/orchestration/service.py`. Neither path is exposed here.

## Dependencies

Internal (all within this project):

| Module | Role |
|--------|------|
| `svos.orchestration.service.SVOSPlatform` | Bootstraps strategy catalog; owns lifecycle, registry, reports, governance sub-services |
| `svos.deployment.service.DeploymentStatusService` | Reads deployment state per strategy |
| `svos.monitoring.service.MonitoringStatusService` | Reads live monitoring health snapshot |
| `core.strategy_registry.get_current_strategy_name` | Reads active strategy name from catalog YAML |

External callables (injected at construction — not imported by this package):

| Parameter | Expected return type | Role |
|-----------|---------------------|------|
| `health_snapshot_factory` | `dict[str, Any]` | Forwarded to `MonitoringStatusService` |
| `latest_reports_factory` | `dict[str, Any]` | Latest report artifacts surfaced in `overview()` |
| `control_state_factory` | `dict[str, Any]` | Control plane state; `overview()` reads `emergency_stop` key |

No third-party libraries are imported by this package directly. All external
dependencies are pulled in transitively through the sub-services above.

## Limitations

- **No caching.** Every call to `overview()` triggers `bootstrap()`, which
  iterates the entire catalog and calls `ensure_strategy` for each entry.
  Under a large catalog this is an unbounded synchronous operation.

- **No authentication or authorization.** See the Authentication section above.

- **`service_status` is partially synthetic.** The `research`, `validation`,
  `governance`, and `deployment` fields in the `service_status` block are
  always `"ONLINE"` regardless of actual sub-service health. Only
  `monitoring` reflects a live value.

- **`bootstrap()` is called on every query.** `registry_snapshot()` and
  `strategy_snapshot()` each call `bootstrap()` independently. There is no
  shared bootstrap state between calls; concurrent requests each pay the full
  bootstrap cost.

- **No streaming or subscription support.** All methods are request/response
  synchronous calls returning plain dicts. Push notifications and real-time
  updates are outside the scope of this package.

- **`catalog_path` defaults are duplicated.** Both `SVOSOperationalAPI` and
  `SVOSPlatform` independently default `catalog_path` to
  `root / "config" / "strategy_catalog.yaml"`. The caller should pass an
  explicit value to both if the catalog is not at the default path.
