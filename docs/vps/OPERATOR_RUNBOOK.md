# System 2 Operator Runbook

Date started: 2026-07-04 (owner feedback: begin alongside implementation, update every sprint —
do not treat this as a one-time, end-of-project document)
Scope: `auto-trade-vps` (GCP `asia-southeast1-b`) — the demo-only System 2 execution host.
Status: Living document. Update after every sprint that changes deployment, recovery, or risk
behavior. Complements `SYSTEM2_MASTER_PLAN.md`'s Definition of Done, not a duplicate of it.

**Safety reminder before any action below**: `LIVE_TRADING=false`/`DEMO_ONLY=true` must never be
changed by any procedure in this runbook. If a step seems to require it, stop and escalate instead.

---

## 1. Daily startup checks

Run these first, in order, at the start of every operating day:

```bash
# 1. Both production services active, zero restarts overnight
systemctl show smc-demo-runner.service live-dashboard.service -p NRestarts,ActiveState,SubState

# 2. Zero failed units platform-wide
systemctl --failed --no-pager

# 3. PostgreSQL healthy
systemctl is-active postgresql@16-main.service
sudo -u postgres psql -c "SELECT 1"

# 4. Dashboard responds
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8090/
curl -s http://127.0.0.1:8090/api/operations/health | python3 -m json.tool

# 5. Runner is actually ticking (not stale)
cat logs/strategy_demo_state.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('last_tick_at:', d.get('last_tick_at')); print('broker_status:', d.get('broker_status')); print('strategy:', d.get('strategy'))"

# 6. Disk headroom (alert threshold: 85%, per docs/vps/LOG_RETENTION_POLICY.md)
df -h /
```

**Expected good state**: `NRestarts=0` on both services (a nonzero, *stable* count from a known
prior incident is acceptable — climbing is not), `ActiveState=active`, 0 failed units, `SELECT 1`
returns a row, dashboard HTTP 200/307, `last_tick_at` within the last ~2 minutes, `broker_status`
`connected`, disk under 85%.

**If anything above is wrong**, jump to the matching section below before doing anything else.

## 2. Monitoring routines (ongoing, not just at startup)

- Watch `/api/operations/health`'s `health_score` — below 85 warrants investigation (see
  `dashboard/status_server.py::_health_summary()` for the exact scoring: broker disconnect −30,
  stale tick −20, emergency stop active −15, governance/permission denied −20/−15).
- Watch `/api/operations/risk`'s `halted`/`consecutive_losses` — if `halted: true`, a real loss
  limit fired; do not manually reset it without understanding why first (§5).
- Watch `smc-demo-runner.service`'s restart count (`systemctl show ... -p NRestarts`) — any increase
  since the last check is a crash, investigate via `journalctl -u smc-demo-runner.service -n 60`.
- Watch `/api/operations/events` for `recovery_checkpoint` entries with `resolved != []` or
  `orphaned_positions != []` — the former means a crash was auto-recovered (informational unless
  frequent), the latter means a broker position exists with no local record and needs manual review.
- Watch disk (`df -h /`) — no automated retention policy is applied yet
  (`docs/vps/LOG_RETENTION_POLICY.md` is a proposal, not yet applied); manual attention required
  until that lands.

## 3. Responding to broker disconnects

Symptom: `broker_status` in `logs/strategy_demo_state.json` (or `/api/operations/health`'s
`execution_runner`) shows anything other than `connected`; `reconnect_attempts_total` climbing.

1. Confirm it's real, not a stale read: `curl http://127.0.0.1:8090/api/operations/health`.
2. Check `journalctl -u smc-demo-runner.service -n 100 | grep -i "connect\|metaapi\|websocket"` for
   the actual MetaAPI error.
3. `MT5Connector.ensure_connected()` already retries proactively every tick — a transient drop
   usually self-heals within 1-2 ticks (60-120s). Do not restart the service for a single missed
   tick.
4. If disconnected for more than ~5 minutes: check MetaAPI/Vantage account status externally
   (dashboard credentials in `.env`, not reproduced here) before assuming it's this host's fault.
5. If confirmed host-side and self-healing has stopped: `sudo systemctl restart
   smc-demo-runner.service`, then re-run the daily startup checks (§1) to confirm recovery, and
   check `/api/operations/events` for the `recovery_checkpoint` this restart produces — it must show
   `lost_count: 0` or every lost item accounted for, never silently ignored.

## 4. Recovering after VPS reboots

