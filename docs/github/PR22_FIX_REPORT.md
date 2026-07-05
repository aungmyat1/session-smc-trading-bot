# PR #22 Fix Report — 2026-07-05

Commit `dda40ed` on `codex/demo-smoke-test`, pushed to PR #22. Scope: merge-blocking/safety-critical review findings only. No new features, no unrelated refactors, `LIVE_TRADING`/`DEMO_ONLY` untouched.

## Fixed (8 items)

| Severity | File | Fix |
|---|---|---|
| P1 | `svos/lifecycle/authority.py` | `transition()` now commits on success, rolls back on failure — previously never committed, so successful promotions were silently rolled back. |
| P1 | `SocketContext.tsx` (Gai dashboard) | Kill switch now posts to real `/api/emergency-stop` (confirm token + `close_positions` scope) instead of a dev-only simulated route; no longer reports success on a failed response. |
| Major | `dashboard/rbac.py` | Bearer auth grants a fixed server-side role (`SVOS_OPERATOR_ROLE`, default `admin`) instead of trusting the caller's `X-SVOS-Role` header. |
| Major | `dashboard/status_server.py` | `/ws` authenticates before accept/subscribe. |
| Major | `dashboard/status_server.py` | `/overview`, `/live/trades`, `/svos/status`, `/strategies/performance`, `/system/health` now require an authenticated identity (read-only RBAC). |
| P2 | `execution/close_reconciliation.py` | Fetches the broker's real closing deal (new `VantageDemoExecutor.get_closing_deal`) instead of scoring from stale unrealized profit; falls back to prior behavior if unavailable. |
| Critical (found during fix, not in original review) | `execution/close_reconciliation.py` | `_last_positions` now advances only after successful reconciliation; a balance-fetch failure defers to next tick instead of silently zeroing P&L. |
| Minor | `dashboard/events.py` | Stopped double-wrapping event payloads under `payload["payload"]`. |
| (explicitly requested) | `core/trade_journal_db.py` | `get_trade_by_broker_order_id` rejects a blank id before querying. |

## Follow-up commit (`a41a102`) — resume-scoping fix

| Severity | File | Fix |
|---|---|---|
| Major | `dashboard/control_state.py`, `dashboard/status_server.py` | `emergency_stop` state now tracks a `source` (which control path created it: `control_pause`, `control_close_all`, `strategy_toggle:<id>`, `emergency_stop_endpoint`). `/api/control/toggle-strategy`'s resume branch now refuses (409, stop left active) instead of clearing a stop it didn't create. Global `/api/control/resume` and `/api/emergency-stop/clear` are unchanged — they're deliberately unscoped. |

Tests: 2 new regressions (own-stop resume succeeds; unrelated-stop resume is refused and the stop stays active in persisted state) + 70 passed across `test_status_server`, `emergency_stop_integration`, `control_plane`, `lifecycle_authority`, `system2_demo_readiness`, `test_dashboard_app`. `ruff`: same pre-existing findings, nothing new.

## Follow-up commit (`fa6b4c4`) — two edge cases CodeRabbit found reviewing `dda40ed`

| Severity | File | Fix |
|---|---|---|
| Major | `execution/close_reconciliation.py` | A returned balance of `0` (not just a fetch exception) now defers reconciliation instead of proceeding and silently recording `pnl_pct`/`r_multiple` as 0 while still marking WIN/LOSS from `profit`. |
| Major | `execution/vantage_demo_executor.py` | `get_closing_deal()` now lets a real broker-lookup failure propagate instead of collapsing it to `None` (same as "no deal found"); the caller defers the whole tick (no journal update, `_last_positions` not advanced) instead of silently trusting stale snapshot data. |

Tests: 2 new regressions + 24 passed across close-detection, position-close-detector, reconcile-positions, system2-demo-readiness. `ruff` clean.

## Not fixed

None remaining from the original 9 review findings or the 2 follow-on findings — all addressed across the three commits above.

## Tests (cumulative)

194 passed, 0 failed across all three commits (100 from `dda40ed` + 70 from `a41a102` + 24 from `fa6b4c4`, no overlap in suites run).

`ruff check` on all touched files: same pre-existing findings as before any of these commits — nothing new introduced. Frontend change verified by manual review only (no test runner in that app; `node_modules` not installed).

## CI

All required GitHub Actions checks pass on PR #22 post-fix (Required CI, Tests unit/integration, Quality and architecture, Documentation and package contracts, Security and dependencies).
