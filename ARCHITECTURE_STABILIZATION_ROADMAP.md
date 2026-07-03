# Architecture Stabilization Roadmap

- Date: 2026-07-03
- Status: Review
- Source: `PROJECT_GAP_ANALYSIS.md`
- Scope: Architecture decisions and implementation sequencing only
- Safety: This roadmap does not authorize live trading, broker connectivity, deployment, or strategy changes

> **Owner sequencing amendment — 2026-07-03:** ADR-0003 is assigned to
> **Single Runtime Authority** by explicit owner instruction. The earlier
> proposed ADR-0003 broker-truth workstream in this planning document remains
> unimplemented and must be renumbered before future authorization.

> **Owner sequencing amendment — 2026-07-03:** ADR-0004 is assigned to
> **Canonical Execution Pipeline** by explicit owner instruction. The earlier
> ADR-0004 default-deny broker-write workstream and ADR-0005 runtime-replay
> proposal remain future work and must be renumbered before authorization.

## 1. Purpose

This roadmap converts every architectural risk in `PROJECT_GAP_ANALYSIS.md` into a governed workstream. It preserves the repository's validation-first objective and its non-negotiable separation:

- **System 1 — Strategy Engineering Platform:** researches, replays, backtests, validates, qualifies, governs, and approves strategies. It never submits broker orders.
- **System 2 — Thin Execution Layer:** imports and verifies an approved package, consumes market data, applies runtime risk controls, executes through a broker abstraction, journals outcomes, reconciles state, and reports health. It never researches, optimizes, backtests, changes, or approves strategy logic.

No implementation phase may begin until its ADR is accepted. An ADR records authority; it is not evidence that implementation or qualification has passed.

## 2. Stabilization principles

1. **Validation precedes execution.** System 2 must reject missing, invalid, expired, unapproved, mismatched, or unverifiable packages before opening external connections.
2. **One signed handoff.** The only strategy handoff is a versioned, immutable, verifiable package.
3. **One execution path.** Replay, virtual demo, and demo execution use the same System 2 application services with different market-data and broker adapters.
4. **Broker truth is reconciled.** Risk state, journal state, and broker state must converge before new orders are allowed.
5. **Live remains unavailable.** Stabilization and qualification must not create a live-order path.
6. **Evidence is append-only.** Historical artifacts, decisions, incidents, and qualification outcomes are retained, not rewritten.
7. **Failure is visible.** No `|| true`, broad suppression, silent fallback, or dashboard masking may turn a failed gate into a passing result.
8. **Small PRs, reversible transitions.** Contract, compatibility, adoption, and retirement work are separate changes.

## 3. Workstream map

| Workstream | Source risk | Proposed ADR | Priority | Primary system |
|---|---|---|---:|---|
| WS1 | Executed artifact differs from approved artifact | ADR-0002: Canonical Strategy Package and Handoff | P0 | Boundary |
| WS2 | Runtime loss controls do not reflect closed trades | ADR-0011: Broker-Truth Risk Feedback | P0 | System 2 |
| WS3 | Alternate entrypoint enables broker writes | ADR-0012: Default-Deny Broker Write Boundary | P0 | System 2 |
| WS4 | Replay passes while demo behavior differs | ADR-0013: Runtime-Equivalent Replay | P0 | Both, without dependency inversion |
| WS5 | Restart duplicates or loses an ambiguous order | ADR-0006: Durable Execution and Recovery Authority | P0 | System 2 |
| WS6 | Dashboard reports stale or conflicting state | ADR-0007: Operational Read-Model Authority | P1 | Observation boundary |
| WS7 | Research and production cannot be independently deployed | ADR-0008: Independent System Deployment and Data Ownership | P1 | Both |
| WS8 | Quality regressions escape curated CI paths | ADR-0009: Repository Quality Baseline | P1 | Cross-cutting |

## 4. Dependency model

```text
PR #20: Demo Smoke Test only        PR #21: CircleCI parity (independent)
              |                                  |
              v                                  v
        WS1 Package Contract                WS8 CI evidence
              |
       +------+-------------------+
       |                          |
       v                          v
 WS3 Broker Deny            WS7 Boundary contracts
       |                          |
       +----------+---------------+
                  v
          Canonical System 2 graph
                  |
          +-------+--------+
          |                |
          v                v
 WS2 Risk Feedback    WS5 Durable Recovery
          |                |
          +-------+--------+
                  v
          WS4 Runtime Replay
                  |
                  v
          Replay Qualification
                  |
                  v
          Demo Qualification
                  |
                  v
          WS6 Dashboard Read Model
```

