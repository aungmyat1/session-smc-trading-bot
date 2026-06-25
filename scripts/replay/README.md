# scripts/replay/

Target location for all replay scripts once import paths are updated.

Planned contents:
  replay_db.py            — primary Dukascopy → ST-A2 → PostgreSQL replay
  replay_6m.py            — 6-month BASELINE vs D2_COMBINED
  replay_2025.py          — 2025 EURUSD validation
  replay_parquet.py       — Parquet data adapter
  replay_setup_a_parquet.py — Setup-A 11-phase replay
  replay_st_a2_d1.py      — ST-A2 + D1 gates trial

Status: scripts currently live in scripts/ (parent). Move pending import refactor.
