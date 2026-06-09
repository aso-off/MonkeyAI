import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool

_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from db.db import Base  # noqa: E402
import db.models.user  # noqa: E402,F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    from core.config import settings

    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection", None)
    if connection is not None:
        _do_run_migrations(connection)
        return

    import asyncio

    from sqlalchemy.ext.asyncio import async_engine_from_config

    from core.config import settings

    async def _run() -> None:
        section = config.get_section(config.config_ini_section) or {}
        section["sqlalchemy.url"] = settings.database_url
        engine = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
        async with engine.connect() as conn:
            await conn.run_sync(_do_run_migrations)
        await engine.dispose()

    asyncio.run(_run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
