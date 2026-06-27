# Adaptive SMC Rules

## Entry Rules

- Reuse the underlying ST-A2 session-liquidity chain.
- Require the same bias, sweep, displacement, and minimum stop filters as ST-A2.
- Emit nothing if the underlying engine emits nothing.

## Governance Note

- This branch is monitored in `shadow` mode.
- It is a wrapper and translation layer, not a separate alpha source.

