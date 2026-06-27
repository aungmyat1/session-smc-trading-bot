# Parameter Catalog

## Global Sources

| Source | Key values |
| --- | --- |
| `config/strategy_catalog.yaml` | Strategy lifecycle status, approval, ownership, symbols, and deployment target. |
| `config/strategy_portfolio.yaml` | Execution mode, pairs, risk tier, min confidence, and strategy parameters. |
| `adaptive/config/adaptive_engine.yaml` | Session windows, adaptive risk limits, and session-strategy defaults. |
| `strategy/session_liquidity/config.yaml` | ST-A2 execution defaults used by the session-liquidity engine. |
| `config/risk.yaml` | Research/demo backtest assumptions for cost and execution delay. |

## Active Strategy Defaults

| Strategy | Important parameters |
| --- | --- |
| ST-A2 | `rr=3.0`, `sl_buffer_pips=2.0`, `displacement_mult=1.2`, `atr_period=14`, `sweep_timeout_bars=4`, `min_sl_pips=5.0`, `min_range_pips EURUSD=15`, `min_range_pips GBPUSD=20` |
| London Breakout | Asian `00:00-06:00 UTC`, London `06:00-09:00 UTC`, `min_range_pips=15`, `max_range_pips=50`, `tp_rr=1.5`, retest tolerance `0.3 pip` |
| NY Momentum | London `06:00-09:00 UTC`, NY `11:00-15:00 UTC`, `sweep_buffer_pips=1`, `tp_rr=2.0` |
| Adaptive SMC | `per_trade=0.5%`, `daily_loss_limit=1.5%`, `max_trades_per_day=4`, `max_consecutive_losses=3`, `min_score=7`, `max_spread_pips` by pair, `smc_session rr=3.0` |
| VWAP Mean Reversion | `min_session_bars=8` default, `sweep_buffer_mult=0.35`, `extreme_atr_mult=1.0`, `reclaim_atr_mult=0.6`, `tp_rr=1.8` |
| D2E3 | `session_start=8`, `session_end=16`, `confirm_bars=12`, `entry_wait_bars=3`, `min_stop_pips=2.0`, `max_stop_pips=25.0`, `rr=2.0`, `cooldown_bars=3`, `max_hold_bars=32` |

