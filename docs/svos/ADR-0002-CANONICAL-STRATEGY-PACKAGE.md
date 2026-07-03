# ADR-0002: Canonical Strategy Package and Handoff

Date: 2026-07-03
Status: Authoritative — Accepted
Version: 1.0
Updated: 2026-07-03
Owner: Lead Architect
Authority: Level 5 — Decision
Related: `ADR-0001-STABILIZATION-FOUNDATION.md`, `../00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`, `../../ARCHITECTURE_STABILIZATION_ROADMAP.md`

## Context

Three incompatible package representations existed:

1. `svos/application/pipeline.py` emitted an approval-summary JSON document.
2. `approval_package/` emitted a signed evidence directory used by the portfolio runner.
3. `svos/deployment/service.py` emitted a `strategy-package/v1` archive verified by Production.

No contract proved that the package approved by the Strategy Engineering Platform was exactly the package imported and consumed by the Simple Vantage Trading Bot.

## Decision

### Canonical format

The only new cross-system package format is `strategy-package/v2`, represented as a deterministic gzip-compressed tar archive. It contains exactly:

- `manifest.json`
- `strategy_spec.md`
- `parameters.json`
- `risk_policy.json`
- `evidence_manifest.json`
- `approval.json`
- `provenance.json`
- `signature.json`

Unexpected, duplicate, missing, non-file, absolute, or path-traversing archive members are rejected.

### Identity and immutability

`manifest.json` binds:

- package format and package ID;
- strategy identity and version;
- executable adapter identity and version;
- immutable package symbol list;
- `live_trading_enabled=false`;
- SHA-256 hashes of every semantic member.

`package_id` is a deterministic SHA-256 digest of the identities and semantic member hashes. The deployed artifact is identified by the SHA-256 digest of the complete archive. That archive digest is carried unchanged through deployment state, content-addressed storage, import state, and preflight verification.

### Signature and key ownership

Canonical packages use Ed25519:

- System 1 receives `SVOS_PACKAGE_SIGNING_PRIVATE_KEY`, a 32-byte private key encoded as hexadecimal.
- System 2 receives only `SVOS_PACKAGE_VERIFYING_PUBLIC_KEY`, a 32-byte public key encoded as hexadecimal.
- The signature covers a canonical digest map for every member except `signature.json`.
- Neither an unsigned SHA attestation nor an environment boolean is a valid canonical signature.

The private key must be provided by a secrets manager in non-test environments and must never be stored in the package, repository, deployment record, or Production environment. Rotation requires a separately versioned trust-policy change; silently accepting multiple keys is forbidden.

This asymmetric split allows System 1 to build packages and System 2 to verify them. System 2 cannot alter or mint a valid package with its public key.

### Required governed content

A package cannot be built unless it contains:

- non-empty immutable parameters;
- a non-empty risk policy;
- a non-empty evidence manifest;
- an `APPROVED` decision;
- timezone-aware approval and expiry timestamps, with expiry after approval;
- explicit `revoked=false`;
- strategy and adapter identities and versions;
- a private signing key.

Production rejects a package when any signature, content, identity, expiry, revocation, required-field, member, or archive check fails. Rejection occurs before runtime or broker connection.

Revocation is checked both inside the signed approval record and against System 2's external `data/production/revoked_packages.json` deny list. The external deny list may revoke a package but may never approve one.

### System ownership

System 1 owns:

- lifecycle evidence;
- approval authority;
- package construction;
- the private signing key;
- immutable package publication.

System 1 may not import Production or broker-write modules while building a package.

System 2 owns:

- transport and content-addressed import;
- archive-hash comparison;
- signature, identity, expiry, revocation, and policy verification;
- read-only consumption after preflight.

System 2 may not modify evidence, approve a strategy, rebuild a package, or receive the private signing key.

### Compatibility and migration

Legacy formats are not canonical:

- Legacy signed approval directories remain readable by the compatibility validator so existing offline fixtures and rollback paths continue to work.
- `strategy-package/v1` deployment archives are rejected by canonical Production preflight.
- `scripts/migrate_strategy_package.py` converts a valid legacy approval directory only when the operator supplies adapter identity/version, immutable parameters, risk policy, the legacy verification key, and the canonical private signing key.
- Migration preserves hashes of all legacy source files in `provenance.json`.
- Migration does not create an approval. A rejected, expired, tampered, or unsigned legacy package cannot be migrated.
- Legacy writers remain deprecated until adoption evidence permits a separate retirement PR.

## Rejected alternatives

### Sign only `manifest.json`

Rejected because parameters, evidence, risk policy, or approval content could change without invalidating the signature unless every member hash were independently and correctly bound.

### Continue HMAC signing

Rejected for the canonical boundary because a Production verifier holding the shared HMAC secret could also mint packages, violating the rule that Production cannot approve or alter strategy artifacts.

### Treat SHA-256 attestation as a signature

Rejected because an attacker who can alter an archive can recompute an unkeyed checksum.

### Let Production convert legacy packages automatically

Rejected because conversion is a System 1 packaging responsibility and missing legacy fields require explicit governed input.

## Acceptance consequences

- Package production without complete approval, risk, evidence, parameters, expiry, and private-key material fails closed.
- Production preflight requires `strategy-package/v2` and a valid public-key signature.
- Existing v1 deployment artifacts require explicit migration or rollback to the legacy read-only path; they are not silently trusted.
- No broker, strategy, risk-execution, or live-authorization behavior changes under this ADR.
- Retirement of legacy readers is a later PR and requires adoption evidence.

## Rollback

Revert canonical consumers to the legacy read-only compatibility reader while retaining all v2 packages, hashes, deployment/import states, and audit evidence. Do not downgrade signature, expiry, identity, approval, or revocation checks. Disable new package publication if private-key or format integrity is uncertain.
