# ADR-0011: mt5linux Broker Bridge for Vantage Connectivity

Date: 2026-07-06
Status: Proposed
Version: 1.0
Updated: 2026-07-06
Owner: Lead Architect
Authority: Level 5 — Decision
Related: `ADR-0003-SINGLE-RUNTIME-AUTHORITY.md`, `ADR-0004-CANONICAL-EXECUTION-PIPELINE.md`, `../DEPLOYMENT_TOPOLOGY.md`

## Context

The execution layer connects to Vantage exclusively through the MetaAPI Cloud SDK
(`execution/mt5_connector.py`, `execution/metaapi_client.py`). ADR-0003 registers
`vantage-demo` as the only accepted broker adapter identifier for
`production.engine.RuntimeAuthority` and explicitly reserves broker-implementation
changes as "a separate reviewed change" (§ Component selection). This ADR is that
reviewed change.

The owner has requested moving Vantage connectivity from the MetaAPI cloud API to
`mt5linux`, a Linux client that talks to a real MT5 terminal running under Wine via an
RPyC bridge. This is not a like-for-like SDK swap:

- MetaAPI is a hosted cloud API — no local broker process is required.
- mt5linux requires an actual MT5 terminal process, running under Wine, logged into the
  Vantage account, with an RPyC server process bridging the Windows-side `MetaTrader5`
  Python package to the Linux-side client. The terminal itself becomes infrastructure
  that must be supervised (crash recovery, restart-on-boot, login-session persistence).
- `auto-trade-vps` (per `DEPLOYMENT_TOPOLOGY.md`) is a GCP `e2-medium` (2 vCPU, ~3.8 GiB
  RAM) — modest headroom for an added Wine + MT5 terminal process alongside the existing
  demo runner, PostgreSQL, and dashboard.
- A dormant Wine/MT5 install already exists on the VPS (`~/.wine`, `~/.mt5`, ~4.2 GiB),
  flagged in VPS ops docs as "never delete without approval, pending architecture
  decision." This ADR is that decision; the install's health/version must still be
  verified before reuse, not assumed.
- mt5linux/RPyC is synchronous; the existing connector contract
  (`connect/disconnect/reconnect/ensure_connected/heartbeat`, all `async`) is consumed by
  `await`-based callers (`scripts/demo_health_check.py`, the `TradeManager` chain via
  `production.engine.services`).

The `vantage-demo` broker adapter identifier in `production/engine/runtime.py` is a
generic label, not MetaAPI-specific — this migration does not require a new adapter
identifier, only a change to what `vantage-demo` resolves to internally.

## Decision

Replace the MetaAPI-backed implementation behind the existing `vantage-demo` adapter
identifier with an mt5linux-backed implementation, introduced as a new module
(`execution/mt5linux_connector.py`) that preserves the current `MT5Connector` public
interface exactly (method names, return shapes, async signatures via
`asyncio.to_thread` wrapping of blocking RPyC calls). `execution/vantage_demo_executor.py`
is updated to call MT5-native terminal methods instead of MetaAPI RPC methods, but its
own public interface to `TradeManager`/`OrderManager` does not change.

Cutover is gated by a shadow-verification phase: the new connector runs read-only
(price/account/position reads, no order placement) against the same demo account in
parallel with the MetaAPI path, and `run_st_a2_demo.py`'s live wiring is only repointed
once parity holds. `DEMO_ONLY=true` / `LIVE_TRADING=false` are unaffected by this change
in either direction — this ADR governs connectivity only, not trading authorization.

## Rejected alternatives

- **Keep MetaAPI, do nothing:** rejected — explicit owner request to move off the cloud
  SDK.
- **Introduce a second, parallel broker adapter identifier (e.g. `vantage-mt5linux`)
  alongside `vantage-demo`:** rejected as unnecessary — `vantage-demo` is already a
  generic label in `RuntimeAuthority`; adding a second identifier for the same logical
  broker/account would fragment `SUPPORTED_BROKER_ADAPTERS` without benefit.
  Reconsider only if MetaAPI needs to keep running in parallel long-term rather than as
  a temporary shadow-verification baseline.
