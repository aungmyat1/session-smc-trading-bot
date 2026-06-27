# VWAP Mean Reversion

## Overview

VWAP Mean Reversion is the session-scoped VWAP fade strategy in `strategies/adapters/vwap_adapter.py`.

## Audit Status

- Catalog status: `shadow`
- Approval: `false`
- Version: `0.1`
- Deployment target: `shadow`
- Portfolio mode: `shadow`

## Runtime Behavior

- The strategy evaluates London and New York session windows only.
- It looks for an exhaustion sweep away from session VWAP.
- It waits for a reclaim back toward fair value before building a signal.
- If the session slice is thin, the adapter falls back to a trailing window.

