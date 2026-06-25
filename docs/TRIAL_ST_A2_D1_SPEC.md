# TRIAL_ST_A2_D1_SPEC.md
# Trial: TRIAL_ST_A2_D1_001 — ST-A2 + D1 Context Layer
# Status: PRE-REGISTERED
# Registered: 2026-06-25

---

## §0 — Trial Identity

| Field | Value |
|---|---|
| Trial ID | `TRIAL_ST_A2_D1_001` |
| Parent strategy | ST-A2 (Phase-0 PASS, run `20260621T100458-183aaa`) |
| Runner | `scripts/replay_st_a2_d1.py` |
| Test period | 2026-05-01 → 2026-06-30 (data-limited to 2026-06-19) |
| Symbols | EURUSD, GBPUSD |
| Registered | 2026-06-25 — before any run on this trial ID |

---

## §1 — Baseline Definition (CONTROL)

The control is ST-A2 **unchanged**. ST-A2 is fully defined by run `20260621T100458-183aaa`.

**Execution chain (unchanged):**
```
4H + 1H bias (swing_n=3)
  ↓
Asian session range build (London open 02:00 EST / NY open 07:00 EST)
  ↓
Killzone sweep detection (Asian H/L breach + close back inside range)
  ↓
Displacement (ATR × 1.2x body, within 4 bars of sweep)
  ↓
Entry at displacement bar close
  SL: sweep wick − 2pip buffer  |  min_sl: 5pip
  RR: 3.0
```

**Baseline parameters (frozen — do not change):**
```
rr                 = 3.0
sl_buffer_pips     = 2.0
displacement_mult  = 1.2
atr_period         = 14
sweep_timeout_bars = 4
min_sl_pips        = 5.0
min_range_pips     = EURUSD: 15pip | GBPUSD: 20pip
```

**Baseline cost model (PLACEHOLDER — same as ST-A2 Phase-0):**
```
EURUSD: 1.4pip standard / 2.8pip 2×
GBPUSD: 1.8pip standard / 3.6pip 2×
```

**ST-A2 Phase-0 reference result (5yr holdout):**
```
n=169, Win%=32.0%, Gross PF=1.299, Net PF (std)=1.151, Net PF (2×)=1.025, MaxDD=18.72R
```

---

## §2 — What Changes (the experiment)

A D1 (Daily) context layer is inserted **before** sweep detection. It evaluates
whether the session's setup aligns with the daily timeframe's structure and price
location. Three gates are defined; this trial tests Gates A and B only.

**New module:** `session_smc/daily_context.py`

**D1 context outputs:**

| Field | Description |
|---|---|
| `daily_bias` | D1 swing structure: `bullish` / `bearish` / `neutral` |
| `daily_location` | Price position vs PDH/PDL midpoint: `premium` / `discount` / `equilibrium` |
| `daily_liquidity` | PDH, PDL, recent D1 swing highs, recent D1 swing lows |
| `daily_target` | Likely next draw: `draw_to_highs` / `draw_to_lows` / `none` |
| `daily_target_level` | Price of the likely draw target |

**D1 gates (AND-gates applied before sweep detection):**

| Gate | Config flag | Default | Description |
|---|---|---|---|
| A | `d1_bias_filter` | True (when enabled) | D1 structure must not conflict with 4H+1H bias. Neutral D1 = no block. |
| B | `d1_location_filter` | True (when enabled) | Session bar open in discount (long) / premium (short) vs PDH/PDL midpoint. |
| C | `d1_poi_filter` | **False — STUB** | Reserved for `TRIAL_ST_A2_D1_POI_001`. Not tested in this trial. |

**Master switch:**
```yaml
d1_context_enabled: false   # all gates off → exact ST-A2 behavior (BASELINE)
d1_context_enabled: true    # gates evaluated per individual flags above
```

---

## §3 — What Does NOT Change

The following are locked for this trial. Any change = a new trial ID.

