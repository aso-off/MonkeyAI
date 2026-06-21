from collections.abc import Awaitable, Mapping
from typing import Any, Protocol, cast

import redis.asyncio as aioredis

from core.config import settings
from core.logger import logger

_redis: aioredis.Redis | None = None
_redis_binary: aioredis.Redis | None = None

_Encodable = str | int | float | bytes


class RedisAsync(Protocol):
    """Async-вид клиента: redis-py типизирует методы как sync|async в одном классе."""

    def get(self, name: str) -> Awaitable[Any]: ...
    def set(self, name: str, value: _Encodable, *, ex: int | None = ...) -> Awaitable[Any]: ...
    def setex(self, name: str, time: int, value: _Encodable) -> Awaitable[Any]: ...
    def delete(self, *names: str) -> Awaitable[int]: ...
    def exists(self, *names: str) -> Awaitable[int]: ...
    def expire(self, name: str, time: int) -> Awaitable[bool]: ...
    def ttl(self, name: str) -> Awaitable[int]: ...
    def incr(self, name: str, amount: int = ...) -> Awaitable[int]: ...
    def eval(self, script: str, numkeys: int, *keys_and_args: _Encodable) -> Awaitable[Any]: ...
    def ping(self) -> Awaitable[Any]: ...
    def sadd(self, name: str, *values: _Encodable) -> Awaitable[int]: ...
    def srem(self, name: str, *values: _Encodable) -> Awaitable[int]: ...
    def sismember(self, name: str, value: _Encodable) -> Awaitable[bool]: ...
    def hset(
        self,
        name: str,
        key: _Encodable | None = ...,
        value: _Encodable | None = ...,
        mapping: Mapping[str, _Encodable] | None = ...,
        items: list[Any] | None = ...,
    ) -> Awaitable[int]: ...
    def hgetall(self, name: str) -> Awaitable[dict[Any, Any]]: ...
    def pipeline(self, transaction: bool = ...) -> Any: ...


async def init_redis() -> None:
    global _redis, _redis_binary
    _redis = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )
    _redis_binary = aioredis.from_url(
        settings.redis_url,
        decode_responses=False,
        max_connections=5,
    )
    logger.info("Redis pool created")


async def close_redis() -> None:
    global _redis, _redis_binary
    if _redis is not None:
        await _redis.aclose()
        _redis = None
    if _redis_binary is not None:
        await _redis_binary.aclose()
        _redis_binary = None
    logger.info("Redis closed")


def get_redis() -> RedisAsync:
    if _redis is None:
        raise RuntimeError("Redis pool is not initialized")
    return cast(RedisAsync, _redis)


def get_redis_binary() -> aioredis.Redis:
    """Return a binary-mode Redis client (decode_responses=False) for raw bytes."""
    if _redis_binary is None:
        raise RuntimeError("Redis binary pool is not initialized")
    return _redis_binary
