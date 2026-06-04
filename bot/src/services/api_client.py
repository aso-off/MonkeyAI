"""\nThin HTTP client — bot talks to the API service.\nAll methods are async and raise on non-2xx responses.\n"""
import base64
import logging
import os
import time
from datetime import datetime
from io import BytesIO

import httpx
import msgspec

from src.core.config import settings

logger = logging.getLogger(__name__)

_API_URL = os.environ.get("API_URL", "http://api:8000")
_SERVICE_TOKEN = os.environ.get("API_SERVICE_TOKEN", "")

_client: httpx.AsyncClient | None = None


# Typed response structs

class UserResponse(msgspec.Struct, frozen=True):
    id: int
    chat_id: int
    first_name: str
    language: str
    current_chat_mode: str
    current_model: str
    is_admin: bool
    is_whitelisted: bool
    n_used_tokens: dict
    n_generated_images: int
    n_transcribed_seconds: float
    username: str | None = None
    last_name: str | None = None
    current_dialog_id: str | None = None
    first_seen: datetime | None = None
    last_interaction: datetime | None = None


class ChatCompleteResponse(msgspec.Struct, frozen=True):
    answer: str
    n_input_tokens: int
    n_output_tokens: int
    n_first_removed: int
    is_flagged: bool


class ChatStreamChunk(msgspec.Struct, frozen=True):
    status: str
    text: str
    n_input_tokens: int
    n_output_tokens: int
    n_first_removed: int
    is_flagged: bool


class DialogMessagesResponse(msgspec.Struct, frozen=True):
    messages: list


class NewDialogResponse(msgspec.Struct, frozen=True):
    dialog_id: str


class EnsureDialogResponse(msgspec.Struct, frozen=True):
    """Returned by POST /dialogs/{user_id}/ensure — includes messages so the caller
    never needs a separate get_dialog_messages round-trip."""
    dialog_id: str
    messages: list


class UsersStatsResponse(msgspec.Struct, frozen=True):
    all_users_count: int
    active_users_count: int


class MessageCountResponse(msgspec.Struct, frozen=True):
    count: int


class UserFullResponse(msgspec.Struct, frozen=True):
    """Aggregated profile returned by GET /users/{id}/full."""
    user: UserResponse
    message_count: int


class ImageGenerateResponse(msgspec.Struct, frozen=True):
    images_b64: list[str]
    imgbb_urls: list[str] = ()


class TranscribeResponse(msgspec.Struct, frozen=True):
    text: str
    duration_seconds: float


# HTTP client

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=_API_URL,
            headers={"Authorization": f"Bearer {_SERVICE_TOKEN}"},
            timeout=120.0,
        )
    return _client


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


def _decode(data: bytes, typ):
    return msgspec.json.decode(data, type=typ)


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    method_u = method.upper()
    return await get_client().request(method_u, url, **kwargs)


# Users

async def get_or_create_user(
    user_id: int,
    chat_id: int,
    username: str = "",
    first_name: str = "",
    last_name: str = "",
    language: str = "system",
) -> UserResponse:
    r = await _request("POST", "/users", json={
        "id": user_id, "chat_id": chat_id,
        "username": username, "first_name": first_name,
        "last_name": last_name, "language": language,
    })
    r.raise_for_status()
    return _decode(r.content, UserResponse)


async def get_user(user_id: int) -> UserResponse | None:
    r = await _request("GET", f"/users/{user_id}")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return _decode(r.content, UserResponse)


async def update_user(user_id: int, **kwargs) -> UserResponse:
    r = await _request("PATCH", f"/users/{user_id}", json=kwargs)
    r.raise_for_status()
    return _decode(r.content, UserResponse)


# Dialogs

async def start_new_dialog(user_id: int) -> str:
    r = await _request("POST", f"/dialogs/{user_id}/new")
    r.raise_for_status()
    return _decode(r.content, NewDialogResponse).dialog_id


async def ensure_dialog(user_id: int) -> EnsureDialogResponse:
    r = await _request("POST", f"/dialogs/{user_id}/ensure")
    r.raise_for_status()
    return _decode(r.content, EnsureDialogResponse)


async def get_dialog_messages(user_id: int, dialog_id: str | None = None) -> list:
    """Load messages for one dialog. Without dialog_id uses ensure_dialog (never messages_by_mode)."""
    if dialog_id is None:
        return list((await ensure_dialog(user_id)).messages)
    r = await _request("GET", f"/dialogs/{user_id}/messages", params={"dialog_id": dialog_id})
    r.raise_for_status()
    return _decode(r.content, DialogMessagesResponse).messages


async def set_dialog_messages(user_id: int, messages: list, dialog_id: str | None = None) -> None:
    params = {"dialog_id": dialog_id} if dialog_id else {}
    r = await _request(
        "PUT",
        f"/dialogs/{user_id}/messages",
        json={"messages": messages},
        params=params,
    )
    r.raise_for_status()


