from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

ALEMBIC_INI = "/app/alembic.ini"


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session():
    """FastAPI dependency — yields an async DB session."""
    async with Session() as session:
        yield session


def _alembic_config():
    from alembic.config import Config

    ini = ALEMBIC_INI if Path(ALEMBIC_INI).exists() else str(
        Path(__file__).resolve().parents[2] / "alembic.ini"
    )
    return Config(ini)


def _run_migrations(connection) -> None:
    from alembic import command

    cfg = _alembic_config()
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


async def init_db() -> None:
    from db.models.user import Dialog, Reaction, User, UserState, UserStatistics  # noqa: F401

    async with engine.connect() as conn:
        await conn.run_sync(_run_migrations)
