# Strategy Release Environment Hardening Plan

Date: 2026-07-05
Status: Phase 1 — Audit and code-level guard only (no GitHub settings changed)
Owner: Platform Operations

## Scope

Phase 1 hardens the `strategy-release` GitHub environment and its workflow
before any real release is run. This phase only:

- documents current state
- recommends GitHub-side protections (not applied yet)
- adds a fail-fast misconfiguration guard to `.github/workflows/strategy-release.yml`

It does not touch GitHub environment settings, does not add variables or
secrets, and does not trigger the release workflow. See
[deployment_runbook.md](deployment_runbook.md) for the full release/deploy
procedure this environment supports.

## Current state (as audited 2026-07-05)

- The `strategy-release` GitHub environment exists (created 2026-07-05).
- It has **no protection rules**: no required reviewers, no deployment branch
  policy, no wait timer (`gh api repos/.../environments` confirms
  `protection_rules: []`, `deployment_branch_policy: null`).
- **No environment/repository variables are confirmed set.** The workflow
  reads four `vars.*` values (`GCP_WORKLOAD_IDENTITY_PROVIDER`,
  `GCP_RELEASE_SERVICE_ACCOUNT`, `SVOS_KMS_KEY_VERSION`, `SVOS_GCS_BUCKET`);
  none have been verified present.
- **No secrets are required.** Auth is GitHub OIDC → Workload Identity
  Federation; `GH_TOKEN` uses the built-in `github.token`. This matches the
  runbook's explicit "do not store service-account JSON keys" instruction.
- Prior to this plan, a missing/misconfigured `vars.*` value would not fail
  fast: `GCP_WORKLOAD_IDENTITY_PROVIDER` gates the auth step via
  `if: vars.GCP_WORKLOAD_IDENTITY_PROVIDER != ''`, so an unset value silently
  skips cloud auth and the job would only fail later, deeper into the build
  step, with a less direct error.

## Recommended GitHub environment protection (not applied — requires owner action)

The runbook (`deployment_runbook.md`, "GitHub prerequisites") only mandates
required-reviewer approval for `paper` and `production-disabled`. Given that
`strategy-release` runs with `contents: write` + `id-token: write` and
produces a signed, published, immutable release, this plan recommends
extending equivalent protection to it:

1. **Required reviewer approval** — at least one designated release approver
   must approve each run before the job executes. This is the primary control
   against an unreviewed or accidental release.
2. **Trusted branch/tag restriction** (`deployment_branch_policy`) — restrict
   which refs may deploy to this environment (e.g. `main` only, or a
   `release/*` tag pattern) so the workflow cannot be run from an arbitrary
   branch or fork.
3. **No wait timer** — not needed unless a cooling-off period before signing
   is separately desired; omit unless a concrete reason emerges.

These are GitHub environment settings changes and are **owner-approved
actions only** — out of scope for this phase.

## Workflow misconfiguration guard (implemented this phase)

Added a `Validate release environment configuration` step as the first step
in `.github/workflows/strategy-release.yml`. It checks that all four required
`vars.*` values are non-empty and fails the job immediately with a
`::error::` annotation listing exactly which are missing, before any
checkout, dependency install, or cloud auth is attempted:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_RELEASE_SERVICE_ACCOUNT`
- `SVOS_KMS_KEY_VERSION`
- `SVOS_GCS_BUCKET`

This closes the silent-skip gap above: a missing var now stops the run at
step 1 with a named list of what's absent, instead of failing later inside
`google-github-actions/auth@v2` or the build step with a less direct error.
The guard reads only `vars.*` (repo/environment configuration set by
maintainers), not workflow-dispatch `inputs.*`, so no injection risk applies
to this step.

The guard does not set, validate the *value* of, or otherwise interact with
these variables beyond checking they are non-empty strings — it does not
verify the workload identity provider is reachable, the service account
exists, the KMS key version is valid, or the GCS bucket is accessible. Those
remain live-auth-time failures.

## Next required owner approvals (before first real release)

1. Approve and apply the three GitHub environment protection rules above to
   `strategy-release` (required reviewer, branch/tag restriction, confirm no
   wait timer).
2. Provision and set the four environment variables this plan's guard
   checks for (`GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_RELEASE_SERVICE_ACCOUNT`,
   `SVOS_KMS_KEY_VERSION`, `SVOS_GCS_BUCKET`), per the GCP/IAM/KMS/GCS
   prerequisites already identified in the prior audit (WIF pool/provider,
   release service account with `roles/cloudkms.signerVerifier` scoped to the
   specific CryptoKeyVersion, GCS write access on the target bucket).
3. Confirm the KMS CryptoKeyVersion's signing algorithm is compatible with
   `KMSAsymmetricAdapter`'s verification path before first use.
4. Run the safe dry-run verification sequence from the prior audit
   (`gh api .../environments/strategy-release`, a real `workflow run` against
   a known-good test strategy/version, then confirm the resulting GitHub
   Release and GCS object) before trusting a production strategy release.
5. Only after 1–4 are complete: authorize the first real `Strategy Release`
   workflow run.

No GitHub settings, variables, or secrets were changed by this phase, and the
release workflow was not run.
