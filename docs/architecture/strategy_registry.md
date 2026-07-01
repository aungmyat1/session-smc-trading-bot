# Strategy Registry Design

Date: 2026-07-01
Status: target architecture design

## Objective

The strategy registry becomes the system of record for approved strategy artifacts and their deployment lifecycle.

It should replace manual code-copy or implicit filesystem promotion workflows.

## Proposed Layout

```text
registry/
  strategies/
    ST-A2/
      v1.0/
      v1.1/
      v1.2/
```

Each version directory should store:

- artifact package
- validation reports
- deployment history
- rollback metadata
- release notes

## Strategy Package Format

```text
strategy_package/
  manifest.yaml
  strategy.py
  parameters.yaml
  validation.json
  metadata.json
  checksum.sha256
```

## Required Manifest Fields

- `strategy_id`
- `version`
- `git_commit`
- `symbols`
- `timeframes`
- `entry_logic`
- `exit_logic`
- `risk_profile`
- `PF`
- `Sharpe`
- `max_drawdown`
- `validation_status`
- `approval_status`
- `created_date`
- `SVOS_version`

## Current State Gap

Current registry-related behavior is split across:

- `svos/registry/service.py`
- `svos/governance/service.py`
- `svos/orchestration/service.py`
- `config/strategy_catalog.yaml`
- report and evidence directories

The current catalog is still a projection and compatibility mechanism, not yet a full artifact registry.

## Migration Recommendation

1. keep `config/strategy_catalog.yaml` as compatibility projection
2. define artifact manifest schema in shared contracts
3. add registry write/read service behind application layer
4. record deployment history separately from research qualification
5. make production consume artifacts, not strategy source directories
