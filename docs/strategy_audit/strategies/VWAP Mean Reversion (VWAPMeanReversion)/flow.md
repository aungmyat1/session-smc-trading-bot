# VWAP Mean Reversion Flow

1. Read the latest M15 candles.
1. Determine the active session from the latest timestamp.
1. Filter the candles to that session.
1. Compute session VWAP and ATR.
1. Compare the latest bar to the rolling local high/low.
1. Detect a sweep and reclaim sequence.
1. Build the signal with VWAP-aware profit logic.
1. Fall back to the trailing window if the session slice is too thin.

