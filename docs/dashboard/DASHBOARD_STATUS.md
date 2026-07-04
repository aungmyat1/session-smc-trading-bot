# Dashboard Status — "Gai Dashboard" Assessment

- Date: 2026-07-04
- Scope: `New Dashborad/Gai dashboard/` (React 19 + Vite + Express/`ws` reference server), assessed
  as the candidate baseline UI for System 2's operator interface per the Phase-1 assessment brief.
- Method: direct source read of every file under `New Dashborad/Gai dashboard/src/`, its
  `server.ts` mock backend, and `src/docs/UPGRADE_SPEC.md` (the spec this dashboard was originally
  built from). Cross-checked against `SYSTEM2_MASTER_PLAN.md` and `docs/audit/*` for backend
  reality — no new backend audit was performed; see
  [DASHBOARD_BACKEND_MAPPING.md](DASHBOARD_BACKEND_MAPPING.md) for that side.
- This is **not** the same code as the dashboard already integrated into `dashboard/app.py` today.
  That integration point is `New Dashborad/` (top level — SVOS-pipeline-only components:
  `AuditReportView`, `ReplayView`, `RobustnessView`, `StatisticalView`, `VirtualDemoView`,
  `GovernanceView`), built to `New Dashborad/dist/` and served at `/new-dashboard/`. **`Gai
  dashboard` is a separate, newer, more complete delivery** one directory level deeper, covering
  both live operations and SVOS research in one app, and has never been built or deployed.

---

## 1. What this app is

A single-page React app with a manual (non-router) 3-tab switcher in `App.tsx`: **LIVE**
(`LiveOperationsDashboard`), **SVOS** (`SvosResearchDashboard`), **SUGGESTIONS**
(`SuggestionsTab`). All three tabs share one `SocketProvider` / `useSocket()` context
(`src/context/SocketContext.tsx`) that holds a single `LiveDashboardState` object (see
`src/types.ts`) refreshed either by WebSocket push or, as a fallback, by polling `GET /api/status`
every 1.5s.

It ships with its own self-contained mock backend, `server.ts` (Express + `ws`, 1101 lines): a
simulated EURUSD/GBPUSD/USDJPY tick engine that fabricates the entire `LiveDashboardState` payload
every 1.5s and broadcasts it as `{type:"TICK", state}` over `/ws` and `/api/ws`. **This mock server
is what the app currently runs against — there is no wiring today to any part of this repository's
real Python backend.** `src/docs/UPGRADE_SPEC.md` (authored alongside this delivery) documents this
mock design explicitly, including its own "Production Readiness Report" section — that section
describes production-readiness of the mock server itself (compiling to `dist/server.cjs` on Cloud
Run), not integration with System 2.

## 2. Implemented screens

| Screen/Tab | Status | Notes |
|---|---|---|
| LIVE — LiveOperationsDashboard | **Partial** | Automated-mode section is real (WS-driven): top KPIs, live positions, strategy deployment controls, embeds `StrategyRuntimeStatus`, `TradeExecutionHistory`, event console. A second, fully separate **"Manual Sandbox Trader" mode is 100% client-side fake** paper trading (hardcoded starting balance, `setTimeout`-simulated fills, no backend contact at all). |
| SVOS — SvosResearchDashboard | **Partial/Placeholder** | Thin real composition shell (renders a pipeline timeline from real per-pair `state.pairs[x].pipeline` data) wrapping `SvosQuantLab`, which is **100% scripted fake** backtest/Monte Carlo/walk-forward/"self-training LSTM" simulation (confirmed zero `fetch`/`api`/`ws`/`env` references). |
| SUGGESTIONS — SuggestionsTab | **Placeholder** | Fully fabricated static suggestion cards and client-only "confluence tweak" math; touches real state only to read one live price number. |

## 3. Reusable components (real data, finished quality)

- `PipelineGrid.tsx`, `RejectionsAndAnalytics.tsx`, `EventStream.tsx`, `TradesTable.tsx`,
  `ActiveTradeCard.tsx`, `StrategyRuntimeStatus.tsx`, `TradeExecutionHistory.tsx` — fully
  prop/context-driven, no hardcoded business data, ready to reuse once fed real payloads.
- `SystemHealth.tsx` — finished, real-data-shaped component (`ServiceHealth`/`SystemHealth` props)
  that is **currently unused/orphaned** — not imported anywhere in `App.tsx`,
  `LiveOperationsDashboard.tsx`, or `SvosResearchDashboard.tsx`. Cheapest real win available (see
  Gap Analysis §Quick Wins).

## 4. Placeholder / fake-data components

