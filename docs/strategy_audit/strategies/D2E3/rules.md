# D2E3 Rules

## Entry Rules

- Only process bars inside the configured session window.
- Require a PDH or PDL sweep.
- Require MSS confirmation within `confirm_bars`.
- Require limit-entry fill within `entry_wait_bars`.
- Reject the setup if the stop size is outside the allowed range.

## Exit Rules

- Exit on stop loss.
- Exit on take profit.
- Exit on time stop after `max_hold_bars`.

## State Rules

- Pending setups expire if confirmation or fill windows are missed.
- A cooldown is enforced after a completed trade.

