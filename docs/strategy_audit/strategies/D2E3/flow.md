# D2E3 Flow

1. Load the latest ordered M15 bars.
1. Build context with PDH, PDL, and rolling pivot highs/lows.
1. Detect a sweep setup.
1. Wait for MSS confirmation.
1. Wait for a limit fill.
1. Manage the open trade until stop, target, or time exit.
1. Emit the corresponding event type into the journal.

