# DEP_02_CONNECTION_REPORT.md
# DEP-02 — MetaAPI Demo Connection Validation
# Run: 2026-06-21T17:46:43 UTC

---

## Verdict

### ✅ PASS — all connection checks passed

---

## Connection Status

| Check | Status | Value |
|---|---|---|
| LIVE_TRADING forced false | ✅ | False |
| .env LIVE_TRADING safe | ✅ | was 'not set in env' |
| METAAPI_TOKEN | ✅ | eyJhbG…MaUo |
| METAAPI_ACCOUNT_ID | ✅ | 026ea073…43af |
| TELEGRAM_BOT_TOKEN | ✅ | SET |
| TELEGRAM_CHAT_ID | ✅ | SET |

---

## Broker / Account Details

| Field | Value |
|---|---|
| Broker | Vantage (VT Markets) via MetaAPI |
| Account ID | `026ea073…` |
| Balance | 100000.00 USD |
| Equity | 100000.00 USD |
| Leverage | 1:500 |
| Open positions | 0 |

---

## Synchronization Status

| Check | Status | Value |
|---|---|---|
| connect() | ✅ | OK |
| is_connected | ✅ | True |
| connection_status() connected | ✅ | True |
| connection_status() live_trading | ✅ | False |
| Heartbeat connected=True | ✅ | True |
| disconnect() | ✅ | is_connected=False |
| reconnect() | ✅ | is_connected=True |
| Post-reconnect account_info | ✅ | balance=100000.00 USD |

---

## Symbol Prices

| Symbol | Bid | Ask | Spread | Spread OK |
|---|---|---|---|---|
| EURUSD | `1.14708` | `1.14780` | `7.2` pip | ⚠️ wide |
| GBPUSD | `1.32194` | `1.32386` | `19.2` pip | ⚠️ wide |

---

## Heartbeat Status

| Field | Value |
|---|---|
| ts | `2026-06-21T17:46:53.209368+00:00` |
| connected | `True` |
| live_trading | `False` |
| balance | `100000` |
| open_positions | `0` |

---

## DRY_RUN Order Status

| Check | Status | Value |
|---|---|---|
| place_order() returns DRY_RUN | ✅ | order_id=DRY_RUN  dry_run=True |
| No real order sent to broker | ✅ | confirmed |

> All orders return `order_id=DRY_RUN` and `dry_run=True`.
> No real orders were sent to the broker.

---

## Full Check Log

| # | Check | Status | Value | Detail |
|---|---|---|---|---|
| 1 | LIVE_TRADING forced false | ✅ | False | .env said 'not set in env' — overridden to false |
| 2 | .env LIVE_TRADING safe | ✅ | was 'not set in env' | OK — not set to true in env |
| 3 | METAAPI_TOKEN | ✅ | eyJhbG…MaUo |  |
| 4 | METAAPI_ACCOUNT_ID | ✅ | 026ea073…43af |  |
| 5 | TELEGRAM_BOT_TOKEN | ✅ | SET |  |
| 6 | TELEGRAM_CHAT_ID | ✅ | SET |  |
| 7 | connect() | ✅ | OK |  |
| 8 | is_connected | ✅ | True |  |
| 9 | connection_status() connected | ✅ | True |  |
| 10 | connection_status() live_trading | ✅ | False | must be False |
| 11 | get_account_info() | ✅ | OK |  |
| 12 | balance > 0 | ✅ | 100000.00 USD |  |
| 13 | equity > 0 | ✅ | 100000.00 USD |  |
| 14 | leverage | ✅ | 1:500 |  |
| 15 | currency | ✅ | USD |  |
| 16 | get_open_positions() | ✅ | 0 position(s) |  |
| 17 | EURUSD price | ✅ | bid=1.14708  ask=1.14780  spread=7.2pip | spread wide (off-hours?) |
| 18 | GBPUSD price | ✅ | bid=1.32194  ask=1.32386  spread=19.2pip | spread wide (off-hours?) |
| 19 | place_order() returns DRY_RUN | ✅ | order_id=DRY_RUN  dry_run=True |  |
| 20 | No real order sent to broker | ✅ | confirmed |  |
| 21 | TradeLogger writes JSONL | ✅ | 12 events |  |
| 22 | All records have ts + event | ✅ | valid |  |
| 23 | Log file | ✅ | logs/dep02_validation.jsonl |  |
| 24 | All 6 event types | ✅ | ERROR, ORDER_FILLED, ORDER_REJECTED, ORDER_SUBMITTED, POSITION_CLOSED, SIGNAL_CREATED |  |
| 25 | Heartbeat has all 5 fields | ✅ | ['balance', 'connected', 'live_trading', 'open_positions', 'ts'] |  |
| 26 | Heartbeat connected=True | ✅ | True |  |
| 27 | Heartbeat live_trading=False | ✅ | False |  |
| 28 | disconnect() | ✅ | is_connected=False |  |
| 29 | reconnect() | ✅ | is_connected=True |  |
| 30 | Post-reconnect account_info | ✅ | balance=100000.00 USD |  |

---

## Blockers

None — all checks passed.

---

## Next Steps

1. Start paper trade: `python3 bot.py`
2. Monitor `logs/trades.jsonl` + Telegram for 30 days / ≥50 trades
3. After 50+ trades with no execution errors → DEP-02 complete

*DEP-02 | Run: 2026-06-21T17:46:43 UTC | SDK: metaapi-cloud-sdk 29.1.1*