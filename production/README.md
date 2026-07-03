# System 2 — Production Execution

`production/` is the sole downstream execution boundary. Its canonical flow is:

```text
signed package -> runtime authority -> market data -> installed strategy adapter
-> signal validation -> risk firewall -> position service -> order service
-> disabled Vantage adapter -> operational event journal
```

Only adapters installed in `AdapterRegistry` with an exact ID, version, runtime
API, and code hash may run. Package archives contain configuration and evidence,
not executable code.

This build supports replay, offline Virtual Demo, and disabled demo modes. It
has no live execution mode. `DisabledVantageAdapter` deterministically rejects
place, cancel, and modify operations; `LIVE_TRADING=false` and `DEMO_ONLY=true`
remain required.

PostgreSQL `operations` tables are authoritative for runtime mutations. The
JSONL emergency audit sink is diagnostic only and is never read as state.
