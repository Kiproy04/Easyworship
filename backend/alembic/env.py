"""
alembic/env.py
Wired to the async SQLAlchemy engine and all models.

IMPORTANT — async bridge:
  Alembic is synchronous by default. Since we use create_async_engine,
  we use engine.sync_engine to give Alembic a sync connection to work with.
  This is the official recommended pattern for async SQLAlchemy + Alembic.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# ── Make sure app is importable from here ────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Import settings and Base (Base import pulls in all models) ────────────────
from app.config import settings
from app.db.base import Base  # noqa: F401 — all models are imported inside base.py

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

# Override the sqlalchemy.url with our settings value
config.set_main_option("sqlalchemy.url", settings.DATABASE_SYNC_URL) 

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what Alembic inspects to detect table changes
target_metadata = Base.metadata


# ── Offline mode (generates SQL without connecting) ───────────────────────────
def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Useful for generating a SQL script to review before applying.
    Run with: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,       # detect column type changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (connects to DB and runs migrations) ──────────────────────────
def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations against a live DB.
    Uses the async engine but bridges to sync via .sync_engine
    — the official pattern for async SQLAlchemy + Alembic.
    """
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,  # don't pool — migrations are one-shot
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())