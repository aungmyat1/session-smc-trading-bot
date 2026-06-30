"""
db/connection.py
SQLAlchemy engine + session factory.

DATABASE_URL env var overrides the default (useful for CI or Docker).
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool

from db.runtime import resolve_database_url


class Base(DeclarativeBase):
    pass


_URL = resolve_database_url()
engine = (
    create_engine(
        _URL,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    if _URL
    else None
)
SessionLocal = (
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
    if engine is not None
    else None
)


def get_db():
    """FastAPI / script dependency — yields a session, closes on exit."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is required before opening a database session")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
