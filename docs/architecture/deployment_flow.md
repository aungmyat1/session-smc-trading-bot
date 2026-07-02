# Deployment Flow

Date: 2026-07-01
Status: target deployment workflow

## Target Flow

```text
Research
  ↓
SVOS Validation
  ↓
Artifact Creation
  ↓
Registry
  ↓
Deployment Approval
  ↓
Production Import
  ↓
Health Check
  ↓
Execution
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
- activate strategy runtime
- emit deployment and health status

## Recommended First Implementation

1. define artifact schema
2. create registry directory layout and metadata
3. add deployment import service in application layer
4. keep existing runtime scripts as wrappers until production engine package is stable