- **Direct cutover with no shadow phase:** rejected — ST-A2 is live in demo right now;
  an unverified connectivity swap risks silent execution divergence (price staleness,
  malformed order fields) with no comparison baseline.
- **Reuse the dormant Wine/MT5 install unverified:** rejected — provenance and health are
  unconfirmed; must be checked before any process depends on it.

## Rollback

If shadow verification fails or the mt5linux path proves unstable in demo, revert
`execution/vantage_demo_executor.py` and `run_st_a2_demo.py` wiring to
`execution/mt5_connector.py` (MetaAPI). Do not delete `execution/metaapi_client.py` or
the MetaAPI env vars until the mt5linux path has been stable in demo for an agreed
verification period (see implementation plan). Wine/MT5 terminal processes may be
stopped without affecting the MetaAPI rollback path, since they are independent
infrastructure.

## Consequences

- Vantage connectivity becomes self-hosted (Wine/MT5 terminal + RPyC bridge) rather than
  a managed cloud API — trades a dependency on MetaAPI's uptime for an operational
  burden on `auto-trade-vps` (terminal supervision, restart-on-crash, login persistence).
- `execution/metaapi_client.py` and the superseded `execution/mt5_executor.py` are
  retired once the shadow-verified cutover completes (tracked as cleanup, not part of
  this decision's immediate scope).
- CLAUDE.md §5 (Broker/Auth) is updated to describe mt5linux as the connection method,
  replacing the MetaAPI SDK description.
- No change to `RuntimeAuthority`, `SUPPORTED_BROKER_ADAPTERS`, or the `vantage-demo`
  identifier itself.

## Operational validation appendix (Phase 4A, 2026-07-06 — additive, does not alter the Decision above)

**VPS configuration observed:**
- `auto-trade-vps`: Ubuntu 24.04.4 LTS, 2 vCPU, 3.8G RAM, 38G disk. `wine-staging 11.11~noble-1`
  installed and functional (`wine --version` succeeds).
- `~/.wine` (1.6G) and `~/.mt5` (887M) both exist but are **bare, freshly-bootstrapped Wine
  prefixes** — `Program Files` contains only stock Wine placeholders (Windows Media Player,
  Internet Explorer, WordPad). No MT5 terminal executable, no Wine-side Python, in either prefix.
- No RPyC server process, no `mt5linux` install in the project `.venv` on the VPS, no systemd
  unit for any Wine/MT5/RPyC component. Only `smc-demo-runner.service` (the live MetaAPI-based
  ST-A2 demo) and `live-dashboard.service` are the project-relevant active services.

**Deployment notes:** provisioning a working mt5linux stack requires, at minimum: downloading and
installing a Vantage MT5 terminal `.exe` under the `~/.mt5` Wine prefix, installing a Windows
Python distribution inside that same prefix, installing `mt5linux`'s server-side package, and
logging into the demo account (`VANTAGE_MT5_DEMO_LOGIN`/`_PASSWORD`/`_SERVER`) — none of this has
been done. See `docs/audit/capacity-plan.md` for the storage impact of doing so and
`ADR-0012-SYSTEM2-HOSTING-STRATEGY.md` for whether it should happen on this host at all.

**Operational requirements / known limitations:**
- Host disk was at 86-88% used during this validation pass — above the 80% warning threshold
  in `config/storage_policy.yaml` — before any MT5 provisioning is added.
- mt5linux/RPyC requires a continuously-running Wine-hosted MT5 terminal, which is a materially
  different operational burden than MetaAPI's managed cloud API (terminal crash recovery,
  restart-on-boot, login-session persistence all become this project's responsibility).
- Phases 4B-4G of the original validation task (connector lifecycle, read-only RPC ops, market
  data parity, shadow verification, failure/recovery testing, operational readiness under load)
  **could not run** — there is no terminal or RPyC server to validate against yet. They remain
  blocked on the provisioning step above.

**Recovery procedure (rollback):** unchanged from the ADR's own Rollback section — the MetaAPI
path (`execution/mt5_connector.py`, `execution/metaapi_client.py`) was not touched by this
validation pass and remains the live, working connection for `smc-demo-runner.service`.

## Provisioning attempt appendix (2026-07-07 — additive, does not alter the Decision above)

An actual provisioning attempt was made on `auto-trade-vps` (owner-approved: proceed on this
host despite the capacity risk flagged above). Findings:

- **`~/.mt5` (original prefix) is broken**: `wine cmd /c echo hello` fails with
  `wine: could not load kernel32.dll, status c0000135` — reproducible, not a one-off. Left
  untouched (not deleted) per the hard constraint against removing MT5 directories.
- **A freshly-created prefix (`~/.mt5-terminal`) hit the identical error.** Ruled out prefix
  corruption as the cause — this is a host/environment-level Wine problem, not a
  per-prefix one.
- **`wine-staging` was upgraded 11.11→11.12** (owner-approved) to test whether a known-buggy
  experimental build was the cause. The error persisted after upgrade and after a full
  wineserver/Xvfb process restart, ruling out stale process state.
- **A WINEDEBUG=+loaddll,+module trace was initially misread as a successful run** (module
  init/detach lifecycle visible, no visible error) — this was corrected on immediate re-test:
  3 consecutive clean-state attempts (fresh Xvfb display, 796Mi-1.9G free memory, ruling out
  memory pressure as the cause) produced 3/3 failures with the identical error. The apparent
  "success" was very likely a background Wine service process's lifecycle (`wineserver`,
  `services.exe`), not the target command — logged here so this false positive isn't
  mistaken for progress in a future session.