Both `smc-demo-runner.service` and `live-dashboard.service` are `enabled` (systemd `WantedBy=
multi-user.target`), so they start automatically on boot — no manual action needed for that part.
After any reboot (planned or not):

1. Run the full daily startup checks (§1).
2. **Specifically verify recovery ran**: `journalctl -u smc-demo-runner.service -b | grep -i
   "startup recovery"` — must show a "Startup recovery resolved N incomplete execution(s)" line (or
   confirm there were zero incomplete executions to resolve) before the first tick. This is
   `execution/startup_recovery.py`'s job — it never resubmits an order, only reconciles against
   broker truth (`docs/systems/system2/CANONICAL_EXECUTION_PIPELINE.md` stage 14).
3. Confirm `logs/risk_state.json`/`logs/portfolio_state.json` were reloaded, not reset to zero:
   check `trades_today`/`consecutive_losses`/`open_symbols` in `/api/operations/risk` match
   pre-reboot expectations (they should NOT show `0`/empty if trading happened earlier that day).
4. PostgreSQL: `systemctl is-active postgresql@16-main.service` — this is a separate service,
   confirm it's up before trusting `/api/operations/events`.

## 5. Handling risk limit triggers

Symptom: `/api/operations/risk`'s `halted: true`, or a `CircuitBreaker`/`demo_risk_manager` halt
reason in the logs (`halt_reason` field — e.g. `CONSECUTIVE_LOSS_LIMIT`, daily/weekly/monthly loss).

1. **Do not clear or bypass a halt to "let it keep trading."** The halt is the risk engine doing its
   job (Phase 1 work this session specifically closed the gap where this used to be dead code).
2. Confirm the halt is real, not stale: cross-check `logs/risk_state.json`'s `halted`/`halt_reason`
   against `TradeJournalDB`'s recent closed trades (`/api/operations/trades`) — the halt reason
   should be explainable by an actual sequence of real closes.
3. Escalate to the owner for a decision on whether/when to resume trading for the affected
   day/week/month window — this is a risk-policy decision, not an operational one.
4. Resuming (owner-approved only): the halt clears automatically at the next daily/weekly/monthly
   reset (`reset_daily()` in `execution/demo_risk_manager.py`, keyed off UTC date) — there is
   deliberately no "clear halt now" operator action, consistent with "no silent bypass" governance.

## 6. Performing emergency stops

Use the dashboard's emergency-stop endpoint — never edit `reports/control_state.json` by hand.

**Changed 2026-07-04**: these endpoints now require an authenticated operator identity
(`dashboard/rbac.py`), not just the CONFIRM token — a request without a valid `Authorization`
header now returns `401`/`503` before the token is even checked. Set `SVOS_OPERATOR_TOKEN` in the
dashboard host's environment and pass it as a bearer token, along with your actor name and a role
of `risk_operator` or `admin`:

```bash
AUTH_HEADERS=(-H "Authorization: Bearer $SVOS_OPERATOR_TOKEN" -H "X-SVOS-Actor: <your name>" -H "X-SVOS-Role: risk_operator")

# Activate (requires the exact confirm token)
curl -X POST http://127.0.0.1:8090/api/emergency-stop \
  -H "Content-Type: application/json" "${AUTH_HEADERS[@]}" \
  -d '{"reason": "<real reason>", "confirm_token": "CONFIRM-EMERGENCY-STOP", "scope": "block_only"}'
# scope: "block_only" (no new orders, existing positions untouched) or
#        "close_positions" (also closes managed positions — confirm this is intended)

# Verify it took effect
curl http://127.0.0.1:8090/api/control/state

# Clear (requires its own exact token, after the underlying issue is resolved)
curl -X POST http://127.0.0.1:8090/api/emergency-stop/clear \
  -H "Content-Type: application/json" "${AUTH_HEADERS[@]}" \
  -d '{"reason": "<real reason>", "confirm_token": "CONFIRM-CLEAR-EMERGENCY-STOP"}'
```

