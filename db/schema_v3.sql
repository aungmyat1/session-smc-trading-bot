-- =====================================================================
-- TRADING RESEARCH DATABASE — Schema v3
-- PostgreSQL 16+  |  Industrial-grade control plane for SVOS pipeline
--
-- Schemas
--   strategy    — canonical identity and immutable versioning
--   governance  — stage state (optimistic-locked), gate decisions,
--                 approvals, transactional outbox
--   evidence    — content-addressed artifacts and stage bindings
--   experiments — reproducible experiment registry
--   robustness  — walk-forward, Monte Carlo, sensitivity results
--   execution   — virtual-demo order/fill/position evidence
--   operations  — deployment records and incident log
--
-- Existing schemas kept intact (market, research, analytics, config).
-- v3 tables are additive — no v2 tables are altered or dropped.
--
-- Upgrades over v2
--   • New schemas: strategy, governance, evidence, experiments,
--     robustness, execution, operations
--   • research.run  — UUID-keyed run table with full provenance
--   • analytics.stage_gate — per-stage gate verdicts (replaces
--     analytics.phase0_gate specialisation)
--   • All new timestamps are TIMESTAMPTZ (UTC)
--   • All financial values are NUMERIC (no REAL)
--   • FK constraints are declared and enforced
-- =====================================================================

-- ----- prerequisites ------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ----- existing schemas (kept) --------------------------------------
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS research;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS config;

-- ----- new schemas --------------------------------------------------
CREATE SCHEMA IF NOT EXISTS strategy;
CREATE SCHEMA IF NOT EXISTS governance;
CREATE SCHEMA IF NOT EXISTS evidence;
CREATE SCHEMA IF NOT EXISTS experiments;
CREATE SCHEMA IF NOT EXISTS robustness;
CREATE SCHEMA IF NOT EXISTS execution;
CREATE SCHEMA IF NOT EXISTS operations;

-- =====================================================================
-- strategy schema — canonical identity and immutable spec versioning
-- =====================================================================

CREATE TABLE IF NOT EXISTS strategy.strategy (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL,
    slug        VARCHAR(100) NOT NULL,      -- stable URL-safe key: "ST-A2"
    owner       VARCHAR(100),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT  strategy_name_unique UNIQUE (name),
    CONSTRAINT  strategy_slug_unique UNIQUE (slug)
);

-- Every spec change creates a new immutable version row.
-- spec_hash binds the version to its content — identical hash = identical spec.
CREATE TABLE IF NOT EXISTS strategy.version (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID        NOT NULL REFERENCES strategy.strategy(id),
    version         VARCHAR(30) NOT NULL,        -- semver: "0.2.1"
    spec_hash       VARCHAR(64) NOT NULL,         -- SHA-256 of rules_json
    parent_id       UUID        REFERENCES strategy.version(id),
    source_commit   VARCHAR(40),                  -- git SHA when version was minted
    rules_json      JSONB       NOT NULL,
    notes           TEXT,
    created_by      VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT strategy_version_unique UNIQUE (strategy_id, version)
);
CREATE INDEX IF NOT EXISTS idx_sv_strategy_id ON strategy.version(strategy_id);

-- =====================================================================
-- governance schema — stage state, gate decisions, approvals, outbox
-- =====================================================================

-- One row per strategy. Optimistic lock via opt_lock prevents concurrent
-- stage transitions from racing: caller must read opt_lock and include it
-- in the WHERE clause; mismatch = conflict, retry.
CREATE TABLE IF NOT EXISTS governance.stage_state (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id         UUID        NOT NULL UNIQUE REFERENCES strategy.strategy(id),
    current_stage       VARCHAR(50) NOT NULL,
    current_version_id  UUID        REFERENCES strategy.version(id),
    opt_lock            INTEGER     NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by          VARCHAR(100)
);

