# EXP05_D_RESULTS.md
# ST-A2 Optimization — Variant D

**Filter:** NY only + strict bias + 15M CHoCH+BOS gate between sweep and entry
**Signals:** 2 of 169 baseline
**Trades:**  2

---

## Metrics

| Metric | Standard | 2× Stress | Target | Pass? |
|---|---|---|---|---|
| n | 2 | — | ≥ 100 | ❌ |
| PF | 0.472 | 0.406 | PF₂ₓ > 1.25 | ❌ |
| Win Rate | 50.0% | — | ≥ 40% | ✅ |
| Avg R | -0.2922 | -0.3606 | — | — |
| Max DD (R) | 1.11 | 1.21 | < 15.0 | ✅ |

**VERDICT: ❌ FAIL**

---

## Session Breakdown (standard spread)

| Session | n | PF | Win% |
|---|---|---|---|
| new_york | 2 | 0.472 | 50.0% |

## Symbol Breakdown (standard spread)

| Symbol | n | PF | Win% |
|---|---|---|---|
| EURUSD | 1 | 0.000 | 0.0% |
| GBPUSD | 1 | ∞ | 100.0% |

---

## Finding

**D=2 / 6.9% pass rate (2 of 29 C-signals passed CHoCH+BOS gate)**

With 30 pre-session bars of M15 context prepended (`PRE_SESSION_BARS=30`), CHoCH and BOS can
technically complete within the baseline's 4-bar displacement window — but require both to fire
in consecutive bars immediately after the sweep. This occurs in ~7% of cases over 5yr EUR+GBP.

n=2 is statistically meaningless. Even if the PF were strong, no inference is possible.

**Root constraint:** The baseline's `sweep_timeout_bars=4` means entry is at the displacement
close, which is 1–4 bars after the sweep. For CHoCH+BOS to precede that close, both structural
confirmations must complete within that narrow window. The full 15M CHoCH+BOS+FVG-retest chain
(the 11-phase signal in `session_smc/`) defers entry to the FVG retest, giving the structure
time to develop. That is ST-B territory — not an optimization of the ST-A2 entry model.

See `docs/VERDICT_LOG.md` EXP05 section for full experiment record.
