from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import GeneratedImage


async def add_generated_image(
    session: AsyncSession, user_id: int, dialog_id: str, url: str, prompt: str
) -> None:
    session.add(
        GeneratedImage(user_id=user_id, dialog_id=dialog_id, url=url, prompt=(prompt or "")[:2000])
    )
    await session.commit()


async def list_images(
    session: AsyncSession,
    user_id: int,
    before: datetime | None = None,
    limit: int = 30,
) -> list[GeneratedImage]:
    q = select(GeneratedImage).where(GeneratedImage.user_id == user_id)
    if before is not None:
        q = q.where(GeneratedImage.created_at < before)
    q = q.order_by(GeneratedImage.created_at.desc()).limit(limit)
    return list((await session.execute(q)).scalars().all())