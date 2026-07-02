# Production/SVOS Rollout Index

Date: 2026-07-02
Status: central navigation for implementation, completion, and remaining rollout work

## Documents

### 1. Implementation plan

- [Production/SVOS implementation plan](production_svos_implementation_plan.md)

Use this as the intended target-state and phased implementation reference.

### 2. Completion report

- [Production/SVOS implementation completion report](production_svos_implementation_completion_report.md)

Use this to see what has already been completed inside the repository and what
was validated.

### 3. Remaining real-world rollout tasks

- [Remaining real-world rollout tasks](remaining_real_world_rollout_tasks.md)

Use this to track what still has to happen outside the current repo-only safe
implementation boundary.

## Quick status

The July 1 read-only audit (`CURRENT_ARCHITECTURE.md` and
`docs/project_readiness_assessment.md`) is the migration baseline. Statements in
that snapshot that packaging or production import did not exist are historical;
the completion report below records the subsequently implemented July 2 delta.

### Repo-side implementation

Current status:

- substantially complete for `live-ready, disabled`

Included:

- strategy packaging
- deployment records
- production import
- preflight verification
- report generation
- report discovery
- disabled runtime staging
- consolidated operator status

### Real-world rollout

Current status:

- not complete

Remaining categories:

- production GCS bucket/KMS resource provisioning and IAM
- remote host rollout
- secrets and network hardening
- runtime execution from imported artifacts
- rollout rehearsals and rollback drills
- activation governance

## Recommended reading order

1. implementation plan
2. completion report
3. remaining rollout tasks

## Practical use

If you need to answer:

- “What was the intended design?”
  - read the implementation plan

- “What is already done in code?”
  - read the completion report

- “What still remains before real deployment?”
  - read the remaining rollout tasks
