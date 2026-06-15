"""
Тесты для bot/src/bot/middleware/throttling.py.

Покрываем:
- __init__: без пароля Redis, с паролем, кастомный rate
- __call__: нет user, admin → пропуск, redis allowed → пропуск,
            redis throttled → None, ключ содержит user_id
"""

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


def _make_mw(rate_ms: int = 1000, redis_password=None, admin_ids: list | None = None):
    """Создаёт ThrottlingMiddleware с замокированным Redis."""
    pwd_mock = None
    if redis_password:
        pwd_mock = MagicMock()
        pwd_mock.get_secret_value.return_value = redis_password

    with patch("src.bot.middleware.throttling.settings") as mock_s, \
         patch("src.bot.middleware.throttling.Redis") as MockRedis:
        mock_s.throttle_rate_ms = rate_ms
        mock_s.redis_host = "localhost"
        mock_s.redis_port = 6379
        mock_s.redis_password = pwd_mock
        mock_s.admin_ids = admin_ids or []
        MockRedis.from_url.return_value = MagicMock()
        from src.bot.middleware.throttling import ThrottlingMiddleware
        mw = ThrottlingMiddleware()

    mock_redis = MagicMock()
    mock_redis.set = AsyncMock(return_value=True)
    mw._redis = mock_redis
    return mw


# ── __init__ ──────────────────────────────────────────────────────────────────


class TestThrottlingMiddlewareInit:

    def test_no_password_builds_plain_url(self) -> None:
        with patch("src.bot.middleware.throttling.settings") as mock_s, \
             patch("src.bot.middleware.throttling.Redis") as MockRedis:
            mock_s.throttle_rate_ms = 500
            mock_s.redis_host = "myredis"
            mock_s.redis_port = 6380
            mock_s.redis_password = None
            MockRedis.from_url.return_value = MagicMock()
            from src.bot.middleware.throttling import ThrottlingMiddleware
            ThrottlingMiddleware()
        url = MockRedis.from_url.call_args[0][0]
        assert "myredis:6380" in url
        assert "@" not in url

    def test_with_password_includes_password_in_url(self) -> None:
        secret = fake.password(length=16)
        pwd = MagicMock()
        pwd.get_secret_value.return_value = secret
        with patch("src.bot.middleware.throttling.settings") as mock_s, \
             patch("src.bot.middleware.throttling.Redis") as MockRedis:
            mock_s.throttle_rate_ms = 1000
            mock_s.redis_host = "localhost"
            mock_s.redis_port = 6379
            mock_s.redis_password = pwd
            MockRedis.from_url.return_value = MagicMock()
            from src.bot.middleware.throttling import ThrottlingMiddleware
            ThrottlingMiddleware()
        url = MockRedis.from_url.call_args[0][0]
        assert secret in url

    def test_custom_rate_overrides_settings(self) -> None:
        custom_rate = fake.random_int(min=200, max=5000)
        mw = _make_mw(rate_ms=999)
        with patch("src.bot.middleware.throttling.settings") as mock_s, \
             patch("src.bot.middleware.throttling.Redis") as MockRedis:
            mock_s.throttle_rate_ms = 999
            mock_s.redis_host = "localhost"
            mock_s.redis_port = 6379
            mock_s.redis_password = None
            MockRedis.from_url.return_value = MagicMock()
            from src.bot.middleware.throttling import ThrottlingMiddleware
            mw2 = ThrottlingMiddleware(rate_ms=custom_rate)
        assert mw2.rate_ms == custom_rate


# ── __call__ ──────────────────────────────────────────────────────────────────


class TestThrottlingMiddlewareCall:

    @pytest.mark.asyncio
    async def test_no_user_passes_through(self) -> None:
        mw = _make_mw()
        handler = AsyncMock(return_value="ok")
        result = await mw(handler, MagicMock(), {})
        assert result == "ok"
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_admin_user_skips_throttle(self) -> None:
        admin_id = _uid()
        mw = _make_mw(admin_ids=[admin_id])
        handler = AsyncMock(return_value="ok")
        user = MagicMock()
        user.id = admin_id
        with patch("src.bot.middleware.throttling.settings") as mock_s:
            mock_s.admin_ids = [admin_id]
            result = await mw(handler, MagicMock(), {"event_from_user": user})
        assert result == "ok"
        handler.assert_awaited_once()
        cast(AsyncMock, mw._redis.set).assert_not_awaited()

    @pytest.mark.asyncio
    async def test_redis_allows_passes_through(self) -> None:
        mw = _make_mw()
        mw._redis.set = AsyncMock(return_value=True)
        handler = AsyncMock(return_value="ok")
        user = MagicMock()
        user.id = _uid()
        with patch("src.bot.middleware.throttling.settings") as mock_s:
            mock_s.admin_ids = []
            result = await mw(handler, MagicMock(), {"event_from_user": user})
        assert result == "ok"
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_throttled_returns_none(self) -> None:
        mw = _make_mw()
        mw._redis.set = AsyncMock(return_value=None)
        handler = AsyncMock()
        user = MagicMock()
        user.id = _uid()
        with patch("src.bot.middleware.throttling.settings") as mock_s:
            mock_s.admin_ids = []
            result = await mw(handler, MagicMock(), {"event_from_user": user})
        assert result is None
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_throttle_key_contains_user_id(self) -> None:
        mw = _make_mw()
        mw._redis.set = AsyncMock(return_value=True)
        uid = fake.random_int(min=100_000, max=999_999_999)
        user = MagicMock()
        user.id = uid
        with patch("src.bot.middleware.throttling.settings") as mock_s:
            mock_s.admin_ids = []
            await mw(AsyncMock(), MagicMock(), {"event_from_user": user})
        key = mw._redis.set.call_args[0][0]
        assert str(uid) in key

    @pytest.mark.asyncio
    async def test_faker_multiple_non_admin_users_throttled(self) -> None:
        mw = _make_mw()
        mw._redis.set = AsyncMock(return_value=None)
        for _ in range(3):
            handler = AsyncMock()
            user = MagicMock()
            user.id = _uid()
            with patch("src.bot.middleware.throttling.settings") as mock_s:
                mock_s.admin_ids = []
                result = await mw(handler, MagicMock(), {"event_from_user": user})
            assert result is None
            handler.assert_not_awaited()
