# SVOS Sample London Sweep

Market: FX
Instruments: EURUSD
Timeframe: M15
Session: London and New York killzones only
Direction: Long only when H1 bias is bullish
Bias: Bullish market structure with BOS close beyond the prior swing high by at least 1 pip
Entry Trigger: During London or New York, wait for a liquidity sweep of the prior session low by at least 2 pips, then enter on the first M15 close that confirms CHOCH within 3 candles
Confirmation: Require a BOS close beyond the prior swing and a three-candle FVG of at least 1 pip after measurable displacement
Invalidation: Cancel if CHOCH does not occur within 3 candles after the sweep or price closes below the swept low before entry
Entry Rules: Enter on the first qualifying M15 confirmation close during the active killzone after the sweep and CHOCH sequence
Stop Loss: Place the stop 2 pips below the swept low
Take Profit: Close the full position at 2R
Risk: Use 0.3% fixed fractional risk per trade
Risk Model: Maximum daily loss is 2R and maximum drawdown is 8%
Position Sizing: Calculate size from stop distance so account risk equals 0.3%
Maximum Daily Loss: 2R
Maximum Drawdown: 8%
Maximum Open Positions: 1
News Rules: Do not open a trade within 15 minutes of high-impact EUR or USD news
Filters: Require HTF bias, an explicit session filter for the defined killzones, and spread below 1.5 pips
Exit Rules: Close at 2R or the stop loss and cancel an unconfirmed setup when its three-candle window expires
