# Demo Validation Mode

Status: implemented 2026-07-06 (Production Candidate Advancement).
Runner: `scripts/run_st_a2_demo.py --mode demo_validation`.

## Purpose

Demo Validation Mode proves out the full System 2 order lifecycle on a real
MT5 demo broker, using the exact same execution pipeline production will
eventually use — it is **not** a paper simulator. It adds session tracking,
per-stage lifecycle timing, and recovery-event visibility on top of the
existing `demo` mode, so a validation campaign produces auditable evidence
(reports, dashboard panel, Telegram alerts) rather than just log lines.

It does **not** change risk controls, broker gating, or trade placement
logic. `DEMO_ONLY`/`LIVE_TRADING` env vars and
`execution/vantage_demo_executor.py`'s `_guard()` are untouched — this is an
instrumentation layer, not a new execution mode at the broker level.

## Architecture

```
scripts/run_st_a2_demo.py --mode demo_validation
  │
  ├─ ValidationSessionManager (execution/validation_session.py)
  │     one operations.validation_session row per campaign — survives
  │     restarts, unlike operations.runtime (one row per process start)
  │
  ├─ CanonicalExecutionPipeline event_sink (unchanged wiring) also feeds
  │     ValidationLifecycleRecorder (execution/validation_recorder.py)
  │     → operations.validation_lifecycle_event, one row per
  │       (trade_id, stage) with a computed duration_ms since the previous
  │       stage for that trade_id
  │
  ├─ startup reconcile_pending_executions() (unchanged) result is also
  │     logged as a "recovery" stage row
  │
  └─ position-close detection in _tick() (unchanged detection point) is
        also logged as a "position_close" stage row

execution/validation_metrics.py   — read-side: avg/max/p50/p95/p99 per stage
execution/validation_report.py    — writes reports/demo_validation/*.json +
                                     validation_report.md
dashboard /api/validation/*       — read-only endpoints (status_server.py)
New Dashborad .../ValidationDashboard.tsx — VALIDATION tab in the SPA
monitoring/telegram.py            — send_validation_started/failure/summary
```

### Honesty note on the 13-stage lifecycle

`CanonicalExecutionPipeline` only emits `intent_received` / `risk_decision` /
`execution_result` / `intent_rejected` / `package_rejected` — it does not see
broker acknowledgement, fill, or SL/TP as distinct events (those happen
synchronously inside `TradeManager`, called from the adapter). This module
maps the real events to four honest stages —
`signal_generated`, `risk_evaluation`, `order_submission`, `order_rejected`
— plus two more from other real call sites: `recovery` (startup
reconciliation) and `position_close` (tick-level close detection, at
tick granularity, not per-position). It does not fabricate a
broker-ack/fill/SL-TP-modify breakdown that the underlying engine cannot
currently observe. Extending the pipeline itself to emit those finer events
is future work, not part of this change.

## Configuration

`config/demo_validation.yaml` — modeled on `config/demo.yaml`. Key
differences: tighter risk limits (max 3 trades/day, 1 open position, 0.10
lot cap) so a validation campaign proves the lifecycle out on a small,
capped sample rather than accumulating P&L; a `validation:` section with
the report output directory, promotion trade-count target, and informational
latency SLA thresholds (these do not block trading — see
`execution/validation_recorder.py`'s module docstring).

Set `VALIDATION_OPERATOR` env var to tag sessions with a human operator name.

## Running it

```
TRADING_MODE=demo_validation python3 scripts/run_strategy_demo.py
# or
python3 scripts/run_st_a2_demo.py --mode demo_validation
```

This behaves exactly like `--mode demo` for broker/order-placement purposes.
`DEMO_ONLY` must still be `true`; `LIVE_TRADING` must still be `false`.

## Dashboard

New `VALIDATION` tab (`New Dashborad/Gai dashboard/src/App.tsx`) shows:
session info (operator/broker/account/version/commit/config hash), lifecycle
success rate, per-stage latency table, and recent recovery events. Backed by
`GET /api/validation/session`, `/lifecycle`, `/latency`, `/recovery` —
`require_authenticated()` only (read-only, same auth as every other read
endpoint; no new auth system).

## Recovery / restart behavior

Reuses existing mechanisms — does not reimplement broker reconnect or
execution recovery:
- `execution/startup_recovery.py::reconcile_pending_executions()` (existing,
  unchanged) resolves incomplete `ExecutionRecord`s against broker truth on
  every startup; its outcome is additionally logged as a `recovery` stage row
  when in `demo_validation` mode.
- `execution/mt5_connector.py`'s existing `reconnect()` (heartbeat-triggered)
  handles broker disconnects; its `reconnect_attempts_total`/
  `last_reconnect_at` are already surfaced in the tick state and reused here,
  not reimplemented.
- No duplicate orders: idempotency is enforced by `ExecutionStateStore`
  (unchanged) and `operations.order_record.idempotency_key` (unchanged) —
  this instrumentation layer never places or retries an order itself.

## Validation reports

`execution/validation_report.py::generate_report(session_id)` writes to
`reports/demo_validation/`:

| File | Contents |
|---|---|
| `session_summary.json` | session metadata + lifecycle success rate |
| `trade_lifecycle.json` | per-stage latency stats |
| `latency_summary.json` | same latency stats, dedicated file per spec |
| `broker_health.json` | broker/account + reconnect-related events |
| `dashboard_health.json` | DB health check + recent runtime starts |
| `telegram_health.json` | persisted `telegram_alert:*` events |
| `ledger_health.json` | current risk/portfolio state (RiskPortfolioStore) |
| `recovery_summary.json` | recovery_checkpoint events |
| `validation_report.md` | human-readable summary of all of the above |

Generate on demand:

```python
from execution.validation_report import generate_report
generate_report("val-...")
```

## Failure handling

Every write in this feature (session, lifecycle event, dormant-table
writers) is best-effort: a DB hiccup is logged and swallowed, never raises,
never blocks a tick or an order — consistent with
`execution/operations_recorder.py`/`execution/risk_portfolio_store.py`'s
existing design. This is an audit/observability layer, not a safety gate.

## Promotion checklist

A human operator makes the promotion call — this report is evidence, not a
decision. Per `execution/validation_report.py`'s generated markdown:

- Minimum 20-50 successful demo trades (config: `validation.minimum_trades_for_promotion`)
- Stable lifecycle success rate (no unexplained `order_rejected`/error spikes)
- No unresolved recovery orphans (`recovery_summary.json`'s `orphaned_positions`)
- Latency within informational SLA thresholds (or a documented reason if not)

Explicitly **not** covered by this feature (deferred to the next production
validation phase, per the task that introduced it): VPS reboot testing,
long-running live/demo trade collection, production release tagging, version
freeze.

## Troubleshooting

- **No active session on the dashboard** — the runner was not started with
  `--mode demo_validation`, or `DATABASE_URL` is not configured (session
  tracking degrades to non-durable in that case — see
  `execution/validation_session.py`).
- **Empty latency table** — no lifecycle stages have been recorded yet for
  the active session; this is expected immediately after startup before the
  first signal.
- **`ValueError: unsupported execution mode`** — this would only happen if
  `demo_validation` were passed to `CanonicalExecutionPipeline(mode=...)`
  directly; it is not — the pipeline itself always runs `mode="demo"` in
  this runner, by design (see the Architecture honesty note above).
