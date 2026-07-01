# Implementation Plan: Governance, Safety, Duplication & Observability Fixes

**Repo:** `session-smc-trading-bot` | **Date:** 2026-07-01 | **Trigger:** follow-up to the full operational audit (Phases 1-15) run earlier this session.

## Context

The audit found the platform's execution engine, broker connection, and signal pipeline are healthy (0 crashes, self-healing reconnects), but surfaced 18 concrete gaps spanning governance, safety, code duplication, and observability. Three are the most consequential:

1. **Governance gap:** the strategy `SMCOrderBlockFVGSession` is registered in the SVOS lifecycle registry at stage `INTAKE` with all evidence gates (`backtest`/`replay`/`walk_forward`) marked `pending` and zero entry in `docs/VERDICT_LOG.md` — yet it runs live (dry-run orders, `LIVE_TRADING=false`) via `smc-demo-runner.service` every 60s against real market data. Nothing in `svos/lifecycle/manager.py` (a pure topology validator) or the file-based registry enforces evidence gates the way `db/control_plane.py`'s Postgres path does.
2. **Broken kill switch:** `dashboard/app.py` already implements `POST /api/emergency-stop` (CONFIRM-token gated) and `execution/trade_manager.py` already implements `emergency_close_all()` — but neither is wired to the other, and the live tick loop never checks the resulting control-state file. Today, pressing "emergency stop" does nothing to the running bot.
3. **Doc drift:** `CLAUDE.md` §5 documents magic numbers and a symbol set that no longer match the deployed config (`config/demo.yaml`, `scripts/run_st_a2_demo.py`), which itself violates this repo's own §0.3 rule ("treat this file's numbers as last-known, not ground truth... alert if API disagrees").

This plan closes those gaps plus 15 smaller findings (duplication cleanup, broker reconciliation, order retry, metrics/latency observability, infra hygiene), sequenced P0→P3 by risk and dependency. **User decisions already made** (via clarifying questions) and baked into this plan:
- Governance gap → **document only**, do not halt the running service or change the lifecycle schema.
- Kill switch → **add the route to the already-deployed `dashboard/status_server.py`** (FastAPI, port 8090), not a new service.
- `bot.py` → treated as **legacy/retired**; only docstring-clarify `execution/risk_manager.py` for now, no deletion.
- Scope → **full P0-P3** in this plan, executed phase by phase.

Governing constraints from `CLAUDE.md` that every item below respects: never touch `LIVE_TRADING`/`DEMO_ONLY`; no self-executed writes without an exact CONFIRM token; `svos/lifecycle/manager.py` stays the exclusive lifecycle-mutation authority (not touched); read-only reconciliation/observability additions need no new tokens; anything that changes a *running* service (systemd restarts, log deletion) needs a lightweight human go-ahead before executing, even though it's not a "trade" write endpoint.

---

## Phase P0 — Governance & doc-drift (land first, cheapest, unblocks trust)

### P0.1 — Fix `logger` NameError
- **File:** `scripts/run_st_a2_demo.py:287` — `logger.warning(...)` → `_log.warning(...)` (the module logger defined at line 88).
- One-line fix in the candle-cache exception handler; currently masks real errors with a `NameError`.
- **Verify:** `python -m py_compile scripts/run_st_a2_demo.py`; `grep -n "^logger\b" scripts/run_st_a2_demo.py` returns nothing.

