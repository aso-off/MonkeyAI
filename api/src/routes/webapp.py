"""
Mini App — webapp routes.

All endpoints are authenticated via Telegram initData (Authorization: tma <initData>).
The user_id is extracted server-side from the validated initData — it is never
trusted from the request body.

Auth spec: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.ratelimit import enforce_rate_limit
from core.redis import get_redis
from core.security import verify_webapp_init_data
from services import whitelist
from db.db import Session, get_session
from db.repositories import dialogs as dialog_repo
from db.repositories import users as user_repo
from schemas.user import UserRead
from services.image_generation import IMAGE_MODELS, generate_image_url
from services.moderation import moderate_content
from services.openai import ChatGPT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webapp", tags=["webapp"])

# Fields cached in Redis for instant reads/writes.
# Stored as HSET webapp:user_prefs:{user_id} with TTL 24h.
_PREFS_FIELDS = frozenset({"language", "current_model", "theme", "mini_app_chat_mode"})
_PREFS_TTL = 86_400  # 24 hours


def _prefs_key(user_id: int) -> str:
    return f"webapp:user_prefs:{user_id}"


async def _redis_write_prefs(user_id: int, data: dict) -> None:
    r = get_redis()
    key = _prefs_key(user_id)
    await r.hset(key, mapping=data)
    await r.expire(key, _PREFS_TTL)


async def _redis_read_prefs(user_id: int) -> dict:
    """Read cached prefs from Redis. Returns {} on miss or timeout."""
    try:
        r = get_redis()
        return await asyncio.wait_for(r.hgetall(_prefs_key(user_id)), timeout=2.0)
    except Exception:
        return {}


async def _db_write_prefs(user_id: int, data: dict) -> None:
    try:
        async with Session() as session:
            await user_repo.update_user(session, user_id, **data)
        logger.debug("Persisted prefs to DB for user %d: %s", user_id, list(data.keys()))
    except Exception:
        logger.exception("Failed to persist prefs to DB for user %d", user_id)


async def _redis_invalidate_user_cache(user_id: int) -> None:
    """Delete bot-side user cache so the next GET /users/{id} reflects fresh prefs."""
    try:
        r = get_redis()
        await r.delete(f"user:{user_id}", f"user_full:{user_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_tg_user(init_data: dict) -> dict:
    """
    Parse the ``user`` JSON field that Telegram embeds in initData.
    Raises 401 if the field is missing or malformed.
    """
    raw = init_data.get("user")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user field missing in initData",
        )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user field is not valid JSON",
        ) from exc


async def _require_user(session: AsyncSession, user_id: int):
    # Redis-first: reuse the shared user cache populated by /users routes.
    try:
        r = get_redis()
        data = await asyncio.wait_for(r.get(f"user:{user_id}"), timeout=2.0)
        if data:
            return UserRead.model_validate_json(data)
    except Exception:
        pass
    user = await user_repo.get_user(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not registered — call GET /webapp/me first",
        )
    return UserRead.model_validate(user)


async def _require_whitelisted(session: AsyncSession, user_id: int):
    """Raise 403 if not whitelisted. Общий Redis-сет первым, БД-флаг — fallback."""
    cached = await whitelist.is_allowed(user_id)
    if cached is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted — account not whitelisted",
        )
    if cached is True:
        return None

    user = await _require_user(session, user_id)
    if not user.is_whitelisted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted — account not whitelisted",
        )
    return user


def _unwhitelisted_profile(tg: dict) -> UserRead:
    """Синтетический профиль для не-whitelist — без записи в БД; фронт покажет «Доступ ограничен»."""
    now = datetime.now(timezone.utc)
    return UserRead(
        id=tg["id"],
        chat_id=tg["id"],
        username=tg.get("username"),
        first_name=tg.get("first_name", ""),
        last_name=tg.get("last_name"),
        language=tg.get("language_code", "system"),
        is_admin=False,
        is_whitelisted=False,
        first_seen=now,
        last_interaction=now,
        current_dialog_id=None,
        current_chat_mode="assistant",
        mini_app_chat_mode="mini_app_assistant",
        current_model="",
        theme="system",
        n_used_tokens={},
        n_generated_images=0,
        n_transcribed_seconds=0.0,
    )


# ---------------------------------------------------------------------------
# Schemas (webapp-specific, user_id comes from initData not body)
# ---------------------------------------------------------------------------

class WebAppChatBody(BaseModel):
    message: str
    dialog_id: str | None = None
    dialog_messages: list = []
    chat_mode: str = "mini_app_assistant"
    model: str
    image_b64: str | None = None
    skip_moderation: bool = False

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Привет! Что умеешь?",
                    "model": "gpt-4o-mini",
                    "chat_mode": "mini_app_assistant",
                }
            ]
        }
    }


class WebAppUpdateBody(BaseModel):
    language: str | None = None
    model: str | None = None
    theme: str | None = None
    mini_app_chat_mode: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"language": "ru", "model": "gpt-4o-mini", "theme": "dark"}
            ]
        }
    }


class WebAppChatResponse(BaseModel):
    answer: str = ""
    n_input_tokens: int = 0
    n_output_tokens: int = 0
    n_first_removed: int = 0
    is_flagged: bool = False


class _DialogIdResponse(BaseModel):
    dialog_id: str


class _BootstrapResponse(BaseModel):
    dialog_id: str
    messages: list
    next_before_index: int = 0


class _PagedMessagesResponse(BaseModel):
    messages: list
    next_before_index: int  # 0 means no more older messages
    has_more: bool          # convenience: next_before_index > 0


class _MessagesResponse(BaseModel):
    messages: list | None = None
    messages_by_mode: dict | None = None


class _OkResponse(BaseModel):
    ok: bool


async def _resolve_mini_app_dialog_id(
    session: AsyncSession,
    user_id: int,
    body_dialog_id: str | None = None,
) -> str:
    """Return dialog_id from request or ensure one exists for the current mini-app mode."""
    if body_dialog_id:
        return body_dialog_id
    return await dialog_repo.ensure_active_mini_app_dialog(session, user_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserRead)
async def get_me(
    init_data: dict = Depends(verify_webapp_init_data),
    session: AsyncSession = Depends(get_session),
):
    """
    Register or return the current Telegram user.
    Multi-device access is allowed — all devices for a user share one account.
    Prefs (language/theme/model/mode) are read from Redis first for instant
    consistency with changes made via PATCH /me.
    """
    tg = _extract_tg_user(init_data)

    # не-whitelist отсекаем до БД: синтетический профиль, без записи
    if await whitelist.is_allowed(tg["id"]) is False:
        return _unwhitelisted_profile(tg)

    user, created = await user_repo.get_or_create_user(
        session,
        user_id=tg["id"],
        chat_id=tg["id"],  # mini-app has no separate chat_id
        username=tg.get("username", ""),
        first_name=tg.get("first_name", ""),
        last_name=tg.get("last_name", ""),
        language=tg.get("language_code", "system"),
    )
    if created:
        wl = "whitelisted" if user.is_whitelisted else "not whitelisted"
        logger.info("New webapp user registered: %d (%s)", tg["id"], wl)

    # Apply Redis-cached prefs on top of DB values.
    # Redis is the source of truth for settings changed via PATCH /me
    # (written there first, then async to PostgreSQL).
    redis_prefs = await _redis_read_prefs(user.id)
    if redis_prefs:
        user_read = UserRead.model_validate(user)
        for field in _PREFS_FIELDS:
            if field in redis_prefs:
                setattr(user_read, field, redis_prefs[field])
        return user_read

    return user


@router.patch("/me", response_model=_OkResponse)
async def update_me(
    body: WebAppUpdateBody,
    init_data: dict = Depends(verify_webapp_init_data),
    session: AsyncSession = Depends(get_session),
) -> _OkResponse:
    """
    Update user preferences from the mini-app.

    Redis is written first (instant read on next GET /me), then PostgreSQL.
    Both are awaited — 200 means data is consistent in Redis and DB.
    """
    tg = _extract_tg_user(init_data)
    user_id = tg["id"]
    await _require_user(session, user_id)

    update_data: dict = {}
    if body.language is not None:
        update_data["language"] = body.language
    if body.model is not None:
        update_data["current_model"] = body.model
    if body.theme is not None:
        update_data["theme"] = body.theme
    if body.mini_app_chat_mode is not None:
        update_data["mini_app_chat_mode"] = body.mini_app_chat_mode

    if update_data:
        redis_data = {
            k: v for k, v in update_data.items() if k in _PREFS_FIELDS
        }
        if redis_data:
            await _redis_write_prefs(user_id, redis_data)
        # Bust the bot-side user cache so the next GET /users/{id} returns fresh prefs.
        await _redis_invalidate_user_cache(user_id)
        await _db_write_prefs(user_id, update_data)
        logger.debug("Prefs updated for user %d: %s", user_id, list(update_data.keys()))

    return _OkResponse(ok=True)


@router.post("/dialogs/new", response_model=_DialogIdResponse)
async def new_dialog(
    init_data: dict = Depends(verify_webapp_init_data),
    session: AsyncSession = Depends(get_session),
) -> _DialogIdResponse:
    """Start a new dialog and return its ID."""
    tg = _extract_tg_user(init_data)
    await _require_whitelisted(session, tg["id"])
    dialog_id = await dialog_repo.start_new_mini_app_dialog(session, tg["id"])
    return _DialogIdResponse(dialog_id=dialog_id)


@router.post("/dialogs/ensure", response_model=_DialogIdResponse)
async def ensure_dialog(
    init_data: dict = Depends(verify_webapp_init_data),
    session: AsyncSession = Depends(get_session),
) -> _DialogIdResponse:
    """Ensure an active mini-app dialog exists and return its ID."""
    tg = _extract_tg_user(init_data)
    await _require_whitelisted(session, tg["id"])
    dialog_id = await dialog_repo.ensure_active_mini_app_dialog(session, tg["id"])
    return _DialogIdResponse(dialog_id=dialog_id)


@router.post("/dialogs/bootstrap", response_model=_BootstrapResponse)
async def bootstrap_dialog(
    init_data: dict = Depends(verify_webapp_init_data),
    session: AsyncSession = Depends(get_session),
) -> _BootstrapResponse:
    """Ensure mini-app dialog and return the last 20 messages + total count."""
    tg = _extract_tg_user(init_data)
    user_id = tg["id"]
    await _require_whitelisted(session, user_id)
    dialog_id = await dialog_repo.ensure_active_mini_app_dialog(session, user_id)
    messages, _total, next_before_index = await dialog_repo.get_dialog_messages_page(
        session, user_id, dialog_id, limit=20
    )
    return _BootstrapResponse(dialog_id=dialog_id, messages=messages, next_before_index=next_before_index)


@router.get("/dialogs/messages/page", response_model=_PagedMessagesResponse)
async def get_messages_page(
    dialog_id: str,
    before_index: int,
    limit: int = 20,
    init_data: dict = Depends(verify_webapp_init_data),
    session: AsyncSession = Depends(get_session),
) -> _PagedMessagesResponse:
    """Return a paginated slice of dialog messages using cursor-based pagination.

    before_index=N → return up to ``limit`` messages whose array index is < N.
    Response includes ``next_before_index`` (0 = no more messages).
    """
    tg = _extract_tg_user(init_data)
    user_id = tg["id"]
    await _require_whitelisted(session, user_id)
    messages, _total, next_before_index = await dialog_repo.get_dialog_messages_page(
        session, user_id, dialog_id, limit=limit, before_index=before_index
    )
    return _PagedMessagesResponse(
        messages=messages,
        next_before_index=next_before_index,
        has_more=next_before_index > 0,
    )


@router.get("/dialogs/messages", response_model=_MessagesResponse)
async def get_messages(
    dialog_id: str | None = None,
    chat_mode: str | None = None,
    init_data: dict = Depends(verify_webapp_init_data),
    session: AsyncSession = Depends(get_session),
) -> _MessagesResponse:
    """
    Retrieve dialog messages.
    - Provide ``dialog_id`` to get a specific dialog.
    - Provide ``chat_mode`` to get the dialog for that mode.
    - Omit both to get all modes at once ({"messages_by_mode": {...}}).
    """
    tg = _extract_tg_user(init_data)
    user_id = tg["id"]

    if not dialog_id and not chat_mode:
        await _require_whitelisted(session, user_id)
        try:
            data = await dialog_repo.get_dialog_messages_by_mode(session, user_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return _MessagesResponse(messages_by_mode=data)

    if chat_mode and not dialog_id:
        await _require_whitelisted(session, user_id)
        dialog_id = await dialog_repo.get_mini_app_dialog_id(session, user_id, chat_mode)

    messages = await dialog_repo.get_dialog_messages(session, user_id, dialog_id)
    return _MessagesResponse(messages=messages)


@router.post("/chat", response_model=WebAppChatResponse)
async def chat_complete(
    body: WebAppChatBody,
    init_data: dict = Depends(verify_webapp_init_data),
    session: AsyncSession = Depends(get_session),
) -> WebAppChatResponse:
    """
    Non-streaming chat for the mini-app.
    Returns the full answer in one JSON response (stable on mobile networks).
    """
    tg = _extract_tg_user(init_data)
    user_id = tg["id"]
    await _require_whitelisted(session, user_id)

    image_buffer: BytesIO | None = None
    if body.image_b64:
        try:
            image_buffer = BytesIO(base64.b64decode(body.image_b64))
            image_buffer.name = "image.jpg"
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid image data") from exc

    is_flagged, _, _ = await moderate_content(text=body.message, image_buffer=image_buffer)
    if image_buffer is not None:
        image_buffer.seek(0)
    if is_flagged and not body.skip_moderation:
        return WebAppChatResponse(answer="", is_flagged=True)

    chat_mode = body.chat_mode or "mini_app_assistant"

    if body.model in IMAGE_MODELS:
        await enforce_rate_limit(
            "image_gen",
            user_id,
            settings.image_rate_limit_count,
            settings.image_rate_limit_window_seconds,
        )
        try:
            image_url = await generate_image_url(prompt=body.message, model=body.model)
        except Exception as exc:
            logger.exception("Image generation failed for user %d", user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
        try:
            dialog_id = await _resolve_mini_app_dialog_id(session, user_id, body.dialog_id)
            await dialog_repo.append_dialog_message(
                session, user_id,
                {"user": body.message, "bot": image_url},
                dialog_id,
            )
            await user_repo.update_last_interaction(session, user_id)
        except Exception:
            logger.exception("Failed to persist image result for user %d", user_id)
        return WebAppChatResponse(answer=image_url)

    chatgpt = ChatGPT(model=body.model)
    if image_buffer is not None:
        answer, (n_input, n_output), n_removed = await chatgpt.send_vision_message(
            body.message,
            dialog_messages=body.dialog_messages,
            chat_mode=chat_mode,
            image_buffer=image_buffer,
        )
    else:
        answer, (n_input, n_output), n_removed = await chatgpt.send_message(
            body.message,
            dialog_messages=body.dialog_messages,
            chat_mode=chat_mode,
        )

    try:
        dialog_id = await _resolve_mini_app_dialog_id(session, user_id, body.dialog_id)
        b64: str | None = None
        if image_buffer:
            image_buffer.seek(0)
            b64 = base64.b64encode(image_buffer.read()).decode()
        new_msg = {
            "user": (
                [{"type": "text", "text": body.message},
                 {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]
                if b64 else [{"type": "text", "text": body.message}]
            ),
            "bot": answer,
        }
        await dialog_repo.append_dialog_message(session, user_id, new_msg, dialog_id)
        await dialog_repo.update_n_used_tokens(session, user_id, body.model, n_input, n_output)
        await user_repo.update_last_interaction(session, user_id)
    except Exception:
        logger.exception("Failed to persist webapp chat result for user %d", user_id)

    return WebAppChatResponse(
        answer=answer,
        n_input_tokens=n_input,
        n_output_tokens=n_output,
        n_first_removed=n_removed,
    )


# ---------------------------------------------------------------------------
# Reactions
# ---------------------------------------------------------------------------

class _ReactionPayload(BaseModel):
    reaction: str        # "like" | "dislike"
    model: str
    user_message: str
    bot_message: str


@router.post(
    "/reactions",
    status_code=204,
    summary="Record message reaction",
    description=(
        "Save a **like** or **dislike** reaction for a bot response.\n\n"
        "Stored in `message_reactions` table. Useful for analytics — "
        "query by `model` + `reaction` to see which models need improvement.\n\n"
        "**Analytics queries:**\n"
        "```sql\n"
        "-- Likes/dislikes per model\n"
        "SELECT model, reaction, COUNT(*) AS cnt\n"
        "FROM message_reactions GROUP BY model, reaction ORDER BY cnt DESC;\n\n"
        "-- Recent dislikes with messages (for review)\n"
        "SELECT model, user_message, bot_message, created_at\n"
        "FROM message_reactions WHERE reaction = 'dislike'\n"
        "ORDER BY created_at DESC LIMIT 50;\n"
        "```"
    ),
    responses={
        204: {"description": "Reaction saved"},
        400: {"description": "Invalid reaction value (must be 'like' or 'dislike')"},
        401: {"description": "Invalid or missing Telegram init_data"},
    },
    tags=["webapp"],
)
async def post_reaction(
    payload: _ReactionPayload,
    init_data: dict = Depends(verify_webapp_init_data),
    session: AsyncSession = Depends(get_session),
) -> None:
    if payload.reaction not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="Invalid reaction value")

    from db.models.user import MessageReaction

    tg = _extract_tg_user(init_data)
    user_id = tg["id"]
    reaction = MessageReaction(
        user_id=user_id,
        reaction=payload.reaction,
        model=payload.model,
        user_message=payload.user_message[:2000],
        bot_message=payload.bot_message[:6000],
    )
    session.add(reaction)
    await session.commit()
