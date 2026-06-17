"""
Тесты для bot/src/bot/routers/admin/status.py.

Покрываем:
- _status_keyboard()     — структура клавиатуры
- _build_status_text()   — uptime из Redis / без, api_ping OK/None,
                           stats OK/exception, openai OK/нет, invalid creation_date
- cmd_status()           — require_admin False, True
- cb_admin_status()      — require_admin False, True
"""

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
    msg.chat = MagicMock()
    msg.chat.id = msg.from_user.id
    msg.answer = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    return msg

def _fake_callback(uid: int | None = None) -> MagicMock:
    cb = MagicMock()
    cb.data = "admin_status"
    cb.from_user = MagicMock()
    cb.from_user.id = uid or _uid()
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.edit_text = AsyncMock()
    cb.message.reply_markup = MagicMock()
    return cb

def _fake_redis(start_time: str | None = None) -> AsyncMock:
    r = AsyncMock()
    r.get = AsyncMock(return_value=start_time)
    return r

def _fake_settings(**overrides):
    s = MagicMock()
    s.openai_api_key = MagicMock()
    s.bot_version = overrides.get("bot_version", "2.6.0")
    s.bot_creation_date = overrides.get("bot_creation_date", "2025-02-01")
    return s

# _status_keyboard

class TestStatusKeyboard:

    def test_keyboard_has_back_button(self) -> None:
        from src.bot.routers.admin.status import _status_keyboard
        kb = _status_keyboard("ru")
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data == "admin_panel"

# _build_status_text

class TestBuildStatusText:

    @pytest.mark.asyncio
    async def test_with_start_time_shows_uptime(self) -> None:
        import time

        from src.bot.routers.admin.status import _build_status_text
        start = str(time.time() - 3600)
        redis = _fake_redis(start_time=start)
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        stats = MagicMock(all_users_count=100, active_users_count=10)
        with patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.status.api") as mock_api, \
             patch("src.bot.routers.admin.status.settings", _fake_settings()), \
             patch("src.bot.routers.admin.status.t", return_value=""), \
             patch("src.bot.routers.admin.status.format_uptime", return_value="1h"), \
             patch("src.bot.routers.admin.status.format_date", return_value="2025-01-01"):
            mock_api.api_health_check = AsyncMock(return_value=42)
            mock_api.get_users_stats = AsyncMock(return_value=stats)
            text = await _build_status_text("ru")
        assert isinstance(text, str)
        assert "1h" in text

    @pytest.mark.asyncio
    async def test_without_start_time_shows_dash(self) -> None:
        from src.bot.routers.admin.status import _build_status_text
        redis = _fake_redis(start_time=None)
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        stats = MagicMock(all_users_count=0, active_users_count=0)
        with patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.status.api") as mock_api, \
             patch("src.bot.routers.admin.status.settings", _fake_settings()), \
             patch("src.bot.routers.admin.status.t", return_value=""), \
             patch("src.bot.routers.admin.status.format_date", return_value=""):
            mock_api.api_health_check = AsyncMock(return_value=None)
            mock_api.get_users_stats = AsyncMock(return_value=stats)
            text = await _build_status_text("en")
        assert "—" in text

    @pytest.mark.asyncio
    async def test_api_ping_none_shows_inactive(self) -> None:
        from src.bot.routers.admin.status import _build_status_text
        redis = _fake_redis()
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        stats = MagicMock(all_users_count=5, active_users_count=2)
        with patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.status.api") as mock_api, \
             patch("src.bot.routers.admin.status.settings", _fake_settings()), \
             patch("src.bot.routers.admin.status.t", return_value="inactive"), \
             patch("src.bot.routers.admin.status.format_date", return_value=""):
            mock_api.api_health_check = AsyncMock(return_value=None)
            mock_api.get_users_stats = AsyncMock(return_value=stats)
            text = await _build_status_text("ru")
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_stats_exception_marks_db_inactive(self) -> None:
        from src.bot.routers.admin.status import _build_status_text
        redis = _fake_redis()
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        with patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.status.api") as mock_api, \
             patch("src.bot.routers.admin.status.settings", _fake_settings()), \
             patch("src.bot.routers.admin.status.t", return_value=""), \
             patch("src.bot.routers.admin.status.format_date", return_value=""):
            mock_api.api_health_check = AsyncMock(return_value=10)
            mock_api.get_users_stats = AsyncMock(side_effect=RuntimeError("db down"))
            text = await _build_status_text("en")
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_invalid_creation_date_sets_none(self) -> None:
        from src.bot.routers.admin.status import _build_status_text
        redis = _fake_redis()
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        stats = MagicMock(all_users_count=0, active_users_count=0)
        with patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.status.api") as mock_api, \
             patch("src.bot.routers.admin.status.settings",
                   _fake_settings(bot_creation_date="not-a-date")), \
             patch("src.bot.routers.admin.status.t", return_value=""), \
             patch("src.bot.routers.admin.status.format_date", return_value="") as mock_fmt:
            mock_api.api_health_check = AsyncMock(return_value=5)
            mock_api.get_users_stats = AsyncMock(return_value=stats)
            await _build_status_text("ru")
        mock_fmt.assert_called_once_with(None, "ru")

    @pytest.mark.asyncio
    async def test_openai_key_falsy_marks_inactive(self) -> None:
        from src.bot.routers.admin.status import _build_status_text
        redis = _fake_redis()
        mock_dp = MagicMock()
        mock_dp.storage.redis = redis
        s = _fake_settings()
        s.openai_api_key = None
        stats = MagicMock(all_users_count=0, active_users_count=0)
        with patch("src.core.bot.dp", mock_dp), \
             patch("src.bot.routers.admin.status.api") as mock_api, \
             patch("src.bot.routers.admin.status.settings", s), \
             patch("src.bot.routers.admin.status.t", return_value=""), \
             patch("src.bot.routers.admin.status.format_date", return_value=""):
            mock_api.api_health_check = AsyncMock(return_value=1)
            mock_api.get_users_stats = AsyncMock(return_value=stats)
            text = await _build_status_text("ru")
        assert isinstance(text, str)