WS8 runs incrementally throughout the roadmap but may not weaken an existing gate to unblock another workstream.

## 5. Workstreams

### WS1 — Canonical strategy package and handoff

**Source risk:** The executed artifact can differ from the approved artifact because three package formats coexist.

**Proposed ADR:** `docs/svos/ADR-0002-CANONICAL-STRATEGY-PACKAGE.md`

The ADR must decide:

- the single versioned package schema and archive representation;
- mandatory identity, adapter version, configuration, evidence, approval, risk, expiry, and live-disabled fields;
- deterministic serialization and package hashing;
- signature scheme and key ownership;
- System 1 build authority and System 2 read-only verification authority;
- explicit compatibility rules for all existing formats;
- package revocation and expiry behavior.

**Implementation phases:**

1. Decision: inventory and field-map the three existing formats; accept ADR-0002.
2. Contract: add schema, canonical examples, deterministic fixtures, and compatibility test vectors.
3. Producer: make System 1 emit the canonical package without removing old readers.
4. Consumer: make System 2 import and verify the canonical package before connection.
5. Migration: convert or explicitly reject legacy packages; document provenance.
6. Retirement: remove legacy write paths only after adoption evidence passes.

**Dependencies:** Architecture-owner approval; signing-key policy; lifecycle evidence definitions; strategy identity rules.

**Acceptance criteria:**

- One package hash identifies the approved and imported artifact.
- The signature covers strategy identity, executable adapter version, immutable parameters, evidence references, approval decision, risk policy, expiry, and `live_trading_enabled=false`.
- System 1 can build but cannot execute the package.
- System 2 can verify and consume but cannot alter or approve it.
- Invalid, expired, tampered, revoked, or mismatched packages fail before external connection.
- Legacy formats have explicit, tested migration outcomes.

**Testing strategy:** Golden fixtures; deterministic rebuild hashes; schema validation; tamper matrix; signature/key tests; expiry/revocation tests; identity and adapter mismatch tests; cross-system contract tests; migration fixtures; startup-before-connect assertion.

**Rollback plan:** Keep old readers read-only behind explicit compatibility adapters. Revert the consumer selection to the prior reader while retaining canonical artifacts and audit records. Never downgrade signature or approval validation.

**Estimated effort:** 5–8 engineering days.

**Estimated PR sequence:**

- PR #22: ADR-0002, schema, field mapping, and fixtures.
- PR #23: canonical System 1 builder and deterministic contract tests.
- PR #24: System 2 importer/verifier integration.
- PR #25: compatibility migration and legacy-writer deprecation.

### WS2 — Broker-truth risk feedback

**Source risk:** Runtime loss controls do not reflect closed trades.

**Proposed ADR:** `docs/svos/ADR-0011-BROKER-TRUTH-RISK-FEEDBACK.md`

The ADR must decide:

- the authoritative closed-trade event and stable identifiers;
- exactly-once application of realized P&L to portfolio, daily/weekly/monthly loss, circuit-breaker, and position-limit state;
- startup and periodic reconciliation behavior;
- precedence among broker, execution state, and journal records;
- fail-closed thresholds and `BLOCK_NEW` behavior.

**Implementation phases:**

1. Decision: define identifiers, P&L semantics, and reconciliation authority.
2. Contract: define closed-trade and reconciliation-result schemas.
3. Virtual integration: feed virtual-broker closures into risk and journal state.
4. Runtime integration: adopt the same handler in demo mode.
5. Qualification: prove boundary halts and exactly-once recovery.

**Dependencies:** WS1; canonical System 2 service graph; WS5 durable idempotency and recovery records; broker history contract.

**Acceptance criteria:**

- Every closure updates all required risk controls exactly once.
- Duplicate broker events do not double-count P&L.
- Missing or contradictory critical state blocks new orders.
- Open-position counters are released from reconciled broker truth.
- Daily, weekly, monthly, consecutive-loss, and max-position limits halt at documented boundaries.
- No reconciliation action can create a new position.

**Testing strategy:** Winning/losing closure fixtures; exact-boundary and over-boundary tests; duplicate and reordered events; orphan broker position; missing journal entry; partial fill/close; restart during closure; property tests for P&L aggregation; virtual-broker end-to-end qualification.

**Rollback plan:** Activate `BLOCK_NEW` or close-only mode, restore the last consistent state snapshot, and replay append-only broker events through the prior calculator. Never roll back by discarding broker or journal evidence.

