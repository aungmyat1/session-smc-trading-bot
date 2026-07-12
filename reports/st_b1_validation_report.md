# ST-B1 Validation Report

Generated: 2026-07-12T00:00:00+00:00

## Verdict: BLOCKED

Historical validation and walk-forward validation could not run because real
EURUSD/GBPUSD H1+M15 data was unavailable in the validation environment.
Dukascopy returned `403 Forbidden`, and no reachable local real-data dataset
was available for the required run.

- No trades were produced.
- No Profit Factor, Sharpe, Max Drawdown, expectancy or walk-forward verdict
  exists.
- Synthetic/unit-test mechanics are not validation evidence.
- ST-B1 remains research-only and must not be deployed, frozen or used as
  approval evidence.

See `docs/audit/ST_B1_VALIDATION_REPORT.md` and
`docs/audit/ST_B1_MISSION_SUMMARY.md` for the detailed blocker evidence.
