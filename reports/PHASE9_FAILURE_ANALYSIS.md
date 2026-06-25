# PHASE 9 — Failure Analysis
Symbol: EURUSD | Period: 2025

## Identified Causes

1. **PF_2x=0.948 ≤ 1.0:** Fails 2× stress test. Edge may be marginal — spread-sensitive.

## Session Diagnosis

| Session | n | WR | PF_std | MaxDD |
|---|---|---|---|---|
| London | 12 | 33.3% | 1.200 | 4.76R |
| New York | 4 | 25.0% | 0.726 | 3.23R |

## What NOT to Do

- Do NOT modify strategy parameters based on this 1yr sample
- Do NOT re-run with different date window to find better results
- Any parameter change = new trial row in VERDICT_LOG.md