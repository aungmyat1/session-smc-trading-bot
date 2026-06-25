# Walk-Forward Research Plan
# Session & SMC Trading Bot — ST-A2 + Future Strategies

---

## §1 — Why Walk-Forward

Phase-0 used a single 5yr holdout backtest (2021–2026). Walk-forward validation
provides additional confidence by testing the signal on unseen folds after training
on prior folds. It cannot substitute for Phase-0 but provides:

1. Time-based stability check: does PF decay in later years?
2. Regime sensitivity: which market regimes (2022 bear, 2023 chop, 2024 trend) favour the strategy?
3. Parameter drift detection: do optimal params shift across folds?

---

## §2 — Data Requirements

| Symbol | Required range | Current data | Gap |
|---|---|---|---|
| EURUSD | 2021-01 → 2026-06 | CSV available | None (5yr covered) |
| GBPUSD | 2021-01 → 2026-06 | CSV starts 2023-03 | 2021-01 → 2023-02 missing |

**GBPUSD 2021–2023 gap** must be filled via `download_dukascopy.py` before
the 5yr GBPUSD walk-forward can run.

---

## §3 — Fold Design (Anchored Walk-Forward)

Use anchored (expanding window) folds: training window grows each fold,
test window stays 1 year.

```
Fold 1: Train 2021-01 → 2022-12 | Test 2023
Fold 2: Train 2021-01 → 2023-12 | Test 2024
Fold 3: Train 2021-01 → 2024-12 | Test 2025
Fold 4: Train 2021-01 → 2025-12 | Test 2026-H1 (partial)
```

**Do NOT tune parameters per fold.** Each fold uses the frozen ST-A2 Phase-0 params
(rr=3.0, sl_buffer=2pip, displacement_mult=1.2, min_sl=5pip). If these params fail
a fold, it is a signal that the strategy is regime-sensitive, not a tuning opportunity.

---

## §4 — Per-Fold Metrics

For each fold (train + test), report:

| Metric | Target | Notes |
|---|---|---|
| n (test) | ≥ 25 | Half of Phase-0 gate |
| PF_2x (test) | > 1.0 | Net after 2× spread stress |
| MaxDD (test) | < 20R | Same gate as Phase-0 |
| Win% | — | Informational |
| Monthly PF stability | < 2× variance across months | Fragility flag |

A single fold below PF_2x = 1.0 is a WARN, not a fail (small sample). Two consecutive
below-1.0 folds = ALERT (regime shift or strategy decay).

---

## §5 — Regime Classification per Fold

For each test fold, classify the dominant regime to contextualize results:

| Year | Expected regime (approximate) |
|---|---|
| 2022 | USD strength trend (DXY +15%) — directional, high volatility |
| 2023 | Range / correction phase |
| 2024 | Rate-cut positioning — mixed |
| 2025 | Normalization |

Regime classification does not gate the walk-forward — it contextualizes anomalies.

---

## §6 — Cross-Symbol Walk-Forward

Separate fold results for EURUSD and GBPUSD. Do NOT average:

```
Fold 3 EURUSD: n=23, PF_2x=1.18  → PASS
Fold 3 GBPUSD: n=11, PF_2x=0.88  → WARN (n too small to conclude)
```

If EURUSD consistently outperforms GBPUSD across folds, the portfolio decision
(CLAUDE.md §4 and VERDICT_LOG EXP05-A finding) to weight EURUSD higher is supported.

---

## §7 — Runner Implementation

When GBPUSD Parquet is available:

```bash
# Register new trial in VERDICT_LOG before running:
#   TRIAL_ST_A2_WF_001 — Walk-Forward 4-fold

python scripts/replay_parquet.py  # (or extend replay_6m.py for fold-aware runner)
```

The fold runner does not yet exist — it will be a new script `scripts/walk_forward.py`
registered as a new trial before implementation.

**Pre-registration required:** Per CLAUDE.md §9, a walk-forward runner that uses
different date windows than the Phase-0 holdout = new trial row in VERDICT_LOG.

---

## §8 — Blocked Items

| Item | Blocker | Expected unblock |
|---|---|---|
| GBPUSD 5yr fold | GBPUSD 2021-2023 Parquet not downloaded | After `download_dukascopy.py` run |
| Walk-forward runner | No script yet | After GBPUSD data available |
| E6 cost revalidation | Gate open ~2026-06-30 | After E6 spread collection completes |

---

*WALK_FORWARD_RESEARCH_PLAN.md | Written 2026-06-25*
