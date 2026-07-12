# ADR-0002 Implementation Report

- Date: 2026-07-03
- Status: Implemented; validation recorded below
- ADR: `docs/svos/ADR-0002-CANONICAL-STRATEGY-PACKAGE.md`
- Scope: Canonical package format and handoff only
- Safety: No trading logic, broker adapter, risk-execution logic, or live-trading authorization was changed

## Outcome

`strategy-package/v2` is now the canonical System 1 to System 2 handoff. System 1 builds deterministic Ed25519-signed archives. System 2 imports the identical archive by SHA-256 and verifies it using only the public key before disabled staging or runtime startup.

The former approval-directory reader remains available as an explicit compatibility path. Legacy deployment archive v1 is no longer accepted by canonical Production preflight and must be migrated explicitly.

## Changed files

### Contract and schema

- `shared/strategy_package.py` — deterministic builder and fail-closed verifier.
- `schemas/strategy-package-v2.schema.json` — canonical manifest schema.

### System 1 producer

- `svos/deployment/service.py` — emits canonical v2 packages and records the archive hash.

### System 2 consumers

- `production/verifier.py` — verifies format, complete-member signature, approval, expiry, revocation, identity, and archive hash.
- `approval_package/package_validator.py` — dispatches archive inputs to the canonical verifier while retaining the legacy directory reader.
- `scripts/run_portfolio.py` — uses the public verification key for canonical archives before runtime startup.
- `scripts/validate_strategy_identity.py` — reads canonical strategy identity from the signed manifest.
- `scripts/validate_strategy_package.py` — validates v2 archives.

### Migration

- `scripts/migrate_strategy_package.py` — explicit validated legacy-directory migration with provenance hashes.

### Documentation

- `docs/svos/ADR-0002-CANONICAL-STRATEGY-PACKAGE.md` — accepted decision.
- `ADR_0002_IMPLEMENTATION_REPORT.md` — this report.

### Tests

- `tests/shared/test_strategy_package.py` — determinism, tamper matrix, expiry, revocation, identity, adapter, and key tests.
- `tests/integration/test_canonical_package_handoff.py` — migration and startup-before-runtime tests.
- `tests/production/conftest.py`, `tests/svos/conftest.py` — isolated Ed25519 test key material.
- Existing SVOS deployment, Production import/preflight/activation, CLI, and validator tests were updated to use the governed v2 contract.

## Acceptance criteria results

| Criterion | Result | Evidence |
|---|---|---|
| One package hash identifies approved and imported artifact | PASS | Archive SHA-256 is generated once, stored in deployment state, checked on import, and checked again by preflight. |
| Signature covers identity, adapter version, parameters, evidence, approval, risk, expiry, and live-disabled policy | PASS | Ed25519 signs the canonical hash map of every semantic member and manifest. Tamper matrix tests cover each member. |
| System 1 builds but cannot execute | PASS | Builder is in a shared contract module and called by `svos/deployment`; SVOS architecture imports remain broker-free. |
| System 2 verifies but cannot alter or approve | PASS | Production receives only the Ed25519 public key and imports the existing archive read-only. |
| Invalid, expired, tampered, revoked, or mismatched packages fail before connection | PASS | Unit and integration negative tests; `run_portfolio.main()` validates before `asyncio.run()`. |
| Legacy formats have explicit, tested outcomes | PASS | Directory v1 remains read-only compatible; archive v1 is rejected; explicit migration validates legacy signature and records provenance. |
| Deterministic package generation | PASS | Identical governed inputs produce byte-identical archives, package IDs, and archive SHA-256 values. |
| Package symbols are immutable and execution-checked | PASS | The signed v2 manifest contains symbols; Production and the runtime reject symbols outside the execution scope. |

## Validation record

- ADR-0002, Production, portfolio compatibility, CLI, and architecture suites: **56 passed**.
- Targeted Ruff checks: **PASS**.
- Targeted mypy checks: **PASS**.
- Canonical package validator self-test: **PASS**.
- Documentation drift: **PASS**.
- Documentation dead links and orphan checks: **PASS**; existing repository header warnings remain non-blocking.
- Extended SVOS/Production/portfolio/readiness run: **246 passed, 7 failed**. All seven failures are the pre-existing `svos.application.robustness` integration defect already recorded in `PROJECT_GAP_ANALYSIS.md`; ADR-0002 does not change robustness or lifecycle orchestration.

## Migration steps

1. Provision the System 1 private key as `SVOS_PACKAGE_SIGNING_PRIVATE_KEY` and the corresponding System 2 public key as `SVOS_PACKAGE_VERIFYING_PUBLIC_KEY` through separate secret scopes.
2. Prepare non-empty immutable parameters and risk-policy JSON documents.
3. Validate the legacy directory with its original `STRATEGY_PACKAGE_SIGNING_KEY`.
4. Run:

   ```bash
   python scripts/migrate_strategy_package.py LEGACY_DIRECTORY \
     --output canonical-package.tar.gz \
     --adapter-id ADAPTER_ID \
     --adapter-version ADAPTER_VERSION \
     --parameters-json parameters.json \
     --risk-policy-json risk-policy.json
   ```

5. Validate with `python scripts/validate_strategy_package.py canonical-package.tar.gz` in the System 2 verification environment.
6. Compare and record the archive SHA-256 before import.
7. Do not replace or delete the legacy artifact; retain it for provenance and rollback.

## Rollback instructions

1. Stop publishing new v2 packages.
2. Revert consumers to the legacy read-only directory validator where operationally required.
3. Preserve all v2 archives, package hashes, deployment/import records, preflight reports, and migration provenance.
4. Do not accept v1 deployment archives through v2 preflight.
5. Do not weaken signature, approval, expiry, identity, or revocation checks.
6. Resume v2 publication only after key and format integrity are revalidated.

## Follow-up work

- A separate PR should add managed key provisioning/rotation and, if required, KMS-backed Ed25519 signing without changing the v2 semantic contract.
- Legacy writer retirement requires adoption evidence and is intentionally deferred.
- ADR-0010 may later compose canonical runtime services; this implementation does not begin that work.
- ADR-0003 through ADR-0009 remain unimplemented.