# Chat

async def chat_complete(
    user_id: int,
    dialog_id: str | None,
    message: str,
    dialog_messages: list,
    chat_mode: str,
    model: str,
    image_b64: str | None = None,
) -> ChatCompleteResponse:
    r = await _request("POST", "/chat/complete", json={
        "user_id": user_id,
        "dialog_id": dialog_id,
        "message": message,
        "dialog_messages": dialog_messages,
        "chat_mode": chat_mode,
        "model": model,
        "image_b64": image_b64,
        "skip_moderation": not settings.enable_content_moderation,
    })
    r.raise_for_status()
    return _decode(r.content, ChatCompleteResponse)


async def chat_stream(
    user_id: int,
    dialog_id: str | None,
    message: str,
    dialog_messages: list,
    chat_mode: str,
    model: str,
    image_b64: str | None = None,
):
    """Async generator yielding ChatStreamChunk objects."""
    payload = {
        "user_id": user_id,
        "dialog_id": dialog_id,
        "message": message,
        "dialog_messages": dialog_messages,
        "chat_mode": chat_mode,
        "model": model,
        "image_b64": image_b64,
        "skip_moderation": not settings.enable_content_moderation,
    }
    async with get_client().stream("POST", "/chat/stream", json=payload) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                yield _decode(line[6:].encode(), ChatStreamChunk)


# Media

async def generate_images(
    prompt: str,
    n_images: int = 1,
    size: str = "1024x1024",
    quality: str = "medium",
    user_id: int | None = None,
) -> tuple[list[BytesIO], list[str]]:
    """Returns (webp_buffers, imgbb_urls). imgbb_urls may contain empty strings if upload failed."""
    payload: dict = {"prompt": prompt, "n_images": n_images, "size": size, "quality": quality}
    if user_id is not None:
        payload["user_id"] = user_id
    r = await _request("POST", "/media/images/generate", json=payload)
    r.raise_for_status()
    resp = _decode(r.content, ImageGenerateResponse)
    buffers = [_b64_to_buf(b64, "image.png") for b64 in resp.images_b64]
    return buffers, list(resp.imgbb_urls)


async def transcribe_audio(audio_buf: BytesIO, user_id: int, lang: str = "ru") -> tuple[str, float]:
    audio_buf.seek(0)
    r = await _request(
        "POST",
        "/media/audio/transcribe",
        params={"user_id": user_id, "lang": lang},
        files={"file": (audio_buf.name, audio_buf, "audio/ogg")},
    )
    r.raise_for_status()
    resp = _decode(r.content, TranscribeResponse)
    return resp.text, resp.duration_seconds


def _b64_to_buf(b64: str, name: str) -> BytesIO:
    buf = BytesIO(base64.b64decode(b64))
    buf.name = name
    buf.seek(0)
    return buf


# User helpers

async def is_user_admin(user_id: int) -> bool:
    from src.core.config import settings
    if user_id in settings.admin_ids:
        return True
    user = await get_user(user_id)
    return user is not None and user.is_admin


async def set_user_admin(user_id: int, value: bool) -> None:
    if value:
        # User may not be in DB yet (never ran /start); create a minimal stub first.
        user = await get_user(user_id)
        if user is None:
            await get_or_create_user(user_id, chat_id=user_id)
    await update_user(user_id, is_admin=value)


async def set_user_whitelisted(user_id: int, value: bool) -> None:
    if value:
        # User may not be in DB yet (never ran /start); create a minimal stub first.
        user = await get_user(user_id)
        if user is None:
            await get_or_create_user(user_id, chat_id=user_id)
    await update_user(user_id, is_whitelisted=value)


async def get_all_users_count() -> int:
    r = await _request("GET", "/users/stats")
    r.raise_for_status()
    return _decode(r.content, UsersStatsResponse).all_users_count


async def get_users_stats() -> UsersStatsResponse:
    r = await _request("GET", "/users/stats")
    r.raise_for_status()
    return _decode(r.content, UsersStatsResponse)


async def api_health_check() -> float | None:
    """Returns API response time in ms, or None if unreachable."""
    try:
        t0 = time.monotonic()
        r = await _request("GET", "/health", timeout=3.0)
        r.raise_for_status()
        return round((time.monotonic() - t0) * 1000, 1)
    except Exception:
        return None


async def get_user_message_count(user_id: int) -> int:
    r = await _request("GET", f"/dialogs/{user_id}/message-count")
    r.raise_for_status()
    return _decode(r.content, MessageCountResponse).count


async def get_user_full(user_id: int) -> UserFullResponse | None:
    """Aggregated profile: user + message_count in one request."""
    r = await _request("GET", f"/users/{user_id}/full")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return _decode(r.content, UserFullResponse)