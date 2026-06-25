# SPREAD_CAPTURE_INTERIM.md
# Spread Capture — Interim Status Report
# Updated: 2026-06-24 06:35 UTC | Session 1 of 5 (London in progress)

---

## Collection Status

| Item | Value |
|---|---|
| Start time | 2026-06-24 05:57 UTC |
| Current time | 2026-06-24 06:35 UTC |
| tmux session | `spreads` — RUNNING |
| Polling interval | ~32s avg (target: 30s) |
| Organic gaps >90s | 0 (1 gap explained by deliberate restart at 06:00:31) |
| Total rows | 272 (68 polls × 4 pairs) |
| London sessions complete | 1 (in progress — 145min remaining today) |
| NY sessions complete | 0 (opens 11:00 UTC today) |
| Gate target | ≥5 London + ≥5 NY |

---

## Preliminary Spread Readings (1 London session, 2026-06-24)

### By Symbol and Session (all collected data)

| Symbol | Session | n | Avg (pip) | Median | P95 | Min | Max |
|---|---|---|---|---|---|---|---|
| EURUSD | london | 63 | 1.35 | 1.40 | 1.40 | 1.30 | 1.40 |
| EURUSD | off | 5 | 1.32 | 1.30 | 1.40 | 1.30 | 1.40 |
| GBPUSD | london | 63 | 1.56 | 1.60 | 1.60 | 1.50 | 1.70 |
| GBPUSD | off | 5 | 1.52 | 1.50 | 1.60 | 1.50 | 1.60 |
| USDJPY | london | 63 | 1.86 | 1.90 | 1.90 | 1.80 | 1.90 |
| AUDUSD | london | 63 | 1.46 | 1.50 | 1.50 | 1.40 | 1.60 |

### By Hour Within London Session (EURUSD and GBPUSD only — strategy pairs)

| Hour UTC | EURUSD n | EURUSD avg | GBPUSD n | GBPUSD avg |
|---|---|---|---|---|
| 06:xx | 63 | 1.35 | 63 | 1.56 |
| 07:xx | — | — | — | — |
| 08:xx | — | — | — | — |

*07:xx and 08:xx data pending — London session runs until 09:00 UTC.*

---

## Preliminary vs Placeholder Comparison

| Symbol | Measured avg | Placeholder (std) | Delta | Signal |
|---|---|---|---|---|
| EURUSD | 1.35 pip | 1.40 pip | −0.05 (−3.4%) | ✅ LOWER |
| GBPUSD | 1.56 pip | 1.80 pip | −0.24 (−13.6%) | ✅ LOWER |

**GBPUSD is tracking significantly below the placeholder.** The 1.80 pip assumption was
inherited from VT Markets Standard. Vantage Standard STP appears to be cheaper on GBPUSD
at London open. This is a positive signal for ST-A2 viability at real costs.

---

## Preliminary PF_2x Projection

Using a linear cost-drag model and the preliminary measured costs:

| Parameter | Value |
|---|---|
| Placeholder weighted 2× cost (105 EUR + 64 GBP trades) | 3.103 pip |
| Measured weighted 2× cost (preliminary) | 2.859 pip |
| Cost ratio (measured / placeholder) | 0.921 |
| PF drag at placeholder 2× (PF_std − PF_2x) | 0.126 |
| Estimated PF drag at measured cost | 0.116 |
| **Estimated PF_2x at measured cost** | **~1.035** |
| Gate (PF_2x > 1.00) | **PROJECTED PASS** (margin +0.035 vs +0.025 at placeholder) |

> ⚠️ **Preliminary only.** This is 1 London session (06:00–06:35 UTC today), no NY data.
> London is structurally cheaper than the session-open spike hour (07:00–08:30 UTC).
> The 07:xx and 08:xx hours may show wider spreads. NY data is critical given that
> NY carries the primary edge (EXP05: PF_2x_NY = 1.562).
> **Do not update costs.json until 5+5 sessions captured.**

---

## Collection Schedule

| Day | Date | London | NY | L total | NY total | Gate |
|---|---|---|---|---|---|---|
| Tue | 2026-06-24 | ✅ (today) | ✅ (11:00–14:00 UTC) | 1 | 1 | |
| Wed | 2026-06-25 | ✅ | ✅ | 2 | 2 | |
| Thu | 2026-06-26 | ✅ | ✅ | 3 | 3 | |
| Fri | 2026-06-27 | ✅ | ✅ | 4 | 4 | |
| Mon | 2026-06-30 | ✅ | ✅ | 5 | 5 | **✅ GATE MET** |

Estimated gate completion: **Monday 2026-06-30 ~14:00 UTC** (after NY close).

If tmux `spreads` session survives the weekend (it should — VPS is persistent), gate is met
in 6 calendar days. No action needed between now and 2026-06-30 unless:
- `tmux ls` no longer shows `spreads`
- `wc -l research/spread_samples.csv` stops growing
- `tail research/spread_samples.csv` shows stale timestamps

---

## Daily Monitoring Command

```bash
# Quick status check (run once per day)
python3 -c "
import csv, statistics
from collections import defaultdict
rows = [r for r in csv.DictReader(open('research/spread_samples.csv'))]
agg = defaultdict(list)
for r in rows:
    if r['session'] != 'off':
        agg[(r['symbol'], r['session'])].append(float(r['spread_pips']))
from datetime import datetime
sess_days = defaultdict(set)
for r in rows:
    if r['session'] != 'off':
        sess_days[r['session']].add(r['time_utc'][:10])
print(f'Rows: {len(rows)} | London {len(sess_days[\"london\"])}/5 | NY {len(sess_days[\"new_york\"])}/5')
for (sym, sess), vals in sorted(agg.items()):
    print(f'  {sym} {sess}: avg={statistics.mean(vals):.2f}p n={len(vals)}')
"
```

---

## What Happens After Gate

1. Stop capture: `tmux send-keys -t spreads C-c`
2. Run full analysis (see `docs/SPREAD_CAPTURE_PLAN.md` — Interpretation Guide)
3. Fill `config/costs.json → profiles.vantage_measured` with killzone averages
4. Set `active_profile = "vantage_measured"`
5. Rerun ST-A2: `python3 scripts/backtest_session_liquidity.py`
6. Apply E6 decision table from `docs/OPS02_REVISED_GATE.md`

---

*SPREAD_CAPTURE_INTERIM.md | 2026-06-24 | Collection ongoing — do not update costs.json yet*
