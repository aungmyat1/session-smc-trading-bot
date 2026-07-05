# Dashboard Readiness — Production Interfaces

Date: 2026-07-04
Status: Interface inventory only — no frontend work in this document
Purpose: identify what production data source backs each dashboard surface, and which are real vs.
placeholder today, ahead of dashboard live-integration work. Companion:
`docs/dashboard/DASHBOARD_IMPLEMENTATION_PLAN.md` (full frontend phase plan, unchanged by this pass).

---

| Interface | Production source today | Real or placeholder? |
|---|---|---|
| **Account** | `TradeManager.get_account_info()` via `VantageDemoExecutor`/`MT5Connector` — live MetaAPI balance/equity | Real, already surfaced in `logs/strategy_demo_state.json`'s `account` field |
| **Orders** | `execution/execution_state.py::ExecutionStateStore` (durable per-order state machine) + `operations.order_record`/`operations.intent`/`operations.risk_decision` (Postgres, Sprint 2.3) | Real, durable, queryable — not yet read by any dashboard code |
| **Positions** | `TradeManager.get_positions()` (live broker snapshot) + `logs/strategy_demo_state.json`'s `open_positions` | Real |
| **Trade history** | `core/trade_journal_db.py::TradeJournalDB` (SQLite, `trades` table — full signal-to-close lifecycle) | Real, mature, already the "source of truth for reconciliation and analytics" per its own docstring |
| **Strategy runtime** | `logs/strategy_demo_state.json`'s `strategy`/`mode`/`status`/`last_decision`/`pair_results` fields | Real — one strategy per process (this runner is single-strategy; a multi-strategy view would need `config/strategy_portfolio.yaml` reconciliation, noted as open in `docs/systems/system2/ROADMAP.md`) |
| **Risk** | `execution/demo_risk_manager.py` (`risk_state` — daily/weekly/monthly loss, consecutive losses, halted) + `core/portfolio_manager.py::PortfolioManager.stats()` + `operations.risk_decision` (Sprint 2.3, per-decision detail) | Real, but must be labeled "configured limits, currently enforced," not "durable ledger" — the risk_state JSON is not yet a transactional store (`SYSTEM2_MASTER_PLAN.md`'s still-open item) |
| **Health** | `dashboard/live_state_adapter.py::_build_health()` — real checks for broker/database/risk engine/execution engine/strategy engine; `redis` and `websocket` explicitly hardcoded `"N/A"` (neither exists in this architecture) | **Mixed** — 5 real checks, 2 honestly-labeled non-applicable, not fabricated |
| **Alerts** | `monitoring/telegram.py::TelegramAlerter` — real, already fires on trade open/close, emergency stop, errors, reconciliation mismatches | Real, but Telegram-only — no in-dashboard alert feed/history exists yet |
| **Operator controls** | `/api/emergency-stop` (dashboard) → `reports/control_state.json` → `TradingPermissionService`/`StrategyExecutionGuard` checked every tick in the canonical pipeline | Real for emergency-stop specifically; **other mutation-class actions** (position close/protect/cancel, strategy promote/demote, activation) exist but lack emergency-stop's CONFIRM-token pattern — a known, already-tracked gap, not new |
| **WebSocket events** | None — polling only, by deliberate prior decision (`SYSTEM2_MASTER_PLAN.md`) | Placeholder by design, not a gap to close incidentally |

## What changed this pass that's relevant to dashboard integration

1. `smc-demo-runner.service` is now actually trading ST-A2 (see `SYSTEM2_MASTER_PLAN.md`'s
   "Deployment fix" entry) — every interface above now has real, continuously-updating data behind
   it for the first time, not just a healthy-looking but empty pipeline.
2. `operations.*` Postgres tables (Sprint 2.3) are a materially better source for **Orders** and
   **Risk** (per-decision detail) than the current JSON/JSONL files — recommended as the next
   concrete wiring step (already flagged in `docs/systems/system2/ROADMAP.md`).
3. The "Production Platform v2" cluster removed this pass (`production/api.py::ProductionReadAPI`
   etc.) was **not** a dashboard data source in practice — it was never wired to anything — so its
   removal has zero impact on any interface above.

## Recommended interface priority for the next milestone

Highest-value, lowest-effort first: **Orders** and **Risk**, reading from the new `operations.*`
tables (data already flowing in, nothing to build on the producer side) — then **Alerts** (surface
Telegram's existing alert stream in-dashboard) — then **Operator controls** consistency
(CONFIRM-token on the remaining mutation routes). **WebSocket events** remains correctly deferred.
