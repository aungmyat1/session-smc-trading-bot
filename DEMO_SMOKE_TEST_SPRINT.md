# Demo Smoke Test Sprint

- Date: 2026-07-02
- Status: PREFLIGHT BLOCKED — APPROVED PACKAGE REQUIRED
- Owner: Engineering / Operations
- Live trading: DISABLED

## Entry conditions

- PR #19 merged: **PASS** (`284dcab` on `main`)
- Demo runtime integration report preserved: **PASS**
- Package and identity CLI self-tests: **PASS**
- Active approved package: **BLOCKED** (`reports/approved_packages/active` is absent)
- Broker connection attempt: **NOT STARTED**
- Order submission: **NOT STARTED**

The smoke test must not create, approve, or select a package on behalf of the strategy engineering platform. Operations must provide a signed, unexpired, risk-approved package whose identity matches the catalog, portfolio, SVOS registry, and runner.

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

## Required operator input

Place or link the approved package at `reports/approved_packages/active`, configure `STRATEGY_PACKAGE_SIGNING_KEY`, and identify the canonical strategy with `RUNNER_STRATEGY_ID`. No broker smoke test should run until those inputs validate.
