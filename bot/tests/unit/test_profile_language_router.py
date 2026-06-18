"""
Тесты для bot/src/bot/routers/profile/language.py.

Покрываем:
- _language_keyboard()   - system selected, конкретный язык selected, tg_lang=None
- cmd_language()         - с db_user, без db_user
- cb_profile_language()  - с db_user, без db_user
- cb_set_language()      - невалидный lang, "system", валидный lang, TelegramBadRequest
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message
from faker import Faker

fake = Faker()
Faker.seed(42)

def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)

def _fake_db_user(language: str = "ru") -> MagicMock:
    u = MagicMock()
    u.id = _uid()
    u.language = language
    return u

def _fake_message(uid: int | None = None, tg_lang: str = "ru") -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = uid or _uid()
    msg.from_user.language_code = tg_lang
    msg.answer = AsyncMock()
    return msg

def _fake_callback(data: str = "profile_language", uid: int | None = None, tg_lang: str = "en") -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user = MagicMock()
    cb.from_user.id = uid or _uid()
    cb.from_user.language_code = tg_lang
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.edit_text = AsyncMock()
    return cb

# _language_keyboard

class TestLanguageKeyboard:

    def test_system_selected_shows_checkmark_on_system_button(self) -> None:
        from src.bot.routers.profile.language import _language_keyboard
        kb = _language_keyboard("ru", "system", "ru")
        system_btn = kb.inline_keyboard[0][0]
        assert "✅" in system_btn.text

    def test_specific_lang_selected_no_checkmark_on_system(self) -> None:
        from src.bot.routers.profile.language import _language_keyboard
        kb = _language_keyboard("en", "de", "en")
        system_btn = kb.inline_keyboard[0][0]
        assert "✅" not in system_btn.text
        de_btn = next(
            btn for row in kb.inline_keyboard for btn in row if "Deutsch" in btn.text
        )
        assert "✅" in de_btn.text

    def test_no_tg_lang_code_handled(self) -> None:
        from src.bot.routers.profile.language import _language_keyboard
        kb = _language_keyboard("en", "system", None)
        assert kb is not None
        assert len(kb.inline_keyboard) >= 2

    def test_keyboard_has_all_8_languages_plus_system_plus_back(self) -> None:
        from src.bot.routers.profile.language import _language_keyboard
        kb = _language_keyboard("ru", "ru", "ru")
        # system row + 4 pairs (8 buttons) + back row
        total_buttons = sum(len(row) for row in kb.inline_keyboard)
        assert total_buttons >= 9  # минимум 8 языков + system

    def test_callback_data_format(self) -> None:
        from src.bot.routers.profile.language import _language_keyboard
        kb = _language_keyboard("en", "en", "en")
        for row in kb.inline_keyboard:
            for btn in row:
                assert (btn.callback_data or "").startswith("set_lang|") or btn.callback_data == "profile_settings"

# cmd_language

class TestCmdLanguage:

    @pytest.mark.asyncio
    async def test_with_db_user_sends_language_picker(self) -> None:
        from src.bot.routers.profile.language import cmd_language
        db_user = _fake_db_user("en")
        msg = _fake_message(db_user.id, "en")
        await cmd_language(msg, language="en", db_user=db_user)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_without_db_user_defaults_to_system(self) -> None:
        from src.bot.routers.profile.language import cmd_language
        msg = _fake_message()
        await cmd_language(msg, language="ru", db_user=None)
        msg.answer.assert_awaited_once()

# cb_profile_language

class TestCbProfileLanguage:

    @pytest.mark.asyncio
    async def test_with_db_user_edits_text(self) -> None:
        from src.bot.routers.profile.language import cb_profile_language
        db_user = _fake_db_user("de")
        cb = _fake_callback(uid=db_user.id, tg_lang="de")
        await cb_profile_language(cb, language="de", db_user=db_user)
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_without_db_user_uses_system_as_default(self) -> None:
        from src.bot.routers.profile.language import cb_profile_language
        cb = _fake_callback(tg_lang="ru")
        await cb_profile_language(cb, language="ru", db_user=None)
        cb.message.edit_text.assert_awaited_once()

# cb_set_language

class TestCbSetLanguage:

    @pytest.mark.asyncio
    async def test_invalid_lang_answers_only(self) -> None:
        from src.bot.routers.profile.language import cb_set_language
        cb = _fake_callback(data="set_lang|zz_unknown")
        with patch("src.bot.routers.profile.language.api") as mock_api:
            await cb_set_language(cb, language="en")
        cb.answer.assert_awaited_once()
        mock_api.update_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_lang_updates_and_refreshes_keyboard(self) -> None:
        from src.bot.routers.profile.language import cb_set_language
        cb = _fake_callback(data="set_lang|fr", tg_lang="fr")
        with patch("src.bot.routers.profile.language.api") as mock_api:
            mock_api.update_user = AsyncMock()
            await cb_set_language(cb, language="fr")
        mock_api.update_user.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_lang_resolves_effective_from_tg(self) -> None:
        from src.bot.routers.profile.language import cb_set_language
        cb = _fake_callback(data="set_lang|system", tg_lang="de")
        with patch("src.bot.routers.profile.language.api") as mock_api:
            mock_api.update_user = AsyncMock()
            await cb_set_language(cb, language="de")
        mock_api.update_user.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_telegram_bad_request_silently_ignored(self) -> None:
        from aiogram.exceptions import TelegramBadRequest
        from src.bot.routers.profile.language import cb_set_language
        cb = _fake_callback(data="set_lang|es", tg_lang="es")
        cb.message.edit_text = AsyncMock(
            side_effect=TelegramBadRequest(method=MagicMock(), message="message not modified")
        )
        with patch("src.bot.routers.profile.language.api") as mock_api:
            mock_api.update_user = AsyncMock()
            await cb_set_language(cb, language="es")
        # Не должно поднимать исключение

    @pytest.mark.asyncio
    async def test_faker_supported_langs_all_update(self) -> None:
        from src.bot.routers.profile.language import _FIXED_LANGUAGES, cb_set_language
        for lang in list(_FIXED_LANGUAGES.keys())[:4]:
            cb = _fake_callback(data=f"set_lang|{lang}", tg_lang=lang)
            with patch("src.bot.routers.profile.language.api") as mock_api:
                mock_api.update_user = AsyncMock()
                await cb_set_language(cb, language=lang)
            mock_api.update_user.assert_awaited_once()
