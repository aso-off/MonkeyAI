"""
Module-level auth state — plain Python sets, no pydantic involved.
Auth middleware reads from here; whitelist router updates here after each save.
"""

import asyncio
from pathlib import Path

import yaml

_admin_ids: set[int] = set()
_allowed_ids: set[int] = set()

_USER_IDS_PATH = Path("/app/configs/user-ids.yml")

# общий с API сет разрешённых id (db 0)
_ALLOWED_KEY = "auth:allowed"


def reload_sync() -> None:
    global _admin_ids, _allowed_ids
    try:
        data = yaml.safe_load(_USER_IDS_PATH.read_text(encoding="utf-8")) or {}
        _admin_ids = {int(x) for x in data.get("admin_user_ids", [])}
        _allowed_ids = {int(x) for x in data.get("allowed_user_ids", [])}
    except Exception:
        pass


async def reload() -> None:
    await asyncio.to_thread(reload_sync)


def is_admin(user_id: int) -> bool:
    return user_id in _admin_ids


def is_allowed(user_id: int) -> bool:
    return user_id in _admin_ids or user_id in _allowed_ids


async def is_allowed_cached(user_id: int) -> bool | None:
    """True/False из общего Redis-сета; None — если Redis недоступен или сет не построен."""
    from src.core.bot import fsm_redis

    try:
        r = fsm_redis()
        if await r.sismember(_ALLOWED_KEY, user_id):
            return True
        if await r.exists(_ALLOWED_KEY):
            return False
        return None
    except Exception:
        return None
