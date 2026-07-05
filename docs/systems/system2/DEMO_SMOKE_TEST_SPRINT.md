# Demo Smoke Test Sprint

- Date: 2026-07-02
- Status: OFFLINE PREFLIGHT PASS — BROKER PHASE NOT STARTED
- Owner: Engineering / Operations
- Live trading: DISABLED

## Entry conditions

- PR #19 merged: **PASS** (`284dcab` on `main`)
- Demo runtime integration report preserved: **PASS**
- Package and identity CLI self-tests: **PASS**
- Deterministic demo-only package fixture: **PASS** (`tests/fixtures/demo_approved_package`)
- Test/demo SVOS registration: **PASS** (`tests/fixtures/svos_demo_registry/ST-A2`)
- Broker connection attempt: **NOT STARTED**
- Order submission: **NOT STARTED**

The fixture is explicitly `DEMO_ONLY`, dry-run only, not live eligible, deterministic, test-signed, and tied to `ST-A2`. It is test evidence only and cannot authorize a broker or live runtime.

## Offline smoke result

The package, identity chain, canonical runner preflight, SVOS registration, dashboard stage mapping, and JSON/Markdown report generation pass. The smoke command contains no broker construction or order submission path. Live mode raises before validation or report generation.

## Smoke sequence

1. Validate package signature, approval, expiry, validation, and risk status.
2. Validate the five-source strategy identity chain.
3. Assert `LIVE_TRADING=false`, reject `--mode live`, and use demo/dry-run only.
4. Check demo broker connectivity and market-data freshness without placing an order.
5. Submit a validated dry-run order with mandatory stop loss.
6. Verify daily-loss and risk-firewall enforcement.
7. Reconcile journal and broker positions; require zero orphans.
8. Verify dashboard and Telegram state against runtime events.
9. Restart the demo process and verify state recovery and signal deduplication.
10. Begin the two-week minimum observation window only after every preflight check passes.

## Next operator-gated phase

Broker connectivity remains intentionally unstarted. Before any connected demo test, operations must separately authorize the demo account configuration and provide a non-fixture approved package. The fixture and its test key must never be promoted to a runtime or live credential path.
