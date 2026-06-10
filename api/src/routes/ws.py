"""
WebSocket endpoint for the Telegram Mini App.

Multiple devices per user are supported simultaneously — all devices receive
the same stream of events in real time.

Protocol
--------
Frames are JSON objects. Direction marks: → client→server, ← server→client.

Auth (must be first frame):
  → {"type": "auth", "init_data": "<raw tma initData>"}
  ← {"type": "auth_ok",    "user_id": 123}
  ← {"type": "auth_error", "error":   "..."}

Text chat:
  → {"type": "chat", "id": "<uuid>", "message": "...", "model": "gpt-4o",
      "dialog_id": "..." | null, "dialog_messages": [...], "chat_mode": "..."}

  ← {"type": "user_message",   "id": "<uuid>", "text": "...", "dialog_id": "..."|null}
     (sent to all OTHER devices so they show the message before generation starts)
  ← {"type": "generation_start", "id": "<uuid>"}
     (sent to ALL devices including sender)
  ← {"type": "chat_done",      "id": "<uuid>", "answer": "...", "dialog_id": "...",
      "n_input_tokens": 0, "n_output_tokens": 0, "n_first_removed": 0, "is_flagged": false}
  ← {"type": "chat_error",     "id": "<uuid>", "error": "..."}

Image generation:
  → {"type": "image", "id": "<uuid>", "message": "...", "dialog_id": "..." | null}

  ← {"type": "user_message",      "id": "<uuid>", "text": "...", "dialog_id": "..."|null}
     (other devices only)
  ← {"type": "generation_start",  "id": "<uuid>"}  (all devices)
  ← {"type": "image_progress",    "id": "<uuid>", "step": "moderating" | "generating"}
  ← {"type": "image_done",        "id": "<uuid>", "data": "<base64-webp>",
      "size_kb": 220.5, "dialog_id": "..."}
  ← {"type": "image_error",       "id": "<uuid>", "error": "..."}

Connection state on reconnect:
  ← {"type": "connection_ack", "is_generating": bool, "generating_id": str|null,
      "generating_text": str|null}

Keepalive (every 15 s, server → client):
  ← {"type": "ping"}
  → {"type": "pong"}

Global generation guard:
  Only one active generation per user is allowed at a time.
  If a second request arrives while generating, it is rejected with:
  ← {"type": "chat_error" | "image_error", "id": "<uuid>", "error": "already generating"}
"""

import asyncio
import base64
import contextlib
import json
import logging
import secrets
import time
import uuid
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Response, WebSocket, WebSocketDisconnect

from core.config import settings
from core.redis import get_redis_binary
from core.security import _verify_init_data
from db.db import Session
from db.repositories import dialogs as dialog_repo
from db.repositories import users as user_repo
from services.image_generation import generate_image_b64
from services.image_processing import process_generated_image, upload_to_imgbb
from services.moderation import moderate_content
from services.openai import ChatGPT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webapp")

# user_id → set of active WebSocket connections (one per device).
_WS_POOL: dict[int, set[WebSocket]] = defaultdict(set)

# user_id → req_id of the active generation.
# Only one generation per user allowed at a time — all devices see the stream.
_USER_GENERATING: dict[int, str] = {}

# user_id → original user message text for the active generation.
# Sent in connection_ack so late-joining devices can display the user message.
_USER_GENERATING_TEXT: dict[int, str] = {}

# Strong references prevent asyncio from GC-collecting running tasks.
_BG_TASKS: set[asyncio.Task] = set()

# In-memory image store: avoids sending 2-4 MB base64 frames over WebSocket.
# Cloudflare tunnels drop connections on very large frames; we serve the image
# over a lightweight HTTP endpoint instead and broadcast only a short URL.
_IMAGE_STORE: dict[str, bytes] = {}
_IMAGE_TS: dict[str, float] = {}
_IMAGE_TTL = 3_600      # 1 h in-memory  (warm cache)
_IMAGE_REDIS_TTL = 86_400  # 24 h in Redis  (survives server restart)


# Server-initiated ping interval (keeps Cloudflare tunnel alive).
# 15 s < Cloudflare's 100 s idle timeout — extra headroom on mobile where
# pong replies may be delayed.
_PING_INTERVAL = 15  # seconds


# ---------------------------------------------------------------------------
# Image store helpers
# ---------------------------------------------------------------------------

