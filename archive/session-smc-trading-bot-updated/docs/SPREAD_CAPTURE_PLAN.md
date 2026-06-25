# SPREAD_CAPTURE_PLAN.md
# Real Vantage Spread Capture — Operations Guide
# Version 1.0 | 2026-06-24

---

## Why This Matters

ST-A2 passed Phase-0 with PF_2x=1.025 — a margin of 0.025 above the gate. That margin is
determined almost entirely by the spread assumption. The current assumption (EURUSD 1.4pip,
GBPUSD 1.8pip round-trip) was inherited from VT Markets Standard and has **never been
verified against Vantage**. If the real Vantage killzone-hour spread is wider (common at
session opens), ST-A2 may actually be a FAIL on the real account.

This capture run answers: what is the actual round-trip cost on your Vantage Standard account
at the exact hours the strategy trades?

---

## Script Location

```
scripts/capture_spreads.py
```

Reads market data only. Places no orders. Uses `execution/metaapi_client.py` (same SDK
as the trading bot). Writes append-only to `research/spread_samples.csv`.

---

## Exact tmux Command

```bash
# Start a detached tmux session named 'spreads'
tmux new-session -d -s spreads \
  'python3 scripts/capture_spreads.py \
     --commission-pips 0.0 \
     --interval 30 \
     2>&1 | tee logs/spread_capture.log'

# Attach to watch live output
tmux attach -t spreads

# Detach without stopping: Ctrl-B, then D

# To stop cleanly (generates the report)
tmux send-keys -t spreads C-c
```

**Environment variables required (already set in .env for the trading bot):**
```bash
export METAAPI_TOKEN=...
export METAAPI_ACCOUNT_ID=...
# OR: source .env before running
```

**Full command with .env sourcing:**
```bash
tmux new-session -d -s spreads \
  'source .env && python3 scripts/capture_spreads.py \
     --commission-pips 0.0 --interval 30 \
     2>&1 | tee logs/spread_capture.log'
```

---

## Account Details (Vantage Demo)

| Field | Value |
|---|---|
| Broker | VantageMarkets-Demo |
| Account ID | d6f6eec3-96d5-4001-a802-62b3f4b49817 |
| Platform | MT5 |
| Account type | Standard STP |
| Commission | 0.0 pip (spread-only; commission embedded) |
| LIVE_TRADING | false (no orders placed) |

---

## Required Runtime

**Minimum: 5 London sessions + 5 NY sessions** (≈ 1 full trading week).

**Recommended: 7 calendar days** (2 trading weeks minimum coverage, captures weekday variation).

The strategy is sensitive to within-week spread patterns:
- Monday opens typically have wider spreads (weekend gap + low liquidity)
- Wednesday/Thursday sessions are usually tighter
- News events (CPI, NFP) spike spreads to 5–15 pip — these are off-hours for the strategy
  but the capture script tags them "off", so they don't pollute killzone averages

---

## Expected Sample Count

| Duration | Sessions captured | Samples per session | Total samples |
|---|---|---|---|
| 1 day | ~2 (London + NY) | ~180 (90 min × 2/min at 30s) | ~360 |
| 5 days (1 week) | ~10 | ~180 | ~1,800 |
| 7 days | ~14 | ~180 | ~2,520 |

**At 30-second interval:**
- London session (3h = 180 min): ~360 samples/pair/session
- NY session (3h = 180 min): ~360 samples/pair/session
- Per week: ~3,600 samples per pair across both sessions

A 7-day run yields ~25,000 total rows across 4 pairs + off-session samples.

---

## Session Windows (DST-Aware)

The script uses `session_builder.classify_session()` from the trading bot — the SAME
function that classifies bars in the backtest and live bot. Sessions shift with DST:

| Season | London UTC | NY UTC |
|---|---|---|
| Winter (EST, Nov–Mar) | 07:00–10:00 | 12:00–15:00 |
| Summer (EDT, Mar–Nov) | 06:00–09:00 | 11:00–14:00 |

The fixed 13:00–16:00 UTC window for NY used in the original script is wrong; the
corrected script handles this automatically.

---

## Monitoring During Capture

