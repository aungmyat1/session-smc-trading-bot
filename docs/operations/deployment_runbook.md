# Disabled Strategy Deployment Runbook

Date: 2026-07-02  
Status: Active  
Owner: Platform Operations

## Safety invariant

All rollout environments must set `LIVE_TRADING=false` and `DEMO_ONLY=true`.
The implemented activation service rejects live requests even if invoked directly.

## GitHub prerequisites

Create protected environments named `strategy-release`, `paper`, and
`production-disabled`. Require reviewer approval for the latter two. Configure
repository/environment variables for the workload identity provider, service
accounts, GCS bucket, KMS key version, production VM and zone. Use GitHub OIDC;
do not store service-account JSON keys.

## Host installation

1. Create a non-login `agtrade` service account.
2. Install the repository under `/opt/session-smc-trading-bot` and its locked
   virtual environment.
3. Create `/etc/session-smc-trading-bot/production.env` with non-secret policy
   values and Secret Manager references.
4. Install `agtrade-deployment-agent.service` and its timer from
   `deploy/gcp-vm1/systemd/`.
5. Enable the timer and confirm its sandbox with `systemd-analyze security`.

## Release procedure

1. Confirm registry stage `PRODUCTION_APPROVAL`, immutable validation evidence,
   approved version, broker/symbol support and rollback target.
2. Run the `Strategy Release` workflow with exact strategy and version.
3. Confirm the GitHub Release contains the archive, checksum, manifest,
   signature, deployment metadata, and notes.
4. Confirm the package also exists in the immutable GCS location.

## Deployment procedure

1. Run `Deploy Production Disabled` with the deployment ID and protected target.
2. The remote command performs import, checksum/signature preflight and disabled
   staging as one idempotent operation.
3. Verify:

```bash
agtrade production status --deployment-id DEPLOYMENT_ID
agtrade production health --heartbeat
curl --fail http://127.0.0.1:8080/api/v1/production/health
curl --fail http://127.0.0.1:8080/metrics
```

Expected deployment status is `STAGED_DISABLED`; `activated` and
`live_trading_enabled` must both be false.

## Rollback drill

Create a rollback record through
`POST /api/v1/deployments/{deployment_id}/rollback` with a prior approved version
and mandatory reason. The replacement follows the same import/preflight/disabled
staging flow. Never overwrite or mutate the failed package.

## Failure handling

- Checksum or signature failure: quarantine the deployment and do not retry with
  modified bytes under the same package ID.
- GCS/KMS outage: retain the last staged-disabled version and alert an operator.
- Health failure: stop the deployment timer, retain evidence, and restore the
  previous disabled package.
- Policy violation (`LIVE_TRADING=true` or `DEMO_ONLY=false`): treat as a critical
  incident; health becomes failed and activation remains blocked.
