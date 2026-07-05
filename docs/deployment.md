# Deployment Guide

**Document:** Production Deployment Runbook
**Last updated:** 2026-06-30

---

## IMPORTANT: No Current Strategy is Active

The Vantage bot must not be deployed with a live strategy until a Production Approval Package exists. `LIVE_TRADING=false` and `DEMO_ONLY=true` at all times until the owner explicitly changes these settings after all qualification phases have passed.

---

## Prerequisites

Before any deployment:

1. [ ] Strategy has received Phase 5 PASS (Virtual Demo)
2. [ ] Production Approval Package issued
3. [ ] Owner has reviewed and signed off on the approval report
4. [ ] `.env` file populated with correct credentials (never committed to git)
5. [ ] MetaAPI account connectivity verified
6. [ ] Telegram alerts operational
7. [ ] Daily loss limit and position sizing verified in bot config

---

## Environment Setup

```bash
# Clone the repo
git clone git@github.com:owner/smc-trading-bot.git
cd smc-trading-bot

# Install dependencies
pip install -r requirements.lock

# Copy and populate env file
cp .env.example .env
# Edit .env: set VANTAGE_DEMO_METAAPI_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

---

## Deployment Modes

### 1. Virtual Demo Mode (Phase 5 — Offline, no broker)

```bash
DEMO_ONLY=true LIVE_TRADING=false python -m svos.application.virtual_demo \
    --strategy ST-A2 \
    --dataset data/eurusd_m15_2022_2024.parquet
```

No network connection required. Fully deterministic.

### 2. Demo Account Mode (post-Production Approval only)

```bash
DEMO_ONLY=true LIVE_TRADING=false python bot/main.py --strategy ST-A2
```

Uses `VANTAGE_DEMO_METAAPI_ID` from `.env`. Requires MetaAPI connectivity.

### 3. Live Mode (requires CONFIRM-LIVE-ON token from owner)

```bash
# Owner must set LIVE_TRADING=true and DEMO_ONLY=false manually in .env
# DO NOT enable programmatically
LIVE_TRADING=true DEMO_ONLY=false python bot/main.py --strategy ST-A2
```

---

## Magic Numbers

| Symbol | Magic Number | Purpose |
|--------|-------------|---------|
| EURUSD | 21001 | Identifies bot-placed EURUSD orders |
| GBPUSD | 21002 | Identifies bot-placed GBPUSD orders |

The bot only manages positions with its own magic numbers. Third-party or manual positions are ignored.

---

## Health Checks

The monitoring service (`svos/monitoring/service.py`) aggregates:
- Log file scan for ERROR/CRITICAL/WARN/DISCONNECTED events
- Health snapshot from the broker connection layer
- Incident count and recent incident list

Dashboard: `python -m dashboard.app` (requires `dashboard/` module).

---

## Emergency Stop

To immediately halt all trading:

1. Send `/stop` command via Telegram (if bot command is configured)
2. Or set `LIVE_TRADING=false` in `.env` and restart the bot
3. Manual close: log into Vantage MT5 and close positions manually (magic numbers 21001/21002)

All emergency actions must be logged in `docs/INCIDENT_RESPONSE.md`.

---

## Rollback

1. Stop the running bot process
2. Revert to previous strategy version: `git checkout <previous-commit>`
3. Restart bot with previous config
4. Log the incident and root cause in the Verdict Log

---

## VPS Deployment

See `docs/VPS_DEPLOYMENT_RUNBOOK.md` for VPS-specific setup, systemd service configuration, and log rotation.
