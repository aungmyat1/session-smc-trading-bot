# ST-A2 Demo Go-Live Validation Report
# Generated: 2026-06-24 19:19 UTC
# Phase: Demo Validation (Phase 1)

---

## Validation Summary

| Gate | Result | Notes |
|------|--------|-------|
| Automated test suite | PASS — 964/964 tests | All suites green |
| Risk controls | PASS | All guards confirmed via test + runtime |
| Portfolio control layer | PASS | SignalRouter + CircuitBreaker + PortfolioManager wired |
| Execution mode switch | PASS | shadow/demo/live modes enforced |
| LIVE_TRADING guard | PASS | Hard-blocked in runner + .env |
| Broker connection | UNVERIFIED — needs live test | Last connection: 2026-06-24 18:47 UTC |
| Data feed (EURUSD) | VERIFIED — 2026-06-24 session | 200-bar M15 confirmed |
| Data feed (XAUUSD) | UNVERIFIED — not yet tested | Pip table configured; needs live test |
| Order placement | UNVERIFIED — awaiting first demo trade | Code ready, DEMO_ONLY guard tested |
| Trade journal DB | PASS | SQLite created, read/write confirmed |

---

## Test Suite Results

```
Date:     2026-06-24 19:18 UTC
Command:  python3 -m pytest tests/ -q
Result:   964 passed in 2.42s
```

### Coverage by module

| Module | Tests | Status |
|--------|-------|--------|
| tests/adaptive_engine/ | ~218 | PASS |
| tests/execution/ | 34 | PASS |
| tests/core/ (signal, registry, adapters) | 36 | PASS |
| tests/portfolio/ (router, breaker, limits, correlation, shadow) | 81 | PASS |
| tests/test_session.py + test_sweep.py etc | ~595 | PASS |

---

## Risk Controls Verification

### Demo Risk Manager (execution/demo_risk_manager.py)
- `calculate_lots()` — PASS: sizing formula verified for EURUSD, GBPUSD, XAUUSD
- `check_limits()` — PASS: max_trades, max_positions, daily_loss, consec_loss all enforced
- `reset_daily()` — PASS: resets at UTC day boundary

### Portfolio Manager (core/portfolio_manager.py)
- Daily loss limit 2.0% — PASS (1.5% in config/demo.yaml is more conservative)
- Weekly loss limit 5.0% — PASS
- Monthly loss limit 8.0% — PASS
- Max trades per day cap — PASS
- Correlation filter — PASS: same-group same-direction blocked
- Risk tiers: ST-A2=tier1(0.30%) — PASS

### CircuitBreaker (core/circuit_breaker.py)
- Signal rate limit (max 4/hr per config) — PASS
- Daily trade cap — PASS
- Consecutive loss cooldown — PASS

### SignalRouter (core/signal_router.py)
- TTL expiry (300s default) — PASS
- Geometry validation (BUY: sl<entry<tp) — PASS
- Conflict resolution (BUY+SELL same symbol → reject both) — PASS
- Dedup same direction — PASS (keeps highest confidence)

---

## Broker Connection Status

Last confirmed connection: 2026-06-24 18:47 UTC
Last failure: 2026-06-24 18:48 UTC (MetaAPI WebSocket timeout)
Auto-reconnect: coded (commit c0706d4); not yet confirmed to recover from live timeout
Account: d6f6eec3-96d5-4001-a802-62b3f4b49817 (VantageMarkets-Demo, cloud-g2, full redundancy)

Connection checklist: see docs/VANTAGE_DEMO_CONNECTION_CHECKLIST.md
Items PASS(live): 11 | Items PASS(code): 23 | Items UNVERIFIED: 9 | FAIL: 0

---

## Execution Readiness

| Env var | Current value | Required for demo |
|---------|--------------|------------------|
| TRADING_MODE | shadow (default) | Set to `demo` |
| DEMO_ONLY | false | Must remain `false` |
| LIVE_TRADING | false | MUST remain `false` |
| METAAPI_TOKEN | set | Confirmed |
| VANTAGE_DEMO_METAAPI_ID | set | d6f6eec3-… confirmed |

To enable demo orders: `TRADING_MODE=demo` in `.env` (runner restart required).

---

## Known Limitations

| # | Limitation | Severity | Mitigation |
|---|-----------|----------|-----------|
| 1 | XAUUSD data feed not live-tested | LOW | Confirm with health_check.py before first XAUUSD trade |
| 2 | Live order placement not yet confirmed | MEDIUM | First demo order clears this; use shadow mode first |
| 3 | WebSocket reconnect not battle-tested | MEDIUM | Monitor runner log for timeout messages; restart if needed |
| 4 | Session close not auto-implemented | LOW | Manual review at 10:00 UTC and 16:00 UTC |
| 5 | TP1 partial close not automated | LOW | Phase 1: full-position exit only, TP1/TP2 treated as single TP |
| 6 | Phase-0 formally UNVALIDATED | HIGH (formal) | ST-A2 passed internal backtest; 2× spread re-run needed on new spec |

**No BLOCKER items.** Demo trading is safe to begin with TRADING_MODE=shadow → confirm signals → switch to TRADING_MODE=demo.

---

## Execution Verdict

```
SYSTEM STATUS   2026-06-24 19:19 UTC
Runner          ~ WARN      (not running — restart required)
Risk Engine     ✓ PASS      trades=0/4  consec_L=0  daily_loss=0.00%
Portfolio       ✓ PASS      daily=+0.000%  weekly=+0.000%
Execution       ~ SHADOW    mode=shadow  (no live orders)
Journal         ✓ PASS      total=0 trades

Overall:  ✓ READY (shadow mode)
```

---

## Pre-Demo Steps

1. `[ ]` Start runner in shadow mode for one full London session
2. `[ ]` Confirm at least 1 signal fires (check logs/shadow_trades.jsonl)
3. `[ ]` Run health_check.py — all PASS or SHADOW
4. `[ ]` Set TRADING_MODE=demo in .env
5. `[ ]` Restart runner
6. `[ ]` Monitor first demo order placement closely
7. `[ ]` Confirm broker_order_id appears in data/trade_journal.db
8. `[ ]` After first trade closes — verify close recorded in DB

---

## Approvals Required

| Gate | Approver | Status |
|------|----------|--------|
| Enable demo orders | Owner (manual: TRADING_MODE=demo in .env) | PENDING |
| Phase 2 (live) | Owner only after 30-trade demo + Phase-0 re-run | BLOCKED |

No agent may enable LIVE_TRADING=true. See CLAUDE.md §0 rule 1.