**Estimated effort:** 5–8 engineering days.

**Estimated PR sequence:**

- PR #29: ADR-0011 and event/reconciliation contracts.
- PR #30: virtual-broker close-result integration.
- PR #31: canonical demo-runtime integration.
- PR #32: loss-limit qualification and evidence report.

### WS3 — Default-deny broker write boundary

**Source risk:** An alternate entrypoint can enable broker writes through lower-level environment flags.

**Proposed ADR:** `docs/svos/ADR-0012-DEFAULT-DENY-BROKER-WRITES.md`

The ADR must decide:

- explicit environments: `virtual`, `demo`, and unavailable `live`;
- one broker write capability interface owned by System 2;
- authorization at object construction and each write call;
- prohibition of environment-only authorization;
- compile/import boundaries preventing System 1 from loading write-capable adapters;
- future live authorization as a separate owner-approved project, not a flag.

**Implementation phases:**

1. Decision: map every broker-write method and caller; accept ADR-0012.
2. Boundary: define a capability/token contract with no valid live token in current builds.
3. Adoption: route virtual and demo writes through the boundary.
4. Containment: make legacy clients non-write-capable or inaccessible to active entrypoints.
5. Verification: add negative architecture and direct-invocation tests.

**Dependencies:** WS1 package environment declaration; canonical runtime composition; operator mode vocabulary.

**Acceptance criteria:**

- `LIVE_TRADING=true`, `DEMO_ONLY=false`, or direct adapter construction cannot enable live writes.
- No current code path can construct a live-authorized broker capability.
- Demo writes require an explicitly demo-scoped account and package.
- System 1 has no import path to broker-write implementations.
- Shadow and replay use non-writing adapters.

**Testing strategy:** Environment permutation matrix; direct method invocation; alternate entrypoint tests; AST import boundaries; monkeypatched broker assertions; demo-account identity mismatch; negative deployment tests.

**Rollback plan:** Revert adapter adoption while leaving the global write deny active. The safe rollback state is virtual/shadow-only, never restoration of an environment-enabled live path.

**Estimated effort:** 3–5 engineering days.

**Estimated PR sequence:**

- PR #26: ADR-0012 and broker-write inventory.
- PR #27: default-deny capability boundary with virtual adapter.
- PR #28: demo adapter adoption and legacy containment.

### WS4 — Runtime-equivalent deterministic replay

**Source risk:** Replay can pass while demo behavior differs.

**Proposed ADR:** `docs/svos/ADR-0013-RUNTIME-EQUIVALENT-REPLAY.md`

The ADR must decide:

- the canonical System 2 application service graph reused by replay and demo;
- ports for event clock, market data, broker, state, journal, and report sink;
- deterministic ordering, time, randomness, latency, slippage, spread, and stop/target collision policies;
- how System 1 invokes replay without importing broker-write adapters;
- evidence hashes and replay qualification thresholds.

**Implementation phases:**

1. Decision: compare existing replay engines and select reusable components.
2. Extraction: isolate the canonical System 2 orchestration from its external adapters.
3. Assembly: connect historical market feed and virtual broker through the same ports.
4. Evidence: produce deterministic journal, execution timeline, risk decisions, and replay report.
5. Qualification: execute fixed datasets repeatedly and compare hashes.
6. Retirement: label noncanonical engines comparison-only before removal decisions.

**Dependencies:** WS1, WS2, WS3, and WS5; canonical event clock; canonical report schema.

**Acceptance criteria:**

- Historical candles traverse the same strategy adapter, permission, risk, execution manager, execution-state, journal, and reconciliation services used by demo.
- System 1 controls datasets and qualification; System 2 services remain unable to approve strategies.
- No future candle is visible to strategy or risk code.
- Same package, dataset, and simulator policy produce identical event and report hashes across repeated runs.
- Replay uses no network or live broker credentials.

**Testing strategy:** Golden event streams; no-lookahead tests; repeatability across processes; deterministic seed tests; clock boundary and DST cases; spread/latency/slippage cases; stop/target collision policy; crash/restart replay; service-graph identity assertions; comparison against accepted baseline evidence.

**Rollback plan:** Keep current replay implementations available as read-only comparison tools. Switch qualification back to “not qualified” if parity fails; never substitute legacy replay evidence as canonical without an explicit decision.

**Estimated effort:** 8–12 engineering days.

**Estimated PR sequence:**

