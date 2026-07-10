"""
db/models.py
SQLAlchemy ORM — v3 synchronized, single authoritative schema definition.

Covers all tables in both db/schema_v2.sql and db/schema_v3.sql.

Schema layout
─────────────
v2 (existing, unchanged)
  market      : Instrument, Candle(*), AsianRange, SessionRange, SmcEvent
  research    : Strategy, ReplayRun, Trade, TradeFeature, DailyEquity
  analytics   : StrategyMetric, MonthlyMetric, Phase0Gate, ExperimentLog,
                OptimizationResult(*)
  config      : SystemConfig(*)
  (* = previously missing from ORM — D-03 fix)

v3 (new control-plane additions)
  strategy    : StrategyEntity, StrategyVersion
  governance  : StageState, GateDecision, Approval, Outbox
  evidence    : Artifact, ArtifactBinding
  research    : Run, Metric          (new UUID-keyed tables; legacy v2 kept)
  analytics   : StageGate            (generalises Phase0Gate)
  experiments : Experiment, ParameterSet, ExperimentResultBinding
  robustness  : WalkForwardResult, MonteCarloResult, SensitivityResult
  execution   : VirtualOrder, VirtualFill, VirtualPosition, DriftObservation
  operations  : Deployment, Incident, Runtime, MarketDataHealth, Intent, RiskDecision,
                OrderRecord, Fill, PositionRecord, Reconciliation, RecoveryCheckpoint,
                ExecutionEvent  (migration 004 — System 2 operations recording, added
                Sprint 2.3 / SYSTEM2_MASTER_PLAN.md Phase 2; ORM previously missing for these)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey,
    Integer, JSON, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .connection import Base


# ═══════════════════════════════════════════════════════════════════════════
# market schema  ── v2, unchanged
# ═══════════════════════════════════════════════════════════════════════════

class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = {"schema": "market"}

    id             = Column(Integer, primary_key=True)
    symbol         = Column(String(20), unique=True, nullable=False)
    asset_type     = Column(String(20), nullable=False)
    broker_symbol  = Column(String(30))
    base_currency  = Column(String(10))
    quote_currency = Column(String(10))
    pip_size       = Column(Numeric(10, 6), default=0.0001)
    created_at     = Column(DateTime, default=datetime.utcnow)


class Candle(Base):
    """market.candles — live broker candles; was in SQL but missing from ORM (D-03)."""
    __tablename__  = "candles"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp"),
        {"schema": "market"},
    )

    id         = Column(BigInteger, primary_key=True)
    symbol     = Column(String(20), nullable=False)
    timeframe  = Column(String(10), nullable=False)
    timestamp  = Column(DateTime, nullable=False)
    open       = Column(Numeric(12, 5))
    high       = Column(Numeric(12, 5))
    low        = Column(Numeric(12, 5))
    close      = Column(Numeric(12, 5))
    volume     = Column(BigInteger)
    bid        = Column(Numeric(12, 5))
    ask        = Column(Numeric(12, 5))
    spread     = Column(Numeric(8, 5))
    source     = Column(String(30))
    created_at = Column(DateTime, default=datetime.utcnow)


class AsianRange(Base):
    __tablename__  = "asian_ranges"
    __table_args__ = (
        UniqueConstraint("symbol", "date"),
        {"schema": "market"},
    )

    id               = Column(BigInteger, primary_key=True)
    symbol           = Column(String(20), nullable=False)
    date             = Column(Date, nullable=False)
    asian_high       = Column(Numeric(12, 5), nullable=False)
    asian_low        = Column(Numeric(12, 5), nullable=False)
    asian_mid        = Column(Numeric(12, 5), nullable=False)
    asian_range_pips = Column(Numeric(8, 2), nullable=False)
    asian_volume     = Column(BigInteger)
    created_at       = Column(DateTime, default=datetime.utcnow)


class SessionRange(Base):
    __tablename__  = "session_ranges"
    __table_args__ = (
        UniqueConstraint("symbol", "date", "session"),
        {"schema": "market"},
    )

    id                 = Column(BigInteger, primary_key=True)
    symbol             = Column(String(20), nullable=False)
    date               = Column(Date, nullable=False)
    session            = Column(String(20), nullable=False)
    session_high       = Column(Numeric(12, 5), nullable=False)
    session_low        = Column(Numeric(12, 5), nullable=False)
    session_mid        = Column(Numeric(12, 5), nullable=False)
    session_range_pips = Column(Numeric(8, 2), nullable=False)
    session_type       = Column(String(10))
    created_at         = Column(DateTime, default=datetime.utcnow)


class SmcEvent(Base):
    __tablename__ = "smc_events"
    __table_args__ = {"schema": "market"}

    id             = Column(BigInteger, primary_key=True)
    symbol         = Column(String(20), nullable=False)
    timeframe      = Column(String(10), nullable=False)
    timestamp      = Column(DateTime, nullable=False)
    event_type     = Column(String(30), nullable=False)
    event_price    = Column(Numeric(12, 5))
    strength_score = Column(Numeric(5, 2))
    metadata_json  = Column(JSON)
    created_at     = Column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# research schema  ── v2, unchanged
# ═══════════════════════════════════════════════════════════════════════════

class Strategy(Base):
    """research.strategies — legacy table; superseded by strategy.StrategyEntity for new code."""
    __tablename__  = "strategies"
    __table_args__ = (
        UniqueConstraint("strategy_name", "version"),
        {"schema": "research"},
    )

    id            = Column(Integer, primary_key=True)
    strategy_name = Column(String(100), nullable=False)
    version       = Column(String(20), nullable=False)
    description   = Column(Text)
    rules_json    = Column(JSON)
    created_at    = Column(DateTime, default=datetime.utcnow)
    status        = Column(String(20), default="active")


class ReplayRun(Base):
    """research.replay_runs — legacy table; superseded by research.Run for new code."""
    __tablename__ = "replay_runs"
    __table_args__ = {"schema": "research"}

    id          = Column(Integer, primary_key=True)
    run_id      = Column(String(100), unique=True, nullable=False)
    strategy_id = Column(Integer, ForeignKey("research.strategies.id"))
    symbol      = Column(String(20))
    start_date  = Column(Date)
    end_date    = Column(Date)
    scenario    = Column(String(20), default="standard")
    data_source = Column(String(50))
    created_at  = Column(DateTime, default=datetime.utcnow)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = {"schema": "research"}

    id                 = Column(BigInteger, primary_key=True)
    trade_id           = Column(String(150), unique=True, nullable=False)
    run_id             = Column(String(100), ForeignKey("research.replay_runs.run_id"))
    strategy_id        = Column(Integer, ForeignKey("research.strategies.id"))
    symbol             = Column(String(20), nullable=False)
    session            = Column(String(20))
    direction          = Column(String(10))
    setup_type         = Column(String(5), default="A")
    entry_time         = Column(DateTime)
    exit_time          = Column(DateTime)
    entry_price        = Column(Numeric(12, 5))
    stop_price         = Column(Numeric(12, 5))
    take_profit        = Column(Numeric(12, 5))
    tp2_price          = Column(Numeric(12, 5))
    sl_pips            = Column(Numeric(8, 2))
    risk_reward        = Column(Numeric(5, 2))
    spread_cost_pips   = Column(Numeric(8, 2))
    cost_in_r          = Column(Numeric(8, 4))
    gross_result_r     = Column(Numeric(8, 4))
    net_result_r       = Column(Numeric(8, 4))
    exit_reason        = Column(String(30))
    tp1_hit            = Column(Boolean, default=False)
    session_high       = Column(Numeric(12, 5))
    session_low        = Column(Numeric(12, 5))
    session_range_pips = Column(Numeric(8, 2))
    created_at         = Column(DateTime, default=datetime.utcnow)


class TradeFeature(Base):
    __tablename__  = "trade_features"
    __table_args__ = (
        UniqueConstraint("trade_id"),
        {"schema": "research"},
    )

    id                      = Column(BigInteger, primary_key=True)
    trade_id                = Column(String(150), ForeignKey("research.trades.trade_id"))
    bos_present             = Column(Boolean)
    choch_present           = Column(Boolean)
    fvg_present             = Column(Boolean)
    liquidity_sweep_present = Column(Boolean)
    spread_scenario         = Column(String(20))
    feature_json            = Column(JSON)
    created_at              = Column(DateTime, default=datetime.utcnow)


class DailyEquity(Base):
    __tablename__  = "daily_equity"
    __table_args__ = (
        UniqueConstraint("run_id", "date"),
        {"schema": "research"},
    )

    id         = Column(BigInteger, primary_key=True)
    run_id     = Column(String(100), ForeignKey("research.replay_runs.run_id"))
    date       = Column(Date, nullable=False)
    daily_r    = Column(Numeric(8, 4))
    equity_r   = Column(Numeric(10, 4))
    drawdown   = Column(Numeric(8, 6))
    created_at = Column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# analytics schema  ── v2, + 2 previously missing tables (D-03 fix)
# ═══════════════════════════════════════════════════════════════════════════

class StrategyMetric(Base):
    __tablename__ = "strategy_metrics"
    __table_args__ = {"schema": "analytics"}

    id             = Column(Integer, primary_key=True)
    run_id         = Column(String(100), ForeignKey("research.replay_runs.run_id"))
    strategy       = Column(String(100))
    total_trades   = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades  = Column(Integer)
    win_rate       = Column(Numeric(5, 2))
    profit_factor  = Column(Numeric(8, 4))
    expectancy     = Column(Numeric(8, 4))
    average_win    = Column(Numeric(8, 4))
    average_loss   = Column(Numeric(8, 4))
    max_drawdown   = Column(Numeric(8, 4))
    net_r          = Column(Numeric(10, 2))
    created_at     = Column(DateTime, default=datetime.utcnow)


class MonthlyMetric(Base):
    __tablename__ = "monthly_metrics"
    __table_args__ = {"schema": "analytics"}

    id            = Column(Integer, primary_key=True)
    run_id        = Column(String(100), ForeignKey("research.replay_runs.run_id"))
    month         = Column(String(7))
    trades        = Column(Integer)
    win_rate      = Column(Numeric(5, 2))
    profit_factor = Column(Numeric(8, 4))
    net_r         = Column(Numeric(10, 2))
    drawdown      = Column(Numeric(8, 4))
    created_at    = Column(DateTime, default=datetime.utcnow)


class Phase0Gate(Base):
    __tablename__  = "phase0_gate"
    __table_args__ = (
        UniqueConstraint("run_id"),
        {"schema": "analytics"},
    )

    id             = Column(Integer, primary_key=True)
    run_id         = Column(String(100), unique=True, nullable=False)
    symbol         = Column(String(20))
    scenario       = Column(String(20))
    n_trades       = Column(Integer)
    net_pf         = Column(Numeric(8, 4))
    min_trades_req = Column(Integer)
    min_pf_req     = Column(Numeric(8, 4))
    gate_pass      = Column(Boolean)
    evaluated_at   = Column(DateTime, default=datetime.utcnow)
    notes          = Column(Text)


class ExperimentLog(Base):
    """analytics.experiment_log — legacy experiment notes; superseded by experiments.Experiment."""
    __tablename__ = "experiment_log"
    __table_args__ = {"schema": "analytics"}

    id                 = Column(Integer, primary_key=True)
    experiment_name    = Column(String(200))
    hypothesis         = Column(Text)
    change_description = Column(Text)
    result             = Column(Text)
    verdict_log_ref    = Column(String(20))
    created_at         = Column(DateTime, default=datetime.utcnow)


class OptimizationResult(Base):
    """analytics.optimization_results — was in SQL but missing from ORM (D-03 fix)."""
    __tablename__ = "optimization_results"
    __table_args__ = {"schema": "analytics"}

    id              = Column(Integer, primary_key=True)
    strategy_id     = Column(Integer, ForeignKey("research.strategies.id"))
    parameter_name  = Column(String(50))
    parameter_value = Column(Text)
    trade_count     = Column(Integer)
    profit_factor   = Column(Numeric(8, 4))
    expectancy      = Column(Numeric(8, 4))
    max_drawdown    = Column(Numeric(8, 4))
    created_at      = Column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# config schema  ── v2, previously missing from ORM (D-03 fix)
# ═══════════════════════════════════════════════════════════════════════════

class SystemConfig(Base):
    """config.system_config — was in SQL but missing from ORM (D-03 fix)."""
    __tablename__ = "system_config"
    __table_args__ = {"schema": "config"}

    key         = Column(String(100), primary_key=True)
    value       = Column(Text)
    description = Column(Text)
    updated_at  = Column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# strategy schema  ── v3  (canonical identity + immutable versioning)
# ═══════════════════════════════════════════════════════════════════════════

class StrategyEntity(Base):
    """strategy.strategy — canonical UUID-keyed identity record."""
    __tablename__  = "strategy"
    __table_args__ = {"schema": "strategy"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(100), nullable=False, unique=True)
    slug       = Column(String(100), nullable=False, unique=True)
    owner      = Column(String(100))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class StrategyVersion(Base):
    """strategy.version — immutable spec snapshot; new version row on every change."""
    __tablename__  = "version"
    __table_args__ = (
        UniqueConstraint("strategy_id", "version"),
        {"schema": "strategy"},
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id   = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"), nullable=False)
    version       = Column(String(30), nullable=False)
    spec_hash     = Column(String(64), nullable=False)
    parent_id     = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"))
    source_commit = Column(String(40))
    rules_json    = Column(JSONB, nullable=False)
    notes         = Column(Text)
    created_by    = Column(String(100))
    created_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# governance schema  ── v3
# ═══════════════════════════════════════════════════════════════════════════

class StageState(Base):
    """governance.stage_state — one row per strategy; opt_lock prevents concurrent transitions."""
    __tablename__  = "stage_state"
    __table_args__ = {"schema": "governance"}

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id        = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"),
                                nullable=False, unique=True)
    current_stage      = Column(String(50), nullable=False)
    current_version_id = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"))
    opt_lock           = Column(Integer, nullable=False, default=0)
    updated_at         = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_by         = Column(String(100))


class GateDecision(Base):
    """governance.gate_decision — append-only audit of every gate evaluation."""
    __tablename__ = "gate_decision"
    __table_args__ = {"schema": "governance"}

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id    = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"), nullable=False)
    version_id     = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"))
    from_stage     = Column(String(50), nullable=False)
    to_stage       = Column(String(50), nullable=False)
    allowed        = Column(Boolean, nullable=False)
    actor          = Column(String(100), nullable=False)
    reason         = Column(Text)
    blockers       = Column(JSONB, nullable=False, default=list)
    evidence_ids   = Column(JSONB, nullable=False, default=list)
    policy_version = Column(String(20))
    decided_at     = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Approval(Base):
    """governance.approval — named human sign-off for LIVE_DEMO / PRODUCTION gates."""
    __tablename__ = "approval"
    __table_args__ = {"schema": "governance"}

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id      = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"), nullable=False)
    version_id       = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"))
    gate_decision_id = Column(UUID(as_uuid=True), ForeignKey("governance.gate_decision.id"))
    from_stage       = Column(String(50), nullable=False)
    to_stage         = Column(String(50), nullable=False)
    approver         = Column(String(100), nullable=False)
    approver_role    = Column(String(50))
    reason           = Column(Text, nullable=False)
    approved_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    expires_at       = Column(DateTime(timezone=True))
    revoked_at       = Column(DateTime(timezone=True))


class Outbox(Base):
    """governance.outbox — transactional outbox; events written in same txn as stage_state (D-06 fix)."""
    __tablename__ = "outbox"
    __table_args__ = {"schema": "governance"}

    id           = Column(BigInteger, primary_key=True)
    event_type   = Column(String(100), nullable=False)
    strategy_id  = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"))
    payload      = Column(JSONB, nullable=False)
    created_at   = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime(timezone=True))


class StageTransition(Base):
    """governance.stage_transition — immutable committed lifecycle change."""
    __tablename__ = "stage_transition"
    __table_args__ = (
        CheckConstraint("to_revision = from_revision + 1", name="ck_stage_transition_revision"),
        {"schema": "governance"},
    )

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id      = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"), nullable=False)
    version_id       = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"), nullable=False)
    gate_decision_id = Column(UUID(as_uuid=True), ForeignKey("governance.gate_decision.id"), nullable=False, unique=True)
    from_stage       = Column(String(50), nullable=False)
    to_stage         = Column(String(50), nullable=False)
    from_revision    = Column(Integer, nullable=False)
    to_revision      = Column(Integer, nullable=False)
    actor            = Column(String(100), nullable=False)
    reason           = Column(Text, nullable=False)
    transitioned_at  = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# evidence schema  ── v3
# ═══════════════════════════════════════════════════════════════════════════

class Artifact(Base):
    """evidence.artifact — content-addressed report file (sha256 = integrity anchor)."""
    __tablename__ = "artifact"
    __table_args__ = {"schema": "evidence"}

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id    = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"), nullable=False)
    stage          = Column(String(50), nullable=False)
    report_type    = Column(String(100), nullable=False)
    uri            = Column(Text, nullable=False)
    sha256         = Column(String(64), nullable=False)
    media_type     = Column(String(100))
    size_bytes     = Column(BigInteger)
    schema_version = Column(String(20))
    recorded_by    = Column(String(100))
    recorded_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ArtifactBinding(Base):
    """evidence.binding — links artifact to (strategy version, run, stage)."""
    __tablename__ = "binding"
    __table_args__ = {"schema": "evidence"}

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"), nullable=False)
    version_id  = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"))
    run_id      = Column(UUID(as_uuid=True))
    stage       = Column(String(50), nullable=False)
    artifact_id = Column(UUID(as_uuid=True), ForeignKey("evidence.artifact.id"), nullable=False)
    status      = Column(String(20), nullable=False, default="active")
    trust       = Column(String(30), nullable=False, default="LEGACY_IMPORTED")
    bound_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    invalidated_at = Column(DateTime(timezone=True))
    invalidation_reason = Column(Text)


class ReportRecord(Base):
    """evidence.report_record — queryable immutable report identity and lineage."""
    __tablename__ = "report_record"
    __table_args__ = {"schema": "evidence"}

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id            = Column(String(200), nullable=False, unique=True)
    strategy_id          = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"), nullable=False)
    version_id           = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"), nullable=False)
    run_id               = Column(UUID(as_uuid=True), ForeignKey("research.run.id"))
    stage                = Column(String(50), nullable=False)
    report_type          = Column(String(100), nullable=False)
    status               = Column(String(20), nullable=False)
    trust                = Column(String(30), nullable=False)
    json_artifact_id     = Column(UUID(as_uuid=True), ForeignKey("evidence.artifact.id"), nullable=False)
    markdown_artifact_id = Column(UUID(as_uuid=True), ForeignKey("evidence.artifact.id"))
    schema_version       = Column(String(20), nullable=False)
    generator_version    = Column(String(40), nullable=False)
    created_at           = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class LegacyImport(Base):
    """evidence.legacy_import — idempotent import ledger."""
    __tablename__ = "legacy_import"
    __table_args__ = (
        UniqueConstraint("source_path", "source_sha256", "record_type", name="uq_legacy_import_source"),
        {"schema": "evidence"},
    )

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_path      = Column(Text, nullable=False)
    source_sha256    = Column(String(64), nullable=False)
    source_timestamp = Column(DateTime(timezone=True))
    record_type      = Column(String(50), nullable=False)
    record_count     = Column(Integer, nullable=False, default=0)
    imported_by      = Column(String(100), nullable=False)
    imported_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# research schema  ── v3 additions (legacy v2 tables kept above)
# ═══════════════════════════════════════════════════════════════════════════

class Run(Base):
    """research.run — UUID-keyed run with full provenance; supersedes ReplayRun for new code."""
    __tablename__ = "run"
    __table_args__ = {"schema": "research"}

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id           = Column(String(100), unique=True, nullable=False)
    strategy_id      = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"))
    version_id       = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"))
    strategy_name    = Column(String(100))
    symbol           = Column(String(20))
    start_date       = Column(Date)
    end_date         = Column(Date)
    scenario         = Column(String(20), nullable=False, default="standard")
    code_commit      = Column(String(40))
    env_hash         = Column(String(64))
    dataset_snapshot = Column(String(64))
    seed             = Column(Integer)
    parameters       = Column(JSONB)
    status           = Column(String(20), nullable=False, default="pending")
    started_at       = Column(DateTime(timezone=True))
    completed_at     = Column(DateTime(timezone=True))
    created_at       = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Metric(Base):
    """research.metric — typed metric store; all run output dimensions in one table."""
    __tablename__  = "metric"
    __table_args__ = (
        UniqueConstraint("run_id", "metric_name", "window"),
        {"schema": "research"},
    )

    id          = Column(BigInteger, primary_key=True)
    run_id      = Column(UUID(as_uuid=True), ForeignKey("research.run.id"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    value       = Column(Numeric(14, 6), nullable=False)
    unit        = Column(String(30))
    window      = Column(String(50))
    created_at  = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# analytics schema  ── v3 addition
# ═══════════════════════════════════════════════════════════════════════════

class StageGate(Base):
    """analytics.stage_gate — per-stage gate verdict; generalises the Phase0Gate specialisation."""
    __tablename__ = "stage_gate"
    __table_args__ = {"schema": "analytics"}

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id       = Column(UUID(as_uuid=True), ForeignKey("research.run.id"))
    strategy_id  = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"))
    stage        = Column(String(50), nullable=False)
    scenario     = Column(String(20))
    n_trades     = Column(Integer)
    metrics      = Column(JSONB)
    gate_pass    = Column(Boolean, nullable=False)
    blockers     = Column(JSONB, nullable=False, default=list)
    evaluated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    notes        = Column(Text)


# ═══════════════════════════════════════════════════════════════════════════
# experiments schema  ── v3
# ═══════════════════════════════════════════════════════════════════════════

class Experiment(Base):
    """experiments.experiment — pre-registration registry (CLAUDE.md §7 mandate)."""
    __tablename__ = "experiment"
    __table_args__ = {"schema": "experiments"}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exp_id          = Column(String(50), unique=True, nullable=False)
    strategy_id     = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"))
    version_id      = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"))
    title           = Column(String(200), nullable=False)
    hypothesis      = Column(Text)
    instrument      = Column(String(20))
    dataset_version = Column(String(64))
    feature_set     = Column(JSONB)
    parameters      = Column(JSONB)
    status          = Column(String(20), nullable=False, default="pending")
    verdict         = Column(String(20))
    verdict_reason  = Column(Text)
    created_by      = Column(String(100))
    created_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    concluded_at    = Column(DateTime(timezone=True))


class ParameterSet(Base):
    """experiments.parameter_set — immutable parameter snapshot; one per scenario."""
    __tablename__ = "parameter_set"
    __table_args__ = {"schema": "experiments"}

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiments.experiment.id"), nullable=False)
    label         = Column(String(100))
    parameters    = Column(JSONB, nullable=False)
    created_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ExperimentResultBinding(Base):
    """experiments.result_binding — links experiment to its run results and evidence."""
    __tablename__ = "result_binding"
    __table_args__ = {"schema": "experiments"}

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiments.experiment.id"), nullable=False)
    run_id        = Column(UUID(as_uuid=True), ForeignKey("research.run.id"))
    stage         = Column(String(50), nullable=False)
    verdict       = Column(String(20))
    artifact_id   = Column(UUID(as_uuid=True), ForeignKey("evidence.artifact.id"))
    bound_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# robustness schema  ── v3
# ═══════════════════════════════════════════════════════════════════════════

class WalkForwardResult(Base):
    """robustness.walk_forward_result — one row per fold."""
    __tablename__  = "walk_forward_result"
    __table_args__ = (
        UniqueConstraint("run_id", "fold_index"),
        {"schema": "robustness"},
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id        = Column(UUID(as_uuid=True), ForeignKey("research.run.id"), nullable=False)
    fold_index    = Column(Integer, nullable=False)
    train_start   = Column(Date, nullable=False)
    train_end     = Column(Date, nullable=False)
    test_start    = Column(Date, nullable=False)
    test_end      = Column(Date, nullable=False)
    n_trades      = Column(Integer)
    profit_factor = Column(Numeric(8, 4))
    win_rate      = Column(Numeric(5, 2))
    net_r         = Column(Numeric(10, 2))
    max_drawdown  = Column(Numeric(8, 4))
    gate_pass     = Column(Boolean)
    created_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class MonteCarloResult(Base):
    """robustness.monte_carlo_result — summary statistics from MC simulation."""
    __tablename__ = "monte_carlo_result"
    __table_args__ = {"schema": "robustness"}

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id           = Column(UUID(as_uuid=True), ForeignKey("research.run.id"), nullable=False)
    n_simulations    = Column(Integer, nullable=False)
    percentile_5_pf  = Column(Numeric(8, 4))
    percentile_25_pf = Column(Numeric(8, 4))
    median_pf        = Column(Numeric(8, 4))
    percentile_75_pf = Column(Numeric(8, 4))
    percentile_95_pf = Column(Numeric(8, 4))
    ruin_probability = Column(Numeric(6, 4))
    max_dd_p95       = Column(Numeric(8, 4))
    gate_pass        = Column(Boolean)
    created_at       = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class SensitivityResult(Base):
    """robustness.sensitivity_result — one row per parameter/value sweep point."""
    __tablename__ = "sensitivity_result"
    __table_args__ = {"schema": "robustness"}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id          = Column(UUID(as_uuid=True), ForeignKey("research.run.id"), nullable=False)
    parameter_name  = Column(String(100), nullable=False)
    parameter_value = Column(Text, nullable=False)
    n_trades        = Column(Integer)
    profit_factor   = Column(Numeric(8, 4))
    net_r           = Column(Numeric(10, 2))
    max_drawdown    = Column(Numeric(8, 4))
    created_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# execution schema  ── v3
# ═══════════════════════════════════════════════════════════════════════════

class VirtualOrder(Base):
    """execution.virtual_order — order lifecycle record for virtual-demo runs."""
    __tablename__ = "virtual_order"
    __table_args__ = {"schema": "execution"}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id          = Column(UUID(as_uuid=True), ForeignKey("research.run.id"))
    symbol          = Column(String(20), nullable=False)
    direction       = Column(String(10), nullable=False)
    requested_price = Column(Numeric(12, 5))
    filled_price    = Column(Numeric(12, 5))
    slippage_pips   = Column(Numeric(8, 4))
    latency_ms      = Column(Integer)
    status          = Column(String(20), nullable=False)
    reason          = Column(Text)
    ordered_at      = Column(DateTime(timezone=True), nullable=False)
    filled_at       = Column(DateTime(timezone=True))
    created_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class VirtualFill(Base):
    """execution.virtual_fill — individual fill event against a virtual order."""
    __tablename__ = "virtual_fill"
    __table_args__ = {"schema": "execution"}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id        = Column(UUID(as_uuid=True), ForeignKey("execution.virtual_order.id"), nullable=False)
    symbol          = Column(String(20), nullable=False)
    direction       = Column(String(10), nullable=False)
    requested_price = Column(Numeric(12, 5))
    filled_price    = Column(Numeric(12, 5))
    slippage_pips   = Column(Numeric(8, 4))
    latency_ms      = Column(Integer)
    execution_time  = Column(DateTime(timezone=True), nullable=False)
    created_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class VirtualPosition(Base):
    """execution.virtual_position — full open→close lifecycle of a virtual position."""
    __tablename__ = "virtual_position"
    __table_args__ = {"schema": "execution"}

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id         = Column(UUID(as_uuid=True), ForeignKey("execution.virtual_order.id"), nullable=False)
    run_id           = Column(UUID(as_uuid=True), ForeignKey("research.run.id"))
    symbol           = Column(String(20), nullable=False)
    direction        = Column(String(10), nullable=False)
    entry_price      = Column(Numeric(12, 5), nullable=False)
    exit_price       = Column(Numeric(12, 5))
    sl_price         = Column(Numeric(12, 5))
    tp_price         = Column(Numeric(12, 5))
    spread_cost_pips = Column(Numeric(8, 4))
    gross_profit_r   = Column(Numeric(8, 4))
    net_profit_r     = Column(Numeric(8, 4))
    duration_seconds = Column(Numeric(12, 2))
    exit_reason      = Column(String(50))
    opened_at        = Column(DateTime(timezone=True), nullable=False)
    closed_at        = Column(DateTime(timezone=True))
    created_at       = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class DriftObservation(Base):
    """execution.drift_observation — backtest expectation vs live execution comparison."""
    __tablename__ = "drift_observation"
    __table_args__ = {"schema": "execution"}

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id             = Column(UUID(as_uuid=True), ForeignKey("research.run.id"))
    observation_time   = Column(DateTime(timezone=True), nullable=False)
    symbol             = Column(String(20), nullable=False)
    expected_direction = Column(String(10))
    actual_direction   = Column(String(10))
    expected_entry     = Column(Numeric(12, 5))
    actual_entry       = Column(Numeric(12, 5))
    slippage_pips      = Column(Numeric(8, 4))
    latency_ms         = Column(Integer)
    verdict            = Column(String(20))
    created_at         = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# operations schema  ── v3
# ═══════════════════════════════════════════════════════════════════════════

class Deployment(Base):
    """operations.deployment — record of each demo or live deployment."""
    __tablename__ = "deployment"
    __table_args__ = {"schema": "operations"}

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id       = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"), nullable=False)
    version_id        = Column(UUID(as_uuid=True), ForeignKey("strategy.version.id"))
    environment       = Column(String(30), nullable=False)
    broker            = Column(String(50))
    account_id        = Column(String(100))
    status            = Column(String(20), nullable=False, default="active")
    deployed_by       = Column(String(100))
    deployed_at       = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    decommissioned_at = Column(DateTime(timezone=True))


class Incident(Base):
    """operations.incident — production or demo incident log."""
    __tablename__ = "incident"
    __table_args__ = {"schema": "operations"}

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("operations.deployment.id"))
    strategy_id   = Column(UUID(as_uuid=True), ForeignKey("strategy.strategy.id"))
    severity      = Column(String(10), nullable=False)
    title         = Column(String(200), nullable=False)
    description   = Column(Text)
    status        = Column(String(20), nullable=False, default="open")
    opened_at     = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    resolved_at   = Column(DateTime(timezone=True))
    resolution    = Column(Text)


# ═══════════════════════════════════════════════════════════════════════════
# operations schema (migration 004) ── System 2 execution recording
# Added Sprint 2.3 (SYSTEM2_MASTER_PLAN.md Phase 2): the migration already
# existed (`db/migrations/versions/004_system2_operations.py`) but had no ORM
# layer. Each table is a typed key column or two plus a JSONB `payload` for
# everything else — mirrors the migration's `_record()` helper exactly.
# ═══════════════════════════════════════════════════════════════════════════

class Runtime(Base):
    """operations.runtime — one row per runner process start."""
    __tablename__ = "runtime"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runtime_id = Column(String(100), nullable=False)
    status     = Column(String(30), nullable=False)
    payload    = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class MarketDataHealth(Base):
    """operations.market_data_health — price feed health checks."""
    __tablename__ = "market_data_health"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol     = Column(String(20), nullable=False)
    status     = Column(String(30), nullable=False)
    payload    = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Intent(Base):
    """operations.intent — strategy intent, one row per ExecutionIntent submitted."""
    __tablename__ = "intent"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intent_id  = Column(String(150), nullable=False, unique=True)
    symbol     = Column(String(20), nullable=False)
    payload    = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class RiskDecision(Base):
    """operations.risk_decision — risk engine approval/rejection, keyed by intent_id."""
    __tablename__ = "risk_decision"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intent_id  = Column(String(150), nullable=False)
    approved   = Column(Boolean, nullable=False)
    payload    = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class OrderRecord(Base):
    """operations.order_record — order lifecycle; idempotency_key prevents duplicate rows
    for the same submission (Sprint 2.3 "no duplicate order" requirement)."""
    __tablename__ = "order_record"
    __table_args__ = {"schema": "operations"}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id        = Column(String(150))
    idempotency_key = Column(String(200), nullable=False, unique=True)
    status          = Column(String(40), nullable=False)
    payload         = Column(JSONB, nullable=False, default=dict)
    created_at      = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Fill(Base):
    """operations.fill — broker fill result, keyed by order_id."""
    __tablename__ = "fill"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id   = Column(String(150), nullable=False)
    status     = Column(String(40), nullable=False)
    payload    = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class PositionRecord(Base):
    """operations.position_record — current/recent position state snapshot."""
    __tablename__ = "position_record"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol     = Column(String(20), nullable=False)
    status     = Column(String(40), nullable=False)
    payload    = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Reconciliation(Base):
    """operations.reconciliation — periodic broker-truth vs. local-state comparison."""
    __tablename__ = "reconciliation"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runtime_id = Column(String(100), nullable=False)
    consistent = Column(Boolean, nullable=False)
    payload    = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class RecoveryCheckpoint(Base):
    """operations.recovery_checkpoint — one row per ExecutionRecord resolved by
    execution/startup_recovery.py::reconcile_pending_executions() after a restart."""
    __tablename__ = "recovery_checkpoint"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runtime_id = Column(String(100), nullable=False)
    state      = Column(JSONB, nullable=False)
    payload    = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ExecutionEvent(Base):
    """operations.execution_event — generic append-only log of every
    CanonicalExecutionPipeline NormalizedExecutionEvent."""
    __tablename__ = "execution_event"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(80), nullable=False)
    payload    = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class RiskPortfolioState(Base):
    """operations.risk_portfolio_state — current risk/portfolio state, upserted
    atomically per (state_type, period_date).  Migration 005; replaces the
    JSON-file persistence from SYSTEM2_MASTER_PLAN.md Phase 1."""
    __tablename__  = "risk_portfolio_state"
    __table_args__ = (
        UniqueConstraint("state_type", "period_date",
                         name="uq_risk_portfolio_state_type_date"),
        {"schema": "operations"},
    )

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runtime_id  = Column(String(100), nullable=False)
    state_type  = Column(String(20), nullable=False)
    state_data  = Column(JSONB, nullable=False)
    period_date = Column(Date, nullable=False)
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class RiskPortfolioHistory(Base):
    """operations.risk_portfolio_history — append-only audit trail of significant
    risk/portfolio state changes (trade_close, daily_reset, startup_restore)."""
    __tablename__ = "risk_portfolio_history"
    __table_args__ = {"schema": "operations"}

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runtime_id = Column(String(100), nullable=False)
    state_type = Column(String(20), nullable=False)
    event      = Column(String(50), nullable=False)
    state_data = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ValidationSession(Base):
    """operations.validation_session — one row per Demo Validation Mode campaign.

    Distinct from operations.runtime (one row per process start): a
    validation session must survive runner restarts, so it carries its own
    identity/lifecycle rather than being derived from a process's runtime_id.
    Migration 006."""
    __tablename__  = "validation_session"
    __table_args__ = {"schema": "operations"}

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id       = Column(String(100), nullable=False, unique=True)
    operator         = Column(String(100), nullable=False)
    broker           = Column(String(50), nullable=False)
    account          = Column(String(100), nullable=False)
    software_version = Column(String(100), nullable=False)
    git_commit       = Column(String(64), nullable=False)
    config_hash      = Column(String(64), nullable=False)
    status           = Column(String(20), nullable=False)
    started_at       = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    ended_at         = Column(DateTime(timezone=True), nullable=True)


class ValidationLifecycleEvent(Base):
    """operations.validation_lifecycle_event — per-trade, per-stage timing and
    status for a Demo Validation Mode session (signal -> ... -> trade_archive).
    Migration 006."""
    __tablename__  = "validation_lifecycle_event"
    __table_args__ = {"schema": "operations"}

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    validation_session_id = Column(String(100), nullable=False)
    trade_id              = Column(String(150), nullable=False)
    stage                 = Column(String(50), nullable=False)
    status                = Column(String(20), nullable=False)
    duration_ms           = Column(Float, nullable=True)
    error                 = Column(Text, nullable=True)
    metadata_             = Column("metadata", JSONB, nullable=False, default=dict)
    created_at            = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
