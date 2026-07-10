# System 2 — Dashboard Readiness Validation

- Date: 2026-07-05
- Status: Landed — read-only, demo-scope only
- Scope: `dashboard/status_server.py` (the only actually-deployed dashboard backend,
  via `live-dashboard.service`) and `execution/operations_recorder.py`.
- Safety: This change does **not** enable live trading, does **not** change
  `LIVE_TRADING`/`DEMO_ONLY`, secrets, broker credentials, GitHub environment
  variables, VPS production settings, or trading capital settings. It is
  read-only: every new endpoint is `GET`. See "Rollback" below.

---

## 1. What was added

Two new files' worth of code, no existing endpoint removed or changed in behavior:

- **`execution/operations_recorder.py`**: `db_health_check()` — a direct Postgres
  reachability probe (`SELECT 1` with a timed round-trip), distinct from that
  module's existing `_read()` helper because a fail-closed readiness check needs
  to know *why* the database is unreachable (not configured vs. configured-but-down),
  not just silently degrade to an empty default like the existing dashboard-widget
  reads do.
- **`dashboard/status_server.py`**:
  - `_system2_readiness()` — the fail-closed aggregator described in §3 below.
  - `_strategy_catalog_entry()` — direct read of `config/strategy_catalog.yaml`'s
    raw `approved` flag for one strategy (bypasses the UI-stage mapping in
    `dashboard/strategy_service.py` so this compliance signal reflects the
    literal catalog value, not a presentation transform of it).
  - `_duplicate_runtime_check()` — ground-truth OS process count for the deployed
    runner via `/proc/*/cmdline` exact-argv matching. **Not** `pgrep -f`, which
    does substring matching against the *entire* command line and produced false
    positives against unrelated processes that merely mentioned the script name
    in a quoted string (caught during development — see git history for this file).
  - `_control_state_known()` — whether `reports/control_state.json` exists and
    parses; `load_control_state()` itself silently substitutes defaults on any
    error, which would otherwise make an unknown/corrupt file indistinguishable
    from a known-good one.
  - `GET /api/system2/readiness` — JSON, the machine-readable readiness report.
  - `GET /system2/readiness` — server-rendered HTML readiness dashboard (same
    pattern as the existing `/dashboard/` route: no frontend build/deploy
    required, reuses the file's existing `_CSS` block).

Everything else the task's panel list needed already existed and was reused,
not duplicated: broker/positions/orders/risk/strategy/events data comes from
the pre-existing `/api/operations/{account,positions,orders,risk,strategy,events}`
family and `dashboard.live_dashboard_service.load_snapshot()`.

## 2. What the dashboard panels mean

`GET /system2/readiness` renders:

| Panel | Meaning | Source |
|---|---|---|
| **Readiness Summary** | The 10 fail-closed checks (§3) and the overall READY/NOT_READY verdict | `_system2_readiness()` |
| **Broker Connection** | Whether the deployed runner's broker connection is currently up | `_health_summary()` (existing) |
| **Strategy Package** | Which strategy is running, its literal `approved` flag and SVOS lifecycle status | `config/strategy_catalog.yaml` |
| **Database Health** | Postgres reachability + round-trip latency | `db_health_check()` |
| **Risk Firewall** | Whether the risk engine has a live state file, halted flag, daily P&L | `logs/risk_state.json` / `logs/portfolio_state.json` (existing) |
| **Emergency Stop** | Active/inactive, reason, scope | `reports/control_state.json` (existing) |
| **Heartbeat** | Age of the last strategy tick vs. the 180s staleness threshold | `logs/strategy_demo_state.json` (existing) |
| **Open Positions** | Current broker positions | `live_dashboard_service.load_snapshot()` (existing) |
| **Order Lifecycle Timeline** | Recent orders/executions | `live_dashboard_service.load_snapshot()` (existing) |
| **Recent Events / Incident Log** | Durable `operations.execution_event`/`recovery_checkpoint` history | `execution.operations_recorder.get_recent_events()` (existing) |

The header also shows the **mode indicator** (`DEMO` / `LIVE` / `READ_ONLY`),
read directly from the `LIVE_TRADING`/`DEMO_ONLY` environment variables already
in effect — this endpoint only reads them, never sets them.

## 3. What produces READY vs. NOT_READY

`_system2_readiness()` evaluates exactly 10 checks. **Every check defaults to
failing on missing, unparseable, or unreachable data — never to passing.**
`ready = True` only when all 10 are `ok`.

| # | Check | Passes when | Carve-out |
|---|---|---|---|
| 1 | `database_reachable` | Postgres answers `SELECT 1` | none |
| 2 | `runtime_authority_valid` | `trading_allowed` (from `TradingPermissionService`, which already folds in emergency-stop/safe-mode/reconciliation-block state) is true AND the runner reports `running` | none |
| 3 | `strategy_package_approved` | The running strategy's `config/strategy_catalog.yaml` entry has `approved: true` | none |
| 4 | `risk_firewall_active` | `logs/risk_state.json` exists and parses | none |
| 5 | `broker_reachable_or_disabled` | broker connected | **or** `broker_status == "disabled"` (explicit read-only mode) |
| 6 | `emergency_stop_known` | `reports/control_state.json` exists and parses | none — this checks the state is *known*, not that it's inactive; an active stop is still surfaced (see §2 Emergency Stop panel) and separately fails check #2 via `trading_allowed` |
| 7 | `no_critical_incident` | neither `health.safe_mode.active` nor `health.critical_unknown` is set | none |
| 8 | `heartbeat_fresh` | last tick age ≤ 180s | none |
| 9 | `no_duplicate_runtime` | exactly one OS process matches the deployed runner's argv | none — an *undeterminable* count fails closed too, it is never assumed to be "fine" |
| 10 | `reconciliation_available` | `reconciliation.status` is a non-empty, non-`"unknown"` value | **or** the status is explicitly `"unavailable"` — a known, honest answer, not a blocker |

**As of this writing, the live system reports `NOT_READY`** — honestly, not a
bug: `strategy_package_approved` fails because ST-A2 is `DEFERRED_REVALIDATION`
in `config/strategy_catalog.yaml` (`approved: false`), and `runtime_authority_valid`
fails for the same underlying reason (the governance chain doesn't authorize an
unapproved strategy). This matches this repo's own documented governance
position (`CLAUDE.md` §1, §6) — the dashboard is not softening or hiding it.

## 4. What is still required before demo trading

Demo trading is **already running** today (ST-A2 on `smc-demo-runner.service`) —
this dashboard change doesn't gate that, it only makes its true state visible.
Nothing in this change is required *before* demo trading; demo trading already
proceeds under the tracked governance gap documented in `CLAUDE.md` §1.

## 5. What is still required before live trading

Unchanged by this work, and out of scope for it — live trading remains gated
behind SVOS Production Approval per `CLAUDE.md` §0.1, which no strategy
currently holds. This dashboard change makes it easier to *observe* that gate
(the readiness page will show `NOT_READY` for as long as it isn't met) but
does not itself implement, weaken, or bypass any part of it. In particular,
`LIVE_TRADING`/`DEMO_ONLY` are read-only here and were not touched.

## 6. Rollback instructions

This change is additive-only — no existing route, function, or file was
modified in a way that changes prior behavior (`db/models.py` and
`scripts/run_st_a2_demo.py`'s unrelated in-flight WIP from another session was
left untouched, per instructions). To roll back:

1. `git revert <this-commit-sha>` — removes `_system2_readiness()`, the two new
   routes, `_strategy_catalog_entry()`, `_duplicate_runtime_check()`,
   `_control_state_known()`, and `db_health_check()`. No migration, no schema
   change, no config change to undo.
2. Restart `live-dashboard.service` to load the reverted code:
   `sudo systemctl restart live-dashboard.service`.
3. `smc-demo-runner.service` (the trading runner) requires no action — it was
   never touched by this change and does not import anything added here.

No data was written by this change (`reports/control_state.json`,
`logs/risk_state.json`, `config/strategy_catalog.yaml` are all read, never
written, by the new code), so there is nothing to restore beyond the code
itself.

## 7. Known limitations / not built here

- `no_duplicate_runtime` matches by exact argv token against the deployed
  runner's entrypoint script name; it does not (and cannot, from a single
  process) detect a duplicate runtime on a *different host*.
- `runtime_authority_valid` intentionally does **not** use
  `production.engine.runtime.RuntimeAuthority` (the lock-file-based authority)
  — that class belongs to `run_portfolio.py`, the undeployed canonical runner
  (see `SYSTEM2_MASTER_PLAN.md` Phase 2). Using it here would test a runner
  that isn't the one actually running.
- The HTML panel page (`/system2/readiness`) is server-rendered, matching the
  existing `/dashboard/` route's pattern — it is not part of the Gai dashboard
  React SPA (`/new-dashboard/`). Integrating a tenth panel into that SPA is a
  separate, larger frontend task, not attempted here per "prefer small, safe
  changes."

## 8. WebSocket repair (2026-07-05)

A follow-on task asked for a live functional check of `/new-dashboard/`, which
surfaced three real bugs in the existing (2026-07-04) Real-Time Operations
Layer — all now fixed, verified live, and covered by tests. `/ws` is treated
as canonical throughout; no second WebSocket server was introduced.

**Bug 1 — auth-transport mismatch (the main fix).** `/ws` only accepted
header-based auth (`Authorization`/`X-SVOS-Actor`, same as every REST route).
Browsers cannot set custom headers on a WebSocket upgrade request — verified
live before the fix: an unauthenticated connection attempt got HTTP 403. The
Gai dashboard's `SocketContext.tsx` had real client code trying to use `/ws`,
but it could never have authenticated as written.

*Fix*: `dashboard/rbac.py::mint_ws_ticket()`/`validate_ws_ticket()` — a
short-lived (30s), single-use, HMAC-signed ticket. A caller first makes a
normal, fully-authenticated REST call (`GET /api/ws-ticket`, gated by the same
`require_authenticated()` dependency as any other read endpoint) to obtain
one, then passes it as `?ticket=` on the WS URL — the one place a browser
*can* attach a credential. Header-based auth on `/ws` is preserved unchanged
as a fallback for any non-browser caller. This does not add a new way in,
only a new way to carry an already-established identity onto a transport
that can't carry headers, and issuance requires the identical gate every
other read endpoint already enforces — no security weakening.

**Bug 2 — dead reconnect target.** The frontend alternated reconnect attempts
between `/ws` and `/api/ws`. `/api/ws` does not exist (verified live: 404) —
half of all reconnect attempts were guaranteed to fail. Fixed: always target
the one real, canonical `/ws` route.

**Bug 3 — event schema mismatch.** The frontend's `onmessage` handler only
reacted to `payload.type === "INITIAL_STATE" || "TICK"`. The real `/ws`
sends `BaseEvent`-shaped messages (`event_type`, `source_system`, `payload`,
`severity`, ... — see `dashboard/events.py`) with no `type`/`state` fields at
all; that shape was only ever sent by this app's original mock `server.ts`.
Even with auth fixed, the frontend would have connected successfully, then
silently discarded every real event — and since a successful connection
stops REST polling, the dashboard would have **frozen** instead of continuing
to show stale-but-refreshing data. Fixed: `onmessage` now treats any message
with a real `event_type` field as a "something changed" signal and refetches
`/api/new-dashboard/live-state`; `onopen` does the same immediately, since
the server sends no bootstrap snapshot on connect (only discrete events).

**Verification performed (live, against the actual production process, not
just local tests):**
1. Unauthenticated `/ws` connection → rejected (was already broken; still
   correctly rejected, not weakened).
2. `GET /api/ws-ticket` without credentials → 401. With real production
   credentials → a valid ticket.
3. `/ws?ticket=<valid>` → connects successfully.
4. Reusing the same ticket for a second connection → rejected (single-use
   enforced).
5. A real event published through the actual `_event_broadcaster` (via a
   local `TestClient`, running the exact same imported code the production
   process runs) → delivered to the connected client with the exact
   `BaseEvent` shape, byte-identical `event_type`/`payload` to what was
   published.
6. Rebuilt SPA (`npx vite build`) deployed and confirmed serving the new JS
   bundle from `live-dashboard.service`; bundle inspected and confirmed to
   contain the new ticket-fetching code.
7. `smc-demo-runner.service` (trading runner) confirmed untouched throughout
   — same `ActiveEnterTimestamp`, 0 restarts.

**Remaining gap before operator-control integration (Priority 1):** this fix
makes `/ws` *capable* of browser auth, but the browser still has no source
for an operator credential — there is no login screen. `getOperatorAuthHeaders()`
reads an optional `svosOperatorToken`/`svosOperatorActor` pair from
`localStorage`, which nothing currently sets. Until a credential source
exists, real-world behavior in an actual browser is still "poll" — the ticket
fetch will 401, and the code deliberately does not attempt a doomed WS
connection when that happens, falling back to REST polling instead of
spamming reconnects. **This same missing piece — not WebSocket, not any
individual endpoint — is also the actual blocker for every operator-control
REST action** (`/api/emergency-stop`, `/api/control/*`): the Gai dashboard's
fetch calls never set an `Authorization` header today, so those would 401 if
clicked from a real browser right now, independent of whether their target
routes exist. Solving frontend credential acquisition once (e.g., a minimal
login step that populates the same `localStorage` keys) would unblock both
WebSocket and operator controls simultaneously — recommended as the actual
first step of Priority 1, not a separate concern.

## 9. Operator authentication integration (2026-07-05, second pass)

This closes the gap §8 identified: the browser had no credential source.
**One authentication implementation throughout** — no OAuth/SSO/JWT/new user
system was introduced; this is a client-side session wrapper around the
existing `dashboard/rbac.py` bearer-token backend.

### 9.1 Phase 1 audit findings

- **Credential source**: a single shared secret, `SVOS_OPERATOR_TOKEN`
  (bearer token) or trusted-reverse-proxy headers (`DASHBOARD_PROXY_SECRET` +
  `X-Forwarded-Email`/`X-SVOS-Proxy-Role`). Stateless — read fresh from env
  vars on every request, no server-side session store. In this deployment,
  only the bearer-token path is configured (no proxy secret set).
- **RBAC flow**: `_ROLE_ACTIONS` (`dashboard/auth.py`) maps
  `research_operator`/`incident_operator`/`risk_operator`/`admin` to
  permitted-action strings; `dashboard/rbac.py::require_role(*roles)` is the
  FastAPI dependency gate. For bearer auth, role is **fixed server-side**
  via `SVOS_OPERATOR_ROLE` (default `admin`) — a caller cannot self-declare
  a role via header. **Divergence found, not fixed (out of scope — lives in
  the undeployed Flask backend)**: `dashboard/auth.py::_resolve_identity`
  (used by `app.py`/`live_app.py`, neither deployed) still lets a bearer
  caller supply `X-SVOS-Role` directly — the exact self-declared-role
  vulnerability `dashboard/rbac.py` was already fixed against. Flagged for
  a future pass if `app.py` is ever revived; no live exposure today since
  it isn't running.
- **CONFIRM-token flow**: mutation endpoints require an exact-match
  `confirm_token` string in the POST body (e.g. `"CONFIRM-PAUSE-TRADING"`),
  checked after the RBAC role check. Confirmed via direct testing that the
  check order is role → confirm-token (a wrong-role caller never learns
  whether their confirm-token would have been accepted).
- **WebSocket ticket flow**: unchanged from §8 — `GET /api/ws-ticket`
  (`require_authenticated()`) mints a 30s single-use signed ticket; `/ws`
  accepts it via `?ticket=` or falls back to header auth.
- **Frontend assumptions (the actual gaps)**: `SocketContext.tsx` had zero
  credential storage or login UI. All operator-control fetch calls except
  `triggerKillSwitch` targeted nonexistent routes (`/api/action`,
  `/api/live/strategy/*`, `/api/live/risk-controls`, `/api/live/broker/reconnect`
  — leftover from the original mock `server.ts`). `triggerKillSwitch` hit
  the correct route but with a hardcoded `confirm_token` and no operator
  confirmation step. **No call anywhere set an `Authorization` header.**

### 9.2 What was integrated (not redesigned)

- **Operator login** (`OperatorLogin.tsx`, new): a minimal form — operator
  token + actor name, no registration/password-reset/account-management.
  Submits to the existing `GET /api/ws-ticket` purely to *validate* the
  credential (a 401 means invalid, 503 means auth isn't configured
  server-side, 200 means valid) before storing anything.
- **Session storage**: `sessionStorage` (cleared when the tab/browser
  closes) under `svosOperatorToken`/`svosOperatorActor` — the same keys
  §8's `getOperatorAuthHeaders()` already read from (originally
  `localStorage`; moved to `sessionStorage` this pass per this sprint's
  "current session" storage requirement).