### P0.2 — Correct `CLAUDE.md` §5
- Replace the stale `EURUSD=21001 / GBPUSD=21002` magic-number line with the actual deployed value: flat `magic_number: 21099` (per `config/demo.yaml:11`, `execution/trade_manager.py`'s `_MAGIC`).
- Clarify traded-pairs: `scripts/run_st_a2_demo.py`'s `PAIRS` (`EURUSD, GBPUSD, XAUUSD`) is what's actually live-traded; `config/demo.yaml`'s broader list (adds `USDJPY`) is a config ceiling, not all of which is traded — add a one-line note so future readers don't conflate the two.
- **Verify:** manual diff against `config/demo.yaml:11` and `run_st_a2_demo.py:91`.

### P0.3 — Record the governance gap (documentation only, per decision above)
- **`docs/VERDICT_LOG.md`:** append (never edit/delete existing rows — this file is append-only by convention) an entry stating `SMCOrderBlockFVGSession` runs live-demo (dry-run, `LIVE_TRADING=false`) via `smc-demo-runner.service` while its SVOS stage is `INTAKE` with all gates `pending`; explicitly note this is a tracked gap, not evidence of a passed gate.
- **`docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`:** add a short note that `svos/lifecycle/manager.py` is a pure topology validator with no evidence-gate enforcement against the file-based registry (`data/svos/registry/*/state.json`) — only `db/control_plane.py`'s Postgres path enforces evidence via `_validate_evidence()`. Cross-reference the VERDICT_LOG entry.
- No changes to `svos/lifecycle/manager.py`, registry JSON, or any schema — docs only.
- **Verify:** `git diff docs/VERDICT_LOG.md` shows only additions; `python scripts/lint_docs.py --root docs --index docs/index.md` still passes.

### P0.4 — Minimal doc-drift checker
- **New file:** `scripts/check_docs_drift.py` (kept separate from `scripts/lint_docs.py`, which is scoped to structural markdown checks only).
- Parses `config/demo.yaml`'s `magic_number` + pair list and `scripts/run_st_a2_demo.py`'s `PAIRS` list **via AST/regex, not `import`** (importing the runner module triggers side-effecting startup code). Compares both against `CLAUDE.md` §5. Warns/fails on mismatch. Scope stays to magic-number + symbol-list only — no general config/doc diff engine.
- **CI wiring:** add a step to the existing `docs-lint` job in `.github/workflows/quality.yml`, right after the `lint_docs.py` step.
- **Depends on P0.2** landing first (needs a correct baseline, otherwise the first run immediately flags the drift this plan just fixed).
- **New test:** `tests/scripts/test_check_docs_drift.py` (match existing `tests/` layout) — one passing case against real repo files, one synthetic-mismatch case using a `tmp_path` fixture.
- **Verify:** `python scripts/check_docs_drift.py` exits 0 post-P0.2; new pytest passes; `.github/workflows/quality.yml` still valid YAML.

**P0 checkpoint:** `python -m py_compile scripts/run_st_a2_demo.py scripts/check_docs_drift.py`; `pytest tests/scripts/test_check_docs_drift.py`; confirm no changes touched `svos/lifecycle/manager.py` or any registry file.

---

## Phase P1 — Safety features (kill switch, reconciliation, retry) + duplication cleanup

### P1.1 — Wire the kill switch into the live tick loop
- **Read side (`scripts/run_st_a2_demo.py`):** at the top of each tick (`_tick()` around line 153, or the `while True` loop in `run()` around line 553), call `dashboard/control_state.py`'s existing `load_control_state()` and check `state["emergency_stop"]["active"]`. If active:
  - Skip signal generation / new order placement for that tick.
  - Call the already-implemented, never-called `TradeManager.emergency_close_all()` (`execution/trade_manager.py:78-90`) — **once per activation only**, tracked via a flag in `risk_state` (e.g. `risk_state["_emergency_stop_handled_at"]`) compared against the control-state's `activated_at` timestamp, reset when `active` flips back to `False`.
  - Set `state["last_decision"] = "emergency_stop_active"`; alert via `TelegramAlerter` (reuse `send_circuit_breaker()` or add a small dedicated call — match the existing per-concern-method style in `monitoring/telegram.py`).
- **Write side (per decision above):** add a new route to the already-deployed `dashboard/status_server.py` (FastAPI, `app` at line 41) — e.g. `POST /api/emergency-stop` and `POST /api/emergency-stop/clear`, gated by an exact-match CONFIRM token (mirror `dashboard/app.py`'s existing token-check logic rather than reinventing it — reuse `dashboard/control_state.py`'s `activate_emergency_stop()`/`clear_emergency_stop()` functions directly so both dashboards share one control-state file and one source of truth). This is a genuine write endpoint per `CLAUDE.md §4` — the route itself must reject any request without the correct CONFIRM token; no self-execution.
- **New tests:** `tests/execution/test_emergency_stop_integration.py` — write a synthetic `reports/control_state.json` with `active=True`, run one mocked `_tick()`, assert `emergency_close_all()` is called exactly once and not again on a second tick with the same activation timestamp. Extend `tests/test_status_server.py` (create if absent) with a case hitting the new route without a token (expect 403) and with the correct token (expect success + control-state file updated).
- **Manual verify:** `python scripts/run_st_a2_demo.py --strategy SMCOrderBlockFVGSession --mode shadow --once` with a manually-set `active: true` in a local `reports/control_state.json` copy — confirm the log shows `emergency_stop_active` and no signal generation occurs. Confirm via `curl` against a locally-run `status_server.py` that the new route rejects bad tokens.

### P1.2 — Broker reconciliation job
- **New file:** `scripts/reconcile_positions.py`, run out-of-band (systemd timer, not embedded in the hot tick loop).
- Fetch broker truth via `execution/vantage_demo_executor.py`'s existing `get_positions()` / `get_account_info()`. Fetch internal truth via `core/trade_journal_db.py`'s `TradeJournalDB` — add a `get_open_trades()` method (mirrors the existing `get_trades_by_symbol()` pattern, `WHERE status='OPEN'`). Compare by symbol+magic; flag orphan broker positions, stale DB "OPEN" records with no matching broker position, on mismatch alert via a new `TelegramAlerter.send_reconciliation_mismatch()` (matching the existing ~15 dedicated `send_*` methods rather than overloading `send_error()`).
- Add `deploy/gcp-vm1/systemd/reconcile-positions.timer` + `.service`, following the existing timer/service pairing pattern already in `deploy/gcp-vm1/systemd/`.
- Add a `--dry-run` flag (logs only, no Telegram) for safe manual smoke-testing.
- **New test:** `tests/execution/test_reconcile_positions.py` — mock `get_positions()` and a temp-SQLite `TradeJournalDB`, cover: orphan broker position, stale DB record, exact match (no alert).
- **Verify:** unit tests pass; `python scripts/reconcile_positions.py --dry-run` run manually against real demo state reports "in sync" or a real, expected mismatch.

### P1.3 — Retry/backoff for order placement
- **File:** `execution/trade_manager.py` — wrap the `place_order()` call inside `open_position()` (lines 54-62) with a small async retry helper local to this file (exponential backoff, capped attempts), following `bot.py`'s existing `_connect_with_retry` style (same bare-`except Exception`, same Telegram-alert-on-exhaustion pattern via `send_error()`). No new shared "retry utils" module — keep it local to avoid scope creep.
- Constants (`max_attempts`, `base_delay_s`) as module-level constants matching the existing `_MAGIC = 21099` style, unless `config/demo.yaml` already has an obvious `execution:` section (check first) — default to hardcoded if not.
- Preserve `open_position()`'s existing return contract (check current callers in `run_st_a2_demo.py`'s `_tick()` before deciding whether exhaustion raises or returns an error dict — match what callers already expect).
- **Extend test:** `tests/execution/test_trade_manager.py` — case for "fails N-1 times then succeeds" and "fails all attempts → alert fires once, contract preserved."
- **Verify:** new/extended tests pass.

