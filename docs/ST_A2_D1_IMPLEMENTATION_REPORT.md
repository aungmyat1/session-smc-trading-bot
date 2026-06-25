# ST_A2_D1_IMPLEMENTATION_REPORT.md
# TRIAL_ST_A2_D1_001 — Implementation Report
# Date: 2026-06-25

---

## §1 — Summary

This report documents the implementation of the D1 context layer for
`TRIAL_ST_A2_D1_001`. All new code is additive — the ST-A2 execution chain
(`strategy/session_liquidity/`) is unchanged.

---

## §2 — New Files Created

### `session_smc/daily_context.py`

**Purpose:** Clean D1 daily context interface for the A/B replay framework.
Extends `daily_bias.py` with structured output and a single gate-evaluation function.

**Key additions over `daily_bias.py`:**

| Component | Description |
|---|---|
| `DailyContext` dataclass | Structured container vs plain dict in `daily_bias.py` |
| `daily_liquidity` dict | PDH, PDL, recent D1 swing highs, recent D1 swing lows (last 3 confirmed) |
| `daily_target` | `draw_to_highs` / `draw_to_lows` / `none` — likely D1 liquidity draw |
| `daily_target_level` | Price of the next likely draw |
| `apply_d1_gates()` | Single function evaluating all gates, returns `(pass_flag, reason)` |

**Gate implementation:**

```python
# Gate A: D1 bias must agree with HTF bias (neutral D1 = no block)
if c.get("d1_bias_filter", True):
    if ds != "neutral" and ds != htf_bias:
        return False, f"gate_A_bias: d1={ds} vs htf={htf_bias}"

# Gate B: price location must support trade direction
if c.get("d1_location_filter", True):
    loc = classify_location(session_open_price, ctx.pdh, ctx.pdl)
    if htf_bias == "bullish" and loc == "premium":
        return False, "gate_B_location: bullish but price above D1 midpoint"
    if htf_bias == "bearish" and loc == "discount":
        return False, "gate_B_location: bearish but price below D1 midpoint"

# Gate C: ARCHITECTURE STUB (TRIAL_ST_A2_D1_POI_001 — never enabled here)
if c.get("d1_poi_filter", False):
    assert False, "d1_poi_filter reserved for TRIAL_ST_A2_D1_POI_001"
```

**No lookahead guarantee:** `build_d1_context()` calls `build_daily_context()` from
`daily_bias.py` which only uses days strictly before `before_dt.date()`. All D1
swing detection is performed on closed daily bars only.

---

### `scripts/replay_st_a2_d1.py`

**Purpose:** A/B walk-forward replay comparing 4 variants over identical data.

**Architecture:**
- Uses `strategy/session_liquidity/` execution chain (ST-A2 canonical)
- D1 context applied at sweep-detection point (before sweep is accepted)
- Gate A applied at displacement confirm (final check to avoid race with session change)
- Gate B applied before each sweep-detection attempt (per killzone bar)

**Why `strategy/session_liquidity/` and not `session_smc/`:**
The `session_smc/` 11-phase CHoCH+BOS+FVG chain produces 0 signals in 6-month
windows (confirmed EXP05 Variant D: 2/29 signals = 6.9%, and in a 6-month clean run
the count was 0). The D1 context trial must run on a code path that generates
sufficient baseline signals. The `strategy/session_liquidity/` path is the ST-A2
Phase-0 code that produced 169 trades over 5 years.

**Variants:**
```
BASELINE      — d1_context_enabled=False  (exact ST-A2 replication)
D1_BIAS       — Gate A only
D1_LOCATION   — Gate B only
D1_ALL        — Gates A + B combined
```

---

### `docs/TRIAL_ST_A2_D1_SPEC.md`

Pre-registered trial specification with baseline definition, hypothesis, gate
criteria, and future trial sequence. Registered before any run.

---

## §3 — Unchanged Components (verified)

The following files were NOT modified:

| File | Status |
|---|---|
| `strategy/session_liquidity/session_strategy.py` | UNCHANGED |
| `strategy/session_liquidity/sweep_detector.py` | UNCHANGED |
| `strategy/session_liquidity/displacement_detector.py` | UNCHANGED |
| `strategy/session_liquidity/entry_engine.py` | UNCHANGED |
| `strategy/session_liquidity/bias_filter.py` | UNCHANGED |
| `strategy/session_liquidity/session_builder.py` | UNCHANGED |
| `session_smc/daily_bias.py` | UNCHANGED |
| `session_smc/confirmation_entry.py` | UNCHANGED |
| `scripts/backtest_session_liquidity.py` | UNCHANGED |
| `config/costs.json` | UNCHANGED |
| All risk parameters | UNCHANGED |

---

## §4 — Data Correctness Checks

**No-lookahead guarantee (confirmed):**
- D1 context uses only daily bars where `date < session_open_date`
- `aggregate_to_daily()` groups H4 bars by UTC calendar day
- Cutoff: `cutoff_date = before.date().isoformat()` → `closed = [d for d in daily if d["time"][:10] < cutoff_date]`

**Baseline replication (verified):**
- `d1_context_enabled=False` → `apply_d1_gates()` is never called
- All ST-A2 parameters identical to ST-D2-6M run and Phase-0 baseline
- BASELINE variant output is independent of `session_smc/daily_context.py`

---

## §5 — Future Trial Architecture (POI stub)

`session_smc/daily_context.py` contains an architecture stub for Gate C:

```python
# Gate C: POI proximity — ARCHITECTURE STUB
# Reserved for TRIAL_ST_A2_D1_POI_001. Never enable in TRIAL_ST_A2_D1_001.
if c.get("d1_poi_filter", False):
    assert False, "d1_poi_filter reserved for TRIAL_ST_A2_D1_POI_001"
```

Enabling `d1_poi_filter=True` will raise an AssertionError to prevent accidental
misuse within this trial. Activating Gate C constitutes a new trial
(`TRIAL_ST_A2_D1_POI_001`) requiring a new VERDICT_LOG entry before any run.

---

*ST_A2_D1_IMPLEMENTATION_REPORT.md | Written 2026-06-25 | TRIAL_ST_A2_D1_001*