- **Disk cost of this attempt**: the new prefix bootstrap (~800M) plus the wine-staging
  upgrade (303M download, more on-disk after unpack) moved disk from 5.6G free (86%) to
  **4.1G free (90% — the critical threshold)**, for no working result. ~168M was separately
  reclaimed first (`~/.codex/.tmp`, `~/.continue/index`, owner-approved per path) but did not
  materially change the outcome.
- **No MT5 terminal was ever installed** — `mt5setup.exe` never got past Wine's own
  `kernel32.dll` load step, so no MT5-specific disk footprint was added beyond the base
  prefix bootstrap.

**Root cause: unconfirmed.** Candidates not yet ruled out: kernel 6.17.0-1020-gcp vs.
wine-staging NTDLL loader incompatibility, a virtualization/seccomp restriction on this GCE
`e2-medium` instance blocking a syscall Wine's loader needs, or a corrupted underlying
`wine-staging` package install that a version upgrade (as opposed to a full purge+reinstall)
doesn't fix. Not investigated further in this pass, per owner decision to stop and report
rather than continue iterating at the critical disk threshold.

**Revised cutover recommendation: Option C — block cutover, unchanged from the Phase 4A
recommendation above**, now with stronger evidence: this host has both a capacity problem
and an unresolved Wine compatibility problem. Recommend `ADR-0012`'s dedicated-node option
be weighted more heavily in any future hosting decision, since a fresh node sidesteps both
issues simultaneously rather than requiring this host's specific Wine installation to be
debugged further.

**Cutover recommendation:** **Option C — block cutover.** The runtime cannot be evaluated for
operational readiness because it does not exist yet on this host. This is a "not provisioned"
finding, not a "provisioned but failing" finding — Phases 4B-4G should be re-attempted only after
either (a) a working terminal is provisioned per the deployment notes above, following
`ADR-0012`'s hosting-strategy recommendation, or (b) the owner explicitly decides to provision on
`auto-trade-vps` anyway after acting on the capacity plan's reclaim recommendations.
