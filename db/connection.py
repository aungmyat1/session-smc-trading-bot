"""
db/connection.py
SQLAlchemy engine + session factory.

DATABASE_URL env var overrides the default (useful for CI or Docker).
"""
from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool

_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://trading_user:trading_research_2025@localhost:5432/trading_research",
)

engine = create_engine(
    _URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI / script dependency — yields a session, closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