- `SvosQuantLab.tsx` (1852 lines) — entirely scripted demo, not a functioning backtester.
- `SuggestionsTab.tsx` — fabricated recommendations.
- `StrategyGuide.tsx` — static educational content (only the kill-zone clock needle computes live
  from `Date.now()`; everything else, including a 17-candle example SVG, is hardcoded).
- `LiveOperationsDashboard.tsx`'s Manual Sandbox mode — fake paper-trading UI.
- Partial/hardcoded-within-real-component: `LiveChart.tsx` (Asian-range and BOS/CHoCH price levels
  hardcoded per symbol — will misrender for any symbol/price range not in the mock's 3-pair set)
  and `PairCards.tsx` (BOS/CHoCH display values hardcoded per symbol).

## 5. WebSocket usage

`SocketContext.tsx` connects same-origin (`${protocol}//${host}${path}`, alternating `/ws` and
`/api/ws` across reconnect attempts — no configurable host/port, relies on being served from the
same process as its API). Reconnect is a fixed 3s delay (not exponential), with an automatic
fallback to REST polling of `GET /api/status` (returns the raw `LiveDashboardState` object, not
wrapped) every 1.5s while disconnected. All user actions (`pauseTrading`, `forceCloseTrade`,
`activateStrategy`, `triggerKillSwitch`, `updateRiskControls`, `reconnectBroker`, etc.) are REST
`POST`s, not WS messages — WS is receive-only from the client's perspective. `PING`/`PONG` exists
in the type surface but the client never actually sends `PING` (dead code path).

## 6. API requirements (as the frontend already expects them)

Called by the frontend today (against the mock `server.ts`):
`GET /api/status`, `POST /api/action` (`pause|resume|reset|select_pair|force_close`),
`POST /api/live/strategy/activate`, `POST /api/live/strategy/pause`,
`POST /api/live/kill-switch`, `POST /api/live/risk-controls`, `POST /api/live/broker/reconnect`.

`server.ts` additionally defines `GET /api/trades`, `GET /api/rejections`,
`GET /api/live/positions`, `GET /api/live/strategies`, `GET /api/live/status`,
`GET /api/live/broker` — none of these are actually called by any frontend code found; they are
orphaned mock-server endpoints.

None of these paths exist today with this shape — but **`GET /api/status` is not a free path**:
it already exists in both `dashboard/app.py:831` and `dashboard/status_server.py` with an
unrelated, incompatible contract (SVOS/EVF/system summary, per `SYSTEM2_MASTER_PLAN.md`'s
duplicate-route finding), so a real integration must expose the Gai dashboard's expected state
under a **new, distinct path** (e.g. `/api/new-dashboard/live-state`) and repoint the frontend's
`SocketContext.tsx` fetch calls at it, rather than overloading the existing `/api/status`. See
[DASHBOARD_BACKEND_MAPPING.md](DASHBOARD_BACKEND_MAPPING.md) for the closest real equivalents.

## 7. Routing

No React Router. `App.tsx` holds `useState<"LIVE"|"SVOS"|"SUGGESTIONS">` toggled by 3 header nav
buttons; a single `SocketProvider` wraps the whole app so all tabs share one connection/state.

## 8. State management

Single global `LiveDashboardState` object (see `src/types.ts` for the full field list) held in
React context (`SocketContext`), replaced wholesale on every `INITIAL_STATE`/`TICK` frame or REST
poll — no per-field diffing, no local caching/store library (no Redux/Zustand/React Query).

## 9. Authentication

**None.** No login, no token, no per-user session anywhere in the frontend or `server.ts`; the
mock backend holds one global mutable state shared by all connected clients. This is a hard gap
against the real backend's `dashboard/auth.py` (Bearer token + `X-SVOS-Actor`/`X-SVOS-Role`
headers, or trusted-proxy header scheme with CSRF double-submit — see backend mapping doc).

## 10. Production readiness verdict

**Not production ready as-is against System 2.** The component layer (chart, tables, panels,
health bar) is largely finished, well-typed, and reusable. The data layer is the blocker: it is
100% mock-server-shaped, has no auth, assumes a single unified WebSocket-pushed state object that
does not exist anywhere in the real Python backend, and several visually-convincing panels
(`SvosQuantLab`, `SuggestionsTab`, Manual Sandbox mode) are elaborate fabrications that would
actively mislead an operator if shipped unchanged. Treat the component tree as the UI baseline (per
the task brief — do not redesign it), and treat the entire data/transport/auth layer as needing to
be rebuilt against real System 2 services. Full gap detail:
[DASHBOARD_GAP_ANALYSIS.md](DASHBOARD_GAP_ANALYSIS.md).