```bash
# Watch log in real time
tail -f logs/spread_capture.log

# Count samples so far
wc -l research/spread_samples.csv

# See per-session average so far (quick check)
python3 -c "
import csv; from collections import defaultdict
agg = defaultdict(lambda:[0.0,0])
for r in csv.DictReader(open('research/spread_samples.csv')):
    k = (r['symbol'], r['session'])
    agg[k][0] += float(r['spread_pips']); agg[k][1] += 1
for (s,sess),v in sorted(agg.items()):
    if sess != 'off' and v[1]>0:
        print(f'{s} {sess}: {v[0]/v[1]:.2f}p (n={v[1]})')
"
```

---

## Interpretation Guide

### What to look for

**EURUSD at London open (07:00–07:30 UTC, winter):**
- Typical Vantage Standard: 1.0–2.0 pip (tight)
- At London open spike (08:00–09:00 UTC): may hit 1.5–3.0 pip
- Assume the worst 30-min window to be conservative

**GBPUSD at London open:**
- Typically 1.5–3.0 pip, wider than EURUSD
- Check if average is above 1.8pip (the current assumption) — if so, ST-A2 fails 2× stress

**NY session (12:00–15:00 UTC, winter):**
- Usually tighter than London open: 1.0–1.5 pip EURUSD, 1.2–1.8 pip GBPUSD
- NY is the primary edge carrier (EXP05: PF_2x=1.562) — cheaper NY spread strengthens the case

### Decision thresholds

| Measurement | Action |
|---|---|
| EURUSD avg < 1.4pip AND GBPUSD avg < 1.8pip | Current assumption is conservative → ST-A2 PASS is confirmed or improved |
| EURUSD avg 1.4–1.6pip OR GBPUSD avg 1.8–2.0pip | Marginal — re-run backtest with measured costs, may still PASS |
| EURUSD avg > 1.6pip OR GBPUSD avg > 2.0pip | Current assumption underestimates cost → ST-A2 may FAIL on real account |
| Any pair avg > 3.0pip | Session-open spike contaminating average; filter by hour before averaging |

---

## costs.json Update Procedure

After 7 days of capture, run the script once more to generate the final report, then:

**Step 1: Get killzone averages**
```bash
tmux send-keys -t spreads C-c   # stop the running script; it prints the report
# OR: python3 scripts/capture_spreads.py --interval 30 (if already stopped, re-run briefly)
```

**Step 2: Fill config/costs.json**

Edit `config/costs.json` → `profiles.vantage_measured`:
```json
"vantage_measured": {
  "_note": "Measured 2026-07-01 to 2026-07-07 — London+NY killzone average",
  "EURUSD": { "standard": <measured_avg + commission>, "stress2x": <2×> },
  "GBPUSD": { "standard": <measured_avg + commission>, "stress2x": <2×> }
}
```

**Step 3: Update active_profile**
```json
"active_profile": "vantage_measured"
```

**Step 4: Re-run ST-A2 backtest**
```bash
python3 scripts/backtest_session_liquidity.py
```
Compare new `PF_std` and `PF_2x` against the 1.151 / 1.025 documented in
`docs/ST_A2_CONFIRMATION.md`.

**Step 5: Update VERDICT_LOG.md**

Add a row under the EXP-SPREAD section (new section) with:
- Date measured
- EURUSD killzone avg, GBPUSD killzone avg
- New PF_std, PF_2x at measured cost
- PASS / FAIL verdict

---

## Decision Tree After Measurement

```
Measure real Vantage killzone spreads
          │
          ▼
    Both pairs avg ≤ assumed?
     /                     \
   Yes                      No
    │                        │
    ▼                        ▼
ST-A2 confirmed or        Re-run backtest with
improved on real costs    measured costs
    │                        │
    ▼                        ├── PASS → continue demo
Continue demo (DEP-02)    │
+ resume STB-01           └── FAIL → prioritize cost
                                      reduction (NY-only
                                      trial = ST-A3?)
```

---

## What NOT to Do

- Do NOT modify `config/costs.json` until 5+ killzone sessions are captured.
- Do NOT re-run the backtest during spread capture (separate concerns).
- Do NOT stop the capture script during a killzone window — re-attach and wait for off-hours.
- Do NOT use off-session samples for the killzone average (tagged "off" and excluded automatically).

---

## Files

| File | Purpose |
|---|---|
| `scripts/capture_spreads.py` | Live spread capture script |
| `config/costs.json` | Cost profiles (placeholder + measured) |
| `research/spread_samples.csv` | Raw sample output (append-only) |
| `logs/spread_capture.log` | Console output with session tagging |

---

*SPREAD_CAPTURE_PLAN.md | v1.0 | 2026-06-24*
