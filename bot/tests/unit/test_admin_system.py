"""
Тесты для bot/src/bot/routers/admin/system.py.

Покрываем:
- _back_keyboard()       — структура
- _get_cached_text()     — нет данных, корректный JSON с blocks, пустые blocks, invalid JSON
- cmd_system()           — require_admin False, нет кэша, есть кэш
- cb_admin_system()      — require_admin False, нет кэша, есть кэш,
                           message not modified (исключение проглатывается),
                           другое исключение > answer fallback
"""

import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message
from faker import Faker

fake = Faker()
Faker.seed(42)

def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)

def _fake_message(uid: int | None = None) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = uid or _uid()
    msg.answer = AsyncMock()
    return msg

def _fake_callback(uid: int | None = None) -> MagicMock:
    cb = MagicMock()
    cb.data = "admin_system"
    cb.from_user = MagicMock()
    cb.from_user.id = uid or _uid()
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    return cb

def _fake_redis(cached: bytes | None = None) -> AsyncMock:
    r = AsyncMock()
    r.get = AsyncMock(return_value=cached)
    return r

# _back_keyboard

class TestBackKeyboard:

    def test_has_back_to_admin_button(self) -> None:
        from src.bot.routers.admin.system import _back_keyboard
        kb = _back_keyboard("ru")
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data == "admin_panel"

# _get_cached_text

class TestGetCachedText:

    @pytest.mark.asyncio
    async def test_no_cached_data_returns_none(self) -> None:
        from src.bot.routers.admin.system import _get_cached_text
        redis = _fake_redis(cached=None)
        result = await _get_cached_text(redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_blocks_returned_joined(self) -> None:
        from src.bot.routers.admin.system import _get_cached_text
        blocks = [fake.sentence(), fake.sentence(), fake.sentence()]
        payload = json.dumps({"blocks": blocks}).encode()
        redis = _fake_redis(cached=payload)
        result = await _get_cached_text(redis)
        assert result == "\n\n".join(blocks)

    @pytest.mark.asyncio
    async def test_empty_blocks_returns_none(self) -> None:
        from src.bot.routers.admin.system import _get_cached_text
        payload = json.dumps({"blocks": []}).encode()
        redis = _fake_redis(cached=payload)
        result = await _get_cached_text(redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self) -> None:
        from src.bot.routers.admin.system import _get_cached_text
        redis = _fake_redis(cached=b"not valid json {{")
        result = await _get_cached_text(redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_blocks_key_returns_none(self) -> None:
        from src.bot.routers.admin.system import _get_cached_text
        payload = json.dumps({"other_key": "value"}).encode()
        redis = _fake_redis(cached=payload)
        result = await _get_cached_text(redis)
        assert result is None

# cmd_system

class TestCmdSystem:

    @pytest.mark.asyncio
    async def test_not_admin_returns_early(self) -> None:
        from src.bot.routers.admin.system import cmd_system
        msg = _fake_message()
        with patch("src.bot.routers.admin.system.require_admin",
                   AsyncMock(return_value=False)):
            await cmd_system(msg, language="ru", db_user=None)
        msg.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_cached_text_sends_not_available(self) -> None:
        from src.bot.routers.admin.system import cmd_system
        msg = _fake_message()
        redis = _fake_redis(cached=None)
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.system.require_admin",
                   AsyncMock(return_value=True)), \
             patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}), \
             patch("src.bot.routers.admin.system.t", return_value="not available"):
            await cmd_system(msg, language="ru", db_user=MagicMock())
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_has_cached_text_sends_it(self) -> None:
        from src.bot.routers.admin.system import cmd_system
        system_text = fake.paragraph()
        blocks = [system_text]
        payload = json.dumps({"blocks": blocks}).encode()
        msg = _fake_message()
        redis = _fake_redis(cached=payload)
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.system.require_admin",
                   AsyncMock(return_value=True)), \
             patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}):
            await cmd_system(msg, language="en", db_user=MagicMock())
        msg.answer.assert_awaited_once()
        assert msg.answer.call_args[0][0] == system_text

# cb_admin_system

class TestCbAdminSystem:

    @pytest.mark.asyncio
    async def test_not_admin_returns_early(self) -> None:
        from src.bot.routers.admin.system import cb_admin_system
        cb = _fake_callback()
        with patch("src.bot.routers.admin.system.require_admin",
                   AsyncMock(return_value=False)):
            await cb_admin_system(cb, language="ru", db_user=None)
        cb.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_cache_edits_not_available(self) -> None:
        from src.bot.routers.admin.system import cb_admin_system
        cb = _fake_callback()
        redis = _fake_redis(cached=None)
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.system.require_admin",
                   AsyncMock(return_value=True)), \
             patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}), \
             patch("src.bot.routers.admin.system.t", return_value="not available"):
            await cb_admin_system(cb, language="ru", db_user=MagicMock())
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_has_cache_edits_text(self) -> None:
        from src.bot.routers.admin.system import cb_admin_system
        text = fake.paragraph()
        payload = json.dumps({"blocks": [text]}).encode()
        cb = _fake_callback()
        redis = _fake_redis(cached=payload)
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.system.require_admin",
                   AsyncMock(return_value=True)), \
             patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}):
            await cb_admin_system(cb, language="en", db_user=MagicMock())
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_message_not_modified_exception_is_ignored(self) -> None:
        from src.bot.routers.admin.system import cb_admin_system
        cb = _fake_callback()
        cb.message.edit_text = AsyncMock(side_effect=Exception("message is not modified"))
        redis = _fake_redis(cached=None)
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.system.require_admin",
                   AsyncMock(return_value=True)), \
             patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}), \
             patch("src.bot.routers.admin.system.t", return_value="text"):
            await cb_admin_system(cb, language="ru", db_user=MagicMock())
        # Не упало

    @pytest.mark.asyncio
    async def test_other_exception_falls_back_to_answer(self) -> None:
        from src.bot.routers.admin.system import cb_admin_system
        cb = _fake_callback()
        cb.message.edit_text = AsyncMock(side_effect=Exception("some other error"))
        redis = _fake_redis(cached=None)
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.bot.routers.admin.system.require_admin",
                   AsyncMock(return_value=True)), \
             patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}), \
             patch("src.bot.routers.admin.system.t", return_value="text"):
            await cb_admin_system(cb, language="ru", db_user=MagicMock())
        cb.message.answer.assert_awaited_once()
