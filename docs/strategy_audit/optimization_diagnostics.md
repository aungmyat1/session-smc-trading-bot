# Strategy Optimization Diagnostics

Use this table when reviewing failed or fragile strategy validation results.
It is diagnostic guidance only; any parameter or rule change still creates a
new pre-registered trial in `docs/VERDICT_LOG.md`.

| Failure | Meaning | Fix direction |
|---|---|---|
| Low win rate, but high RR | Entries may be too early or too late. | Improve confirmation. |
| High win rate, negative profit | RR too small, or fees and slippage are too high. | Improve exit or risk. |
| Good gross result, bad net result | Cost problem. | Reduce trades or move to a higher timeframe. |
| Few trades | Strategy is over-filtered. | Relax rules. |
| Many trades, big drawdown | Weak filters. | Add session, trend, or regime filter. |
| Works only in one month | Overfitted or regime-dependent. | Walk-forward testing. |
