# Current Operational Status

Date: 2026-07-02  
Status: Current  
Owner: Platform Operations  
Scope: Fresh repository and GitHub audit performed before Phase 2 changes

Architecture truth: SVOS is the Strategy Research and Validating System;
Production is the simple six-component execution machine. Operational services
described here surround that machine and do not broaden its responsibility.

## Executive status

The repository has sound SVOS/Production package boundaries and a working
live-disabled artifact handoff. It is not a live-ready production platform.
No catalog strategy is currently approved, remote infrastructure has not been
rehearsed, and the production runtime is still a facade over legacy execution
modules.

## Verified inventory

| Area | Status | Evidence / gap |
|---|---|---|
| Shared libraries | Implemented | `shared/` contains models, strategy API, configuration, and serialization with architecture gates. |
| SVOS registry | Implemented, extended | Append-only versions, evidence, transitions, deployments, release metadata, and rollback history. Catalog YAML remains the bootstrap projection. |
| Strategy packages | Implemented | Deterministic archive, SHA-256, signature envelope, validation history, immutable GCS support. |
| Production import | Implemented | Checksum-aware local/GCS import and staging. |
| Production preflight | Implemented | Required-file, manifest, policy, checksum, and signature checks. |
| Activation | Safe-disabled | Only `STAGED_DISABLED` is possible; live requests remain blocked. |
| Deployment automation | Implemented for disabled staging | CLI agent, systemd timer, and protected GitHub workflow. Real host rehearsal remains outstanding. |
| GitHub CI | Previously duplicated | Four overlapping workflows were consolidated into required quality, test, security, docs, and package gates. |
| GitHub release | Newly implemented | Approved strategy workflow publishes archive, checksum, signature, manifest, deployment metadata, and notes. No strategy currently qualifies. |
| Cloud | Code complete, infrastructure incomplete | Real GCS, KMS, Secret Manager and Compute SSH paths exist. Project resources, IAM and workload identity require provisioning. |
| Docker | Partial | PostgreSQL exists; it is now loopback-bound by default. Adminer is opt-in and loopback-only. There is no immutable application image yet. |
| Systemd | Partial | Legacy runners exist. A hardened disabled-deployment poller was added. Named service account and target-host installation remain operator tasks. |
| Monitoring | Partial | Existing dashboard/health checks plus production heartbeat, policy health and Prometheus metrics. Broker latency and order-path telemetry remain incomplete. |
| Dashboard | Partial | Registry/deployment/status APIs are available. Existing UI still mixes operational and SVOS concerns. |
| Tests | Strong focused coverage, weak full baseline | Focused operational tests pass. Legacy full-suite collection/lint debt remains and must not be hidden by CI. |
| Secrets | Improved, not provisioned | No tracked `.env`; OIDC and Secret Manager adapter paths exist. Secret resources and rotation drills remain external. |

## Risks and technical debt

1. The production runtime does not yet load and execute strategy code directly
   from an imported package.
2. Broker/risk/position behavior remains split across legacy runners.
3. The single repository and dashboard still contain mixed deployment concerns,
   despite import-level boundary enforcement.
4. Cloud IAM, protected environments, remote services, backups, and rollback
   drills have not been proven on real hosts.
5. Current strategy catalog entries are all unapproved; this correctly blocks a
   real strategy release.
6. Repository-wide Ruff currently exposes substantial legacy debt, so the CI
   quality gate intentionally covers the stabilized architecture boundary.

## Recommended execution order

1. Merge Phase 2 through a protected pull request and make `Required CI` mandatory.
2. Provision GitHub environments, workload identity, GCS, KMS and Secret Manager.
3. Install the deployment poller on the production VM and run a fake-strategy
   disabled rehearsal.
4. Bind imported artifact strategy/runtime configuration without copying research code.
5. Add broker latency, connection state, trade-close feedback and alert tests.
6. Perform backup, restore, rollback, restart, and network-failure drills.
7. Begin controlled paper trading only after every readiness blocker is closed.
