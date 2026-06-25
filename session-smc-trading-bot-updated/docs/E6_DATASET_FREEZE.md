# E6_DATASET_FREEZE.md
# Phase 2 Dataset Freeze — Purpose, Usage, and Verification
# Written: 2026-06-24

---

## Purpose

E6 revalidates ST-A2's Phase-0 result under measured Vantage spread costs.
The verdict is only meaningful if the exact inputs used can be identified and
replicated. Without a freeze, a future question — "was there more data collected
between the cost model and the backtest?" — has no auditable answer.

The freeze guarantees:

```
E6 result = exact spread_samples.csv
          + exact cost_model.json
          + exact costs.json (pre-export state)
```

SHA256 hashes make every input byte-for-byte verifiable. If the E6 result is
ever questioned, the snapshot proves which dataset it was computed against.

---

## When to Run

**Only after `python3 scripts/check_phase2_completion.py` exits 0.**

The gate requires:
- ≥ 5 London killzone sessions
- ≥ 5 New York killzone sessions
- ≥ 7,000 total rows in `research/spread_samples.csv`

Running the freeze before the gate produces a partial snapshot. The script
warns clearly (`⚠️ Gate: NOT YET MET`) and records the gate status in the
manifest, but does not block. **A partial snapshot must not be used for E6.**

Expected gate date: ~2026-06-30 14:00 UTC.

---

## Correct Execution Order

```
# 1. Verify gate is open
python3 scripts/check_phase2_completion.py   # must exit 0

# 2. Build cost model (required input for the freeze)
python3 scripts/build_cost_model.py          # writes research/cost_model.json

# 3. Freeze dataset
python3 scripts/freeze_phase2_dataset.py     # writes research/e6_dataset_snapshot/

# 4. Run E6 pipeline
bash scripts/run_e6_revalidation.sh

# 5. Compare results
python3 scripts/compare_e6_to_baseline.py
```

Steps 2 and 3 can also be run as part of the E6 pipeline (which calls
`build_cost_model.py` internally). If you want the freeze to capture the
pre-pipeline state, run steps 1–3 manually first.

---

## Usage

```bash
python3 scripts/freeze_phase2_dataset.py
```

No arguments. Reads source files from standard project paths.
Overwrites any existing snapshot in `research/e6_dataset_snapshot/` with a
warning showing the previous snapshot's timestamp.

---

## Output

### Directory structure

```
research/e6_dataset_snapshot/
├── spread_samples.csv       — verbatim copy (no transformation)
├── cost_model.json          — verbatim copy
├── costs.json               — verbatim copy (pre-export_spread_limits state)
└── dataset_manifest.json    — SHA256 hashes + coverage + gate status
```

### dataset_manifest.json

```json
{
  "created_at": "2026-06-30T14:05:00Z",
  "freeze_version": "1",
  "gate_status": {
    "collection_complete": true,
    "exit_code": 0,
    "summary": "READY_FOR_COST_REVALIDATION ..."
  },
  "source_files": {
    "spread_samples.csv": {
      "sha256": "<64-char hex>",
      "rows": 8540,
      "size_bytes": 483000
    },
    "cost_model.json": {
      "sha256": "<64-char hex>",
      "size_bytes": 2550
    },
    "costs.json": {
      "sha256": "<64-char hex>",
      "active_profile": "PLACEHOLDER_vt_markets_assumption",
      "size_bytes": 2094
    }
  },
  "coverage": {
    "symbols": ["AUDUSD", "EURUSD", "GBPUSD", "USDJPY"],
    "total_samples": 8540,
    "earliest_timestamp": "2026-06-24T05:57:48Z",
    "latest_timestamp":   "2026-06-30T14:00:00Z",
    "london_sessions": 5,
    "ny_sessions": 5,
    "sessions": {
      "london":   { "samples": 6600, "dates": ["2026-06-24", ...], "session_count": 5 },
      "new_york": { "samples": 1700, "dates": ["2026-06-24", ...], "session_count": 5 },
      "off":      { "samples": 240 }
    },
    "killzone_samples_by_symbol": {
      "AUDUSD": 2075, "EURUSD": 2075, "GBPUSD": 2075, "USDJPY": 2075
    }
  }
}
```

Key fields:
- `gate_status.collection_complete` — must be `true` for a production freeze
- `source_files.costs.json.active_profile` — must be `PLACEHOLDER_vt_markets_assumption` at freeze time
- `coverage.london_sessions` / `ny_sessions` — must be ≥ 5 each

---

## Integrity Verification

To verify a snapshot against its manifest at any future point:

```bash
python3 - <<'EOF'
import hashlib, json
from pathlib import Path

snap = Path("research/e6_dataset_snapshot")
manifest = json.loads((snap / "dataset_manifest.json").read_text())

for name, info in manifest["source_files"].items():
    p = snap / name
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    expected = info["sha256"]
    status = "OK" if h == expected else "MISMATCH"
    print(f"  {status}  {name}")
    if h != expected:
        print(f"    expected: {expected}")
        print(f"    actual:   {h}")
EOF
```

If any file shows `MISMATCH`, the snapshot has been modified and cannot be
used as a reproducibility reference.

---

## What the Freeze Captures

| File | Captures | Key invariant |
|---|---|---|
| `spread_samples.csv` | All spread samples collected up to freeze time | Row count must match manifest; SHA256 must match |
| `cost_model.json` | P95/avg/median per symbol/session at freeze time | Computed from the frozen spread_samples |
| `costs.json` | Config state before E6 modifies it | `active_profile` must be PLACEHOLDER at freeze time |

### What it does NOT capture

- Historical bar data (`data/historical/`) — unchanged from Phase-0, no need to snapshot
- Strategy code — unchanged, tracked by git
- `research/trades.csv` / `research/backtest_runs.csv` — outputs of the backtest, not inputs
- `.env` — never captured (contains secrets)

---

## Relationship to E6 Pipeline

The E6 pipeline (`run_e6_revalidation.sh`) modifies two files:
1. `config/costs.json` — `active_profile` flipped to `vantage_measured`; measured costs filled in
2. `docs/BACKTEST_RESULTS.md` — overwritten with E6 run results

The snapshot preserves the pre-E6 state of `costs.json` so that the exact
inputs to the E6 run are fully reconstructible from `research/e6_dataset_snapshot/`.

---

## Failure Modes

| Error | Cause | Fix |
|---|---|---|
| `cost_model.json MISSING` | `build_cost_model.py` not run | `python3 scripts/build_cost_model.py` |
| `spread_samples.csv MISSING` | Collection never started | Check `tmux spreads` session |
| `Integrity check FAILED` | Copy failure (disk error) | Delete snapshot dir, retry |
| `Gate: NOT YET MET` in manifest | Ran before collection complete | Re-run after gate opens |
| `active_profile` ≠ PLACEHOLDER | `export_spread_limits.py` already ran | Restore: `git checkout config/costs.json`; re-run pipeline from Step 2 |

---

*E6_DATASET_FREEZE.md | Written 2026-06-24 | Run freeze only after check_phase2_completion.py exits 0*
