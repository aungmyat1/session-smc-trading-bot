# Architecture Gap Report

Date: 2026-07-01
Status: Read-only audit finding — synthesis of Phases 1–6
Scope: Phase 7 (final) of the deployment-topology validation audit. See
`current_repository_structure.md`, `deployment_topology_validation.md`,
`module_boundary_analysis.md`, `dependency_boundary_report.md`, `database_topology.md`,
`system_health_baseline.md` for the underlying evidence.

## 1. Is Production correctly isolated?

**Mostly YES, with one real coupling.**

Evidence: Production execution (`execution/`, `bot.py`, `strategies/`, `dashboard/`) runs on
`auto-trade-vps` (verified via `hostname` and active systemd units `smc-demo-runner.service`,
`live-dashboard.service`), demo-only (`LIVE_TRADING=false`, `DEMO_ONLY=true`). It depends on
SVOS's governance/registry module in-process (`execution/governance_guard.py`,
`dashboard/app.py`) — a documented, intentional design (the lifecycle gate), not an accident.
It does not depend on replay, backtesting, optimization, or research analytics code for its hot
path. The one place production's *data*, not code, isn't isolated: the Postgres instance
production writes to (`vmassit`) also holds the research schema and runs on VPS 1 instead of
the VPS 2 research node the topology doc assigns it to.

## 2. Is SVOS correctly isolated?

**Mostly YES, with one script-level exception.**

Evidence: no SVOS/research package (`svos/`, `research/`, `research_db/`, `research_engine/`,
`research_sweep/`, `strategy_validation/`, `pipeline/`) calls `place_order`, `open_position`, or
any live broker mutation. The single exception is `adaptive/run_shadow.py`, which imports
`execution.mt5_executor` and the MetaAPI SDK directly for a live market-data feed in shadow
(no-order) mode — it doesn't trade, but it does create a hard runtime dependency from a
research script onto the production execution package and the broker SDK.

## 3. What prevents independent deployment?

1. **Shared Postgres instance and host.** `db/control_plane.py`'s `vmassit` database holds
   both production (`execution`, `operations`) and research (`research`, `governance`,
   `strategy`) schemas, and currently runs on VPS 1 (loopback), not the VPS 2 research node.
   Splitting the two nodes into truly independent deployments requires finishing the cutover
   already scheduled in `docs/svos/PREFLIGHT_STATUS.md` (dedicated SVOS roles/DB on VPS 2,
   restricted network exposure, checksummed data copy).
2. **In-process governance coupling.** `execution/governance_guard.py` and `dashboard/app.py`
   import SVOS's `GovernanceService`/`StrategyRegistryService`/`SVOSOperationalAPI` directly.
   This works today because both nodes check out the same repository, per the topology doc's
   own model — but it means production cannot be packaged/shipped without also shipping SVOS's
   governance code, unless that call is later turned into a network/API boundary.
3. **`adaptive/run_shadow.py`'s broker-SDK import.** Blocks shipping research code as a
   broker-credential-free package until the market-data-feed dependency is abstracted away from
   `execution.mt5_executor`.
4. **VPS 2 capacity.** Even where the topology is correctly assigned, VPS 2 (955 MiB RAM, no
   swap) cannot yet run full replay/backtest/robustness workloads — `DEPLOYMENT_TOPOLOGY.md`
   §6 explicitly gates that behind an 8 GB (16 GB recommended) RAM requirement, so "SVOS runs
   on gcp-vm1" is currently true only for lighter workloads (DB, schema work, small fixtures),
   not the full research pipeline.
5. **Test-suite segfault.** Not a deployment-separation blocker per se, but it means there is
   currently no way to get a full green pytest baseline before or after any migration step —
   any future migration work will inherit this pre-existing gap in verification coverage.

## 4. What should be migrated first?

Priority order (informational — no migration performed by this audit):

1. **Postgres cutover to VPS 2** (already scheduled in `PREFLIGHT_STATUS.md`): provision
   dedicated SVOS roles/database, restrict network exposure to loopback/Tailscale, complete the
   checksummed dataset copy, verify restore. This is the single highest-leverage move — it's
   the one place the current state diverges most from the authoritative topology doc, and it's
   already next in that doc's own plan.
2. **Abstract `adaptive/run_shadow.py`'s market-data feed** away from a direct
   `execution.mt5_executor`/MetaAPI SDK import, so research code has zero broker-SDK
   dependency, not just zero order-placement calls.
