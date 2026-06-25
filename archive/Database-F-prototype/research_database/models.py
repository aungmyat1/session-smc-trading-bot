"""
research_database/models.py
SQLAlchemy ORM models for trading_research database.
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, JSON, Date, BigInteger
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = {"schema": "market"}

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), unique=True, nullable=False)
    asset_type = Column(String(20))
    broker_symbol = Column(String(30))
    base_currency = Column(String(10))
    quote_currency = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = {"schema": "market"}

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Numeric(12, 5))
    high = Column(Numeric(12, 5))
    low = Column(Numeric(12, 5))
    close = Column(Numeric(12, 5))
    volume = Column(BigInteger)
    bid = Column(Numeric(12, 5))
    ask = Column(Numeric(12, 5))
    spread = Column(Numeric(8, 5))
    source = Column(String(30))
    created_at = Column(DateTime, default=datetime.utcnow)


class SmcEvent(Base):
    __tablename__ = "smc_events"
    __table_args__ = {"schema": "market"}

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10))
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String(30), nullable=False)
    event_price = Column(Numeric(12, 5))
    strength_score = Column(Numeric(5, 2))
    metadata_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class Strategy(Base):
    __tablename__ = "strategies"
    __table_args__ = {"schema": "research"}

    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(100), nullable=False)
    version = Column(String(20))
    description = Column(String)
    rules_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="active")


class ReplayRun(Base):
    __tablename__ = "replay_runs"
    __table_args__ = {"schema": "research"}

    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), unique=True, nullable=False)
    strategy_id = Column(Integer, ForeignKey("research.strategies.id"))
    symbol = Column(String(20))
    start_date = Column(Date)
    end_date = Column(Date)
    data_source = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = {"schema": "research"}

    id = Column(BigInteger, primary_key=True)
    trade_id = Column(String(50), unique=True, nullable=False)
    run_id = Column(String(50), ForeignKey("research.replay_runs.run_id"))
    strategy_id = Column(Integer, ForeignKey("research.strategies.id"))

    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10))
    session = Column(String(20))
    direction = Column(String(10))

    entry_time = Column(DateTime)
    exit_time = Column(DateTime)

    entry_price = Column(Numeric(12, 5))
    stop_price = Column(Numeric(12, 5))
    take_profit = Column(Numeric(12, 5))
    risk_reward = Column(Numeric(5, 2))

    result_r = Column(Numeric(8, 2))
    profit_loss = Column(Numeric(12, 2))

    exit_reason = Column(String(30))
    spread = Column(Numeric(8, 5))
    market_condition = Column(String(30))
    entry_reason = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)


class TradeFeature(Base):
    __tablename__ = "trade_features"
    __table_args__ = {"schema": "research"}

    id = Column(BigInteger, primary_key=True)
    trade_id = Column(String(50), ForeignKey("research.trades.trade_id"))

    bos_present = Column(Boolean)
    choch_present = Column(Boolean)
    fvg_present = Column(Boolean)
    liquidity_sweep_present = Column(Boolean)

    fvg_size = Column(Numeric(8, 5))
    bos_strength = Column(Numeric(5, 2))
    sweep_distance = Column(Numeric(8, 5))

    feature_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyEquity(Base):
    __tablename__ = "daily_equity"
    __table_args__ = {"schema": "research"}

    id = Column(BigInteger, primary_key=True)
    run_id = Column(String(50), ForeignKey("research.replay_runs.run_id"))
    date = Column(Date, nullable=False)
    starting_balance = Column(Numeric(15, 2))
    ending_balance = Column(Numeric(15, 2))
    daily_r = Column(Numeric(8, 2))
    drawdown = Column(Numeric(8, 4))
    created_at = Column(DateTime, default=datetime.utcnow)


class StrategyMetric(Base):
    __tablename__ = "strategy_metrics"
    __table_args__ = {"schema": "analytics"}

    id = Column(Integer, primary_key=True)
    run_id = Column(String(50))
    strategy = Column(String(100))
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    win_rate = Column(Numeric(5, 2))
    profit_factor = Column(Numeric(8, 2))
    expectancy = Column(Numeric(8, 2))
    average_win = Column(Numeric(8, 2))
    average_loss = Column(Numeric(8, 2))
    max_drawdown = Column(Numeric(8, 4))
    net_r = Column(Numeric(10, 2))
    created_at = Column(DateTime, default=datetime.utcnow)