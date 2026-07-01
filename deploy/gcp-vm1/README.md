# gcp-vm1 Quant Research Stack

This folder prepares `gcp-vm1` as the dedicated research VPS for `D2E3` and
future strategy testing.

## What runs here

- PostgreSQL 16 research database
- `D2E3` demo runner
- Standalone live trading dashboard on its own address/port
- Replay/backtest ingestion from `data/` and `logs/`
- Structured trade journal at `logs/d2e3_trades.jsonl`
- 5-minute journal sync into PostgreSQL for runs, trades, and metrics

## Why this exists

The production `ST-A2` bot stays isolated on the current VPS. `gcp-vm1` is the
separate research node so strategy testing, database writes, and experimental
replays do not compete with live demo execution.

## Bring-up

1. Copy `.env.example` to `.env` and set real secrets.
   - Set `DB_BACKEND=postgres` for the research node so the DB health check
     validates the local Postgres service.
2. Start Postgres:

```bash
docker compose --env-file .env up -d postgres
```

3. Bootstrap the full schema and seed rows:

```bash
python3 scripts/bootstrap_quant_db.py --database-url "$DATABASE_URL"
```

4. Verify the bootstrap inputs:

```bash
python3 scripts/bootstrap_quant_db.py --dry-run
```

5. Run D2E3:

```bash
DEMO_LIVE=false python3 scripts/run_d2_e3_demo.py
```

For a persistent D2E3 service, install [`systemd/d2e3.service`](systemd/d2e3.service)
and point it at [`run_d2e3.sh`](run_d2e3.sh).

To keep the journal reflected in PostgreSQL, enable
[`systemd/d2e3-journal-sync.timer`](systemd/d2e3-journal-sync.timer) and its
paired service.

## Standalone live dashboard

The live trading dashboard is now a separate Flask app from SVOS.

- SVOS/control panel remains on port `8080`
- Live trading dashboard runs on port `8090` by default

Run it manually:

```bash
python3 dashboard/live_app.py
```

Or use the wrapper:

```bash
./deploy/gcp-vm1/run_live_dashboard.sh
```

For a persistent service, install
[`systemd/live-dashboard.service`](systemd/live-dashboard.service) and use an
environment file like:

```bash
sudo install -d /etc/session-smc-trading-bot
sudo tee /etc/session-smc-trading-bot/live-dashboard.env >/dev/null <<'EOF'
REPO_DIR=/opt/session-smc-trading-bot
PYTHON_BIN=/opt/session-smc-trading-bot/.venv/bin/python
SVOS_OPERATOR_TOKEN=replace-me
VPS_IP_ADDRESS=34.87.36.159
LIVE_DASHBOARD_HOST=0.0.0.0
LIVE_DASHBOARD_PUBLIC_HOST=34.87.36.159
LIVE_DASHBOARD_PORT=8090
LIVE_TRADING=false
DEMO_ONLY=true
EOF
```

Install and enable it:

```bash
sudo cp deploy/gcp-vm1/systemd/live-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now live-dashboard.service
sudo systemctl status live-dashboard.service
```

Expected live dashboard address:

```text
http://34.87.36.159:8090
```

## Database layout

The database is initialized from both:

- `db/schema_v2.sql` for market/research/analytics/config
- `db/schema_v3.sql` for strategy/governance/evidence/experiments/robustness/execution/operations

That includes:

- `market.*` for instruments, candles, session ranges, and SMC events
- `research.*` for strategies, replay runs, trades, trade features, and equity
- `analytics.*` for metrics and gates
- `strategy.*` for canonical strategy identity and immutable versions
- `governance.*` for stage state, decisions, approvals, and outbox
- `evidence.*` for artifacts, bindings, reports, and legacy imports
- `experiments.*`, `robustness.*`, `execution.*`, and `operations.*` for the SVOS control plane

The bootstrap script seeds:

- `EURUSD`, `GBPUSD`, `USDJPY`, `XAUUSD`
- `ST-A2`
- `ST-D2-E3-OPT2`

## Suggested next step

After the first backtest import, point `DATABASE_URL` at the Postgres instance
and wire the replay writers to store each run in `research.replay_runs`,
`research.trades`, and `analytics.strategy_metrics`.
