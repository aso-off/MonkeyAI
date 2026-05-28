import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from redis.asyncio import Redis

from src.core.config import settings

logger = logging.getLogger(__name__)

_RATE_MS = 1000  # 1 message per second per user


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_ms: int = _RATE_MS) -> None:
        self.rate_ms = rate_ms
        self._redis: Redis = Redis.from_url("redis://redis:6379/1")

    def _get_redis(self) -> Redis:
        return self._redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")

        if user is None:
            return await handler(event, data)

        if user.id in settings.admin_ids:
            return await handler(event, data)

        key = f"throttle:{user.id}"
        allowed = await self._get_redis().set(key, 1, px=self.rate_ms, nx=True)
        if not allowed:
            logger.debug("Throttled user %d", user.id)
            return None

        return await handler(event, data)
