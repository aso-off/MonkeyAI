"""
Тесты для bot/src/bot/middleware/auth.py.

Покрываем:
- _chat_id_for_user()     — Update+message, Update+callback, fallback
- AuthMiddleware.__call__ — нет user, whitelist deny cached, whitelist allow cached,
                            cache-miss с sync fallback, whitelist off, api-ошибка
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)

def _tg_user(uid: int | None = None) -> MagicMock:
    u = MagicMock()
    u.id = uid or _uid()
    u.username = fake.user_name()
    u.first_name = fake.first_name()
    u.last_name = fake.last_name()
    u.language_code = fake.random_element(["ru", "en", "de"])
    return u

# _chat_id_for_user

class TestChatIdForUser:

    def test_non_update_event_returns_user_id(self) -> None:
        from src.bot.middleware.auth import _chat_id_for_user
        uid = _uid()
        assert _chat_id_for_user(MagicMock(), uid) == uid

    def test_update_with_message_returns_message_chat_id(self) -> None:
        from aiogram.types import Update
        from src.bot.middleware.auth import _chat_id_for_user
        uid = _uid()
        chat_id = fake.random_int(min=100_000, max=999_999_999)
        msg = MagicMock()
        msg.chat.id = chat_id
        update = Update.model_construct(update_id=1, message=msg, callback_query=None)
        assert _chat_id_for_user(update, uid) == chat_id

    def test_update_with_callback_query_returns_chat_id(self) -> None:
        from aiogram.types import Update
        from src.bot.middleware.auth import _chat_id_for_user
        uid = _uid()
        chat_id = fake.random_int(min=100_000, max=999_999_999)
        cb = MagicMock()
        cb.message.chat.id = chat_id
        update = Update.model_construct(update_id=2, message=None, callback_query=cb)
        assert _chat_id_for_user(update, uid) == chat_id

    def test_update_without_message_or_callback_returns_user_id(self) -> None:
        from aiogram.types import Update
        from src.bot.middleware.auth import _chat_id_for_user
        uid = _uid()
        update = Update.model_construct(update_id=3, message=None, callback_query=None)
        assert _chat_id_for_user(update, uid) == uid

    def test_faker_various_chat_ids(self) -> None:
        from src.bot.middleware.auth import _chat_id_for_user
        for _ in range(5):
            uid = _uid()
            assert _chat_id_for_user(MagicMock(), uid) == uid

# AuthMiddleware

class TestAuthMiddleware:

    @pytest.mark.asyncio
    async def test_no_user_calls_handler_directly(self) -> None:
        from src.bot.middleware.auth import AuthMiddleware
        mw = AuthMiddleware()
        handler = AsyncMock(return_value="ok")
        event = MagicMock()
        data: dict = {}
        result = await mw(handler, event, data)
        assert result == "ok"
        handler.assert_awaited_once_with(event, data)

    @pytest.mark.asyncio
    async def test_whitelist_cached_deny_returns_none(self) -> None:
        from src.bot.middleware.auth import AuthMiddleware
        mw = AuthMiddleware()
        handler = AsyncMock()
        data = {"event_from_user": _tg_user()}
        with patch("src.bot.middleware.auth.settings") as mock_s, \
             patch("src.bot.middleware.auth.auth_state") as mock_as:
            mock_s.whitelist_mode = True
            mock_as.is_allowed_cached = AsyncMock(return_value=False)
            result = await mw(handler, MagicMock(), data)
        assert result is None
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_whitelist_cached_allow_proceeds(self) -> None:
        from src.bot.middleware.auth import AuthMiddleware
        mw = AuthMiddleware()
        handler = AsyncMock(return_value="ok")
        db_user = MagicMock()
        data = {"event_from_user": _tg_user()}
        with patch("src.bot.middleware.auth.settings") as mock_s, \
             patch("src.bot.middleware.auth.auth_state") as mock_as, \
             patch("src.bot.middleware.auth.api") as mock_api:
            mock_s.whitelist_mode = True
            mock_s.user_cache_ttl_seconds = 45
            mock_as.is_allowed_cached = AsyncMock(return_value=True)
            mock_api.get_or_create_user = AsyncMock(return_value=db_user)
            result = await mw(handler, MagicMock(), data)
        assert result == "ok"
        assert data["db_user"] is db_user

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api(self) -> None:
        from src.bot.middleware.auth import AuthMiddleware
        from src.core import user_cache
        mw = AuthMiddleware()
        handler = AsyncMock(return_value="ok")
        user = _tg_user()
        cached = MagicMock()
        user_cache.put(user.id, cached, 60)
        data = {"event_from_user": user}
        with patch("src.bot.middleware.auth.settings") as mock_s, \
             patch("src.bot.middleware.auth.auth_state") as mock_as, \
             patch("src.bot.middleware.auth.api") as mock_api:
            mock_s.whitelist_mode = True
            mock_as.is_allowed_cached = AsyncMock(return_value=True)
            mock_api.get_or_create_user = AsyncMock()
            result = await mw(handler, MagicMock(), data)
        assert result == "ok"
        assert data["db_user"] is cached
        mock_api.get_or_create_user.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_miss_sync_allow_proceeds(self) -> None:
        from src.bot.middleware.auth import AuthMiddleware
        mw = AuthMiddleware()
        handler = AsyncMock(return_value="ok")
        data = {"event_from_user": _tg_user()}
        with patch("src.bot.middleware.auth.settings") as mock_s, \
             patch("src.bot.middleware.auth.auth_state") as mock_as, \
             patch("src.bot.middleware.auth.api") as mock_api:
            mock_s.whitelist_mode = True
            mock_s.user_cache_ttl_seconds = 45
            mock_as.is_allowed_cached = AsyncMock(return_value=None)
            mock_as.is_allowed = MagicMock(return_value=True)
            mock_api.get_or_create_user = AsyncMock(return_value=MagicMock())
            result = await mw(handler, MagicMock(), data)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_cache_miss_sync_deny_returns_none(self) -> None:
        from src.bot.middleware.auth import AuthMiddleware
        mw = AuthMiddleware()
        handler = AsyncMock()
        data = {"event_from_user": _tg_user()}
        with patch("src.bot.middleware.auth.settings") as mock_s, \
             patch("src.bot.middleware.auth.auth_state") as mock_as:
            mock_s.whitelist_mode = True
            mock_as.is_allowed_cached = AsyncMock(return_value=None)
            mock_as.is_allowed = MagicMock(return_value=False)
            result = await mw(handler, MagicMock(), data)
        assert result is None
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_whitelist_off_skips_check(self) -> None:
        from src.bot.middleware.auth import AuthMiddleware
        mw = AuthMiddleware()
        handler = AsyncMock(return_value="ok")
        data = {"event_from_user": _tg_user()}
        with patch("src.bot.middleware.auth.settings") as mock_s, \
             patch("src.bot.middleware.auth.api") as mock_api:
            mock_s.whitelist_mode = False
            mock_s.user_cache_ttl_seconds = 45
            mock_api.get_or_create_user = AsyncMock(return_value=MagicMock())
            result = await mw(handler, MagicMock(), data)
        assert result == "ok"
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_api_failure_sets_db_user_none_still_calls_handler(self) -> None:
        from src.bot.middleware.auth import AuthMiddleware
        mw = AuthMiddleware()
        handler = AsyncMock(return_value="ok")
        data = {"event_from_user": _tg_user()}
        with patch("src.bot.middleware.auth.settings") as mock_s, \
             patch("src.bot.middleware.auth.auth_state") as mock_as, \
             patch("src.bot.middleware.auth.api") as mock_api:
            mock_s.whitelist_mode = True
            mock_as.is_allowed_cached = AsyncMock(return_value=True)
            mock_api.get_or_create_user = AsyncMock(side_effect=RuntimeError("db down"))
            result = await mw(handler, MagicMock(), data)
        assert result == "ok"
        assert data["db_user"] is None

    @pytest.mark.asyncio
    async def test_faker_multiple_users_allowed(self) -> None:
        from src.bot.middleware.auth import AuthMiddleware
        mw = AuthMiddleware()
        for _ in range(3):
            handler = AsyncMock(return_value="ok")
            data = {"event_from_user": _tg_user(fake.random_int(min=100_000, max=999_999_999))}
            with patch("src.bot.middleware.auth.settings") as mock_s, \
                 patch("src.bot.middleware.auth.auth_state") as mock_as, \
                 patch("src.bot.middleware.auth.api") as mock_api:
                mock_s.whitelist_mode = True
                mock_s.user_cache_ttl_seconds = 45
                mock_as.is_allowed_cached = AsyncMock(return_value=True)
                mock_api.get_or_create_user = AsyncMock(return_value=MagicMock())
                await mw(handler, MagicMock(), data)
            handler.assert_awaited_once()