### P1.4 — Duplication cleanup (docs-only per decisions above)
- **`execution/risk_manager.py`:** add a module docstring noting it's used by the legacy `bot.py` path (via `execution/order_manager.py`), not by the live `run_st_a2_demo.py` path (which uses `execution/demo_risk_manager.py`'s functional API). No deletion.
- **`monitoring/metrics.py`'s `TradeJournal`:** confirmed dead outside its own test (`tests/test_metrics.py`, mirrored in `archive/`). Leave as-is for this pass — flagged as a minor future cleanup, not blocking (avoid deleting tests without a dedicated follow-up ask).
- **`execution/trade_journal.py` vs `core/trade_journal_db.py`:** not duplicates — add a one-line docstring to each clarifying roles: `trade_journal.py`/`DemoTradeJournal` is the JSONL log feeding Telegram daily summaries; `trade_journal_db.py`/`TradeJournalDB` is the fuller SQLite audit trail and **is the source of truth P1.2's reconciliation job should read from** (already reflected in P1.2's design).
- **`dashboard/app.py` vs `dashboard/status_server.py`:** add a comment block at the top of `app.py` clarifying it's a control-plane dashboard whose deployment status is unconfirmed, and that the emergency-stop capability now lives in `status_server.py` per P1.1 — avoid confusion about which dashboard owns which capability going forward.
- **Verify:** docstring/comment additions only; no functional test needed beyond confirming `python -m py_compile` on touched files.