-- Append-only audit of every gate evaluation. Never update or delete rows.
CREATE TABLE IF NOT EXISTS governance.gate_decision (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID        NOT NULL REFERENCES strategy.strategy(id),
    version_id      UUID        REFERENCES strategy.version(id),
    from_stage      VARCHAR(50) NOT NULL,
    to_stage        VARCHAR(50) NOT NULL,
    allowed         BOOLEAN     NOT NULL,
    actor           VARCHAR(100) NOT NULL,
    reason          TEXT,
    blockers        JSONB       NOT NULL DEFAULT '[]',
    evidence_ids    JSONB       NOT NULL DEFAULT '[]',
    policy_version  VARCHAR(20),
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gd_strategy_id ON governance.gate_decision(strategy_id);
CREATE INDEX IF NOT EXISTS idx_gd_decided_at  ON governance.gate_decision(decided_at);

-- Named approvals for stages that require explicit human sign-off
-- (LIVE_DEMO, PRODUCTION per CLAUDE.md §4).
CREATE TABLE IF NOT EXISTS governance.approval (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID        NOT NULL REFERENCES strategy.strategy(id),
    version_id      UUID        REFERENCES strategy.version(id),
    gate_decision_id UUID       REFERENCES governance.gate_decision(id),
    from_stage      VARCHAR(50) NOT NULL,
    to_stage        VARCHAR(50) NOT NULL,
    approver        VARCHAR(100) NOT NULL,
    approver_role   VARCHAR(50),
    reason          TEXT        NOT NULL,
    approved_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_appr_strategy_id ON governance.approval(strategy_id);

-- Transactional outbox — lifecycle events written in the same transaction as
-- stage_state updates. A separate relay publishes them to downstream consumers.
-- This guarantees governance records and downstream notifications are atomic (D-06).
CREATE TABLE IF NOT EXISTS governance.outbox (
    id              BIGSERIAL   PRIMARY KEY,
    event_type      VARCHAR(100) NOT NULL,    -- "stage_transition" | "gate_evaluated" | ...
    strategy_id     UUID        REFERENCES strategy.strategy(id),
    payload         JSONB       NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at    TIMESTAMPTZ             -- NULL = pending relay
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON governance.outbox(processed_at)
    WHERE processed_at IS NULL;

-- =====================================================================
-- evidence schema — content-addressed artifacts and stage bindings
-- =====================================================================

-- One artifact per report/file. URI may be local path or object-storage key.
-- sha256 is the integrity anchor — identical hash = identical content.
CREATE TABLE IF NOT EXISTS evidence.artifact (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID        NOT NULL REFERENCES strategy.strategy(id),
    stage           VARCHAR(50) NOT NULL,
    report_type     VARCHAR(100) NOT NULL,   -- "audit_report" | "backtest_summary" | ...
    uri             TEXT        NOT NULL,
    sha256          VARCHAR(64) NOT NULL,
    media_type      VARCHAR(100),            -- "application/json" | "text/markdown" | ...
    size_bytes      BIGINT,
    schema_version  VARCHAR(20),
    recorded_by     VARCHAR(100),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ea_strategy_stage ON evidence.artifact(strategy_id, stage);
CREATE INDEX IF NOT EXISTS idx_ea_sha256         ON evidence.artifact(sha256);

-- Binding links an artifact to a specific (strategy version, run, stage) tuple.
CREATE TABLE IF NOT EXISTS evidence.binding (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID        NOT NULL REFERENCES strategy.strategy(id),
    version_id      UUID        REFERENCES strategy.version(id),
    run_id          UUID,                    -- references research.run.id (added in v3)
    stage           VARCHAR(50) NOT NULL,
    artifact_id     UUID        NOT NULL REFERENCES evidence.artifact(id),
    status          VARCHAR(20) NOT NULL DEFAULT 'active',   -- active | superseded | retracted
    bound_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_eb_strategy_stage ON evidence.binding(strategy_id, stage);
CREATE INDEX IF NOT EXISTS idx_eb_artifact_id    ON evidence.binding(artifact_id);

-- =====================================================================
-- research schema — run provenance, trades, features, equity
-- (v2 tables kept; research.run is new and supersedes replay_runs)
-- =====================================================================

-- Existing v2 tables (market, research, analytics, config) are declared in
-- schema_v2.sql and applied separately. Only v3 additions are declared here.

-- research.run — UUID-keyed, full provenance.
-- Replaces research.replay_runs for new code.  Legacy run_id VARCHAR column
-- kept so existing queries remain valid during the dual-read transition.
CREATE TABLE IF NOT EXISTS research.run (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           VARCHAR(100) UNIQUE NOT NULL,   -- legacy string key
    strategy_id      UUID        REFERENCES strategy.strategy(id),
    version_id       UUID        REFERENCES strategy.version(id),
    -- kept for backward compat with callers that pass strategy_name directly
    strategy_name    VARCHAR(100),
    symbol           VARCHAR(20),
    start_date       DATE,
    end_date         DATE,
    scenario         VARCHAR(20) NOT NULL DEFAULT 'standard',  -- standard | stress_2x
    -- provenance: exactly what produced this run
    code_commit      VARCHAR(40),
    env_hash         VARCHAR(64),     -- hash of requirements.lock or env snapshot
    dataset_snapshot VARCHAR(64),     -- hash of dataset manifest
    seed             INTEGER,
    parameters       JSONB,
    -- lifecycle
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',   -- pending | running | done | failed
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_run_strategy_id ON research.run(strategy_id);
CREATE INDEX IF NOT EXISTS idx_run_status      ON research.run(status);
CREATE INDEX IF NOT EXISTS idx_run_scenario    ON research.run(scenario);

-- Typed metric store — one row per metric per run.
-- Replaces per-table metric columns; all analysis dimensions land here.
CREATE TABLE IF NOT EXISTS research.metric (
    id          BIGSERIAL   PRIMARY KEY,
    run_id      UUID        NOT NULL REFERENCES research.run(id),
    metric_name VARCHAR(100) NOT NULL,   -- "profit_factor" | "win_rate" | ...
    value       NUMERIC(14,6) NOT NULL,
    unit        VARCHAR(30),             -- "ratio" | "percent" | "r_multiple" | ...
    window      VARCHAR(50),             -- "full" | "walk_forward_fold_3" | "monte_carlo_p50"
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT  run_metric_unique UNIQUE (run_id, metric_name, window)
);
CREATE INDEX IF NOT EXISTS idx_metric_run_id    ON research.metric(run_id);
CREATE INDEX IF NOT EXISTS idx_metric_name      ON research.metric(metric_name);

-- =====================================================================
-- analytics schema — per-stage gate verdicts
-- =====================================================================

-- analytics.stage_gate replaces the phase0_gate specialisation.
-- One row per (run, stage, scenario) evaluation.
CREATE TABLE IF NOT EXISTS analytics.stage_gate (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID        REFERENCES research.run(id),
    strategy_id     UUID        REFERENCES strategy.strategy(id),
    stage           VARCHAR(50) NOT NULL,        -- STATISTICAL_VALIDATION | ROBUSTNESS_VALIDATION | ...
    scenario        VARCHAR(20),
    n_trades        INTEGER,
    metrics         JSONB,                       -- all gate metrics as JSON for flexibility
    gate_pass       BOOLEAN     NOT NULL,
    blockers        JSONB       NOT NULL DEFAULT '[]',
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_sg_run_id      ON analytics.stage_gate(run_id);
CREATE INDEX IF NOT EXISTS idx_sg_strategy_id ON analytics.stage_gate(strategy_id);
CREATE INDEX IF NOT EXISTS idx_sg_stage       ON analytics.stage_gate(stage);

-- =====================================================================
-- experiments schema — reproducible experiment registry
-- =====================================================================

-- Every trial or parameter change pre-registers here before the run starts
-- (CLAUDE.md §7 — never re-run on the same trial ID).
CREATE TABLE IF NOT EXISTS experiments.experiment (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    exp_id          VARCHAR(50) NOT NULL UNIQUE,   -- EXP-2026-0042, ST-A, T27, ...
    strategy_id     UUID        REFERENCES strategy.strategy(id),
    version_id      UUID        REFERENCES strategy.version(id),
    title           VARCHAR(200) NOT NULL,
    hypothesis      TEXT,
    instrument      VARCHAR(20),
    dataset_version VARCHAR(64),                   -- hash of dataset snapshot
    feature_set     JSONB,                         -- which feature layers were used
    parameters      JSONB,                         -- parameter dict at registration time
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | running | complete | failed
    verdict         VARCHAR(20),                   -- accepted | rejected | inconclusive | deferred
    verdict_reason  TEXT,
    created_by      VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    concluded_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_exp_strategy_id ON experiments.experiment(strategy_id);
CREATE INDEX IF NOT EXISTS idx_exp_exp_id      ON experiments.experiment(exp_id);

-- Immutable parameter set snapshots.  Multiple sets per experiment support
-- comparative runs (e.g. standard vs 2× spread) without confusion.
CREATE TABLE IF NOT EXISTS experiments.parameter_set (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id   UUID        NOT NULL REFERENCES experiments.experiment(id),
    label           VARCHAR(100),                  -- "standard" | "stress_2x" | "walk_fwd"
    parameters      JSONB       NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ps_experiment_id ON experiments.parameter_set(experiment_id);

-- Links an experiment to its run results and evidence artifacts.
CREATE TABLE IF NOT EXISTS experiments.result_binding (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id   UUID        NOT NULL REFERENCES experiments.experiment(id),
    run_id          UUID        REFERENCES research.run(id),
    stage           VARCHAR(50) NOT NULL,
    verdict         VARCHAR(20),                   -- accepted | rejected | inconclusive
    artifact_id     UUID        REFERENCES evidence.artifact(id),
    bound_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rb_experiment_id ON experiments.result_binding(experiment_id);

-- =====================================================================
-- robustness schema — walk-forward, Monte Carlo, sensitivity results
-- =====================================================================

CREATE TABLE IF NOT EXISTS robustness.walk_forward_result (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID        NOT NULL REFERENCES research.run(id),
    fold_index      INTEGER     NOT NULL,
    train_start     DATE        NOT NULL,
    train_end       DATE        NOT NULL,
    test_start      DATE        NOT NULL,
    test_end        DATE        NOT NULL,
    n_trades        INTEGER,
    profit_factor   NUMERIC(8,4),
    win_rate        NUMERIC(5,2),
    net_r           NUMERIC(10,2),
    max_drawdown    NUMERIC(8,4),
    gate_pass       BOOLEAN,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT wfr_run_fold_unique UNIQUE (run_id, fold_index)
);
CREATE INDEX IF NOT EXISTS idx_wfr_run_id ON robustness.walk_forward_result(run_id);

CREATE TABLE IF NOT EXISTS robustness.monte_carlo_result (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID        NOT NULL REFERENCES research.run(id),
    n_simulations    INTEGER     NOT NULL,
    percentile_5_pf  NUMERIC(8,4),
    percentile_25_pf NUMERIC(8,4),
    median_pf        NUMERIC(8,4),
    percentile_75_pf NUMERIC(8,4),
    percentile_95_pf NUMERIC(8,4),
    ruin_probability NUMERIC(6,4),
    max_dd_p95       NUMERIC(8,4),
    gate_pass        BOOLEAN,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mcr_run_id ON robustness.monte_carlo_result(run_id);

CREATE TABLE IF NOT EXISTS robustness.sensitivity_result (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID        NOT NULL REFERENCES research.run(id),
    parameter_name  VARCHAR(100) NOT NULL,
    parameter_value TEXT        NOT NULL,
    n_trades        INTEGER,
    profit_factor   NUMERIC(8,4),
    net_r           NUMERIC(10,2),
    max_drawdown    NUMERIC(8,4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sr_run_id ON robustness.sensitivity_result(run_id);

-- =====================================================================
-- execution schema — virtual-demo order / fill / position evidence
-- =====================================================================

-- PostgreSQL-backed version of the SQLite execution_log.
-- SQLite remains acceptable for isolated developer runs; these tables
-- receive promoted evidence from virtual demo sessions for the permanent record.

CREATE TABLE IF NOT EXISTS execution.virtual_order (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID        REFERENCES research.run(id),
    symbol          VARCHAR(20) NOT NULL,
    direction       VARCHAR(10) NOT NULL CHECK (direction IN ('long', 'short')),
    requested_price NUMERIC(12,5),
    filled_price    NUMERIC(12,5),
    slippage_pips   NUMERIC(8,4),
    latency_ms      INTEGER,
    status          VARCHAR(20) NOT NULL,           -- submitted | filled | rejected | cancelled
    reason          TEXT,
    ordered_at      TIMESTAMPTZ NOT NULL,
    filled_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vo_run_id    ON execution.virtual_order(run_id);
CREATE INDEX IF NOT EXISTS idx_vo_symbol    ON execution.virtual_order(symbol);
CREATE INDEX IF NOT EXISTS idx_vo_status    ON execution.virtual_order(status);

CREATE TABLE IF NOT EXISTS execution.virtual_fill (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID        NOT NULL REFERENCES execution.virtual_order(id),
    symbol          VARCHAR(20) NOT NULL,
    direction       VARCHAR(10) NOT NULL,
    requested_price NUMERIC(12,5),
    filled_price    NUMERIC(12,5),
    slippage_pips   NUMERIC(8,4),
    latency_ms      INTEGER,
    execution_time  TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vf_order_id ON execution.virtual_fill(order_id);

CREATE TABLE IF NOT EXISTS execution.virtual_position (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id         UUID        NOT NULL REFERENCES execution.virtual_order(id),
    run_id           UUID        REFERENCES research.run(id),
    symbol           VARCHAR(20) NOT NULL,
    direction        VARCHAR(10) NOT NULL,
    entry_price      NUMERIC(12,5) NOT NULL,
    exit_price       NUMERIC(12,5),
    sl_price         NUMERIC(12,5),
    tp_price         NUMERIC(12,5),
    spread_cost_pips NUMERIC(8,4),
    gross_profit_r   NUMERIC(8,4),
    net_profit_r     NUMERIC(8,4),
    duration_seconds NUMERIC(12,2),
    exit_reason      VARCHAR(50),
    opened_at        TIMESTAMPTZ NOT NULL,
    closed_at        TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vp_run_id    ON execution.virtual_position(run_id);
CREATE INDEX IF NOT EXISTS idx_vp_symbol    ON execution.virtual_position(symbol);

-- Drift detection: comparison between backtest expectation and live execution.
CREATE TABLE IF NOT EXISTS execution.drift_observation (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID        REFERENCES research.run(id),
    observation_time    TIMESTAMPTZ NOT NULL,
    symbol              VARCHAR(20) NOT NULL,
    expected_direction  VARCHAR(10),
    actual_direction    VARCHAR(10),
    expected_entry      NUMERIC(12,5),
    actual_entry        NUMERIC(12,5),
    slippage_pips       NUMERIC(8,4),
    latency_ms          INTEGER,
    verdict             VARCHAR(20),  -- within_tolerance | drift_detected
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_do_run_id ON execution.drift_observation(run_id);

-- =====================================================================
-- operations schema — deployment records and incident log
-- =====================================================================

CREATE TABLE IF NOT EXISTS operations.deployment (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id         UUID        NOT NULL REFERENCES strategy.strategy(id),
    version_id          UUID        REFERENCES strategy.version(id),
    environment         VARCHAR(30) NOT NULL,   -- demo | live
    broker              VARCHAR(50),
    account_id          VARCHAR(100),
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
    deployed_by         VARCHAR(100),
    deployed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    decommissioned_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_dep_strategy_id ON operations.deployment(strategy_id);

CREATE TABLE IF NOT EXISTS operations.incident (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id   UUID        REFERENCES operations.deployment(id),
    strategy_id     UUID        REFERENCES strategy.strategy(id),
    severity        VARCHAR(10) NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'open',   -- open | investigating | resolved
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    resolution      TEXT
);
CREATE INDEX IF NOT EXISTS idx_inc_strategy_id   ON operations.incident(strategy_id);
CREATE INDEX IF NOT EXISTS idx_inc_deployment_id ON operations.incident(deployment_id);

-- =====================================================================
-- Seed: import known strategies into canonical registry
-- Run once after schema creation.  Idempotent via ON CONFLICT DO NOTHING.
-- =====================================================================

INSERT INTO strategy.strategy (name, slug, owner) VALUES
    ('ST-A2', 'ST-A2', 'aung.pro1@gmail.com')
ON CONFLICT (slug) DO NOTHING;