3. **Decide the governance-guard boundary**: if independent packaging/containers per node
   becomes an explicit future goal, convert `execution/governance_guard.py`'s and
   `dashboard/app.py`'s SVOS imports into a network call against the SVOS control plane instead
   of an in-process import. Not urgent while both nodes share a repo checkout.
4. **Install or formally retire** the `d2e3.service`, `d2e3-journal-sync.*`, and
   `reconcile-positions.*` systemd units that exist as files in `deploy/gcp-vm1/systemd/` but
   are not installed on this host — currently ambiguous whether they're planned-but-not-yet
   deployed or dead configuration.
5. **VPS 2 capacity increase**, if/when full replay/backtest/robustness runs on the research
   node are actually needed — explicitly a paid-infrastructure decision requiring an owner
   call, per `DEPLOYMENT_TOPOLOGY.md` §6.

## 5. What should NOT be changed

- **`svos/lifecycle/manager.py`** — confirmed the sole stage-mutation authority; no other
  script/runner/catalog writes lifecycle YAML/JSON directly (per repo CLAUDE.md §3 and
  observed structure).
- **The `deploy/gcp-vm1/` directory name**, despite being confusing (it holds VPS 1's own unit
  files, colliding with VPS 2's actual hostname) — renaming it is a real, if cosmetic, fix, but
  is out of scope for this read-only audit and should be a deliberate, separately-approved
  change, not a side effect of a broader migration.
- **`bot.py`** — legacy/retired per prior audit findings (`docs/AUDIT_IMPLEMENTATION_PLAN_2026-07-01.md`),
  but not deleted; leave as-is until an explicit retirement decision is made.
- **The Postgres schema itself** (`schema_v2.sql`, Alembic migrations) — `DEPLOYMENT_TOPOLOGY.md`
  §5 already states Alembic owns new schemas and `schema_v2.sql` is baseline input only; don't
  touch pending the cutover.
- **The pandas segfault** — already correctly deferred per `docs/migration/current_test_status.md`
  ("do not fix during Phase 0; isolate as separate remediation"); this audit does not change
  that call.
- **Any live/order-capable process** — `PREFLIGHT_STATUS.md` explicitly notes the order-capable
  VPS 1 bot was already stopped once during an incident response and should not be restarted
  during platform construction; this audit took no action that touches that state.

## Summary for the requester

1. **Topology validation result:** the assumed `gcp-vm1 = SVOS` / `auto-trade-vps = Production`
   split is real and authoritative (documented 2026-06-29), not aspirational — but migration
   onto it is incomplete, and the "auto-trade-vps" name in the prompt is the correct, live
   identity of the box this audit ran on.
2. **Confirmed production location:** `auto-trade-vps.asia-southeast1-b.c.auto-489108.internal`
   (this host), running `smc-demo-runner.service` + `live-dashboard.service`, demo-only.
3. **Confirmed SVOS location:** a separate machine named `gcp-vm1`, verified online (Tailscale +
   Docker + Postgres 16 healthy) per `docs/svos/PREFLIGHT_STATUS.md`, but not yet running the
   full research pipeline (capacity-gated) and not yet holding the authoritative Postgres
   database (still on VPS 1).
4. **Major architecture problems:** (a) the authoritative Postgres database mixes production
   and research schemas and still runs on VPS 1 instead of VPS 2; (b) `adaptive/run_shadow.py`
   couples research code to the live broker SDK; (c) three systemd unit files
   (`d2e3*`, `reconcile-positions*`) exist in the repo but aren't installed anywhere, an
   ambiguous "planned vs. dead" state; (d) a pre-existing pandas segfault blocks a full-suite
   green baseline.
5. **Migration risks:** cutting the Postgres instance to VPS 2 while production keeps writing
   to it needs the checksummed-backup/rollback discipline `DEPLOYMENT_TOPOLOGY.md` §4/§7
   already specifies — don't delete VPS 1 source data until cross-checked; VPS 2's low RAM
   means it cannot yet absorb full research workloads even after the DB cutover.
6. **Recommended next phase:** execute the Postgres cutover to VPS 2 that's already next in
   `docs/svos/PREFLIGHT_STATUS.md`'s own plan, following its documented backup/checksum/rollback
   steps — this closes the single largest gap between current state and the authoritative
   topology, and do it before any renaming or repackaging work on `deploy/gcp-vm1/`.