- PR #35: ADR-0013 and replay component decision matrix.
- PR #36: canonical runtime ports and virtual assembly.
- PR #37: deterministic evidence/report generation.
- PR #38: replay qualification suite and baseline report.

### WS5 — Durable execution and restart recovery

**Source risk:** Restart can duplicate or lose an ambiguous order.

**Proposed ADR:** `docs/svos/ADR-0006-DURABLE-EXECUTION-RECOVERY.md`

The ADR must decide:

- `ExecutionStateStore` or its successor as the order lifecycle authority;
- idempotency-key derivation and retention;
- state persistence before and after broker calls;
- timeout ambiguity policy: reconcile before retry;
- startup recovery ordering and new-order lockout;
- terminal, retryable, and operator-review states.

**Implementation phases:**

1. Decision: formalize state machine, persistence, and idempotency semantics.
2. Contract: add broker correlation and reconciliation schemas.
3. Virtual integration: persist every transition and inject crashes at each boundary.
4. Demo integration: require recovery completion before `trading_allowed=true`.
5. Operations: expose unresolved states and operator actions in reports.

**Dependencies:** WS1 package identity/version; WS3 broker boundary; WS2 reconciliation contract.

**Acceptance criteria:**

- Intent is durable before broker submission.
- Broker acknowledgement and position references are correlated durably.
- A timeout never causes blind resubmission.
- Restart discovers every nonterminal record and reconciles before new orders.
- The same idempotency key cannot create two positions.
- Unresolvable ambiguity remains visible and blocks new trading.

**Testing strategy:** Crash at every state transition; timeout before/after broker acceptance; duplicate signal; duplicate acknowledgement; stale journal; missing broker order; partial fill; process-kill/restart; corrupted state file; concurrency tests.

**Rollback plan:** Stop new submissions, preserve state files and broker evidence, restore the last compatible runtime, and reconcile manually or with the previous read-only tool. Never delete ambiguous records to unblock trading.

**Estimated effort:** 5–8 engineering days.

**Estimated PR sequence:**

- PR #29: ADR-0006 alongside shared reconciliation contracts.
- PR #33: durable state integration and failure-injection harness.
- PR #34: restart qualification and operational recovery report.

### WS6 — Authoritative operational read model

**Source risk:** Dashboard state can be stale or conflicting.

**Proposed ADR:** `docs/svos/ADR-0007-OPERATIONAL-READ-MODEL.md`

The ADR must decide:

- the authoritative source and freshness contract for each displayed field;
- separate System 1 qualification projections and System 2 runtime projections;
- aggregation without transferring control authority to the dashboard;
- stale, unknown, degraded, and conflicting-state presentation;
- authentication and audit requirements for operational commands.

**Implementation phases:**

1. Decision: inventory every page, endpoint, process, and data source.
2. Contract: publish source/freshness/ownership mappings and API schemas.
3. Projection: build read-only System 1 and System 2 status projections.
4. UI adoption: migrate required pages without adding new controls.
5. Control review: separately authorize only required, audited, fail-closed actions.
6. Retirement: remove duplicated projections after parity and freshness evidence.

**Dependencies:** WS1 package identity; WS2/WS5 runtime state; WS4 replay reports; stable incident and health schemas.

**Acceptance criteria:**

- System Health, Runtime Status, Current Package, Execution Status, Risk Firewall, Replay Progress, Qualification Status, Strategy Registry, Audit Log, Incident History, and Health Timeline each declare one authoritative source.
- Stale or conflicting state is displayed as stale/conflicting, never silently replaced.
- Dashboard writes cannot approve strategies or bypass lifecycle governance.
- Secrets and broker credentials never appear in responses.
- Control actions are authenticated, CSRF-protected, audited, and fail closed.

**Testing strategy:** Source-priority and freshness tests; clock-skew cases; conflicting-state fixtures; authorization/CSRF tests; governance-denial tests; secret-redaction tests; API schema tests; UI smoke and accessibility tests.

**Rollback plan:** Keep existing surfaces read-only and switch routing back if the projection is incorrect. Preserve the new projection data for diagnosis; disable dashboard controls independently of read views.

**Estimated effort:** 8–15 engineering days.

**Estimated PR sequence:**

- PR #42: ADR-0007 and dashboard authority inventory.
- PR #43: read-model APIs and freshness semantics.
- PR #44: required page migration.
- PR #45: authenticated operational controls, only if separately approved.

### WS7 — Independent deployment and data ownership

**Source risk:** Research and production cannot be independently deployed.

