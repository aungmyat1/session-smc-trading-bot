# Dashboard → Backend Architecture Mapping

- Date: 2026-07-04
- Maps every Gai-dashboard data need (from [DASHBOARD_STATUS.md](DASHBOARD_STATUS.md)) to the real
  System 2 subsystem that could back it, per the pattern: Dashboard Component → Backend Service →
  Database/File → WebSocket Event → REST API → Status.
- Source of truth for backend facts: direct file:line reads of `dashboard/app.py`,
  `dashboard/live_app.py`, `dashboard/status_server.py`, `dashboard/live_dashboard_service.py`,
  `scripts/health_check.py`, `core/trade_journal_db.py`, `execution/trade_journal.py`,
  `execution/execution_state.py`, `production/observability.py`, `dashboard/control_state.py`,
  `dashboard/auth.py`, `config/strategy_portfolio.yaml`, `config/strategy_catalog.yaml`,
  `svos/lifecycle/manager.py` — no new audit performed; consistent with `SYSTEM2_MASTER_PLAN.md`
  and `docs/audit/*`.

Status legend: **Real** (genuine live data path) · **Real-but-empty** (real plumbing, no data
populated yet) · **File-relay** (real but written by a batch/tick process, not request-time) ·
**Missing** (no backend equivalent exists).

---

## Phase 5 update (2026-07-04): `/api/operations/*` in `dashboard/status_server.py`

`status_server.py` is confirmed the **only actually-deployed** dashboard backend
(`live-dashboard.service` → `uvicorn dashboard.status_server:app`); `app.py` and `live_app.py`
(referenced throughout this document as "best integration point" candidates) remain undeployed —
see the "Summary" table below, unchanged by this pass. New endpoints therefore landed in
`status_server.py`, not `app.py`, so they're actually reachable in production. Every one is a thin
read-only slice over an existing service — no new business logic, no new broker/DB connections
beyond what `dashboard/live_dashboard_service.py`/`TradeJournalDB`/`execution/operations_recorder.py`
already open.

