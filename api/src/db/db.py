from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session():
    """FastAPI dependency — yields an async DB session."""
    async with Session() as session:
        yield session


async def init_db() -> None:
    from db.models.user import Dialog, MessageReaction, User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for col, definition in [
            ("is_admin", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("is_whitelisted", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("current_dialog_ids", "JSON NOT NULL DEFAULT '{}'"),
            ("theme", "VARCHAR(16) NOT NULL DEFAULT 'system'"),
            ("mini_app_chat_mode", "VARCHAR(64) NOT NULL DEFAULT 'mini_app_assistant'"),
            ("mini_app_dialog_ids", "JSON NOT NULL DEFAULT '{}'"),
        ]:
            await conn.exec_driver_sql(
                f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {definition}"
            )