**Proposed ADR:** `docs/svos/ADR-0008-INDEPENDENT-SYSTEM-DEPLOYMENT.md`

The ADR must decide:

- independently buildable System 1 and System 2 dependency sets;
- allowed shared contracts versus forbidden runtime dependencies;
- artifact-only strategy handoff;
- separate service identities, storage ownership, and least-privilege database roles;
- network boundaries and one-way package/evidence transport;
- deployment order, compatibility, and rollback.

**Implementation phases:**

1. Decision: generate dependency, import, database, process, and network inventories.
2. Contract boundary: extract or confirm shared DTOs and interfaces only.
3. Build separation: produce independent locked environments and build manifests.
4. Storage separation: assign schema/data ownership and least-privilege roles.
5. Deployment rehearsal: deploy both systems in isolated non-live environments.
6. Cutover planning: document migration and rollback; no production cutover under this roadmap alone.

**Dependencies:** WS1 artifact contract; WS3 write boundary; database migration audit; infrastructure owner approval.

**Acceptance criteria:**

- System 1 runs without production broker SDKs or credentials.
- System 2 runs without research, replay, backtest, robustness, optimization, or approval packages as runtime dependencies.
- The only strategy handoff is the canonical signed package.
- Service accounts and database roles enforce least privilege.
- Network policy prevents System 1 from reaching broker-write endpoints.
- Independent build, startup, health, backup, and rollback rehearsals pass.

**Testing strategy:** Import-boundary tests; independent clean-environment installs; dependency lock audits; credential absence tests; network-deny tests; database permission tests; backup/restore rehearsal; package compatibility matrix.

**Rollback plan:** Retain the existing topology until isolated rehearsal passes. For later migration, restore prior service routing and database snapshots while preserving artifact and audit stores. Never relax network or credential boundaries as a rollback shortcut.

**Estimated effort:** 10–20 engineering days plus infrastructure rehearsal.

**Estimated PR sequence:**

- PR #39: ADR-0008 and dependency/data topology inventory.
- PR #40: independent dependency manifests and import gates.
- PR #41: least-privilege deployment specifications and rehearsal evidence.

### WS8 — Repository-wide trustworthy quality baseline

**Source risk:** Quality regressions can escape curated CI paths.

**Proposed ADR:** `docs/svos/ADR-0009-QUALITY-BASELINE-AND-CI-PARITY.md`

The ADR must decide:

- required fast PR gates versus complete scheduled gates;
- ownership and expiry of every accepted exception;
- isolation policy for native crashes and nondeterministic tests;
- monotonic Ruff/mypy debt reduction;
- exact GitHub Actions/CircleCI parity requirements;
- artifact retention and failure visibility.

**Implementation phases:**

1. Provider parity: complete PR #21 without replacing GitHub Actions.
2. Baseline: publish full-suite, Ruff, mypy, native-crash, and flaky-test inventories.
3. Isolation: make the full suite complete deterministically without hiding failures.
4. Reduction: address debt in narrow, behavior-neutral PRs.
5. Enforcement: add monotonic or directory-scoped gates as areas become clean.
6. Observation: run repeated scheduled builds and publish stability evidence.

**Dependencies:** PR #21; test ownership; reproducible dependency environment. This workstream must not block safety-critical negative tests in WS1–WS7.

**Acceptance criteria:**

- GitHub Actions and CircleCI run equivalent commands and both are required.
- The four documented dependency-audit exceptions remain explicit and unchanged until separately reviewed.
- No `|| true`, blanket ignore, swallowed exit code, or equivalent suppression is introduced.
- Full pytest completes with deterministic classification of all failures.
- Ruff/mypy debt is measured and cannot increase silently.
- Every exception has an owner, reason, scope, review date, and removal criterion.

**Testing strategy:** Controlled failing commits for every CI gate; provider-log comparison; repeat full-suite runs; test-order randomization; subprocess/native dependency isolation; cache-cold runs; artifact and JUnit verification.

**Rollback plan:** Disable the new CircleCI required check or scheduled expansion while keeping GitHub Actions required and retaining the published debt baseline. Revert narrow cleanup PRs independently; never suppress the failing command.

**Estimated effort:** 8–20 engineering days across focused PRs, plus PR #21 administration.

**Estimated PR sequence:**

- PR #21: CircleCI parity, triggers, and dual-provider branch protection.
- PR #46: ADR-0009 and repository quality baseline.
- PR #47+: isolated native-crash, full-suite, Ruff, mypy, and flaky-test remediation PRs.

## 6. Cross-cutting architecture decisions

