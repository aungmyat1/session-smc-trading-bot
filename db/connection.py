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

from db.runtime import resolve_database_url

_URL = resolve_database_url()
if not _URL:
    raise RuntimeError(
        "DATABASE_URL is required for db.connection; set it explicitly instead of relying on a localhost fallback"
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
