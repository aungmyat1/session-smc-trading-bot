# Replay Integration Plan
# Connecting Parquet Pipeline to Existing Backtests

---

## §1 — Current State

All existing backtest scripts load data from CSV files in `data/historical/`:

| Script | Data source | Format |
|---|---|---|
| `scripts/backtest_session_liquidity.py` | `data/historical/EUR_USD_M15.csv` | CSV mid-price |
| `scripts/replay_6m.py` | `data/historical/*.csv` | CSV mid-price |
| `scripts/replay_st_a2_d1.py` | `data/historical/*.csv` | CSV mid-price |

GBPUSD CSV starts 2023-03-13 (only 3yr of 5yr required). The new Parquet pipeline
will provide 5yr GBPUSD data (2021-01 → 2026-06) once downloaded.

---

## §2 — Adapter: `scripts/replay_parquet.py`

The adapter exposes the same list-of-dicts bar format used by all existing scripts:

```python
from scripts.replay_parquet import load_m15, load_h1, load_h4, load_d1

bars = load_m15("EURUSD", start="2021-01-01T00:00:00Z", end="2026-06-19T23:59:59Z")
# Returns: [{"time": "2021-01-04T00:00:00Z", "open": 1.2270, ...}, ...]
```

**Fallback behaviour:** If Parquet is not yet built for a symbol/TF, the adapter
automatically falls back to the existing CSV files. This means existing scripts
continue to work unchanged until Parquet is available.

---

## §3 — Migration Steps (per script)

### Step 1 — Test adapter produces identical bars to CSV

```python
# Verify adapter matches CSV output
from scripts.replay_parquet import load_m15
bars_parquet = load_m15("EURUSD")
bars_csv = pd.read_csv("data/historical/EUR_USD_M15.csv").to_dict("records")
assert bars_parquet[0]["open"] == bars_csv[0]["open"]
```

### Step 2 — Swap loader (one-line change per script)

```python
# Before:
bars_m15 = load_csv("data/historical/EUR_USD_M15.csv")

# After:
from scripts.replay_parquet import load_m15
bars_m15 = load_m15("EURUSD")
```

### Step 3 — Enable 5yr GBPUSD

Once GBPUSD Parquet is built from 2021-01, pass `start="2021-01-01T00:00:00Z"`
to extend the backtest window from 3yr to 5yr for GBPUSD.

---

## §4 — Walk-Forward Runner Integration

The walk-forward research plan (`WALK_FORWARD_RESEARCH_PLAN.md`) requires loading
specific date windows per fold. The adapter handles this:

```python
# Fold N: train 2021-2023, test 2024
train_m15 = load_m15("EURUSD", start="2021-01-01T00:00:00Z", end="2023-12-31T23:59:59Z")
test_m15  = load_m15("EURUSD", start="2024-01-01T00:00:00Z", end="2024-12-31T23:59:59Z")
```

---

## §5 — Priority Order

1. **Immediate value (no download required):** Validate that `replay_parquet.py` adapter
   correctly loads existing CSVs as fallback → run `replay_6m.py` via adapter.

2. **Short-term (after GBPUSD 5yr download):** Re-run `backtest_session_liquidity.py`
   with full 5yr GBPUSD to improve n from 3yr to 5yr.

3. **Research (after all Parquet built):** Enable walk-forward folds.

---

*REPLAY_INTEGRATION_PLAN.md | Written 2026-06-25*
