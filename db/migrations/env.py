"""
db/migrations/env.py
Alembic environment — reads DATABASE_URL from environment/.env,
imports db.models to give autogenerate full schema awareness.
"""
# ruff: noqa: E402
from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure project root is on sys.path so `db` package resolves.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# Load .env so DATABASE_URL is available without exporting it in the shell.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Import all models so autogenerate sees every table across every schema.
# This also validates that models.py itself is importable.
from db.connection import Base  # noqa: F401  (registers DeclarativeBase)
import db.models  # noqa: F401  (registers all 39 mapped classes)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override the sqlalchemy.url from the environment — never commit credentials.
_db_url = os.environ.get("DATABASE_URL", "")
if _db_url.startswith("postgresql+asyncpg://"):
    _db_url = _db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
if _db_url:
    # Alembic stores this value in ConfigParser, where a literal percent is
    # interpolation syntax. Escaping prevents credential disclosure through a
    # ConfigParser exception while preserving the URL returned to SQLAlchemy.
    config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

# Schemas that autogenerate should inspect.
# Every schema declared in schema_v2.sql and schema_v3.sql must be listed.
_INCLUDE_SCHEMAS = {
    "market", "research", "analytics", "config",
    "strategy", "governance", "evidence",
    "experiments", "robustness", "execution", "operations",
}


def include_object(object, name, type_, reflected, compare_to):
    """Filter autogenerate to only touch tables in our declared schemas."""
    if type_ == "table":
        schema = getattr(object, "schema", None) or ""
        return schema in _INCLUDE_SCHEMAS
    return True


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
