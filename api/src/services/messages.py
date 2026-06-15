"""Канонический формат сообщений диалога (плоский список, как у OpenAI).

user:      {id, role, content, created_at}
assistant: {id, role, content, parent_id, model, usage, reaction, created_at}
"""

import secrets
import time
from datetime import datetime, timezone


def new_message_id() -> str:
    # время в префиксе — id сортируются хронологически (как ULID)
    return f"msg_{int(time.time() * 1000):012x}{secrets.token_hex(5)}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def user_message(content: str | list) -> dict:
    return {
        "id": new_message_id(),
        "role": "user",
        "content": content,
        "created_at": _now_iso(),
    }


def assistant_message(
    content: str,
    parent_id: str | None,
    model: str | None = None,
    usage: dict | None = None,
) -> dict:
    return {
        "id": new_message_id(),
        "role": "assistant",
        "content": content,
        "parent_id": parent_id,
        "model": model,
        "usage": usage or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "reaction": None,
        "created_at": _now_iso(),
    }