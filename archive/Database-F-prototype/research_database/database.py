"""
research_database/database.py
Core database connection and session management using SQLAlchemy.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://trading_user:trading_research_2025@localhost:5432/trading_research",
)

engine = create_engine(
    DATABASE_URL, poolclass=QueuePool, pool_size=10, max_overflow=20, pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI or scripts."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
