"""
Тесты для bot/src/bot/routers/profile/settings.py.

Покрываем:
- _settings_keyboard() — структура клавиатуры
- cmd_settings         — Message handler
- cb_profile_settings  — CallbackQuery handler
"""

import pytest
from faker import Faker

fake = Faker()
Faker.seed(4)

# _settings_keyboard

class TestSettingsKeyboard:

    def test_keyboard_has_model_and_assistant_buttons(self) -> None:
        from src.bot.routers.profile.settings import _settings_keyboard
        kb = _settings_keyboard("ru")
        buttons = [b for row in kb.inline_keyboard for b in row]
        callbacks = {b.callback_data for b in buttons if b.callback_data}
        assert "profile_model" in callbacks
        assert "profile_assistant" in callbacks

    def test_keyboard_has_language_and_ping_buttons(self) -> None:
        from src.bot.routers.profile.settings import _settings_keyboard
        kb = _settings_keyboard("ru")
        buttons = [b for row in kb.inline_keyboard for b in row]
        callbacks = {b.callback_data for b in buttons if b.callback_data}
        assert "profile_language" in callbacks
        assert "ping" in callbacks

    def test_keyboard_has_back_to_profile(self) -> None:
        from src.bot.routers.profile.settings import _settings_keyboard
        kb = _settings_keyboard("en")
        buttons = [b for row in kb.inline_keyboard for b in row]
        callbacks = {b.callback_data for b in buttons if b.callback_data}
        assert "profile" in callbacks

    def test_all_langs(self) -> None:
        from src.bot.routers.profile.settings import _settings_keyboard
        for lang in ["ru", "en", "de", "tr"]:
            kb = _settings_keyboard(lang)
            assert kb is not None

# cmd_settings

class TestCmdSettings:

    @pytest.mark.asyncio
    async def test_sends_settings_message(self, fake_message) -> None:
        from src.bot.routers.profile.settings import cmd_settings
        msg = fake_message()
        await cmd_settings(msg, language="ru")
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_includes_keyboard(self, fake_message) -> None:
        from src.bot.routers.profile.settings import cmd_settings
        msg = fake_message()
        await cmd_settings(msg, language="en")
        kwargs = msg.answer.call_args[1]
        assert "reply_markup" in kwargs

    @pytest.mark.asyncio
    async def test_all_langs(self, fake_message) -> None:
        from src.bot.routers.profile.settings import cmd_settings
        for lang in ["ru", "en", "de"]:
            msg = fake_message()
            await cmd_settings(msg, language=lang)
            msg.answer.assert_awaited_once()

# cb_profile_settings

class TestCbProfileSettings:

    @pytest.mark.asyncio
    async def test_answers_and_edits(self, fake_callback) -> None:
        from src.bot.routers.profile.settings import cb_profile_settings
        cb = fake_callback(data="profile_settings")
        await cb_profile_settings(cb, language="ru")
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_edit_includes_keyboard(self, fake_callback) -> None:
        from src.bot.routers.profile.settings import cb_profile_settings
        cb = fake_callback(data="profile_settings")
        await cb_profile_settings(cb, language="en")
        kwargs = cb.message.edit_text.call_args[1]
        assert "reply_markup" in kwargs

    @pytest.mark.asyncio
    async def test_all_langs(self, fake_callback) -> None:
        from src.bot.routers.profile.settings import cb_profile_settings
        for lang in ["ru", "en", "de", "tr"]:
            cb = fake_callback(data="profile_settings")
            await cb_profile_settings(cb, language=lang)
            cb.answer.assert_awaited_once()