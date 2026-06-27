# Adaptive SMC Flow

1. Load M15 and H4 candles.
1. Call the legacy ST-A2 session-liquidity engine.
1. Convert the raw result to the adaptive signal format.
1. Attach sweep/structure metadata.
1. Forward the signal to the portfolio layer for shadow logging.