The eight risk ADRs require three supporting decisions. These do not replace the risk workstreams:

### Supporting ADR A — Canonical runtime composition

Proposed file: `docs/svos/ADR-0010-CANONICAL-RUNTIME-COMPOSITION.md`.

It should define the one System 2 order path through package guard, configuration validation, governance, permission, risk, durable execution state, broker abstraction, journal, reconciliation, and monitoring. It is the shared prerequisite for WS2, WS4, and WS5.

### Supporting ADR B — Lifecycle responsibility mapping

Proposed file: `docs/svos/ADR-0011-LIFECYCLE-RESPONSIBILITY-MAPPING.md`.

It must resolve how Backtest and Statistical Validation remain distinct responsibilities without inventing an unauthorized stage name, and how `REFINEMENT` is integrated. This is a System 1 decision and must not move validation logic into System 2.

### Supporting ADR C — Fail-closed runtime configuration

Proposed file: `docs/svos/ADR-0012-RUNTIME-CONFIGURATION-AUTHORITY.md`.

It should establish one validated startup configuration, eliminate silent production fallbacks, separate secrets from non-secret configuration, and require all checks to finish before external connection.

## 7. Integrated implementation and PR roadmap

PR numbers after #21 are estimates and may shift. Dependency order is normative; numbering is not.

| Wave | Estimated PRs | Outcome | Promotion gate |
|---|---|---|---|
| 0 | #20 | Demo Smoke Test remains isolated | Offline preflight evidence |
| 1 | #21 | CircleCI parity and dual required checks | CI parity |
| 2 | #22–#25 | Canonical signed package adopted across the handoff | Artifact Integrity |
| 3 | #26–#28 | Broker writes default-denied; virtual/demo explicitly scoped | Runtime Safety |
| 4 | #29–#34 | Closed-trade feedback, durable state, reconciliation, and restart recovery | Operational Integrity |
| 5 | #35–#38 | Runtime-equivalent deterministic replay and evidence | Replay Qualified |
| 6 | #39–#41 | Independent build/deployment boundaries and least privilege | System Separation |
| 7 | #42–#45 | Authoritative read model and operational dashboard | Operational Visibility |
| 8 | #46+ | Full quality baseline and incremental debt reduction | Quality Qualified |
| 9 | Later qualification PRs | Demo execution validation and observation | Demo Qualified, then Long-running Demo |

## 8. Merge and promotion policy

Each workstream PR must include:

- its accepted ADR or a direct link to the governing accepted ADR;
- a boundary-impact statement for System 1, System 2, shared contracts, data, and deployment;
- tests proving acceptance criteria and negative safety behavior;
- migration and rollback instructions;
- generated evidence or a statement explaining why the PR is contract-only;
- no strategy-logic changes;
- no live broker connection or live-order behavior;
- passing GitHub Actions and, after PR #21 activation, passing CircleCI;
- explicit review of new exceptions, with none hidden.

Qualification stages are cumulative. A later stage cannot compensate for a failed earlier gate:

```text
Artifact Integrity
  -> Runtime Safety
  -> Operational Integrity
  -> Replay Qualified
  -> Demo Qualified
  -> Operational Qualified
  -> Security Qualified
  -> Long-running Demo
  -> Production Candidate
```

`Limited Live Trading` and `Production` are outside the authorization of this roadmap. Reaching `Production Candidate` produces a review package, not permission to trade live.

## 9. Roadmap completion criteria

Architecture stabilization is complete only when:

1. All eight risk ADRs and three supporting ADRs are accepted or explicitly rejected with replacement decisions.
2. System 1 and System 2 can be built, tested, and deployed independently.
3. One signed package crosses the boundary and is verified before System 2 connects externally.
4. Replay and demo use the same System 2 application services through different adapters.
5. Risk state reflects reconciled broker truth and survives restart without duplicate orders.
6. No current code path can authorize live broker writes.
7. Dashboards expose authoritative, freshness-aware read models without governance bypass.
8. GitHub Actions and CircleCI are both required and equivalent, and repository-wide debt is visible and decreasing.
9. Replay and demo qualification reports contain deterministic, reviewable evidence.
10. Live trading remains disabled pending a separate owner-authorized production program.

## 10. Immediate next action

Keep PR #20 unchanged in scope. Complete PR #21 for CI parity. Then open PR #22 as a documentation-and-contract-only change containing ADR-0002, the canonical package field mapping, and deterministic fixtures. No runtime implementation should begin before ADR-0002 is accepted.