async def _store_image(b64_data: str) -> str:
    """Decode base64 data-URI, persist to memory + Redis (24 h), return secret image_id."""
    try:
        _, b64 = b64_data.split(',', 1)
    except ValueError:
        b64 = b64_data
    img_bytes = base64.b64decode(b64)
    image_id = secrets.token_hex(24)  # 192-bit random — no auth needed
    # In-memory cache (hot path).
    _IMAGE_STORE[image_id] = img_bytes
    _IMAGE_TS[image_id] = time.monotonic()
    # Evict expired in-memory entries.
    now = time.monotonic()
    expired = [k for k, t in _IMAGE_TS.items() if now - t > _IMAGE_TTL]
    for k in expired:
        _IMAGE_STORE.pop(k, None)
        _IMAGE_TS.pop(k, None)
    # Persist to Redis — survives server restarts for 24 h.
    try:
        await get_redis_binary().setex(f"webapp:image:{image_id}", _IMAGE_REDIS_TTL, img_bytes)
    except Exception:
        logger.warning("Failed to persist image %s to Redis; in-memory only", image_id)
    return image_id


@router.get("/images/{image_id}")
async def get_image(image_id: str) -> Response:
    """Serve a generated image by its temporary ID (no auth — 192-bit token provides security)."""
    img_bytes = _IMAGE_STORE.get(image_id)
    if img_bytes is None:
        # Memory miss — try Redis (e.g. after server restart).
        try:
            img_bytes = await get_redis_binary().get(f"webapp:image:{image_id}")
        except Exception:
            pass
        if not img_bytes:
            raise HTTPException(status_code=404, detail="Image not found or expired")
        # Re-warm in-memory cache.
        _IMAGE_STORE[image_id] = img_bytes
        _IMAGE_TS[image_id] = time.monotonic()
    return Response(content=img_bytes, media_type="image/png")


# ---------------------------------------------------------------------------
# Task helper
# ---------------------------------------------------------------------------

def _spawn(coro) -> asyncio.Task:
    """Create a background task with a strong reference to prevent GC."""
    task = asyncio.create_task(coro)
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)

    def _log_exc(t: asyncio.Task) -> None:
        if not t.cancelled() and (exc := t.exception()):
            logger.exception("Background task failed: %s", exc)

    task.add_done_callback(_log_exc)
    return task


# ---------------------------------------------------------------------------
# Send helpers
# ---------------------------------------------------------------------------

async def _send(ws: WebSocket, payload: dict) -> None:
    """Send a JSON frame to a single connection; silently ignores closed sockets."""
    try:
        await ws.send_text(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


async def _broadcast(user_id: int, payload: dict, exclude: WebSocket | None = None) -> None:
    """Send payload to ALL WebSocket connections for a user.
    Pass exclude=ws to skip the originating device (e.g. for user_message echo).
    """
    for ws in list(_WS_POOL.get(user_id, set())):
        if ws is not exclude:
            await _send(ws, payload)


# ---------------------------------------------------------------------------
# Auth handshake
# ---------------------------------------------------------------------------

async def _auth_handshake(ws: WebSocket) -> int | None:
    """
    Wait for the first frame and validate Telegram initData.
    Returns the authenticated user_id, or None if auth fails.
    """
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=15.0)
        frame = json.loads(raw)
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        await _send(ws, {"type": "auth_error", "error": "expected auth frame within 15 s"})
        return None

    if frame.get("type") != "auth":
        await _send(ws, {"type": "auth_error", "error": "first frame must be {type: 'auth'}"})
        return None

    init_data = str(frame.get("init_data", ""))
    # Strip optional "tma " prefix.
    if init_data.startswith("tma "):
        init_data = init_data[4:]

    try:
        params = _verify_init_data(init_data, settings.telegram_token.get_secret_value())
    except ValueError as exc:
        await _send(ws, {"type": "auth_error", "error": str(exc)})
        return None

    raw_user = params.get("user")
    if not raw_user:
        await _send(ws, {"type": "auth_error", "error": "user field missing in initData"})
        return None
    try:
        user_data = json.loads(raw_user)
        return int(user_data["id"])
    except (json.JSONDecodeError, KeyError, TypeError):
        await _send(ws, {"type": "auth_error", "error": "malformed user field"})
        return None


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

