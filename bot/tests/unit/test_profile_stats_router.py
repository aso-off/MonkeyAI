"""
Тесты для bot/src/bot/routers/profile/stats.py.

Покрываем:
- _stats_keyboard()    — структура, callback_data
- cb_profile_stats()   — profile=None, profile с данными, format_date вызывается
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message
from faker import Faker

fake = Faker()
Faker.seed(42)


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


def _fake_callback(uid: int | None = None) -> MagicMock:
    cb = MagicMock()
    cb.data = "profile_stats"
    cb.from_user = MagicMock()
    cb.from_user.id = uid or _uid()
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.edit_text = AsyncMock()
    return cb


def _fake_profile(message_count: int | None = None) -> MagicMock:
    profile = MagicMock()
    profile.message_count = message_count or fake.random_int(min=0, max=10000)
    profile.user = MagicMock()
    profile.user.first_seen = datetime(
        fake.random_int(min=2020, max=2025),
        fake.random_int(min=1, max=12),
        fake.random_int(min=1, max=28),
        tzinfo=timezone.utc,
    )
    return profile


# ── _stats_keyboard ───────────────────────────────────────────────────────────


class TestStatsKeyboard:

    def test_keyboard_has_back_to_profile_button(self) -> None:
        from src.bot.routers.profile.stats import _stats_keyboard
        kb = _stats_keyboard("ru")
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data == "profile"

    def test_keyboard_back_button_for_all_langs(self) -> None:
        from src.bot.routers.profile.stats import _stats_keyboard
        for lang in ["ru", "en", "de", "fr"]:
            kb = _stats_keyboard(lang)
            assert kb.inline_keyboard[0][0].callback_data == "profile"


# ── cb_profile_stats ──────────────────────────────────────────────────────────


class TestCbProfileStats:

    @pytest.mark.asyncio
    async def test_profile_none_shows_error(self) -> None:
        from src.bot.routers.profile.stats import cb_profile_stats
        cb = _fake_callback()
        with patch("src.bot.routers.profile.stats.api") as mock_api, \
             patch("src.bot.routers.profile.stats.t", return_value="error"):
            mock_api.get_user_full = AsyncMock(return_value=None)
            await cb_profile_stats(cb, language="ru")
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_profile_with_data_shows_stats(self) -> None:
        from src.bot.routers.profile.stats import cb_profile_stats
        uid = _uid()
        cb = _fake_callback(uid=uid)
        profile = _fake_profile(message_count=fake.random_int(min=1, max=5000))
        with patch("src.bot.routers.profile.stats.api") as mock_api, \
             patch("src.bot.routers.profile.stats.t", return_value=""), \
             patch("src.bot.routers.profile.stats.format_date", return_value="01.01.2024"):
            mock_api.get_user_full = AsyncMock(return_value=profile)
            await cb_profile_stats(cb, language="en")
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()
        call_text = cb.message.edit_text.call_args[0][0]
        assert str(profile.message_count) in call_text

    @pytest.mark.asyncio
    async def test_format_date_called_with_first_seen(self) -> None:
        from src.bot.routers.profile.stats import cb_profile_stats
        cb = _fake_callback()
        profile = _fake_profile()
        with patch("src.bot.routers.profile.stats.api") as mock_api, \
             patch("src.bot.routers.profile.stats.t", return_value=""), \
             patch("src.bot.routers.profile.stats.format_date", return_value="date") as mock_fmt:
            mock_api.get_user_full = AsyncMock(return_value=profile)
            await cb_profile_stats(cb, language="ru")
        mock_fmt.assert_called_once_with(profile.user.first_seen, "ru")

    @pytest.mark.asyncio
    async def test_faker_various_message_counts(self) -> None:
        from src.bot.routers.profile.stats import cb_profile_stats
        for count in [0, fake.random_int(min=1, max=100), fake.random_int(min=1000, max=50000)]:
            cb = _fake_callback()
            profile = _fake_profile(message_count=count)
            with patch("src.bot.routers.profile.stats.api") as mock_api, \
                 patch("src.bot.routers.profile.stats.t", return_value=""), \
                 patch("src.bot.routers.profile.stats.format_date", return_value=""):
                mock_api.get_user_full = AsyncMock(return_value=profile)
                await cb_profile_stats(cb, language="en")
            cb.message.edit_text.assert_awaited_once()