- **Session lifecycle**: `authenticatedFetch()` wraps every mutation call
  with the stored credential; any `401` response triggers automatic
  `logout()` (clears storage, closes the WebSocket) — since the backend is
  stateless there is no server-side session to expire, so "expiry" here
  means "the credential this client holds stopped being accepted,"
  detected on next use. `logout()` is also exposed directly as a button.
  A successful `login()` immediately calls `connectWebSocket()` rather than
  waiting for the next scheduled retry (up to 3s).
- **Operator controls repointed to the real, already-existing endpoints**
  (no new backend routes needed for these six):

  | Frontend action | Real endpoint | Confirm token |
  |---|---|---|
  | Pause | `POST /api/control/pause` | `CONFIRM-PAUSE-TRADING` |
  | Resume | `POST /api/control/resume` | `CONFIRM-RESUME-TRADING` |
  | Toggle Strategy (pause) | `POST /api/control/toggle-strategy` | `` CONFIRM-TOGGLE-STRATEGY-<id> `` |
  | Emergency Stop | `POST /api/emergency-stop` | `CONFIRM-EMERGENCY-STOP` |
  | Emergency Clear | `POST /api/emergency-stop/clear` (new frontend wiring — no UI button yet, see 9.4) | `CONFIRM-CLEAR-EMERGENCY-STOP` |
  | Close All | `POST /api/control/close-all` | `CONFIRM-CLOSE-ALL-POSITIONS` (not wired to any UI button — see 9.4) |

  Every one of these now requires `requireLogin()` (blocks with an alert if
  no session) **and** an explicit `window.confirm()` before sending — the
  CONFIRM-token literal is still supplied by the code (it's a fixed
  server-required string, not an operator secret), but it is never sent
  without a deliberate confirmation click, closing the gap the original
  design doc flagged ("must prompt, not auto-fill").