- 15M CHoCH logic
- 15M BOS logic
- FVG detection and retest (not in ST-A2; this is a future ST-B layer)
- Session filters (London / NY window times)
- Displacement body threshold
- SL/TP calculation
- Risk model (position sizing, daily loss limits)
- Spread cost assumptions
- RR ratio

---

## §4 — Variants Tested

| Variant | D1 enabled | Gate A | Gate B | Purpose |
|---|---|---|---|---|
| `BASELINE` | ✗ | ✗ | ✗ | Exact ST-A2 replication (control) |
| `D1_BIAS` | ✓ | ✓ | ✗ | Gate A in isolation |
| `D1_LOCATION` | ✓ | ✗ | ✓ | Gate B in isolation |
| `D1_ALL` | ✓ | ✓ | ✓ | Combined D1 filter (primary outcome measure) |

---

## §5 — Hypothesis

**H₁:** The D1 context layer improves ST-A2's quality-adjusted edge by filtering
out sessions where the daily timeframe structure conflicts with the intraday bias
(Gate A) or where price is already at the wrong side of the daily range (Gate B).

**H₀ (null):** D1 context provides no statistically significant improvement.
The gates over-filter valid trades without compensating quality gain.

**Prior evidence:** `ST-D2-6M` (registered in VERDICT_LOG, run 2026-06-25)
tested an identical hypothesis on a 6-month window (2026-01-01 to 2026-06-19)
with the same three gates. Result: BASELINE n=16 PF_2x=1.909 → D2_COMBINED n=5
PF_2x=0.135. The gates removed 69% of trades and destroyed the edge.

This trial (`TRIAL_ST_A2_D1_001`) uses a narrower window (2026-05-01→2026-06-19,
~7 weeks) to produce an isolated, independently-registered result for the specific
date range requested. Given the ST-D2-6M finding, H₀ is the more likely outcome.

---

## §6 — Success Criteria (D1_ALL vs BASELINE)

| Criterion | PASS condition | FAIL condition |
|---|---|---|
| Primary | D1_ALL PF_2x > BASELINE PF_2x | PF_2x decreases |
| Secondary | n(D1_ALL) ≥ 0.5 × n(BASELINE) | Trade count collapses |
| Tertiary | Max DD reduces | Max DD increases materially |
| Trade count floor | n(D1_ALL) ≥ 10 for statistical comment | n < 10 → INSUFFICIENT |

**Gate pass:** D1 layer is accepted if ALL of:
1. PF_2x(D1_ALL) > PF_2x(BASELINE), AND
2. n(D1_ALL) ≥ 0.5 × n(BASELINE), AND
3. n(D1_ALL) ≥ 10

**Gate fail:** Any of:
- PF_2x decreases
- Drawdown increases materially
- Trade count < 5 (extreme over-filtering)

---

## §7 — Future Trial Sequence

```
TRIAL_ST_A2_D1_001   (this)   — ST-A2 + D1 context (Gates A + B)
TRIAL_ST_A2_D1_POI_001        — ST-A2 + D1 context + Gate C (POI proximity)
```

Gate C is architecturally stubbed in `session_smc/daily_context.py` but
must not be activated in this trial. A parameter change (enabling Gate C)
constitutes a new trial.

---

## §8 — Registration Notes

- ST-D2-6M (VERDICT_LOG entry) covers 2026-01-01 to 2026-06-19 with the
  same gates. Results were catastrophically negative. This trial overlaps
  that period's last 7 weeks but is independently registered.
- The 7-week window (34 trading days) produces very thin trade counts at
  ST-A2's historical frequency (~32 trades/year combined = ~4 trades/7wk).
  Any result must be read in the context of extreme statistical uncertainty.
- Both BASELINE and D1_ALL are run on identical data — no lookahead.

---

*TRIAL_ST_A2_D1_SPEC.md | Registered 2026-06-25 | Do not modify after run starts*
