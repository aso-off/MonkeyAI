"""
Тесты для bot/src/bot/routers/admin/system.py.

Покрываем:
- _back_keyboard()   - структура
- _get_data()        - нет данных, корректный JSON, invalid JSON
- _render_md()       - контейнеры + host, пустые данные
- cmd_system()       - require_admin False, нет кэша, есть кэш
- cb_admin_system()  - require_admin False, нет кэша, есть кэш, message not modified
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

_CONTAINER = {
    "name": "monkey_bot",
    "cpu_percent": 1.5,
    "cpus": 0.5,
    "ram_usage": 0.36,
    "ram_limit": 0.50,
    "net_rx": "14.6MB",
    "net_tx": "38.5MB",
}
_HOST = {
    "hostname": "galaxy",
    "cpu_percent": 45.9,
    "num_cores": 2,
    "ram_usage": 2.52,
    "ram_total": 3.82,
    "disk_usage": 15.0,
    "disk_total": 38.0,
}
_DATA = {"timestamp": 1.0, "containers": [_CONTAINER], "host": _HOST}


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
    cb.message.bot = None
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    return cb


def _fake_redis(cached: bytes | None = None) -> AsyncMock:
    r = AsyncMock()
    r.get = AsyncMock(return_value=cached)
    return r


class TestBackKeyboard:
    def test_has_back_to_admin_button(self) -> None:
        from src.bot.routers.admin.system import _back_keyboard

        kb = _back_keyboard("ru")
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data == "admin_panel"


class TestGetData:
    @pytest.mark.asyncio
    async def test_no_cached_data_returns_none(self) -> None:
        from src.bot.routers.admin.system import _get_data

        assert await _get_data(_fake_redis(cached=None)) is None

    @pytest.mark.asyncio
    async def test_valid_json_returns_dict(self) -> None:
        from src.bot.routers.admin.system import _get_data

        result = await _get_data(_fake_redis(cached=json.dumps(_DATA).encode()))
        assert result is not None
        assert result["host"]["hostname"] == "galaxy"

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self) -> None:
        from src.bot.routers.admin.system import _get_data

        assert await _get_data(_fake_redis(cached=b"not json {{")) is None


class TestRenderMd:
    def test_render_with_containers_and_host(self) -> None:
        from src.bot.routers.admin.system import _render_md

        md = _render_md(_DATA, "ru")
        assert md is not None
        assert "<table>" in md
        assert "bot" in md  # префикс monkey_ убран
        assert "galaxy" in md

    def test_render_empty_returns_none(self) -> None:
        from src.bot.routers.admin.system import _render_md

        assert _render_md({}, "ru") is None


class TestCmdSystem:
    @pytest.mark.asyncio
    async def test_not_admin_returns_early(self) -> None:
        from src.bot.routers.admin.system import cmd_system

        msg = _fake_message()
        with patch("src.bot.routers.admin.system.require_admin", AsyncMock(return_value=False)):
            await cmd_system(msg, language="ru", db_user=None)
        msg.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_cache_sends_not_available(self) -> None:
        from src.bot.routers.admin.system import cmd_system

        msg = _fake_message()
        redis = _fake_redis(cached=None)
        with (
            patch("src.bot.routers.admin.system.require_admin", AsyncMock(return_value=True)),
            patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}),
        ):
            await cmd_system(msg, language="ru", db_user=MagicMock())
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_has_cache_sends_tables(self) -> None:
        from src.bot.routers.admin.system import cmd_system

        msg = _fake_message()
        redis = _fake_redis(cached=json.dumps(_DATA).encode())
        with (
            patch("src.bot.routers.admin.system.require_admin", AsyncMock(return_value=True)),
            patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}),
        ):
            await cmd_system(msg, language="en", db_user=MagicMock())
        msg.answer.assert_awaited_once()
        assert "galaxy" in msg.answer.call_args[0][0]


class TestCbAdminSystem:
    @pytest.mark.asyncio
    async def test_not_admin_returns_early(self) -> None:
        from src.bot.routers.admin.system import cb_admin_system

        cb = _fake_callback()
        with patch("src.bot.routers.admin.system.require_admin", AsyncMock(return_value=False)):
            await cb_admin_system(cb, language="ru", db_user=None)
        cb.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_cache_edits_not_available(self) -> None:
        from src.bot.routers.admin.system import cb_admin_system

        cb = _fake_callback()
        redis = _fake_redis(cached=None)
        with (
            patch("src.bot.routers.admin.system.require_admin", AsyncMock(return_value=True)),
            patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}),
        ):
            await cb_admin_system(cb, language="ru", db_user=MagicMock())
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_has_cache_edits_tables(self) -> None:
        from src.bot.routers.admin.system import cb_admin_system

        cb = _fake_callback()
        redis = _fake_redis(cached=json.dumps(_DATA).encode())
        with (
            patch("src.bot.routers.admin.system.require_admin", AsyncMock(return_value=True)),
            patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}),
        ):
            await cb_admin_system(cb, language="en", db_user=MagicMock())
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_message_not_modified_is_ignored(self) -> None:
        from src.bot.routers.admin.system import cb_admin_system

        cb = _fake_callback()
        cb.message.edit_text = AsyncMock(side_effect=Exception("message is not modified"))
        redis = _fake_redis(cached=None)
        with (
            patch("src.bot.routers.admin.system.require_admin", AsyncMock(return_value=True)),
            patch.dict(sys.modules, {"src.core.bot": types.SimpleNamespace(fsm_redis=lambda: redis)}),
        ):
            await cb_admin_system(cb, language="ru", db_user=MagicMock())
        # не упало
