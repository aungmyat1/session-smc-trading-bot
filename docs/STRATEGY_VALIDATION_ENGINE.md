# Strategy Validation Engine

`strategy_validation/` implements Stage 1 of SVOS: specification quality validation before historical replay.

## Scope

The engine checks whether a strategy specification is:

- complete
- objective
- measurable
- internally consistent
- institutionally defined
- risk-aware
- testable

It does not evaluate profitability.

## Entry Points

- Python API: `strategy_validation.StrategyValidationPipeline`
- CLI: `python -m strategy_validation.cli --spec path/to/strategy_spec.md`

## Outputs

Each run generates:

- `validation_report.json`
- `validation_report.md`
- `validation_report.html`
- `audit_log.json`

## Validator Contract

Each validator returns:

- `validator_name`
- `score`
- `status`
- `findings`
- `recommendations`

## Readiness Decisions

- `READY_FOR_REPLAY`
- `REQUIRES_REVISION`
- `INCOMPLETE`
- `REJECTED`