The runner checks this state every tick (`_tick()`'s emergency-stop branch) — expect it to take
effect within one tick interval (≤60s), not instantly.

**Also new 2026-07-04** — named, RBAC + CONFIRM-token-gated aliases onto the same state machine
(`/api/control/*`), for when the intent is narrower than a full emergency stop:

```bash
# Pause new order entry only (same effect as scope=block_only above)
curl -X POST http://127.0.0.1:8090/api/control/pause \
  -H "Content-Type: application/json" "${AUTH_HEADERS[@]}" \
  -d '{"reason": "<real reason>", "confirm_token": "CONFIRM-PAUSE-TRADING"}'

# Resume
curl -X POST http://127.0.0.1:8090/api/control/resume \
  -H "Content-Type: application/json" "${AUTH_HEADERS[@]}" \
  -d '{"reason": "<real reason>", "confirm_token": "CONFIRM-RESUME-TRADING"}'

# Emergency close all managed positions (same effect as scope=close_positions above)
curl -X POST http://127.0.0.1:8090/api/control/close-all \
  -H "Content-Type: application/json" "${AUTH_HEADERS[@]}" \
  -d '{"reason": "<real reason>", "confirm_token": "CONFIRM-CLOSE-ALL-POSITIONS"}'

# Toggle the one currently-running strategy specifically (409 if <strategy_id> isn't the one
# actually running — check GET /overview's execution.strategy first)
curl -X POST http://127.0.0.1:8090/api/control/toggle-strategy \
  -H "Content-Type: application/json" "${AUTH_HEADERS[@]}" \
  -d '{"strategy_id": "ST-A2", "action": "pause", "confirm_token": "CONFIRM-TOGGLE-STRATEGY-ST-A2"}'
```

**Note**: as of this runbook's writing, no frontend button on the Gai dashboard actually calls any
of these endpoints yet (Operator Controls frontend integration is not yet built — see
`docs/systems/system2/ROADMAP.md`); use `curl` directly until it is. A live event feed of every
control action (and much more) is now available by subscribing to `ws://127.0.0.1:8090/ws`.

## 7. Rolling back deployments

Every change this session was designed to have a one-line rollback. General pattern:

```bash
# Any application code change (runner, dashboard, execution/*, etc.)
git status                          # confirm what's actually changed before reverting
git diff -- <path>                  # review the exact diff first
git checkout -- <path>              # revert a specific file
sudo systemctl restart <affected-service>   # smc-demo-runner.service and/or live-dashboard.service

# Specific known rollback: the ST-A2 strategy fix
git checkout -- deploy/gcp-vm1/run_smc_demo.sh
sudo systemctl restart smc-demo-runner.service

# Database migrations (only if a future migration needs reverting — none needed for migration 004)
alembic downgrade -1
```

After any rollback: re-run the daily startup checks (§1) and confirm the restart count doesn't
start climbing (a rollback that "fixes" a symptom by reintroducing a crash loop is not a fix).

## 8. Restoring from backups

Archives created during VPS stabilization live in `/home/aungp/archives/` (`chmod 600`, owner-only —
several contain secrets). Each has a `.sha256` sidecar — **always verify before restoring**:

```bash
ls -la /home/aungp/archives/
sha256sum -c /home/aungp/archives/<name>.tar.gz.sha256   # must print OK before proceeding

# Restore example (extracts alongside, does not overwrite in place — move into position manually
# after confirming contents, especially for anything under /opt which may need sudo)
mkdir -p /tmp/restore-check && tar -tzf /home/aungp/archives/<name>.tar.gz | head -20   # preview first
tar -xzf /home/aungp/archives/<name>.tar.gz -C /tmp/restore-check
```

Database: no automated backup job exists yet (`docs/database_authority_stabilization.md` §9.3,
still an open gap — manual-only). Manual Postgres backup/restore:

```bash
# Backup
sudo -u postgres pg_dump vmassit | gzip > /home/aungp/archives/vmassit_$(date -u +%Y%m%dT%H%M%SZ).sql.gz

# Restore (destructive — confirm target DB before running)
gunzip -c /home/aungp/archives/vmassit_<timestamp>.sql.gz | sudo -u postgres psql vmassit
```

**Never restore over a running production database without a fresh pre-restore backup first**, and
never run a restore without the owner's explicit go-ahead — this is exactly the class of
hard-to-reverse action that requires confirmation per this project's own operating principles.

---

## Open items (update this runbook as these land)

- No automated Postgres backup job exists — manual only (§8).
- No automated log retention is applied yet (`docs/vps/LOG_RETENTION_POLICY.md` is a proposal).
- No DR rehearsal has been performed — the restore steps above are documented but not yet tested
  end-to-end against this specific host.
- Once Authentication & RBAC and Operator Controls land, this runbook's §6 curl commands should be
  replaced with the equivalent authenticated dashboard UI actions, and this section updated.
- Once the Real-Time Operations Layer lands, §2's polling-based monitoring routine should be
  updated to reference the event subscription instead.