**P1 checkpoint:** `pytest tests/execution/ tests/test_status_server.py -v`; manual `--mode shadow --once` run confirming kill-switch and retry logic don't break the normal tick path.

---

## Phase P2 — Observability

### P2.1 — `/metrics` endpoint
- **File:** `dashboard/status_server.py` — new `GET /metrics` route on the existing `app`, reusing `_load_state()`/`_load_trades()` (and the existing `/api/status` route's data assembly, to avoid re-deriving logic). Hand-rolled Prometheus text-exposition format (no new dependency, matching the file's existing "raw Python string interpolation, no extra libs" style).
- Minimal metric set: connection status (0/1), open position count, last-tick age, win rate/profit factor (from P2.4's extended `summary()`), emergency-stop active (0/1, from P1.1's control-state).
- **Sequence after P2.4** for the fuller field set (or ship a smaller version first and extend — non-blocking).
- **New test:** `tests/test_status_server.py` — `TestClient` hit on `/metrics`, assert 200 + correct content-type/structure.
- **Verify:** `curl http://localhost:8090/metrics` after a local run.

### P2.2 — Latency time-series + dashboard panel
- **File:** `execution/mt5_connector.py` — in `heartbeat()` (line ~148), append `{timestamp, latency_ms, connected}` to `logs/latency_timeseries.jsonl`.
- **File:** `dashboard/status_server.py` — small sparkline panel following the existing hand-rolled SVG pattern (`_render_chart_svg()`, lines ~296-441) as style reference — much simpler geometry than the candle chart.
- **Retention:** coordinate with P3.3 — this file will grow unbounded like `logs/adaptive_shadow.log` did; either trim on write (keep last N entries) or rely on the same logrotate config from P3.3. Do not repeat the unbounded-growth mistake being cleaned up in P3.3.
- **New test:** extend/create `tests/execution/test_mt5_connector.py` asserting the JSONL write on a mocked heartbeat.
- **Verify:** manual `--mode shadow --once` run shows a new line in `logs/latency_timeseries.jsonl`; dashboard renders the new panel without breaking layout.

