# API Contracts

Date: 2026-07-01
Status: versioned contract implemented; authentication hardening remains

## Goal

Define explicit versioned interfaces between SVOS and Production.

## Implemented Endpoints

```text
GET  /api/v1/strategies/{strategy}/latest
GET  /api/v1/strategies/{strategy}/versions/{version}
GET  /api/v1/validations/{strategy}/{version}
POST /api/v1/deployments
POST /api/v1/deployments/{deployment_id}/reports
GET  /api/v1/deployments/{deployment_id}
```

## Contract Requirements

- versioned paths
- schema-validated request/response bodies
- authentication
- audit logging
- stable artifact identifiers

## Current API State

Current API surfaces are mixed:

- Flask control panel in `dashboard/app.py`
- Flask live dashboard in `dashboard/live_app.py`
- FastAPI status surface in `dashboard/status_server.py`
- internal SVOS operational facade in `svos/api/service.py`

Current issues:

- local-file-backed state rather than service contracts
- mixed production and SVOS concerns
- incomplete auth model for production-grade use
- no stable external contract between research and production boundaries

## Recommended API Ownership

### Production API

Should expose:

- live positions
- orders
- broker state
- runtime health
- deployment status
- risk state

### SVOS API

Should expose:

- strategy registry
- validation status
- evidence and reports
- approval decisions
- deployable artifact metadata

## Migration Note

Do not front-load a full distributed-service rewrite.

First define schemas and response models.

Then move current dashboard and deployment surfaces toward those contracts incrementally.
