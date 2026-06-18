"""
Тесты для bot/src/bot/routers/about/router.py.

Покрываем:
- _about_text()      - валидная дата, невалидная дата (ValueError > None)
- _about_keyboard()  - структура клавиатуры
- cmd_about          - Message handler
- cb_about           - CallbackQuery handler
"""

import types
from unittest.mock import patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(3)

@pytest.fixture(autouse=True)
def patch_settings():
    ns = types.SimpleNamespace(
        bot_version="2.7.14",
        bot_creation_date="2025-02-01",
        admin_ids=[123456789],
    )
    with patch("src.bot.routers.about.router.settings", ns):
        yield ns

# _about_text

class TestAboutText:

    def test_valid_date_parses_correctly(self) -> None:
        from src.bot.routers.about.router import _about_text
        text = _about_text("ru")
        assert isinstance(text, str) and len(text) > 0

    def test_invalid_date_falls_back_gracefully(self, patch_settings) -> None:
        from src.bot.routers.about.router import _about_text
        patch_settings.bot_creation_date = "not-a-date"
        text = _about_text("ru")
        assert isinstance(text, str) and len(text) > 0

    def test_version_present_in_text(self, patch_settings) -> None:
        from src.bot.routers.about.router import _about_text
        patch_settings.bot_version = "9.9.9"
        text = _about_text("ru")
        assert "9.9.9" in text

    def test_all_langs(self) -> None:
        from src.bot.routers.about.router import _about_text
        for lang in ["ru", "en", "de"]:
            text = _about_text(lang)
            assert isinstance(text, str) and len(text) > 0

# _about_keyboard

class TestAboutKeyboard:

    def test_keyboard_has_back_button(self) -> None:
        from src.bot.routers.about.router import _about_keyboard
        kb = _about_keyboard("ru")
        buttons = [b for row in kb.inline_keyboard for b in row]
        assert any("back_to_start" in (b.callback_data or "") for b in buttons)

    def test_keyboard_all_langs(self) -> None:
        from src.bot.routers.about.router import _about_keyboard
        for lang in ["ru", "en", "tr"]:
            kb = _about_keyboard(lang)
            assert kb is not None

# cmd_about

class TestCmdAbout:

    @pytest.mark.asyncio
    async def test_sends_about_message(self, fake_message) -> None:
        from src.bot.routers.about.router import cmd_about
        msg = fake_message()
        await cmd_about(msg, language="ru")
        msg.answer.assert_awaited_once()
        text, = msg.answer.call_args[0]
        from src.bot.routers.about.router import _about_text
        assert text == _about_text("ru")

    @pytest.mark.asyncio
    async def test_includes_keyboard(self, fake_message) -> None:
        from src.bot.routers.about.router import cmd_about
        msg = fake_message()
        await cmd_about(msg, language="en")
        kwargs = msg.answer.call_args[1]
        assert "reply_markup" in kwargs

    @pytest.mark.asyncio
    async def test_all_langs(self, fake_message) -> None:
        from src.bot.routers.about.router import cmd_about
        for lang in ["ru", "en", "de"]:
            msg = fake_message()
            await cmd_about(msg, language=lang)
            msg.answer.assert_awaited_once()

# cb_about

class TestCbAbout:

    @pytest.mark.asyncio
    async def test_answers_and_edits(self, fake_callback) -> None:
        from src.bot.routers.about.router import cb_about
        cb = fake_callback(data="about")
        await cb_about(cb, language="ru")
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_edit_contains_about_text(self, fake_callback) -> None:
        from src.bot.routers.about.router import cb_about
        cb = fake_callback(data="about")
        await cb_about(cb, language="ru")
        text = cb.message.edit_text.call_args[0][0]
        from src.bot.routers.about.router import _about_text
        assert text == _about_text("ru")

    @pytest.mark.asyncio
    async def test_all_langs(self, fake_callback) -> None:
        from src.bot.routers.about.router import cb_about
        for lang in ["ru", "en", "de"]:
            cb = fake_callback(data="about")
            await cb_about(cb, language=lang)
            cb.answer.assert_awaited_once()