async def _heartbeat(ws: WebSocket) -> None:
    """Send a ping frame every _PING_INTERVAL seconds to keep the tunnel alive.

    Returns as soon as a send fails so that asyncio.wait(FIRST_COMPLETED) in the
    endpoint can cancel the message-loop task and trigger proper pool cleanup.
    """
    while True:
        await asyncio.sleep(_PING_INTERVAL)
        try:
            await ws.send_text('{"type":"ping"}')
        except Exception:
            return  # Let the endpoint's FIRST_COMPLETED logic cancel _message_loop


# ---------------------------------------------------------------------------
# Generation keepalive
# ---------------------------------------------------------------------------

async def _generation_keepalive(user_id: int, req_id: str) -> None:
    """Broadcast image_progress every 10 s while OpenAI is generating.

    Two purposes:
    1. Keeps the Cloudflare Tunnel alive — without payload, any side of the
       tunnel can time out after 100 s of silence.
    2. Gives the user a progress indicator (elapsed seconds).

    This coroutine runs as a background task; cancel it when generation ends.
    """
    elapsed = 0
    while True:
        await asyncio.sleep(10)
        elapsed += 10
        await _broadcast(user_id, {
            "type": "image_progress",
            "id": req_id,
            "step": "generating",
            "elapsed": elapsed,
        })


# ---------------------------------------------------------------------------
# Chat handler  (runs in background via _spawn)
# ---------------------------------------------------------------------------

async def _handle_chat(ws: WebSocket, user_id: int, frame: dict) -> None:
    req_id = str(frame.get("id") or uuid.uuid4())
    message = str(frame.get("message", "")).strip()
    model = str(frame.get("model") or "gpt-5-nano")
    dialog_id: str | None = frame.get("dialog_id")
    dialog_messages: list = list(frame.get("dialog_messages") or [])
    chat_mode = str(frame.get("chat_mode") or "mini_app_assistant")

    if not message:
        await _send(ws, {"type": "chat_error", "id": req_id, "error": "empty message"})
        return

    # Guard: one generation per user at a time.
    if user_id in _USER_GENERATING:
        await _send(ws, {"type": "chat_error", "id": req_id, "error": "already generating"})
        return

    # 1. Broadcast user’s message to all OTHER devices immediately.
    await _broadcast(user_id, {
        "type": "user_message",
        "id": req_id,
        "text": message,
        "dialog_id": dialog_id,
    }, exclude=ws)

    # 2. Mark generation as active and notify ALL devices (incl. sender).
    _USER_GENERATING[user_id] = req_id
    _USER_GENERATING_TEXT[user_id] = message
    await _broadcast(user_id, {"type": "generation_start", "id": req_id})

    try:
        # 3. Content moderation.
        try:
            is_flagged, _, _ = await moderate_content(text=message)
        except Exception:
            is_flagged = False

        if is_flagged:
            await _broadcast(user_id, {
                "type": "chat_done", "id": req_id,
                "answer": "", "is_flagged": True,
                "n_input_tokens": 0, "n_output_tokens": 0, "n_first_removed": 0,
            })
            return

        # 4. Build ChatGPT instance.
        try:
            chatgpt = ChatGPT(model=model)
        except ValueError as exc:
            await _broadcast(user_id, {"type": "chat_error", "id": req_id, "error": str(exc)})
            return

        # 5. Collect full answer (no per-token broadcast — only chat_done at the end).
        final_answer = ""
        n_input = n_output = n_removed = 0
        try:
            async for _status, answer, (ni, no), nr in chatgpt.send_message_stream(
                message, dialog_messages=dialog_messages, chat_mode=chat_mode
            ):
                final_answer = answer
                n_input, n_output, n_removed = ni, no, nr
        except Exception as exc:
            logger.warning("Chat stream error for user %d: %s", user_id, exc)
            await _broadcast(user_id, {"type": "chat_error", "id": req_id, "error": str(exc)})
            return

        # 6. Persist to DB.
        resolved_dialog_id = dialog_id
        mid: str | None = None
        try:
            async with Session() as session:
                if not resolved_dialog_id:
                    resolved_dialog_id = await dialog_repo.ensure_active_mini_app_dialog(
                        session, user_id
                    )
                new_msg = {
                    "user": [{"type": "text", "text": message}],
                    "bot": final_answer,
                }
                mid = await dialog_repo.append_dialog_message(
                    session, user_id, new_msg, resolved_dialog_id
                )
                await dialog_repo.update_n_used_tokens(session, user_id, model, n_input, n_output)
                await user_repo.update_last_interaction(session, user_id)
        except Exception:
            logger.exception("Failed to persist chat message for user %d", user_id)

        # 7. Final frame to ALL devices.
        await _broadcast(user_id, {
            "type": "chat_done",
            "id": req_id,
            "answer": final_answer,
            "dialog_id": resolved_dialog_id,
            "mid": mid,
            "n_input_tokens": n_input,
            "n_output_tokens": n_output,
            "n_first_removed": n_removed,
            "is_flagged": False,
        })

    finally:
        _USER_GENERATING.pop(user_id, None)
        _USER_GENERATING_TEXT.pop(user_id, None)