| Endpoint | Backend Service (reused, not duplicated) | Status |
|---|---|---|
| `GET /api/operations/health` | `_health_summary()` (existing) + `logs/strategy_demo_state.json` (`started_at` for uptime) + git SHA/hostname | **Real** |
| `GET /api/operations/account` | `dashboard/live_dashboard_service.py::load_snapshot()` → `portfolio.summary` | **Real**, subject to the same decoupled-connection caveat noted elsewhere in this doc (separate MetaAPI session from the runner's own — can return degraded/zeroed values under connection pressure, observed during Phase 5 validation) |
| `GET /api/operations/positions` | same `load_snapshot()` → `positions` | **Real**, same caveat |
| `GET /api/operations/orders` | same `load_snapshot()` → `orders` + `execution_monitor` | **Real** — resolves the "not yet exposed as a dashboard route" gap noted above for orders/execution queue |
| `GET /api/operations/trades` | `TradeJournalDB.summary()` + `load_snapshot()` → `trade_history` | **Real** — resolves the "needs a new REST route" gap noted above for closed-trade history/analytics |
| `GET /api/operations/strategy` | `logs/strategy_demo_state.json` directly (the runner's own state, not the broker-side snapshot) + `TradeJournalDB.summary()` | **Real** |
| `GET /api/operations/risk` | `logs/risk_state.json` + `logs/portfolio_state.json` (the runner's actual persisted counters) + `load_snapshot()` → `risk_dashboard` | **Real** — a better source than `check_portfolio()`'s "Real-but-misleading" throwaway `PortfolioManager()` instance noted below; per-strategy `CircuitBreaker` cooldown state remains genuinely unavailable cross-process (documented, not fabricated) |
| `GET /api/operations/events` | `execution/operations_recorder.py::get_recent_events()`/`get_recent_runtimes()` — Postgres `operations.execution_event`/`recovery_checkpoint`/`runtime` (Sprint 2.3) | **Real** — a genuinely new capability; nothing read these tables before this pass. Telegram alert history remains unavailable (send-only, no persistence) |

Response envelope, consistent across all eight: `{"data": ..., "source": ..., "fetched_at": ..., "unavailable": [...]}`.

---

## Phase 6 update (2026-07-04): dashboard coverage matrix

The Gai dashboard's LIVE tab (`LiveOperationsDashboard.tsx`) is now wired to
`GET /api/new-dashboard/live-state` (added to `status_server.py` this phase — the same
`build_live_state()` `app.py` already had) and verified end-to-end in a real browser (Playwright:
real strategy catalog, real broker status, zero console errors, zero crashes — two real defects
found this way are documented in `SYSTEM2_MASTER_PLAN.md`'s Phase 6 entry). Classification below is
per capability, at the widget level, for the LIVE tab specifically — the `SVOS`/`SUGGESTIONS` tabs
are System 1/fabricated-data territory and out of this System 2 integration's scope.

Legend: **Implemented** (backend complete, frontend connected, production ready) · **Backend Ready**
(real data source exists — via `build_live_state()` and/or `/api/operations/*` — but the LIVE tab
doesn't render it) · **Planned** (no backend source at all yet).

| Capability | Widget | Status |
|---|---|---|
| 1. Platform Health | Broker connection status/latency/heartbeat | **Implemented** — "Broker Gateway Link" card, `state.brokerConnection` |
| 1. Platform Health | Runner/execution status | **Implemented** — inferred from positions/pipeline panels being live vs. idle |
| 1. Platform Health | Database / Risk Engine / Execution Engine / Strategy Engine health grid | **Backend Ready** — `state.health` (`build_live_state()`) and `/api/operations/health` both real; **no widget on the LIVE tab renders `state.health` at all** (confirmed by grep — only the SVOS tab's separate `SystemHealth.tsx` does) |
| 1. Platform Health | Uptime, deployment info (git SHA, systemd unit) | **Backend Ready** — `/api/operations/health` only (Phase 5); not part of `build_live_state()`'s shape, so the LIVE tab has no field to bind to yet |
| 1. Platform Health | Alerts (Telegram) | **Planned** — no persisted alert history exists anywhere (documented gap, not a wiring gap) |
| 2. Trading Operations | Account summary (balance/equity/PnL/margin) | **Implemented** — PnL/Margin cards; data quality subject to the known `live_dashboard_service.py` decoupled-connection caveat (pre-existing, documented) |
| 2. Trading Operations | Open positions | **Implemented** — "Live Positions" panel |
| 2. Trading Operations | Orders (failed/retry queue) | **Implemented** — `state.failedOrders`/`state.retryQueue` rendered; full pending/filled/rejected order table is **Backend Ready** only (`/api/operations/orders` has it, LIVE tab doesn't render a table for it) |
| 2. Trading Operations | Recent/trade execution history | **Implemented** — `TradeExecutionHistory.tsx` |
| 3. Strategy Operations | Active strategy, version, symbols, risk profile | **Implemented** — `StrategyRuntimeStatus.tsx` via `state.strategyPackages` (the exact surface fixed this phase) |
| 3. Strategy Operations | Heartbeat, execution statistics | **Backend Ready** — real via `/api/operations/strategy` (Phase 5); not part of `strategyPackages`' shape, not shown on this specific widget |
| 4. Risk Operations | Daily risk used / daily loss | **Implemented** — "Daily Risk Used" card |
| 4. Risk Operations | Drawdown, exposure, consecutive losses | **Backend Ready** — real via `/api/operations/risk` and `build_live_state()`'s `risk_dashboard`; confirmed by grep, no widget on the LIVE tab binds to these fields |
| 4. Risk Operations | Emergency stop / trading-paused state | **Implemented** (display) — `state.isTradingPaused` drives the Pause/Resume button; **actually pausing/resuming is not wired** (Operator Controls milestone — see below) |
| 4. Risk Operations | Capital Risk Policies editor (max loss/positions/leverage/auto-disable) | **Backend Ready, display-only** — reads real `riskControls` fields where they exist (`maxDailyLoss`, `maxOpenPositions`); `maxLeverage`/`autoDisableConditions` have no backend equivalent and now default safely rather than crash (Phase 6 fix); "Commit Risk Policy" has no working backend endpoint at all |
| 5. Operational Events | Execution/risk/system/broker/startup/shutdown events | **Backend Ready, not connected** — `build_live_state()` hardcodes `"events": []` always; `/api/operations/events` (Phase 5) has the real, durable data (Postgres `operations.*`) but nothing on the LIVE tab reads that endpoint yet. The console-logs panel is real UI bound to permanently-empty data |
| — | Operator Controls (pause/resume/kill-switch/risk-control save/strategy activate-pause/broker reconnect) | **Planned** — `SocketContext.tsx` already has the frontend functions (`pauseTrading`, `triggerKillSwitch`, etc.) but every target endpoint (`/api/action`, `/api/live/*`) is absent from the deployed backend; explicitly the next-but-one milestone, not attempted this phase |

### Implementation percentage by capability (LIVE tab, rough estimate by widget count above)

| Capability | Implemented | Backend Ready | Planned |
|---|---:|---:|---:|
| 1. Platform Health | 2/5 (40%) | 2/5 | 1/5 |
| 2. Trading Operations | 4/4 (100%, one sub-item backend-ready) | — | — |
| 3. Strategy Operations | 1/2 (50%) | 1/2 | — |
| 4. Risk Operations | 2/4 (50%, one display-only) | 2/4 | — |
| 5. Operational Events | 0/1 (0%) | 1/1 | — |
| Operator Controls (cross-cutting) | 0/1 | — | 1/1 |

**Overall**: roughly half of what's displayed is fully real end-to-end; nearly all the rest already
has a real backend source (Phase 5's `/api/operations/*` family) and just needs a frontend binding —
genuinely "Planned" (no backend at all) is limited to Telegram alert history and Operator Controls.

---

## `state.pairs[symbol]` (price/trend/HTF bias/spread/ATR/swing/pipeline/activeObjects/candles)

| Field | Backend Service | Store | WS Event | REST API | Status |
|---|---|---|---|---|---|
| `price`, `candles` | `execution/vantage_demo_executor.py::get_candles()` via `dashboard/live_dashboard_service.py:359` | MetaAPI RPC (live) | none | `GET /api/live-dashboard?symbol=&timeframe=&count=` (`app.py:1251`, `live_app.py:56`) | **Real**, pull-only (no push) |
| `price` (file relay) | demo runner writes per-tick | `logs/candles/{SYMBOL}_M15.json` | none | `status_server.py` reads at request time | **File-relay** |
| `trend`, `htfBias`, `swingHigh/Low`, `atr` | none | none | none | none | **Missing** — no strategy exposes HTF bias/swing/ATR as a queryable field; would require new instrumentation in whichever strategy adapter is live |
| `spread` | `scripts/health_check.py::check_data_feed()` (114-143) computes spread per pair as a health check side-effect | in-memory, per health-check run | none | via `/api/rgm`/`/api/governance`/`/api/smo` health snapshot, not a per-pair feed | **Real-but-narrow** — exists only inside the health-check path, not exposed as its own timeseries |
| `pipeline` (12-stage HTF/liquidity/CHoCH/BOS/OB/FVG/confluence/killzone/spread/risk/position/ready checklist) | none | none | none | none | **Missing** — this is SMC-strategy-specific instrumentation invented for the mock; no adapter in `strategies/adapters/*.py` currently emits per-stage pass/fail state. Would need to be added inside whichever strategy is live if this checklist view is wanted |

> **Route-naming correction**: the frontend hardcodes `GET /api/status` as its unified state
> endpoint. That path is **already taken twice** — `dashboard/app.py:831` (`api_status`, returns an
> SVOS/EVF/system summary) and `dashboard/status_server.py` (its own unrelated `/api/status`,
> merging local file state + `TradeJournalDB().summary()` + control state) — both pre-existing,
> both incompatible with `LiveDashboardState`. Do not add a third, conflicting `/api/status`. Any
> real integration must land under a new path (e.g. `/api/new-dashboard/live-state`) and the
> frontend's fetch calls must be repointed accordingly.
| `activeObjects` (OB/FVG zones w/ age, strength, mitigation) | none | none | none | none | **Missing** — same as above |

## `state.health` (broker/redis/database/riskEngine/executionEngine/strategyEngine/websocket)

| Component | Backend Service | Store | WS Event | REST API | Status |
|---|---|---|---|---|---|
| Broker | `scripts/health_check.py::check_broker()` (96-111), real `MT5Connector.heartbeat()` | in-memory per invocation | none | composed into `/api/rgm`, `/api/governance`, `/api/smo` (`app.py:521 _health_snapshot`) | **Real** |
| Database | `check_research_db()` (232-370), real TCP probe + `systemctl is-active postgresql` | in-memory + escalation-state JSON | none | same as above | **Real** |
| Risk engine | `check_risk_engine()` (373-403) | in-memory | none | same | **Real**, but reads config flags, not the live runner's actual in-memory risk state |
| Portfolio | `check_portfolio()` (406-416) — **instantiates a fresh `PortfolioManager()`** | in-memory (throwaway instance) | none | same | **Real-but-misleading** — never reflects the actual running process's open positions/loss counters (see `SYSTEM2_MASTER_PLAN.md` Position/Risk Engine findings) |
| Execution | `check_execution()` (419-440) | env-var driven | none | same | **Real** (checks `DEMO_ONLY`/`LIVE_TRADING` flags + connectivity) |
| Journal/DB | `check_journal()` (443-451) via `TradeJournalDB().summary()` | SQLite `data/trade_journal.db` | none | same | **Real** |
| Recovery | `check_recovery()` (454+) reads `logs/bot_state.json` + `logs/trades.jsonl` | files | none | same | **Real** |
| Redis, "websocket" health | none | none | none | none | **Missing** — no Redis is used anywhere in this repo; the mock's `redis`/`websocket` health rows have no real counterpart at all |
| Production heartbeat | `production/observability.py::heartbeat()`/`health()` | `data/production/heartbeat.json` | none | `/api/v1/production/health` (`app.py:1082`), `/api/v1/production/heartbeat` POST (1088) | **Real-but-empty** — `data/production/` doesn't exist on this checkout; nothing has called the POST path yet |

## `state.history` / `state.analytics` (trade execution history, KPIs)

| Field | Backend Service | Store | WS Event | REST API | Status |
|---|---|---|---|---|---|
| Closed trades (symbol, entry, exit, SL, TP, PnL, R-multiple) | `core/trade_journal_db.py::TradeJournalDB` | SQLite `data/trade_journal.db`, table `trades` | none | not yet exposed as a dashboard route (only consumed by `status_server.py`'s `/api/status` merge and `check_journal()`) | **Real**, needs a new REST route to expose directly |
| `analytics` (winRate, PF, expectancy, maxDD, Sharpe) | `TradeJournalDB.summary()` (223-276) | same DB | none | same as above | **Real**, same gap |
| MAE/MFE, slippage, latency, commission, realRr | none — **no journal in this repo tracks these fields** | none | none | none | **Missing** — would require new columns/instrumentation in `execution/trade_manager.py`'s order-fill path, not just a dashboard change |
| Two other partial journals: `logs/trades.jsonl` (`TradeJournal`), `logs/strategy_demo_trades.jsonl` (`DemoTradeJournal`) | file-based | JSONL | none | none | **Real-but-fragmented** — three non-unified trade records exist; a dashboard mapping must pick one canonical source (recommend `TradeJournalDB`, the only SQL-queryable one with `.summary()`) |

## `state.activeTrade` / live positions

| Field | Backend Service | Store | WS Event | REST API | Status |
|---|---|---|---|---|---|
| Open broker positions | `live_dashboard_service.py::_fetch_broker_snapshot_async` (284-386), real MetaAPI `rpc.get_positions()` | none (live query) | none | `GET /api/live-dashboard` (`app.py:1251`) | **Real** |
| Position close/protect/cancel | same service | MetaAPI order calls | none | `POST` close (1259), protect (1274), cancel order (1296) — `require_operator("risk_operator","admin")` | **Real**, mutation-gated by role auth (no CONFIRM-token layer per `SYSTEM2_MASTER_PLAN.md` finding) |
| `core/portfolio_manager.py::_open_symbols` | in-memory `set()`, process-local | none | none | none | **Real-but-not-a-dashboard-source** — used for signal dedup, not display; would disagree with the broker snapshot above if surfaced naively |
| `TradeJournalDB.get_open_trades()` | SQLite query, `status='OPEN'` | same DB | none | none | **Real, independent 2nd view** — not reconciled with the broker snapshot; pick one as canonical or reconcile explicitly |

## `state.strategyPackages` / strategy runtime status

| Field | Backend Service | Store | WS Event | REST API | Status |
|---|---|---|---|---|---|
| Strategy list, status, symbols, risk profile | `dashboard/strategy_service.py` | `config/strategy_catalog.yaml` | none | `GET/POST /api/new-dashboard/strategies[/<id>]`, `promote`/`demote` (`app.py:1109-1161`) | **Real**, but this catalog (9 strategies, `DEFERRED_REVALIDATION`/`research`/`shadow`/`draft` vocabulary) is **not the same file** that gates live/shadow order routing |
| Live/shadow execution routing | `scripts/run_portfolio.py`, `strategies/adapters/st_a2_runtime.py` | `config/strategy_portfolio.yaml` (5 strategies: ST-A2, LondonBreakout, NYMomentum, AdaptiveSMC, VWAPMeanReversion) | none | none — not exposed to any dashboard route today | **Real, but unmapped to the dashboard** — a strategy-runtime-status widget wired only to `strategy_catalog.yaml` would show a different picture than what's actually routing orders |
| Pipeline/lifecycle stage per strategy | `svos/lifecycle/manager.py::StrategyStage` enum + `_LEGACY_STAGE_MAP` | manifest field / legacy status string | none | `strategy_service.get_pipeline_report()` → `GET /api/new-dashboard/strategies/<id>/pipeline-report` (1195) | **Real-but-empty** — reads `reports/svos/<id>/<version>/<run>/run_summary.json`; no per-strategy run directories exist yet for any of the 5 portfolio strategies (only `SVOS-SAMPLE`/`platform` exist) |

## `state.brokerConnection`, `state.riskControls`, `state.systemResources`

| Field | Backend Service | Store | WS Event | REST API | Status |
|---|---|---|---|---|---|
| Broker connection status/latency | `live_dashboard_service.py` broker snapshot | live MetaAPI query | none | `GET /api/live-dashboard` | **Real** |
| Risk controls (max daily loss, max positions, max leverage) | `config/*.yaml` risk fields (`strategy_portfolio.yaml` per-strategy `risk` values) | YAML | none | not exposed as an editable dashboard object today | **Real values exist, no dedicated API** |
| CPU/RAM/disk | none found | none | none | none | **Missing** — would need `psutil` or equivalent added; nothing in the repo currently reports process resource usage |

## Emergency stop / kill switch / operator controls

| Field | Backend Service | Store | WS Event | REST API | Status |
|---|---|---|---|---|---|
| Emergency stop activate/clear | `dashboard/control_state.py` | `reports/control_state.json` | none | `app.py`: `POST /api/emergency-stop` (1403, role-gated + `confirm_token: "CONFIRM-EMERGENCY-STOP"`), `/clear` (1420, `"CONFIRM-CLEAR-EMERGENCY-STOP"`) | **Real**, correctly CONFIRM-token gated |
| Same, second copy | `status_server.py` | same file | none | `/api/emergency-stop` (1522) / `/clear` (1538) | **Real but auth-inconsistent** — same confirm-token string, **no role/auth decorator at all** on this copy |

## Auth

| Concern | Backend Service | Mechanism | Status |
|---|---|---|---|
| Session identity | `dashboard/auth.py::build_session_payload` → `GET /api/session/me` | Bearer token + `X-SVOS-Actor`/`X-SVOS-Role`, or trusted-proxy headers + CSRF double-submit | **Real**, but only enforced on `app.py`/`live_app.py` routes — `status_server.py`'s mutation routes bypass it entirely |
| Frontend today | Gai dashboard | none | **Missing** — no login, no token attached to any of its `fetch` calls |

## WebSocket

Confirmed via repo-wide grep: **no WebSocket server exists anywhere in the Python backend**
(`dashboard/`, `core/`, `execution/`, `production/`, `svos/` all clean). Every "live" backend
value is request/response only. This matches `SYSTEM2_MASTER_PLAN.md`'s "Missing" classification —
not a new finding, just reconfirmed against this specific integration.

---

## Summary: what the dashboard's 3 backend processes actually are today

| Process | Framework | Real data it serves | Relevant to Gai dashboard? |
|---|---|---|---|
| `dashboard/app.py` | Flask | SVOS catalog/reports, production observability, live broker positions/candles, emergency-stop, session auth, serves old `New Dashborad/dist/` at `/new-dashboard/` | **Yes — best integration point** (already does auth + live broker + SVOS reads + static SPA hosting) |
| `dashboard/live_app.py` | Flask | Slimmed duplicate of `app.py`'s live-position routes | No — candidate for retirement per `SYSTEM2_MASTER_PLAN.md` Phase 3 |
| `dashboard/status_server.py` | FastAPI | Local demo-runner file reads (`logs/*.json`), its own `/api/status`, unguarded emergency-stop | No direct reuse — but note it is the **currently-deployed** dashboard process (`live-dashboard.service`); `app.py` is not confirmed deployed |