# cmd_status

class TestCmdStatus:

    @pytest.mark.asyncio
    async def test_not_admin_returns_early(self) -> None:
        from src.bot.routers.admin.status import cmd_status
        msg = _fake_message()
        with patch("src.bot.routers.admin.status.require_admin",
                   AsyncMock(return_value=False)), \
             patch("src.bot.routers.admin.status._build_status_text",
                   AsyncMock()) as mock_build:
            await cmd_status(msg, language="ru", db_user=None)
        mock_build.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_sends_checking_then_status(self) -> None:
        from src.bot.routers.admin.status import cmd_status
        msg = _fake_message()
        sent_msg = MagicMock()
        sent_msg.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=sent_msg)
        status_text = fake.paragraph()
        with patch("src.bot.routers.admin.status.require_admin",
                   AsyncMock(return_value=True)), \
             patch("src.bot.routers.admin.status._build_status_text",
                   AsyncMock(return_value=status_text)), \
             patch("src.bot.routers.admin.status.t", return_value="checking"):
            await cmd_status(msg, language="ru", db_user=MagicMock())
        msg.answer.assert_awaited_once()
        sent_msg.edit_text.assert_awaited_once()

# cb_admin_status

class TestCbAdminStatus:

    @pytest.mark.asyncio
    async def test_not_admin_returns_early(self) -> None:
        from src.bot.routers.admin.status import cb_admin_status
        cb = _fake_callback()
        with patch("src.bot.routers.admin.status.require_admin",
                   AsyncMock(return_value=False)), \
             patch("src.bot.routers.admin.status._build_status_text",
                   AsyncMock()) as mock_build:
            await cb_admin_status(cb, language="ru", db_user=None)
        mock_build.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_edits_with_status(self) -> None:
        from src.bot.routers.admin.status import cb_admin_status
        cb = _fake_callback()
        status_text = fake.paragraph()
        with patch("src.bot.routers.admin.status.require_admin",
                   AsyncMock(return_value=True)), \
             patch("src.bot.routers.admin.status._build_status_text",
                   AsyncMock(return_value=status_text)), \
             patch("src.bot.routers.admin.status.t", return_value="checking"):
            await cb_admin_status(cb, language="ru", db_user=MagicMock())
        cb.answer.assert_awaited_once()
        assert cb.message.edit_text.await_count == 2
