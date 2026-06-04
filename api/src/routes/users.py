import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.redis import get_redis
from core.security import verify_service_token
from db.db import Session, get_session
from db.repositories import dialogs as dialog_repo
from db.repositories import users as user_repo
from schemas.user import UserCreate, UserRead, UserUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])

_USER_TTL = 300   # 5 minutes — hot path for every bot message
_STATS_TTL = 60   # 1 minute — rough counts, staleness acceptable
_FULL_TTL = 120   # 2 minutes — aggregated profile (user + message_count)


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

def _user_key(user_id: int) -> str:
    return f"user:{user_id}"


def _full_key(user_id: int) -> str:
    return f"user_full:{user_id}"


async def _redis_write_user(user: UserRead) -> None:
    """Write UserRead to Redis. Also busts the user_full cache so it is rebuilt fresh."""
    try:
        r = get_redis()
        pipe = r.pipeline()
        pipe.set(_user_key(user.id), user.model_dump_json(), ex=_USER_TTL)
        pipe.delete(_full_key(user.id))
        await pipe.execute()
    except Exception:
        logger.warning("Redis write failed for user %d", user.id)


_WEBAPP_PREFS_KEY_TTL = 86_400  # 24 h — mirrors webapp.py
# Mapping from /users PATCH field names → webapp:user_prefs hash field names
_BOT_TO_WEBAPP_PREFS: dict[str, str] = {
    "language": "language",
    "current_model": "current_model",
    "theme": "theme",
}


async def _redis_sync_webapp_prefs(user_id: int, updates: dict) -> None:
    """If webapp:user_prefs cache exists for this user, patch it with any changed
    pref fields so GET /webapp/me doesn't return a stale cached value."""
    prefs = {_BOT_TO_WEBAPP_PREFS[k]: v for k, v in updates.items() if k in _BOT_TO_WEBAPP_PREFS}
    if not prefs:
        return
    try:
        r = get_redis()
        key = f"webapp:user_prefs:{user_id}"
        # Only update if the key already exists — if it's absent the next GET /webapp/me
        # falls through to DB which already has the fresh value.
        if await r.exists(key):
            await r.hset(key, mapping=prefs)
            await r.expire(key, _WEBAPP_PREFS_KEY_TTL)
    except Exception:
        logger.warning("Redis webapp_prefs sync failed for user %d", user_id)


async def _redis_read_user(user_id: int) -> UserRead | None:
    try:
        r = get_redis()
        data = await asyncio.wait_for(r.get(_user_key(user_id)), timeout=2.0)
        if data:
            return UserRead.model_validate_json(data)
    except Exception:
        logger.warning("Redis read failed for user %d", user_id)
    return None


async def _redis_write_stats(data: dict) -> None:
    try:
        r = get_redis()
        await r.set("users:stats", json.dumps(data), ex=_STATS_TTL)
    except Exception:
        pass


async def _redis_read_stats() -> dict | None:
    try:
        r = get_redis()
        raw = await asyncio.wait_for(r.get("users:stats"), timeout=2.0)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


async def _db_update_user(user_id: int, **kwargs) -> None:
    try:
        async with Session() as session:
            await user_repo.update_user(session, user_id, **kwargs)
        logger.debug("DB update user %d: %s", user_id, list(kwargs.keys()))
    except Exception:
        logger.exception("DB update failed for user %d", user_id)


async def _get_user_cached(user_id: int, session: AsyncSession) -> UserRead | None:
    """Read-through: Redis first, fall back to PostgreSQL."""
    cached = await _redis_read_user(user_id)
    if cached is not None:
        return cached
    user = await user_repo.get_user(session, user_id)
    if user is None:
        return None
    user_read = UserRead.model_validate(user)
    await _redis_write_user(user_read)
    return user_read


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/stats")
async def users_stats(
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    cached = await _redis_read_stats()
    if cached is not None:
        return cached
    all_count = await dialog_repo.get_all_users_count(session)
    active_count = await dialog_repo.get_active_users_count(session)
    result = {"all_users_count": all_count, "active_users_count": active_count}
    await _redis_write_stats(result)
    return result


@router.get("/{user_id}/full")
async def get_user_full(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    """Aggregated profile: user + message_count in one request (saves 1 HTTP round-trip)."""
    r = get_redis()
    try:
        cached = await asyncio.wait_for(r.get(_full_key(user_id)), timeout=2.0)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    user, message_count = await asyncio.gather(
        _get_user_cached(user_id, session),
        dialog_repo.get_user_message_count(session, user_id),
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = {"user": json.loads(user.model_dump_json()), "message_count": message_count}

    try:
        await r.set(_full_key(user_id), json.dumps(result), ex=_FULL_TTL)
    except Exception:
        pass

    return result


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
):
    user = await _get_user_cached(user_id, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_or_get_user(
    body: UserCreate,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
):
    user, created = await user_repo.get_or_create_user(
        session,
        user_id=body.id,
        chat_id=body.chat_id,
        username=body.username or "",
        first_name=body.first_name,
        last_name=body.last_name or "",
        language=body.language,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    user_read = UserRead.model_validate(user)
    await _redis_write_user(user_read)
    return user_read


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    body: UserUpdate,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")

    # Get current state (Redis → DB) to build the updated object without a DB round-trip.
    user = await _get_user_cached(user_id, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Merge updates into the cached object.
    updated_user = UserRead.model_validate({**user.model_dump(), **updates})

    # Redis write is synchronous — the next GET returns the new value immediately.
    await _redis_write_user(updated_user)

    # Keep the mini-app's webapp:user_prefs cache in sync so GET /webapp/me
    # sees the bot's change right away (not a stale cached value).
    await _redis_sync_webapp_prefs(user_id, updates)

    await _db_update_user(user_id, **updates)

    logger.debug("User %d updated: %s", user_id, list(updates.keys()))
    return updated_user
