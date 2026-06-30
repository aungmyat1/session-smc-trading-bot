"""
research_database/api.py
High-level research database API (save/query functions).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from .models import ReplayRun, SmcEvent, StrategyMetric, Trade


def save_trade(db: Session, trade_data: dict):
    """Save a single simulated trade."""
    trade = Trade(**trade_data)
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def save_replay_run(db: Session, run_data: dict):
    """Save a replay experiment run."""
    run = ReplayRun(**run_data)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def save_smc_event(db: Session, event_data: dict):
    """Save an SMC event."""
    event = SmcEvent(**event_data)
    db.add(event)
    db.commit()
    return event


def get_strategy_metrics(db: Session, run_id: str):
    """Get performance metrics for a replay run."""
    return db.query(StrategyMetric).filter(StrategyMetric.run_id == run_id).all()


def compare_strategies(db: Session, strategy_ids: list):
    """Compare multiple strategies."""
    return (
        db.query(StrategyMetric).filter(StrategyMetric.strategy.in_(strategy_ids)).all()
    )