# ---------------------------------------------------------------------------
# Image handler  (runs in background via _spawn)
# ---------------------------------------------------------------------------

async def _handle_image(ws: WebSocket, user_id: int, frame: dict) -> None:
    req_id = str(frame.get("id") or uuid.uuid4())
    message = str(frame.get("message", "")).strip()
    dialog_id: str | None = frame.get("dialog_id")

    if not message:
        await _send(ws, {"type": "image_error", "id": req_id, "error": "empty prompt"})
        return

    # Guard: one generation per user at a time.
    if user_id in _USER_GENERATING:
        await _send(ws, {"type": "image_error", "id": req_id, "error": "already generating"})
        return

    # 1. Broadcast user’s message to all OTHER devices immediately.
    await _broadcast(user_id, {
        "type": "user_message",
        "id": req_id,
        "text": message,
        "dialog_id": dialog_id,
    }, exclude=ws)

    # 2. Mark as generating and notify ALL devices.
    _USER_GENERATING[user_id] = req_id
    _USER_GENERATING_TEXT[user_id] = message
    await _broadcast(user_id, {"type": "generation_start", "id": req_id})

    try:
        # 3. Moderation progress.
        await _broadcast(user_id, {"type": "image_progress", "id": req_id, "step": "moderating"})

        try:
            is_flagged, _, _ = await moderate_content(text=message)
        except Exception:
            is_flagged = False

        if is_flagged:
            await _broadcast(user_id, {"type": "image_error", "id": req_id, "error": "flagged"})
            return

        # 4. Generation — keepalive task prevents Cloudflare idle-timeout during
        #    the ~30-120 s wait for OpenAI to return the image.
        await _broadcast(user_id, {"type": "image_progress", "id": req_id, "step": "generating"})
        keepalive_task = asyncio.create_task(_generation_keepalive(user_id, req_id))
        try:
            b64_data = await asyncio.wait_for(
                generate_image_b64(prompt=message),
                timeout=120.0,
            )
        except asyncio.TimeoutError:
            await _broadcast(user_id, {
                "type": "image_error", "id": req_id, "error": "generation timed out",
            })
            return
        except Exception as exc:
            logger.warning("Image generation error for user %d: %s", user_id, exc)
            await _broadcast(user_id, {"type": "image_error", "id": req_id, "error": str(exc)})
            return
        finally:
            keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await keepalive_task

        # 5. Convert PNG → WebP in memory (CPU-bound Pillow, run in thread).
        try:
            img_result = await asyncio.to_thread(process_generated_image, b64_data)
        except Exception:
            logger.exception("Failed to process image for user %d", user_id)
            await _broadcast(user_id, {
                "type": "image_error", "id": req_id, "error": "image processing failed",
            })
            return

        # 6. Upload WebP to ImgBB — returns a permanent CDN URL (~40 bytes).
        #    This avoids sending large base64 frames over WebSocket, which caused
        #    Cloudflare Tunnel to drop the connection every time.
        try:
            img_url = await upload_to_imgbb(img_result["data"], settings.imgbb_api_key)
            logger.info("Uploaded image to ImgBB: %s", img_url)
        except Exception:
            logger.exception("Failed to upload image to ImgBB for user %d", user_id)
            await _broadcast(user_id, {
                "type": "image_error", "id": req_id, "error": "image upload failed",
            })
            return

        # 7. Persist to DB — store the ImgBB URL (~80 bytes) for permanent history.
        resolved_dialog_id = dialog_id
        mid: str | None = None
        try:
            async with Session() as session:
                if not resolved_dialog_id:
                    resolved_dialog_id = await dialog_repo.ensure_active_mini_app_dialog(
                        session, user_id
                    )
                new_msg = {"user": message, "bot": img_url}
                mid = await dialog_repo.append_dialog_message(
                    session, user_id, new_msg, resolved_dialog_id
                )
                await user_repo.update_last_interaction(session, user_id)
        except Exception:
            logger.exception("Failed to persist image for user %d", user_id)

        # 8. Notify client — tiny JSON frame (~120 bytes), Cloudflare won't drop it.
        await _broadcast(user_id, {
            "type": "image_done",
            "id": req_id,
            "url": img_url,
            "size_kb": img_result["size_kb"],
            "dialog_id": resolved_dialog_id,
            "mid": mid,
        })

    finally:
        _USER_GENERATING.pop(user_id, None)
        _USER_GENERATING_TEXT.pop(user_id, None)


