# Research artifacts archive — 2026-07-11

## Archive date
2026-07-11

## Contents
- `research_engine/` — per-symbol research-engine feature cache (Parquet: candles, trades), built 2026-06-26
- `research_sweep/` — per-sweep-variant result cache (Parquet: candles, trades), built 2026-06-26
- `research.db` — DuckDB sink for `build_research_engine.py` (tables: candles, fvg, liquidity, order_blocks, sessions, signals, structure, swings, trades)
- `research_sweep.db` — DuckDB sink for `src/analytics/sweep.py`'s sweep runs (same 9-table schema)

## Rationale
All four artifacts were confirmed, prior to this move:
- **Untracked and gitignored** — never part of the `session-smc-trading-bot` git history; this archival has no effect on GitHub.
- **Stale** — all files dated 2026-06-26, a single batch run, untouched for 15 days.
- **Zero active dependency** — no systemd unit, crontab entry, or currently-running process reads or writes these paths (`lsof` showed nothing had them open; `scripts/health_check.py`'s DuckDB fallback path is dead code under this host's current config, since `DATABASE_URL` is set and the live health check resolves to Postgres, verified by direct execution before this move).
- **Reproducible** — both are default outputs of working CLIs (`scripts/build_research_engine.py`, `scripts/run_research_sweep.py`) that regenerate from `data/historical` (16M raw source, still present, untouched by this archival).

Full inventory evidence (sizes, timestamps, table lists, every code/cron/systemd reference checked) was
compiled before this move — see the review that preceded this archival for the complete audit trail.

## Backup location
A separate, independent backup (created before this move, checksum-verified) exists at:
`~/backups/research_cleanup_2026-07-11/`
containing byte-identical copies of all four artifacts. SHA-256 of both `.db` files matched the
pre-move originals at backup time.

This archive directory (`archive/research_artifacts_2026-07-11/`) is the *primary* relocated copy;
`~/backups/research_cleanup_2026-07-11/` is a *secondary* independent copy — two recoverable copies
exist, nothing was deleted.

## Rebuild commands
From the repo root, with `data/historical` present:

```bash
# Rebuild research_engine/ + research.db
python3 scripts/build_research_engine.py --symbol EURUSD --symbol GBPUSD --symbol XAUUSD --config config/research_engine.yaml

# Rebuild research_sweep/ + research_sweep.db
python3 scripts/run_research_sweep.py
```

Both commands write to their default root-level paths (`research_engine/`, `research.db`,
`research_sweep/`, `research_sweep.db`) — i.e. running them regenerates fresh output at the
original (now-archived) location, not inside this archive directory.

## Verification evidence
Checked before archival:
- `lsof research.db research_sweep.db` — no process had either file open
- `crontab -l` — no crontab for this user
- `git grep` across tracked `.py`/`.yaml` — no active reader of these specific data paths outside their own producer scripts and `tmp_path`-scoped tests
- `python3 scripts/health_check.py` — live run confirmed Research DB check resolves to Postgres (`vmassit`, reachable, PASS), not these DuckDB files
- `sudo -u postgres psql` — confirmed `research` schema in Postgres currently has 0 tables (the Postgres migration path, if any, has not consumed this data — noted for context, not a blocker)

Checked after archival (this move):
- See the post-archive report accompanying this change for `health_check.py`, `vps-health-check.timer`,
  and `smc-demo-runner.service` status immediately following the move.