- **Left deliberately unimplemented, not wired to the wrong thing**:
  `forceCloseTrade` (no single-position-close endpoint exists; the only
  close-related endpoint closes *everything*, so mapping "close this one
  trade" to `close-all` would be a safety bug, not a fix — see 9.4),
  `activateStrategy` (server-side deliberately blocked at
  `production/activation.py`'s `STAGED_DISABLED`), `updateRiskControls`
  (no write endpoint exists), `reconnectBroker` (tied to the separate
  Shared Broker Runtime milestone). `selectPair` and `resetAnalytics` were
  changed from broken fetches to correct client-only behavior (pair
  selection has no server concept; analytics "reset" now just refetches
  live state rather than fabricating a destructive trade-history-reset
  endpoint that was never asked for).

### 9.3 Secret rotation review (Phase 5) — reviewed, not rotated

`SVOS_OPERATOR_TOKEN` in `/etc/session-smc-trading-bot/live-dashboard.env`
is confirmed to be a **generic placeholder value** (10 characters,
lowercase-and-hyphen pattern consistent with a template default, not a
generated secret) — checked for existence and shape only, value never
printed or logged anywhere in this process. `DASHBOARD_PROXY_SECRET` and
`SVOS_OPERATOR_ROLE` are unset (role defaults to `admin`).

**Rotation plan (not executed — requires explicit owner approval per this
sprint's Phase 5 instructions and this repo's "never touch secrets/VPS
production settings" boundary):**
1. Generate a new high-entropy token (e.g. `openssl rand -base64 32`).
2. Update `SVOS_OPERATOR_TOKEN=` in `/etc/session-smc-trading-bot/live-dashboard.env`.
3. `sudo systemctl restart live-dashboard.service`.
4. No other system depends on this value today (confirmed: it's read only
   by `dashboard/rbac.py`/`dashboard/auth.py`, and the latter's backend
   isn't deployed) — operators simply log in again via the new
   `OperatorLogin` widget with the new token; no other coordination needed.
5. Recommend also setting `SVOS_OPERATOR_ROLE` explicitly rather than
   relying on the `admin` default, once more than one operator role is
   actually in use.

### 9.4 Validation performed

**Locally (TestClient — full success path, since these endpoints write to
`reports/control_state.json`, which the live trading runner reads every
tick; the mutation path was deliberately NOT exercised against production
— see "Live" below):**
- Pause → resume → toggle-strategy(pause) → emergency-stop → emergency-stop/clear,
  using the exact JSON payloads the new frontend sends, all succeeded (200)
  and correctly mutated `control_state.json` with actor attribution
  (`activated_by`/`cleared_by`) intact.
- Correct role + wrong CONFIRM token → 403, state unchanged (verified via
  re-read).
- Wrong role (`research_operator`) + correct CONFIRM token → 403 before the
  token is even checked (role gate runs first).
- Full regression suite: 140/140 passed, no change from pre-sprint baseline
  (same pre-existing, unrelated thread-warning noted in §8).

**Live (production `live-dashboard.service`) — auth/rejection paths only,
proven safe because none of these mutate state:**
- Unauthenticated `POST /api/control/pause` → 401.
- Authenticated with wrong CONFIRM token → 403, `emergency_stop.active`
  confirmed still `false` via `GET /api/control/state` afterward.
- `GET /api/ws-ticket` with real production credentials → valid ticket;
  `/ws?ticket=...` → connects.
- `smc-demo-runner.service` confirmed unaffected throughout (same
  `ActiveEnterTimestamp`, 0 restarts, before and after this sprint's work).
- Frontend rebuilt (`npx vite build`) and confirmed served live —
  `/new-dashboard/` returns the new bundle hash immediately (static files
  are read from disk per-request, no backend restart needed for a frontend
  change).

### 9.5 Remaining System 2 authentication gaps

- No UI button exists yet for **Close All** or **Emergency Clear** — both
  are now wired in `SocketContext.tsx` (`clearEmergencyStop` exposed;
  close-all deliberately not exposed at all per 9.2's safety note) and
  verified directly against the backend, but no component calls them yet.
  Wiring a real "Close All" button needs care: today's only close-related
  UI concept (`forceCloseTrade`, a single pending trade) doesn't match
  close-all's actual "everything, everywhere" semantics — a real button
  needs its own, honestly-labeled UI, not a repurposed existing one.
- `dashboard/auth.py`'s `X-SVOS-Role` self-declaration gap (9.1) — no live
  exposure (backend not deployed) but should be fixed to match
  `dashboard/rbac.py` if `app.py` is ever revived.
- Single shared operator credential, not per-user — acceptable for this
  sprint's explicit "no user management systems" boundary, but means audit
  attribution (`actor` field) is only as honest as whatever string an
  operator types into the login form, not cryptographically tied to them.
- `SVOS_OPERATOR_TOKEN` remains a placeholder value — reviewed, rotation
  plan documented (9.3), not executed pending approval.

## 10. Shared Broker Runtime (2026-07-06)

**Problem**: `dashboard/live_dashboard_service.py` opened its own MetaAPI session
(`MT5Connector` + `VantageDemoExecutor`) to read account/positions/market-watch/
chart data — a second, independent broker connection duplicating what the
deployed runner (`scripts/run_st_a2_demo.py`) already has open. This was the
documented cause of `brokerConnection.status` reading `DEGRADED` in production
even while the runner itself was healthy.

**Fix**: `_fetch_broker_snapshot()` now reads the files the runner already
writes every tick — `logs/strategy_demo_state.json` (account, open_positions,
broker_status, last_tick_at, pair_results) and `logs/candles/{SYMBOL}_M15.json`
(chart data) — instead of opening a connection. The old threaded/cached RPC
apparatus (`_fetch_broker_snapshot_async`, a background thread, a stale-value
cache) is removed entirely; a local file read needs none of that. This also
eliminated a latent bug: the removed background thread had an unhandled
`AttributeError` on `None.get()` that was silently surfacing as a
`PytestUnhandledThreadExceptionWarning` in test runs.

- **State ownership**: `scripts/run_st_a2_demo.py` is the sole broker-connection
  owner and sole writer of the state/candle files.
- **Synchronization mechanism**: filesystem — no IPC, no polling of the broker.
- **Refresh strategy**: read fresh from disk on every dashboard request (no
  caching layer; a local read is already fast enough that the caching this
  replaced, built to hide broker RPC latency, no longer serves a purpose).
- **Failure behavior**: missing/unreadable state file, or a heartbeat older
  than 180s (matching the existing readiness-check threshold), reports
  `DISCONNECTED`/`STALE` honestly via the existing `_empty_broker_snapshot`
  shape — never fabricates account/position data behind a stale read.

**Scope boundary, deliberate**: manual position close/modify/cancel
(`close_position`/`modify_position`/`cancel_order` in the same file) still use
their own separate `MT5Connector` — these are live order-mutation calls, not
reads, and routing them through the runner's own connection would require a
command/IPC channel to that process, a materially larger architectural change
not attempted here.

**Known minor limitation**: positions read via shared state lack `open_time`/
`holding_time` (the runner's own position mapping in
`execution/vantage_demo_executor.py::get_positions()` doesn't carry the
broker's raw `time` field through) — reported as empty rather than fabricated.
Fixing this would mean editing the live trading executor for a cosmetic
display field; judged not worth the deployment/restart risk here. Similarly,
`market_watch` bid/ask is derived from the runner's single last-traded
`price` + `spread_pips` (an approximation), not independently observed tick
data — documented in code, not presented as more precise than it is.

**Verified**: 7 new unit tests (`tests/dashboard/test_live_dashboard_shared_runtime.py`)
covering missing/corrupt/stale/disconnected state, correct field mapping, and
— the core proof — that `MT5Connector` is never constructed for a read.
Live: `brokerConnection.status` confirmed `CONNECTED` (was `DEGRADED`) via
`/api/new-dashboard/live-state` immediately after deploy; account balance
matched the real state file exactly ($996.01). `smc-demo-runner.service`
untouched throughout (same `ActiveEnterTimestamp`, 0 restarts).

## 11. Monitoring & Observability (2026-07-06)

New `GET /api/system2/monitoring` consolidates:

| Section | Source | Notes |
|---|---|---|
| `platform_health` | `_health_summary()` (existing) | reused, not recomputed |
| `broker` | shared runtime state | `latency_ms` honestly `null` — no RPC round-trip exists to measure in this architecture; `heartbeat_age_seconds` is the meaningful freshness signal instead |
| `runner` | `logs/strategy_demo_state.json` | status, uptime, pid, strategy |
| `database` | `db_health_check()` (existing) | reused |
| `risk_engine` | `logs/risk_state.json` presence | |
| `dashboard_backend` | existing `_GIT_SHA`/`_DEPLOYMENT_HOSTNAME` | |
| `websocket` | `len(_event_broadcaster._subscribers)` | real, live subscriber count |
| `execution_latency` | `get_recent_events()` | honestly `null` — zero trades have executed yet, so there is no intent→fill duration to compute; not fabricated |
| `resources.memory` | `scripts/ops/mem_monitor.py::get_memory_health()` (existing, reused) | |
| `resources.cpu` | new: `os.getloadavg()` | load 1/5/15m + core count |
| `resources.disk` | new: `os.statvfs("/")` | total/free/used% |
| `api_latency_ms` | self-measured | time to assemble this payload |

All new resource checks are plain-stdlib, read-only OS introspection —
matching `mem_monitor.py`'s existing pattern, no new dependency. Verified: 4
new tests confirm all sections present, execution-latency is null (not
fabricated) with no trades, broker latency is null (not a stale RPC value),
and the WebSocket subscriber count tracks a real connect/disconnect cycle.
Deployed and confirmed live.

## 12. Telegram Alert Persistence & Extended Demo Validation (2026-07-06)

**Persistence**: `monitoring/telegram.py::_post()` now calls
`execution.operations_recorder.record_telegram_alert(category, text, sent=...)`
before the actual network send — for every alert, including ones suppressed
by the existing cooldown logic or skipped because Telegram isn't configured
(`sent=False` in both cases; the underlying operational condition still
happened and belongs in history even if nothing was delivered). Writes into
the *same* `operations.execution_event` table `/api/operations/events`
already reads — no second event store, and no new API needed: persisted
alerts appear automatically once written. `get_recent_events()`'s severity
classification was extended so `telegram_alert:error`/`emergency_stop`/
`watchdog_critical`/`reconnect_failure` show as `error`, `circuit_breaker`/
`reconciliation_mismatch` as `warning`, and routine categories (heartbeat,
daily_summary, trade_open, ...) stay `info` — previously everything would
have shown as flatly `info`. The import is lazy and defensive
(`monitoring/telegram.py` has no hard dependency on `execution.*` and keeps
sending alerts even if that import ever fails), and a DB failure never blocks
the real send (13 tests cover mint/suppress/unconfigured/failure paths).

**Not yet active**: activating this requires restarting
`smc-demo-runner.service` — the only process that imports
`monitoring.telegram`. That process currently has ~77 uncommitted lines of a
different, in-progress session's `RiskPortfolioStore` integration already
loaded (confirmed via `git diff --stat`), unreviewed and untested by this
work. Restarting would deploy that unrelated change alongside this one.
Deliberately not done — this is implemented and tested, not deployed.

**Extended Demo Validation — honest snapshot, not a multi-day report**:
the runner has been up since 2026-07-04 23:43 UTC, ~2 days at review time —
real continuous uptime, but short of genuine multi-day validation. Data
collected this pass:

| Metric | Value |
|---|---|
| Uptime | ~2 days, 0 process restarts |
| Reconnects | 21 (`reconnect_attempts_total`) |
| Distinct `[ERROR]` log entries | 119 — all the same root cause: MetaAPI `TimeoutException` ("Failed to subscribe") on both subscription instances |
| Distinct `WARNING` log entries | 134 |
| Trades executed | 0 (spread filter has rejected every signal so far) |
| Risk state | not halted, 0 consecutive losses, 0 trades today |
| Non-terminal `ExecutionRecord`s | 58, with zero completed trades |

**Issues discovered, not fixed in this pass**:
1. Periodic MetaAPI subscription timeouts (~every 24 minutes on average) —
   handled gracefully by existing reconnect logic (0 crashes), but frequent
   enough to flag as a real reliability characteristic of this deployment,
   not a one-off.
2. **58 non-terminal `ExecutionRecord`s with zero completed trades** —
   unexplained by this pass. `execution/execution_state.py`'s
   `recover_incomplete()` returns any record not in `{COMPLETED,
   FAILED_TERMINAL, CANCELLED, REJECTED}`; a growing count with no real
   trades suggests either an expected artifact of skip-decisions never
   reaching a terminal state, or a real backlog. Investigating this means
   touching the execution state machine — judged out of scope for this
   hardening sprint (risk of a live-runner change without full review), but
   flagged as the top candidate for the next investigation before claiming
   full execution-path confidence.
3. **Zero real trades have occurred** — every real-order-flow code path
   (fill handling, close detection, risk feedback from a real close) remains
   exercised only by tests and by the 2026-07-04 forced-scenario validation,
   not by an actual live decision this deployment made. Extended validation
   under real order flow has not happened.

## 13. Root cause: the 58 non-terminal ExecutionRecords (2026-07-06)

**Confirmed root cause — test isolation, not a state-machine bug.**
`execution/trade_manager.py::TradeManager.__init__` defaults `execution_store`
to `ExecutionStateStore(".")` — resolved relative to the process's current
working directory — whenever a caller doesn't inject one explicitly.
`ExecutionStateStore.store_root` is `root / "data" / "execution"`. Two test
files, `tests/test_demo_execution_safety.py:107` and
`tests/execution/test_trade_manager.py` (3 call sites), constructed
`TradeManager` without an explicit store. Since pytest in this repo always
runs from the repo root, every single run of those tests silently wrote a
simulated `ExecutionRecord` JSON file into the *real* `data/execution/`
directory — the same one `dashboard/status_server.py` reads for
`incomplete_executions`/readiness checks.

**Evidence, not assumption**: inspected all 376 accumulated files —
`signal_id` was `"strategy-demo"` (the generic test-fixture fallback) for
353 of them and `"ST-A2"` for 23; **every single record**, including the
`"ST-A2"`-tagged ones, had `broker_order_id` either empty or prefixed
`SIM-`/`SIM-OK`/`SIM-EURUSD` — the fake executor's literal return values from
these exact test files. Zero real broker order IDs existed anywhere in the
dataset. Dates spanned 2026-07-01 through the day of this investigation —
accumulated across the project's entire history, not a recent regression.

**Not a state-machine defect**: `ExecutionRecord`s aren't "stuck" via a
broken transition — the state machine works correctly. They simply never
progress past `BROKER_ACKNOWLEDGED`/`RECOVERY_PENDING` because the test
process that created them exits after its assertions, never calling
whatever would terminalize the record (a real caller would reach
`COMPLETED`/`FAILED_TERMINAL` on close or rejection). Abandoned test
fixtures, not corrupted execution logic. The real, deployed runner
(`scripts/run_st_a2_demo.py:797`) has always correctly injected an explicit
`ExecutionStateStore(_ROOT)` — production was never actually affected by
the *defect*, only by the *pollution* it caused in a directory production
also reads.

**Fix** (test-only changes, zero production code touched):
- Both call sites now inject `ExecutionStateStore(tmp_path)`.
- New `tests/execution/test_trade_manager_store_isolation.py`: (1) documents
  the dangerous default's exact behavior so a future change to it is
  deliberate; (2) a static, AST-based repo-wide check that fails if *any*
  test anywhere constructs `TradeManager(...)` without `execution_store=` —
  prevents a new test file from reintroducing this exact bug class, not just
  the two known offenders.
- **Verified**: ran the full test suite before and after — `data/execution/`
  file count held at 376 with zero growth (previously grew on every run).
  The 9 pre-existing test failures elsewhere in the suite were confirmed
  via `git stash` to be identical with or without this fix — unrelated.

**Cleanup of already-accumulated pollution** (explicit user approval
obtained before executing, since this touches the live runner's state
directory): all 376 confirmed-synthetic files moved (not deleted) to
`/home/aungp/archives/data-execution-test-pollution-2026-07-06/`, fully
reversible. Verified immediately after: `/api/readiness/report`'s
`incomplete_executions` dropped from 58 to **0** — now honestly reflecting
that zero real trades have executed. `smc-demo-runner.service` confirmed
unaffected throughout (same `ActiveEnterTimestamp`, 0 restarts).

## 14. Durable risk/portfolio ledger + two more test-isolation incidents (2026-07-06)

**Adopted, not built from scratch**: another session's in-progress,
previously-unreviewed work (`execution/risk_portfolio_store.py`, migration
`005`, `db/models.py`'s `RiskPortfolioState`/`RiskPortfolioHistory`, and
their wiring into `scripts/run_st_a2_demo.py`) was reviewed in full —
13 existing unit tests, best-effort error handling matching this repo's
established `operations_recorder.py` pattern exactly, a clean reversible
migration (pure `CREATE TABLE`, tested `downgrade()`), and the existing JSON
file persistence left as an unconditional parallel write, not replaced —
judged high quality and **committed to, not discarded**. Migration `005`
applied (`alembic upgrade head`, verified: 2 pure `CREATE TABLE` + 2
`CREATE INDEX`, zero `ALTER` on existing tables).

**Extended** to close the remaining gap against this task's field list:
`_save_portfolio_state()` now accepts an optional `account` snapshot
(passed from the real tick loop's already-fetched broker data) and enriches
the persisted record with `balance`, `equity`, `margin`, `free_margin`,
`exposure_symbols`, a session-local `peak_equity`/`drawdown_pct`, and
`snapshot_at` — additive keys only, so existing JSON-file consumers are
unaffected. **Known, deliberate limitation**: `peak_equity` is a module-
level variable, not itself persisted/reloaded — it resets to 0 on process
restart rather than surviving across restarts. Fixing that properly (a
proper high-water-mark ledger entry) was judged to deserve its own isolated
pass rather than being rushed into an already-large review.

**Immutability/auditability**: `operations.risk_portfolio_history` is
append-only by construction (no code path anywhere calls `UPDATE`/`DELETE`
on it) — every `trade_close`/`daily_reset`/`halt_engaged` event gets its own
permanent row. The "current state" table is intentionally mutable (an
upserted snapshot, not a ledger entry) — that split is the correct design,
not a gap.

**Two more test-isolation incidents found while verifying this WIP was safe
to build on** — both by actually running the full suite and inspecting the
live host, not by code review alone:

1. **`operations.risk_portfolio_state`/`history` pollution.**
   `RiskPortfolioStore` is a module-level singleton (`_rps_store =
   RiskPortfolioStore()`) with no constructor seam for test injection —
   unlike `ExecutionStateStore(root)`, which tests already isolate via
   `tmp_path`. `tests/execution/test_risk_portfolio_store.py` (the WIP's own
   test file) correctly patches `execution.risk_portfolio_store.SessionLocal`,
   but nothing protected the *other* tests that exercise
   `scripts.run_st_a2_demo`'s save/load functions. Confirmed by running the
   full suite twice and diffing table row counts: 2 rows leaked into a table
   that had existed for seconds. **Fixed**: a root `tests/conftest.py`
   autouse fixture stubs `runner._rps_store` for any test where
   `scripts.run_st_a2_demo` is loaded — verified via two consecutive
   full-suite runs with zero row growth.
2. **`logs/strategy_demo_state.json` corruption — the most serious finding
   of this whole pass.** `tests/execution/test_emergency_stop_integration.py`
   calls `runner._tick()` directly with a fake `manager.get_positions()`
   returning `[{"id": "POS-1"}]`, and never monkeypatched
   `_STATE_PATH`/`_RISK_STATE_PATH`/`_PORTFOLIO_STATE_PATH` (hardcoded
   `Path("logs") / "..."` module constants). Running this test **overwrote
   the real, live-deployed runner's own real-time state file** with the
   test's fake position and an emergency-stop-active flag — caught only by
   directly re-reading the live file immediately after a test run and
   noticing `open_positions`/`status` didn't match what had been observed
   moments earlier. It self-healed because the real runner's next 60s tick
   overwrote it again before any human or automated consumer observed the
   corrupted intermediate state — this was luck, not safety by design.
   **Fixed at two layers**: the specific test now monkeypatches all three
   paths explicitly (documents the incident inline), and the same root
   `tests/conftest.py` fixture now supplies a `tmp_path`-based default for
   all three paths for *any* test touching this module — a test's own
   explicit override still takes precedence (monkeypatch's normal
   last-write-wins), so this is a safety net, not a behavior change, for
   tests that already isolate themselves correctly.

**Verified, definitively**: two consecutive full-suite runs (1687 passed, 10
pre-existing/unrelated failures — confirmed via `git stash` — 4 skipped,
identical both times) with zero growth in `data/execution/` file count,
zero growth in `operations.risk_portfolio_state`/`history` row counts, and
byte-identical `logs/risk_state.json`/`portfolio_state.json` (the one
`logs/strategy_demo_state.json` checksum change between runs was confirmed
to be the real runner's own legitimate tick activity — `status: running`,
`open_positions: []`, `pid` matching the actual live process — not test
pollution). All three cleanup actions (376 files, then 2+2 database rows)
were executed only after explicit user approval for each specific instance,
per this repo's data-destruction safety policy.

## 15. Fourth test-isolation incident: live Telegram alert pollution (2026-07-06)

After restarting `smc-demo-runner.service` with the reviewed §14 code, a
query of `operations.execution_event` for `telegram_alert:*` rows (to verify
persistence end-to-end per the Production Candidate directive's item 3)
found 12 rows with `sent: true`, all with the literal payload text
`xxxx...xxxx` (a run of `x` characters). Timestamps ranged 2026-07-06
03:34–05:03, all preceding the 05:05:56 runner restart.

**Root cause**: `tests/test_telegram_alerter.py::test_long_messages_are_clipped_to_telegram_limit`
is a pre-existing test that supplies a fake HTTP `_Session` to exercise
`TelegramAlerter._post()`'s message-clipping logic, but never mocks the
persistence side effect. `_post()` unconditionally calls
`_persist(category, text, sent=...)` (`monitoring/telegram.py`), which calls
`execution.operations_recorder.record_telegram_alert()` — a real write to
`operations.execution_event` — on every invocation, independent of whether
the HTTP send itself is faked. The test's synthetic `"x" * (LIMIT + 200)`
payload was never intended to reach a live table, but every full-suite run
(and there were many, across all four incidents in §13/§14) wrote one more
row of it into the same table the dashboard's event log reads from.

This is the same root-cause family as §13/§14: new functionality
(persistence side effects) added to already-tested code paths without
updating the pre-existing tests that exercise those paths to isolate the
new effect.

**Fixed**: wrapped the test's `_post()` call in
`patch("execution.operations_recorder.record_telegram_alert")` — patching
the origin module rather than `monitoring.telegram`, since the import inside
`_persist()` is a local (call-time) import, not a module-level binding.
Reviewed every other `_post`-touching test in the file; all others either
replace `_post` itself with an `AsyncMock`/fake (never reaching `_persist`)
or already wrap the call in the same `patch(...)` pattern — this was the one
gap.

**Cleanup**: the 12 confirmed-synthetic rows (`payload->>'message' LIKE
'xxxx%'`, `event_type = 'telegram_alert:generic'`) were deleted after
explicit user approval. Post-cleanup query confirmed 0 remaining
`telegram_alert:*` rows.

**Verification**: full suite re-run (1687 passed, 10 pre-existing/unrelated
failures — confirmed unrelated via `git stash` comparison, see §14 — 4
skipped) with zero new `telegram_alert:*` rows. `test_telegram_alerter.py`
in isolation: 13/13 passed.

**Outstanding**: no *legitimate* Telegram alert has fired since the 05:05:56
restart (no errors, reconnects, or signals have occurred in that window), so
this incident closes the false-positive but does not yet produce a positive,
live-fired example row. The `pipeline_started` event recorded at 05:06:03
confirms the `operations.execution_event` write path itself is live and
functioning post-restart; the Telegram-specific write path is verified by
code review + unit test (`test_telegram_alerter.py`) rather than by an
observed live alert. Treat "Telegram alert persistence verified end-to-end"
as: wiring confirmed correct and pollution-free, live positive example
pending a real trigger.

## 16. Demo Validation Mode (2026-07-06, Production Candidate Advancement item 2)

Full design/architecture in `docs/operations/DEMO_VALIDATION_MODE.md` —
this section records the delivery evidence and the reuse decisions made.

**What was built**: a `--mode demo_validation` fourth value on the existing
`scripts/run_st_a2_demo.py` mode enum (not a new parallel mode system —
see the governing design decision in the plan/doc), adding: durable
per-campaign session tracking (`operations.validation_session`, migration
006), per-trade per-stage lifecycle timing with computed durations
(`operations.validation_lifecycle_event`, same migration), a latency
percentile calculator (first real per-stage timing implementation in this
codebase — `dashboard/status_server.py`'s `_execution_latency()` was an
explicit stub returning `None` before this), an 8-file + Markdown report
generator, three new Telegram alert helpers, four new read-only dashboard
endpoints, and a `VALIDATION` tab in the React dashboard.

**Reuse, not duplication** (verified during planning via 3 Explore agents
before writing any code): `execution/operations_recorder.py`'s
`OperationsRecorder.event_sink`/`CanonicalExecutionPipeline` wiring,
`execution/startup_recovery.py::reconcile_pending_executions()`,
`execution/mt5_connector.py`'s reconnect logic, the RBAC
`require_authenticated()` gate, and the frontend's existing tab-switcher
pattern were all reused unmodified. `operations.fill`/`position_record`/
`reconciliation` tables existed since migration 004 with zero writers
anywhere in the codebase — this work added their first writer functions
(`record_fill`/`record_position`/`record_reconciliation` in
`execution/operations_recorder.py`) rather than creating new tables.

**Safety-relevant fix found during wiring**: `execution/control_plane.py`'s
`TradingPermissionService` only applied its critical-health block
(`state["health"]["critical_unknown"]`) to `environment in {"demo", "live"}`.
Adding `demo_validation` to this set was necessary — without it, a real
broker-trading mode would have silently bypassed a risk-relevant safety
gate. Pinned with two new regression tests in `tests/execution/test_control_plane.py`
(`test_demo_validation_environment_blocks_on_critical_unknown_health`,
`test_shadow_environment_is_not_gated_by_critical_unknown_health`).

**Test isolation discipline applied proactively** (not retrofitted after an
incident, unlike §13-15): the new `_validation_session_mgr` module-level
singleton in `scripts/run_st_a2_demo.py` got a `tests/conftest.py` stub
fixture in the same commit it was introduced, following the exact pattern
established for `_rps_store` in §14.

**Verification**:
- Migration 006 applied (`alembic upgrade head`), both tables confirmed via
  `information_schema.tables`.
- 42 new tests added across `tests/execution/test_validation_session.py`,
  `test_validation_recorder.py`, `test_validation_metrics.py`,
  `test_validation_report.py`, `test_operations_recorder.py` (dormant-table
  writers), `test_control_plane.py` (safety-gate regression),
  `tests/dashboard/test_validation_endpoints.py`, and
  `tests/test_telegram_alerter.py` (new alert helpers) — all mock
  `db.connection.SessionLocal`, matching this repo's established DB-test
  convention; none require a live Postgres connection to pass in CI.
- Full suite: 1729 passed (up from 1687 pre-change), same 10
  pre-existing/unrelated failures (confirmed via `git stash`), 4 skipped —
  zero regressions.
- Manual end-to-end verification against the **real** Postgres database
  (not mocks): created a disposable session, recorded 5 lifecycle stages
  across 2 trades, generated all 9 report files including
  `validation_report.md`, confirmed correct duration/percentile/success-rate
  computation, then deleted the verification rows after explicit user
  approval (same cleanup discipline as §13-15).
- Frontend: `tsc --noEmit` clean after adding `ValidationDashboard.tsx` and
  the `authenticatedFetch` context export.

**Not done in this task** (explicitly out of scope per the task's own
constraints): VPS reboot testing, long-running live/demo trade collection,
production release tagging, version freeze — deferred to the next
production validation phase.
