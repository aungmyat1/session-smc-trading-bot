# gcp-vm1 Quant Research Stack

This folder prepares `gcp-vm1` as the dedicated research VPS for `D2E3` and
future strategy testing.

## What runs here

- PostgreSQL 16 research database
- `D2E3` demo runner
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

3. Bootstrap the schema and seed rows:

```bash
python3 scripts/bootstrap_quant_db.py --database-url "$DATABASE_URL"
```

4. Verify the database:

```bash
python3 scripts/bootstrap_quant_db.py --dry-run
```

5. Run D2E3:

```bash
DEMO_LIVE=false python3 scripts/run_d2_e3_demo.py
```

For a persistent service, install [`systemd/d2e3.service`](systemd/d2e3.service)
and point it at [`run_d2e3.sh`](run_d2e3.sh).

To keep the journal reflected in PostgreSQL, enable
[`systemd/d2e3-journal-sync.timer`](systemd/d2e3-journal-sync.timer) and its
paired service.

## Database layout

The schema is defined in `db/schema_v2.sql` and includes:

- `market.*` for instruments, candles, session ranges, and SMC events
- `research.*` for strategies, replay runs, trades, trade features, and equity
- `analytics.*` for metrics and gates

The bootstrap script seeds:

- `EURUSD`, `GBPUSD`, `USDJPY`, `XAUUSD`
- `ST-A2`
- `ST-D2-E3-OPT2`

## Suggested next step

After the first backtest import, point `DATABASE_URL` at the Postgres instance
and wire the replay writers to store each run in `research.replay_runs`,
`research.trades`, and `analytics.strategy_metrics`.
