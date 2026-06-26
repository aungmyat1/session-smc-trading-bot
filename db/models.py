"""
db/models.py
SQLAlchemy ORM models — mirrors db/schema_v2.sql exactly.
"""
from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey,
    Integer, JSON, Numeric, String, Text, UniqueConstraint,
)
from .connection import Base


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
    asian_range_pips = Column(Numeric(8, 2),  nullable=False)
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
    session_range_pips = Column(Numeric(8, 2),  nullable=False)
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


class Strategy(Base):
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
    strategy_id        = Column(Integer,     ForeignKey("research.strategies.id"))

    symbol             = Column(String(20), nullable=False)
    session            = Column(String(20))
    direction          = Column(String(10))
    setup_type         = Column(String(5), default="A")

    entry_time         = Column(DateTime)
    exit_time          = Column(DateTime)
    entry_price        = Column(Numeric(12, 5))
    stop_price         = Column(Numeric(12, 5))
    take_profit        = Column(Numeric(12, 5))   # TP1
    tp2_price          = Column(Numeric(12, 5))
    sl_pips            = Column(Numeric(8, 2))
    risk_reward        = Column(Numeric(5, 2))

    spread_cost_pips   = Column(Numeric(8, 2))
    cost_in_r          = Column(Numeric(8, 4))
    gross_result_r     = Column(Numeric(8, 4))
    net_result_r       = Column(Numeric(8, 4))    # use this for all P&L analysis
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
    __tablename__ = "experiment_log"
    __table_args__ = {"schema": "analytics"}

    id                 = Column(Integer, primary_key=True)
    experiment_name    = Column(String(200))
    hypothesis         = Column(Text)
    change_description = Column(Text)
    result             = Column(Text)
    verdict_log_ref    = Column(String(20))
    created_at         = Column(DateTime, default=datetime.utcnow)
