# Deployment Flow

Date: 2026-07-01
Status: target deployment workflow

## Target Flow

```text
Strategy Idea
  ↓
Strategy Audit
  ↓
Historical Replay
  ↓
Backtest
  ↓
Statistical Validation
  ↓
Robustness Testing
  ↓
Virtual Demo Trading
  ↓
Production Approval
  ↓
Approved Strategy Package
  ↓
Strategy Package Loader
  ↓
Trading Engine → Risk Manager → Execution Manager → Broker API → Position Management
```

## Required Rules

- no manual copying of strategy code into production
- production imports only approved versioned artifacts
- deployment approvals are audited
- preflight health checks run before activation
- rollback uses prior registry version metadata

## Current-State Observation

Current deployment behavior is mixed:

- strategy code is present directly in the main repository
- production and SVOS coexist in one tree
- deployment scripts and dashboards assume local co-location
- current strategy state still relies heavily on config projection and report artifacts

## Proposed Workflow Components

### SVOS side

- validate strategy
- create artifact
- register version
- mark approval decision
- publish deployment package

### Production side

- fetch or import artifact
- validate checksum and manifest
- verify environment compatibility
- load the approved strategy package
- run only the simple execution chain

## Recommended First Implementation

1. define artifact schema
2. create registry directory layout and metadata
3. add deployment import service in application layer
4. keep existing runtime scripts as wrappers until production engine package is stable
