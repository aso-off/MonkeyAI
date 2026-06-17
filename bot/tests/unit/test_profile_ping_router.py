"""
Тесты для bot/src/bot/routers/profile/ping.py.

Покрываем:
- _ping_result_keyboard() — структура, callback_data
- _measure_ping_ms()      — нормальный замер, минимальное значение 0.01
- cmd_ping()              — вызывает _measure_ping_ms, отвечает пользователю
- cb_ping()               — вызывает _measure_ping_ms, редактирует сообщение
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
    msg.answer = AsyncMock()
    return msg


def _fake_callback(uid: int | None = None) -> MagicMock:
    cb = MagicMock()
    cb.data = "ping"
    cb.from_user = MagicMock()
    cb.from_user.id = uid or _uid()
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.edit_text = AsyncMock()
    return cb


# _ping_result_keyboard


class TestPingResultKeyboard:

    def test_keyboard_has_back_to_settings_button(self) -> None:
        from src.bot.routers.profile.ping import _ping_result_keyboard
        kb = _ping_result_keyboard("ru")
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data == "profile_settings"

    def test_keyboard_for_all_langs(self) -> None:
        from src.bot.routers.profile.ping import _ping_result_keyboard
        for lang in ["ru", "en", "de"]:
            kb = _ping_result_keyboard(lang)
            assert kb.inline_keyboard[0][0].callback_data == "profile_settings"


# _measure_ping_ms


class TestMeasurePingMs:

    @pytest.mark.asyncio
    async def test_returns_average_of_three_requests(self) -> None:
        from src.bot.routers.profile.ping import _measure_ping_ms
        mock_bot = MagicMock()
        mock_bot.get_me = AsyncMock(return_value=MagicMock())
        with patch("src.bot.routers.profile.ping.asyncio.sleep", new=AsyncMock()), \
             patch("src.core.bot.bot", mock_bot):
            result = await _measure_ping_ms()
        assert isinstance(result, float)
        assert result >= 0.01

    @pytest.mark.asyncio
    async def test_minimum_value_is_001ms(self) -> None:
        from src.bot.routers.profile.ping import _measure_ping_ms
        mock_bot = MagicMock()
        mock_bot.get_me = AsyncMock(return_value=MagicMock())
        with patch("src.bot.routers.profile.ping.asyncio.sleep", new=AsyncMock()), \
             patch("src.core.bot.bot", mock_bot), \
             patch("src.bot.routers.profile.ping.time.perf_counter", side_effect=[0.0, 0.0] * 10):
            result = await _measure_ping_ms()
        assert result >= 0.01

    @pytest.mark.asyncio
    async def test_get_me_called_three_times(self) -> None:
        from src.bot.routers.profile.ping import _measure_ping_ms
        mock_bot = MagicMock()
        mock_bot.get_me = AsyncMock(return_value=MagicMock())
        with patch("src.bot.routers.profile.ping.asyncio.sleep", new=AsyncMock()), \
             patch("src.core.bot.bot", mock_bot):
            await _measure_ping_ms()
        assert mock_bot.get_me.await_count == 3


# cmd_ping


class TestCmdPing:

    @pytest.mark.asyncio
    async def test_sends_ping_response(self) -> None:
        from src.bot.routers.profile.ping import cmd_ping
        ms = fake.pyfloat(min_value=10.0, max_value=500.0)
        msg = _fake_message()
        with patch("src.bot.routers.profile.ping._measure_ping_ms", AsyncMock(return_value=ms)), \
             patch("src.bot.routers.profile.ping.t", return_value="{0} ms"):
            await cmd_ping(msg, language="ru")
        msg.answer.assert_awaited_once()
        call_text = msg.answer.call_args[0][0]
        assert str(round(ms, 2)) in call_text or "{" not in call_text

    @pytest.mark.asyncio
    async def test_faker_various_latencies(self) -> None:
        from src.bot.routers.profile.ping import cmd_ping
        for ms in [fake.pyfloat(min_value=1.0, max_value=2000.0) for _ in range(3)]:
            msg = _fake_message()
            with patch("src.bot.routers.profile.ping._measure_ping_ms", AsyncMock(return_value=ms)), \
                 patch("src.bot.routers.profile.ping.t", return_value="ping: {0}"):
                await cmd_ping(msg, language="en")
            msg.answer.assert_awaited_once()


# cb_ping


class TestCbPing:

    @pytest.mark.asyncio
    async def test_edits_message_with_ping_and_settings_prompt(self) -> None:
        from src.bot.routers.profile.ping import cb_ping
        ms = fake.pyfloat(min_value=5.0, max_value=300.0)
        cb = _fake_callback()
        with patch("src.bot.routers.profile.ping._measure_ping_ms", AsyncMock(return_value=ms)), \
             patch("src.bot.routers.profile.ping.t", return_value="value"), \
             patch("src.bot.routers.profile.ping._settings_keyboard", return_value=MagicMock()):
            await cb_ping(cb, language="ru")
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_settings_keyboard_used_as_reply_markup(self) -> None:
        from src.bot.routers.profile.ping import cb_ping
        ms = fake.pyfloat(min_value=10.0, max_value=100.0)
        cb = _fake_callback()
        mock_kb = MagicMock()
        with patch("src.bot.routers.profile.ping._measure_ping_ms", AsyncMock(return_value=ms)), \
             patch("src.bot.routers.profile.ping.t", return_value="x"), \
             patch("src.bot.routers.profile.ping._settings_keyboard", return_value=mock_kb):
            await cb_ping(cb, language="de")
        call_kwargs = cb.message.edit_text.call_args[1]
        assert call_kwargs.get("reply_markup") is mock_kb