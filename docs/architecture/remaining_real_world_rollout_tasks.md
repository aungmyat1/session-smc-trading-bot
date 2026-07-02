# Remaining Real-World Rollout Tasks

Date: 2026-07-02
Status: external rollout checklist after repo-side live-ready-disabled implementation

## Execution update — 2026-07-02

The repository-executable portion of P1 items 6 and 7 is complete:

- real GCS upload/fetch uses Application Default Credentials, immutable object
  creation (`ifGenerationMatch=0`), SHA-256 object metadata, atomic downloads,
  and checksum rejection;
- real Cloud KMS asymmetric SHA-256 signing records the exact crypto key
  version and preflight verifies the signature with that version's public key;
- `SVOS_CLOUD_ADAPTER=mirror` remains the credential-free rehearsal mode and
  `SVOS_CLOUD_ADAPTER=real` selects cloud APIs;
- preflight now verifies supported signatures rather than merely checking that
  a signature field exists;
- rollout environment examples pin `LIVE_TRADING=false` and `DEMO_ONLY=true`.

Items requiring named hosts, cloud project/bucket/key identifiers, IAM grants,
network policy, installed remote services, database placement, or a remote
rehearsal remain external and cannot be truthfully completed from this repo.

## Purpose

This checklist covers the work that still remains after the repository-side
implementation was completed for the safe `live-ready, disabled` scope.

These tasks are the gap between:

- repo-complete disabled deployment workflow

and

- real infrastructure rollout with remote hosts, cloud services, and eventual
  operator-controlled production readiness

## P0 — Must do before host rollout

These are blockers for any serious remote deployment or cutover attempt.

### 1. Finalize target host ownership

- Confirm the final Production host
- Confirm the final SVOS/research host
- Confirm which host owns:
  - strategy validation
  - artifact publishing
  - deployment registry metadata
  - production runtime
  - dashboards
  - monitoring

### 2. Define production and SVOS environment contracts

- Finalize required env vars per host
- Separate:
  - production-only secrets
  - research-only secrets
  - shared read-only config
- Freeze:
  - `LIVE_TRADING=false`
  - `DEMO_ONLY=true`
  for all rollout stages before explicit future authorization

### 3. Secrets management

- Broker credentials location and access rules
- Database credentials location and access rules
- Operator token management
- Cloud credential source
- KMS key reference source
- Secret rotation and recovery process

### 4. Network and security baseline

- Lock down SSH access model
- Confirm Tailscale/private access model
- Restrict public ports
- Restrict database exposure to private interfaces only
- Define firewall rules for:
  - dashboard/API
  - database
  - artifact transport
  - monitoring

### 5. Real cloud resource decisions

- Create or confirm production GCS bucket
- Create or confirm naming convention/prefix layout
- Create or confirm Cloud KMS keyring/key/version
- Define IAM roles for:
  - artifact publisher
  - artifact consumer
  - operator read access

## P1 — Must do before runtime staging on real VM

These tasks are needed before the current repo-side workflow can be exercised on
actual infrastructure.

### 6. Real GCS adapter — completed in repository

- [x] Implement real upload to GCS
- [x] Implement real fetch from GCS
- [x] Handle bucket/object errors cleanly
- [x] Verify checksum behavior with credential-free adapter tests
- [x] Enforce immutable object creation
- [ ] Rehearse against the provisioned production bucket and retain evidence

### 7. Real Cloud KMS signing adapter — completed in repository

- [x] Implement real asymmetric SHA-256 signing using Cloud KMS
- [x] Implement public-key signature verification
- [x] Record the exact key version used for signing
- [x] Reject verification failures and key-version mismatches in preflight
- [ ] Rehearse signing, verification, outage, and rotation behavior against the
  provisioned production key

### 8. Provision remote runtime dependencies

- Python/runtime install on target hosts
- Service accounts and filesystem layout
- Writable directories for:
  - deployment metadata
  - imported artifacts
  - preflight reports
  - logs

### 9. Service/process deployment

- Create systemd units or equivalent for:
  - production API/dashboard
  - production runtime status service
  - SVOS publishing workflow
  - monitoring agents
- Add restart policy
- Add journal/log handling
- Add startup ordering for dependencies

### 10. Database topology implementation

- Finalize actual database split between research and production concerns
- Apply schema placement decisions
- Move deployment/runtime metadata if required
- Validate backup and restore on target infra

### 11. Remote preflight rehearsal

- Create a real deployment package
- Publish it through the real artifact path
- Import it on the production VM
- Run preflight there
- Confirm report generation and retrieval on the actual host

## P2 — Must do before any live consideration

These are mandatory before any future discussion of activation beyond disabled
runtime staging.

### 12. Runtime execution of imported artifacts

- Define how production runtime loads imported package contents
- Define strategy/runtime binding rules
- Confirm no manual code copying is needed
- Verify rollback to prior package version

### 13. Observability and incident handling

- Health checks on deployed services
- Centralized logs or durable log retention
- Alerting for:
  - import failures
  - preflight failures
  - activation-blocked states
  - runtime drift
- Incident acknowledgment and audit flow

### 14. Rollback drills

- Failed import rollback
- Failed preflight rollback
- Broken deployment metadata rollback
- Prior package re-stage verification

### 15. Formal activation governance

- Human approval workflow for activation
- Explicit roles allowed to request activation
- Required evidence before activation
- Required health checks before activation
- Required rollback readiness before activation

### 16. Live policy implementation

Not yet authorized in current scope, but eventually required if live trading is
ever intentionally pursued:

- controlled live enable switch
- final production approval gate
- post-activation verification
- immediate halt/rollback workflow

## Suggested execution order

Recommended order:

1. P0 host ownership + secrets + network decisions
2. Provision GCS/KMS resources and rehearse the completed adapters
3. P1 remote service and filesystem deployment
4. P1 remote import/preflight rehearsal
5. P2 runtime execution from imported artifact
6. P2 observability + rollback drills
7. P2 activation governance
8. only then discuss any live enablement work

## Practical summary

Repo-side status is strong:

- build package
- register deployment
- import
- preflight
- report
- disabled activation staging
- consolidated operator status

Remaining gap is now mainly:

- cloud resource provisioning, IAM, and authenticated integration rehearsal
- infrastructure deployment
- security/secrets/networking
- real host execution
- governance for anything beyond disabled staging