# ---------------------------------------------------------------------------
# Message loop
# ---------------------------------------------------------------------------

async def _message_loop(ws: WebSocket, user_id: int) -> None:
    while True:
        raw = await ws.receive_text()  # raises WebSocketDisconnect on close
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            await _send(ws, {"type": "error", "error": "invalid JSON"})
            continue

        msg_type = frame.get("type")

        if msg_type == "pong":
            pass

        elif msg_type == "chat":
            _spawn(_handle_chat(ws, user_id, frame))

        elif msg_type == "image":
            _spawn(_handle_image(ws, user_id, frame))

        else:
            await _send(ws, {"type": "error", "error": f"unknown type: {msg_type!r}"})


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    Main WebSocket endpoint for the Telegram Mini App.
    Path: /webapp/ws  →  wss://api.si881.ru/webapp/ws

    Multiple devices per user are supported simultaneously.
    All devices receive the same stream of events in real time.
    """
    await ws.accept()
    user_id: int | None = None
    try:
        user_id = await _auth_handshake(ws)
        if user_id is None:
            await ws.close(code=4001)
            return

        _WS_POOL[user_id].add(ws)
        await _send(ws, {"type": "auth_ok", "user_id": user_id})

        # Let the newly connected device know if a generation is already running.
        await _send(ws, {
            "type": "connection_ack",
            "is_generating": user_id in _USER_GENERATING,
            "generating_id": _USER_GENERATING.get(user_id),
            "generating_text": _USER_GENERATING_TEXT.get(user_id),
        })

        logger.info(
            "WS connected: user_id=%d  devices=%d  is_generating=%s",
            user_id, len(_WS_POOL[user_id]), user_id in _USER_GENERATING,
        )

        # Run heartbeat and message-loop concurrently.
        # FIRST_COMPLETED: when either finishes (disconnect or dead-connection ping
        # failure), cancel the other so the pool entry is cleaned up promptly instead
        # of waiting for the OS TCP timeout (minutes on mobile half-close).
        heart_task = asyncio.create_task(_heartbeat(ws))
        loop_task  = asyncio.create_task(_message_loop(ws, user_id))
        # Add done-callback immediately so the exception is marked as
        # "retrieved" the moment _message_loop finishes — most reliable
        # way to silence "Task exception was never retrieved", fires
        # before any GC pass and is not affected by CancelledError
        # propagation in the enclosing coroutine.
        loop_task.add_done_callback(
            lambda t: t.exception() if not t.cancelled() else None
        )
        _loop_exc: BaseException | None = None
        try:
            await asyncio.wait(
                {heart_task, loop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for _t in (heart_task, loop_task):
                if not _t.done():
                    _t.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await _t
            # Retrieve the exception here so asyncio never warns
            # "Task exception was never retrieved", even when this
            # coroutine is cancelled (CancelledError) by Uvicorn on an
            # abrupt TCP/QUIC drop (code 1006) — in that case the
            # post-finally block below is skipped entirely.
            if loop_task.done() and not loop_task.cancelled():
                with contextlib.suppress(Exception):
                    _loop_exc = loop_task.exception()
        # Re-raise so the outer except-WebSocketDisconnect handler fires.
        if _loop_exc:
            raise _loop_exc

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WS session ended for user %s: %s", user_id, exc)
    finally:
        if user_id is not None:
            _WS_POOL[user_id].discard(ws)
            if not _WS_POOL[user_id]:
                del _WS_POOL[user_id]
            logger.info("WS disconnected: user_id=%d  remaining=%d",
                        user_id, len(_WS_POOL.get(user_id, set())))
