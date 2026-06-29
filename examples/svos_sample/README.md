# SVOS Six-Stage Sample

This bundle tests the SVOS lifecycle and report system with deterministic
fixture evidence. It does not represent a profitability claim or authorization
to trade.

Run:

```bash
python3 scripts/run_svos_sample.py
```

The command uses an isolated temporary strategy catalog and cannot modify the
active project strategy. Canonical reports are written under
`reports/svos/SVOS-SAMPLE/` and checked for matching JSON/Markdown decisions
across all six public stages.
