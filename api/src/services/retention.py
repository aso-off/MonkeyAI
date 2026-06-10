import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logger import logger
from db.db import Session
from db.models.user import Dialog, Reaction


async def _purge(session: AsyncSession, model, pk_col, time_col, cutoff, batch_size: int) -> int:
    total = 0
    while True:
        ids = (
            await session.execute(select(pk_col).where(time_col < cutoff).limit(batch_size))
        ).scalars().all()
        if not ids:
            break
        await session.execute(delete(model).where(pk_col.in_(ids)))
        await session.commit()
        total += len(ids)
        if len(ids) < batch_size:
            break
    return total


async def cleanup_dialogs(session: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_dialogs_inactive_days)
    return await _purge(
        session, Dialog, Dialog.id, Dialog.last_activity, cutoff, settings.retention_batch_size
    )


async def cleanup_reactions(session: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_reactions_days)
    return await _purge(
        session, Reaction, Reaction.id, Reaction.created_at, cutoff, settings.retention_batch_size
    )


async def run_once() -> tuple[int, int]:
    async with Session() as session:
        n_dialogs = await cleanup_dialogs(session)
        n_reactions = await cleanup_reactions(session)
    logger.info("Retention: removed %d dialogs, %d reactions", n_dialogs, n_reactions)
    return n_dialogs, n_reactions


async def retention_loop() -> None:
    interval = settings.retention_interval_hours * 3600
    await asyncio.sleep(60)  # не блокируем старт
    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Retention run failed")
        await asyncio.sleep(interval)