### P2.3 — Persisted reconnect-attempt counter
- **File:** `execution/mt5_connector.py` — add a `self._reconnect_count` instance attribute, incremented inside `reconnect()` (lines 102-114), exposed as a public attribute/getter (matches the existing `_reconnecting` guard's pattern of being co-located on the connector).
- **File:** `scripts/run_st_a2_demo.py` — surface it in the state dict already written every tick via `_write_state()` (line 114): `state["reconnect_attempts_total"]`, `state["last_reconnect_at"]`. Simpler than reusing `risk_manager.py`'s state-file pattern (which would pull dead-in-live-path code back into the live path) — a lifetime counter, no auto-reset.
- **New test:** mock a failed connection, call `reconnect()` twice, assert the counter increments correctly.
- **Verify:** `cat logs/strategy_demo_state.json | python -m json.tool | grep reconnect` after a manual run.

### P2.4 — Extend `TradeJournalDB.summary()` with Sharpe/drawdown/expectancy
- **File:** `core/trade_journal_db.py` — `summary()` (lines 220-263) currently returns win_rate/avg_r/profit_factor/total_pnl. Add:
  - **Expectancy:** `(win_rate * avg_win_r) - (loss_rate * avg_loss_r)`, splitting the existing combined average query into win-side/loss-side.
  - **Max drawdown:** new query for ordered `(timestamp, r_multiple)` rows, Python-side running-peak/trough calculation (not a single SQL aggregate) — new private helper `_max_drawdown()` matching the existing `_sum_r()` pattern.
  - **Sharpe:** stdlib `statistics.mean`/`statistics.pstdev` over the same ordered returns (check `requirements.txt` before considering numpy — prefer stdlib if numpy isn't already a dependency).
- Backward-compatible: extends the returned dict, doesn't change existing keys.
- **New test (required, not optional):** `tests/database/test_trade_journal_db.py` (confirm exact path) — fixture trades with hand-calculated expected Sharpe/drawdown/expectancy values. Financial calculations need a verified-correct test before shipping, not just "it runs."
- Dashboard surfacing (a new summary section in `status_server.py`, reusing existing HTML patterns) takes priority over the optional `scripts/generate_live_metrics_report.py` standalone script — build the dashboard section first; treat the script as deferred/optional to keep scope tight.
- **Verify:** new test passes with hand-verified expected values.

**P2 checkpoint:** `pytest tests/database/ tests/execution/ -v`; manual dashboard check at `/dashboard/` and `/metrics`; confirm `logs/strategy_demo_state.json` and `logs/latency_timeseries.jsonl` show the new fields after a `--once` run.

---

## Phase P3 — Infra hygiene

### P3.1 — systemd resource limits
- **File:** `deploy/gcp-vm1/systemd/smc-demo-runner.service` — add under `[Service]`: `MemoryMax=768M`, `CPUQuota=75%`, `StandardOutput=journal`, `StandardError=journal` (conservative-but-roomy defaults for a ~160MB/~1%CPU process with headroom for this plan's new features; adjust if the owner wants tighter/looser limits).
- **Important:** editing this repo-tracked template does not affect the running VM. Rolling it out requires `systemctl daemon-reload` + `systemctl restart smc-demo-runner.service` on the actual VM — a live-service restart, done manually by the owner (or in an explicit follow-up session with VM access), not auto-applied by this plan.
- **Verify:** `systemd-analyze verify deploy/gcp-vm1/systemd/smc-demo-runner.service` (syntax only, from the repo). Post-rollout (manual, on VM): `systemctl show smc-demo-runner.service -p MemoryMax -p CPUQuota`.

### P3.2 — Archive Dockerfile + docker-compose.yml
- `git mv` both files into `archive/` (matching the repo's existing archive convention), with a short note (new or existing archive README) explaining they're vestigial: CMD targets `bot.py` (not the real entrypoint), not referenced in CI, not in README, already flagged in `docs/svos/PROJECT_STATUS_REPORT_2026-06-29.md`.
- **Verify:** `grep -rn "Dockerfile\|docker-compose" --include=*.yml --include=*.md . | grep -v archive/` shows no unexpected remaining references; `git status` shows a clean rename (history preserved via `git mv`).

### P3.3 — Stale log cleanup + retention
- **Recurring prevention (do first, safe):** add a `logrotate` config (e.g. `deploy/gcp-vm1/logrotate/smc-demo-runner`, check first whether `deploy/gcp-vm1/` already has any logrotate pattern to match) sized to prevent the next `adaptive_shadow.log`-style unbounded file. Use `copytruncate` or proper signal-based rotation — do not `rm` a file the running service has an open handle to (e.g. `logs/strategy_demo.log` is actively written via `logging.FileHandler`).
- **One-time cleanup (needs a lightweight go-ahead, not silent):** before deleting anything, regenerate the exact file list via `du -sh logs/* | sort -rh` at execution time (numbers will have shifted since the audit) and present it for a quick yes/no before running any `rm`. Candidates identified in the audit: `logs/adaptive_shadow.log` (5.8M, stale since Jun 24), old `bot.log.*.gz` rotations, old summary JSONs (~13.6MB total, subject to re-check).
- **Verify:** `du -sh logs/` before/after; confirm `smc-demo-runner.service` and `live-dashboard.service` remain healthy throughout (`systemctl status`).

**P3 checkpoint:** `systemd-analyze verify` on the edited unit file; `git log --follow` confirms archive move preserved history; `du -sh logs/` shows expected reduction only after explicit go-ahead.

---

## Sequencing / Dependency Notes

- P0 has no external dependencies — do all four items first, in order (P0.1 → P0.2 → P0.3 → P0.4, since P0.4 needs P0.2's corrected baseline).
- P1.1 (kill switch) is the highest-value fix in P1 — do it first within the phase. P1.2/P1.3/P1.4 are mutually independent and can proceed in any order once P1.1 lands (P1.4's journal-docstring item should land before or alongside P1.2, since it documents which journal P1.2 trusts).
- P2.4 (summary() extension) should land before or alongside P2.1 (metrics endpoint) so the endpoint can expose the fuller field set; P2.2 and P2.3 are independent of both.
- P3 items are all independent of P0-P2 and of each other; P3.1's actual VM rollout and P3.3's one-time deletion are the only two steps in this entire plan that touch a live, running system and need an explicit human go-ahead at execution time (beyond the CONFIRM token already required for P1.1's write route).

## Critical Files (touched by the most items)

- `scripts/run_st_a2_demo.py` — logger fix (P0.1), kill-switch consumption (P1.1), reconnect counter surfacing (P2.3).
- `execution/trade_manager.py` — retry/backoff (P1.3); already has the `emergency_close_all()` that P1.1 wires in.
- `dashboard/status_server.py` — new emergency-stop route (P1.1), `/metrics` endpoint (P2.1), latency panel (P2.2), live-metrics section (P2.4).
- `dashboard/control_state.py` — existing `load_control_state()`/`activate_emergency_stop()`/`clear_emergency_stop()`, reused as-is by P1.1's new route and the tick-loop's read side.
- `core/trade_journal_db.py` — `get_open_trades()` addition (P1.2), `summary()` extension (P2.4).
- `execution/mt5_connector.py` — reconnect counter (P2.3), latency logging (P2.2).
- `CLAUDE.md` — §5 doc-drift fix (P0.2), the baseline P0.4's checker validates against.
- `docs/VERDICT_LOG.md` — governance-gap entry (P0.3).

## End-to-End Verification

Run after each phase, cumulatively:
1. `python -m py_compile` on every touched `.py` file.
2. `pytest tests/ -x` (full suite) after P1 and after P2 — new tests listed per-item above must exist and pass, not just "no regressions."
3. Manual: `python scripts/run_st_a2_demo.py --strategy SMCOrderBlockFVGSession --mode shadow --once` after P1 and P2 changes, confirming no new exceptions in `logs/strategy_demo.log` and expected new fields in `logs/strategy_demo_state.json`.
4. Manual dashboard check: load `/dashboard/`, `/api/status`, and (after P2.1) `/metrics` in a browser/curl, confirm rendering and no errors.
5. Do not restart the live `smc-demo-runner.service` or `live-dashboard.service` on the VM as part of routine verification — that's an explicit, separate rollout step (P3.1) requiring owner action.
