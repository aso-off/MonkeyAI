from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models.user import User, UserState, UserStatistics

_STATE_COLS = frozenset({
    "current_dialog_id", "current_dialog_ids", "current_chat_mode",
    "mini_app_chat_mode", "mini_app_dialog_ids", "current_model", "theme",
})
_STATS_COLS = frozenset({
    "n_used_tokens", "n_generated_images", "n_transcribed_seconds", "last_updated",
})


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def is_user_admin(session: AsyncSession, user_id: int) -> bool:
    db_user = await get_user(session, user_id)
    if db_user is not None:
        return db_user.is_admin
    return user_id in settings.admin_ids


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    chat_id: int,
    username: str = "",
    first_name: str = "",
    last_name: str = "",
    language: str = "system",
) -> tuple[User, bool]:
    user = await get_user(session, user_id)
    if user is not None:
        return user, False

    text_models = settings.models.get("available_text_models", [])
    default_model = text_models[0] if text_models else ""

    user = User(
        id=user_id,
        chat_id=chat_id,
        username=username or None,
        first_name=first_name,
        last_name=last_name or None,
        language=language,
        is_admin=user_id in settings.admin_ids,
        is_whitelisted=user_id in settings.allowed_user_ids,
        state=UserState(current_model=default_model),
        statistics=UserStatistics(),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # Another concurrent request already inserted this user — roll back and fetch.
        await session.rollback()
        user = await get_user(session, user_id)
        if user is None:
            raise RuntimeError(f"User {user_id} vanished after concurrent insert")
        return user, False
    return user, True


async def update_user(session: AsyncSession, user_id: int, **kwargs) -> None:
    state_vals = {k: v for k, v in kwargs.items() if k in _STATE_COLS}
    stats_vals = {k: v for k, v in kwargs.items() if k in _STATS_COLS}
    user_vals = {k: v for k, v in kwargs.items() if k not in _STATE_COLS and k not in _STATS_COLS}
    if user_vals:
        await session.execute(update(User).where(User.id == user_id).values(**user_vals))
    if state_vals:
        await session.execute(update(UserState).where(UserState.user_id == user_id).values(**state_vals))
    if stats_vals:
        await session.execute(update(UserStatistics).where(UserStatistics.user_id == user_id).values(**stats_vals))
    await session.commit()


async def update_last_interaction(session: AsyncSession, user_id: int, commit: bool = True) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(last_interaction=datetime.now(timezone.utc))
    )
    if commit:
        await session.commit()


async def increment_n_generated_images(session: AsyncSession, user_id: int, count: int) -> None:
    await session.execute(
        update(UserStatistics).where(UserStatistics.user_id == user_id).values(
            n_generated_images=UserStatistics.n_generated_images + count
        )
    )
    await session.commit()


async def increment_n_transcribed_seconds(session: AsyncSession, user_id: int, seconds: float) -> None:
    await session.execute(
        update(UserStatistics).where(UserStatistics.user_id == user_id).values(
            n_transcribed_seconds=UserStatistics.n_transcribed_seconds + seconds
        )
    )
    await session.commit()


async def set_user_admin(session: AsyncSession, user_id: int, is_admin: bool) -> None:
    await session.execute(update(User).where(User.id == user_id).values(is_admin=is_admin))
    await session.commit()


async def set_user_whitelisted(session: AsyncSession, user_id: int, is_whitelisted: bool) -> None:
    await session.execute(update(User).where(User.id == user_id).values(is_whitelisted=is_whitelisted))
    await session.commit()


async def sync_auth_from_yaml(
    session: AsyncSession,
    admin_ids: list[int],
    allowed_ids: list[int],
) -> None:
    """On startup, sync is_admin/is_whitelisted flags from user-ids.yml for known users."""
    all_ids = set(admin_ids) | set(allowed_ids)
    for user_id in all_ids:
        user = await get_user(session, user_id)
        if user is None:
            continue
        new_is_admin = user_id in admin_ids
        new_is_wl = user_id in allowed_ids or new_is_admin
        if user.is_admin != new_is_admin or user.is_whitelisted != new_is_wl:
            await session.execute(
                update(User).where(User.id == user_id).values(
                    is_admin=new_is_admin,
                    is_whitelisted=new_is_wl,
                )
            )
    await session.commit()