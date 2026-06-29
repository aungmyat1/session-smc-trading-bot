# Risk Assessment

## Risk register

| ID | Severity | Likelihood | Risk | Required treatment |
|---|---|---|---|---|
| R-01 | Critical | High | Legacy code promotes without governance | Remove direct mutation; architecture test |
| R-02 | Critical | Medium/High | Concurrent file writes corrupt or lose lifecycle state | Transactional DB and optimistic locking |
| R-03 | Critical | High if network-exposed | Unauthenticated dashboard can run jobs, generate reports, acknowledge incidents, and clear stops | Loopback default, auth, RBAC, CSRF/CORS policy |
| R-04 | High | High | Conflicting stage vocabularies produce incorrect eligibility | Canonical enum and compatibility mapping at edge only |
| R-05 | High | Medium | Synthetic virtual-demo evidence is mistaken for execution qualification | Disable by default; label and prohibit promotion |
| R-06 | High | High | Schema changes break deployments or silently diverge | Alembic and contract/migration CI |
| R-07 | High | Medium | Incomplete run lineage prevents reproduction | Mandatory code/data/config/seed identities |
| R-08 | High | Medium | Broad exception handling hides failed controls or persistence | Typed fail-closed policies and alerts |
| R-09 | High | Medium | Duplicate strategy/runtime implementations drift | Canonical adapters and deletion milestones |
| R-10 | High | Medium | Range dependencies produce irreproducible environments | Locked, hashed dependency sets |
| R-11 | Medium | High | Documentation conflict causes operator error | Authority index and generated status views |
| R-12 | Medium | Medium | Float/timezone inconsistencies distort evidence | Unit/precision/time ADR and typed models |
| R-13 | Medium | Medium | SQLite relationship corruption/orphans | FKs, migrations, integrity checks/export |
| R-14 | Medium | Medium | Large report indexes/files degrade and race | Metadata DB, pagination, atomic artifact writes |
| R-15 | Medium | Low/Medium | No tested disaster recovery | Backups, restore drills, declared RPO/RTO |

## Security detail

The dashboard defaults to `0.0.0.0` and calls `CORS(app)` without an origin
allowlist. It has no user authentication or authorization. Confirmation tokens
such as `CONFIRM-CLEAR-EMERGENCY-STOP` are fixed strings, not secrets, and the
API returns required token formats on denial. Some state-changing review
behavior is triggered by a GET query parameter. This is an operator convenience
interface, not a secure control plane.

Immediate containment before architectural remediation:

- do not expose the dashboard to an untrusted network;
- bind to loopback or place it behind authenticated TLS reverse proxy/VPN;
- prohibit live credentials in the dashboard process;
- keep `LIVE_TRADING=false`;
- treat dashboard approvals/control state as non-authoritative.

## Reliability and performance

The analytical architecture can scale reasonably through partitioned Parquet
and DuckDB. The control architecture cannot scale safely while every summary
rescans files and state mutations rewrite YAML/JSON without concurrency
control. PostgreSQL should handle metadata and lifecycle transactions; object
storage and columnar files should handle large evidence/data.

Performance benchmarks are missing for replay throughput, multi-strategy
parallelism, report indexing, database ingestion, and recovery. Establish SLOs
only after canonical contracts exist; otherwise benchmarks compare different
implementations.

## Risk acceptance rule

No Critical risk may be accepted for production or live-demo authorization.
High risks require an owner, expiry date, compensating control, and explicit
governance record. Research-only local runs may tolerate documented Medium
risks when they cannot mutate deployment eligibility.

