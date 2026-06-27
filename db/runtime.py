"""Database runtime helpers shared across sync PostgreSQL entry points."""

from __future__ import annotations

import os


def load_env() -> None:
    """Load `.env` when available so scripts and modules share the same config."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def normalize_database_url(url: str | None) -> str:
    """Convert async SQLAlchemy URLs to the sync form expected by psycopg2."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return url


def resolve_database_url(default: str = "") -> str:
    """Return a normalized DATABASE_URL from the process environment."""
    load_env()
    return normalize_database_url(os.getenv("DATABASE_URL", default))
