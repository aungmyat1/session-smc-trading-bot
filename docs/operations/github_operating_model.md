# GitHub Operating Model

Date: 2026-07-02  
Status: Active  
Owner: Platform Operations

## Applied repository controls

The remote repository now has a `develop` branch, protected `main`, one required
review, CODEOWNER review, stale-review dismissal, last-push approval,
conversation resolution, linear history, admin enforcement, force-push/delete
blocking, and required `Required CI` status.

Use:

- `main` for released, deployable repository state
- `develop` for integration
- `feature/*` for planned changes
- `hotfix/*` for urgent production corrections
- `release/*` for release stabilization

Direct pushes to `main` are prohibited. Strategy releases and deployments use
protected GitHub environments with human review.

## Issue taxonomy and milestones

Applied labels cover Infrastructure, Production, SVOS, Documentation,
Monitoring, Security, Technical Debt, dependencies, and P0/P1/P2 priority.
Applied milestones are Operational Foundation, Paper Trading Readiness, and
Production Hardening. There were no existing issues to recategorize at audit time.

## Project board design

Create an organization/user Project named `Trading Platform Operations` with a
single-select `Stage` field:

1. Backlog
2. Architecture
3. Infrastructure
4. Development
5. Validation
6. Testing
7. Deployment
8. Production
9. Completed

Add fields for Area, Priority, Strategy Version, Deployment ID, Target Engine,
Milestone, and Readiness Evidence. Automate newly added issues to Backlog,
merged pull requests to Completed, and deployment-labelled work to Deployment.

The board was not created automatically because the authenticated GitHub token
lacks the `read:project`/`project` scopes. Repository controls, labels,
milestones, and branches were applied successfully; board creation requires an
operator to grant those scopes first.
