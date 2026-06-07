"""
Тесты для bot/src/bot/routers/profile/assistant.py.

Покрываем:
- _assistant_keyboard()  — skip_keys, текущий режим ✅, имена через t(), статические имена
- _assistant_text()      — template welcome ({key}), static welcome, нет welcome
- cmd_mode()             — db_user=None, с db_user
- cb_profile_assistant() — db_user=None, успешно, TelegramBadRequest
- cb_set_chat_mode()     — режим не найден, db_user=None, тот же режим, смена режима
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


def _fake_db_user(mode: str = "assistant") -> MagicMock:
    u = MagicMock()
    u.id = _uid()
    u.current_chat_mode = mode
    return u


def _fake_message(uid: int | None = None) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = uid or _uid()
    msg.answer = AsyncMock()
    return msg


def _fake_callback(data: str = "profile_assistant", uid: int | None = None) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user = MagicMock()
    cb.from_user.id = uid or _uid()
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    return cb


_BASE_CHAT_MODES = {
    "assistant": {"name": "{assistant_name}", "welcome_message": "{assistant_welcome}"},
    "code_assistant": {"name": "Code Expert", "welcome_message": "Hello from code!"},
    "artist": {"name": "Artist", "welcome_message": ""},
}


# ── _assistant_keyboard ───────────────────────────────────────────────────────


class TestAssistantKeyboard:

    def test_skip_keys_not_in_keyboard(self) -> None:
        from src.bot.routers.profile.assistant import _assistant_keyboard
        modes_with_skip = {
            **_BASE_CHAT_MODES,
            "default_modes": {},
            "premium_modes": {},
            "system_prompt": {},
            "mini_app_assistant": {},
            "mini_app_artist": {},
        }
        with patch("src.bot.routers.profile.assistant.settings") as mock_s:
            mock_s.chat_modes = modes_with_skip
            kb = _assistant_keyboard("ru", "assistant")
        labels = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        for skip_key in ("default_modes", "premium_modes", "system_prompt", "mini_app_assistant", "mini_app_artist"):
            assert not any(skip_key in l for l in labels)

    def test_current_mode_has_checkmark(self) -> None:
        from src.bot.routers.profile.assistant import _assistant_keyboard
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value="Test"):
            mock_s.chat_modes = _BASE_CHAT_MODES
            kb = _assistant_keyboard("ru", "code_assistant")
        code_btn = next(
            btn for row in kb.inline_keyboard for btn in row
            if "set_chat_mode|code_assistant" == btn.callback_data
        )
        assert "✅" in code_btn.text

    def test_template_name_resolved_via_t(self) -> None:
        from src.bot.routers.profile.assistant import _assistant_keyboard
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value="Ассистент") as mock_t:
            mock_s.chat_modes = {"assistant": {"name": "{assistant_name}"}}
            kb = _assistant_keyboard("ru", "assistant")
        mock_t.assert_called()

    def test_static_name_used_directly(self) -> None:
        from src.bot.routers.profile.assistant import _assistant_keyboard
        with patch("src.bot.routers.profile.assistant.settings") as mock_s:
            mock_s.chat_modes = {"coder": {"name": "Coder Bot"}}
            kb = _assistant_keyboard("en", "other")
        labels = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("Coder Bot" in l for l in labels)

    def test_back_button_present(self) -> None:
        from src.bot.routers.profile.assistant import _assistant_keyboard
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value=""):
            mock_s.chat_modes = {}
            kb = _assistant_keyboard("ru", "")
        back_btn = next(
            btn for row in kb.inline_keyboard for btn in row
            if btn.callback_data == "profile_settings"
        )
        assert back_btn is not None


# ── _assistant_text ───────────────────────────────────────────────────────────


class TestAssistantText:

    def test_template_welcome_resolved_via_t(self) -> None:
        from src.bot.routers.profile.assistant import _assistant_text
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value="Welcome!") as mock_t:
            mock_s.chat_modes = {"assistant": {"welcome_message": "{assistant_welcome}"}}
            text = _assistant_text("ru", "assistant")
        assert "Welcome!" in text

    def test_static_welcome_used_directly(self) -> None:
        from src.bot.routers.profile.assistant import _assistant_text
        welcome = fake.sentence()
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value="select"):
            mock_s.chat_modes = {"coder": {"welcome_message": welcome}}
            text = _assistant_text("en", "coder")
        assert welcome in text

    def test_no_welcome_no_extra_newlines(self) -> None:
        from src.bot.routers.profile.assistant import _assistant_text
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value="select:"):
            mock_s.chat_modes = {"silent": {"welcome_message": ""}}
            text = _assistant_text("en", "silent")
        assert not text.startswith("\n")

    def test_unknown_mode_returns_text(self) -> None:
        from src.bot.routers.profile.assistant import _assistant_text
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value=""):
            mock_s.chat_modes = {}
            text = _assistant_text("ru", "nonexistent")
        assert isinstance(text, str)


# ── cmd_mode ──────────────────────────────────────────────────────────────────


class TestCmdMode:

    @pytest.mark.asyncio
    async def test_db_user_none_sends_error(self) -> None:
        from src.bot.routers.profile.assistant import cmd_mode
        msg = _fake_message()
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value="error"):
            mock_s.chat_modes = _BASE_CHAT_MODES
            await cmd_mode(msg, language="ru", db_user=None)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_db_user_sends_keyboard(self) -> None:
        from src.bot.routers.profile.assistant import cmd_mode
        db_user = _fake_db_user("assistant")
        msg = _fake_message(db_user.id)
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value=""):
            mock_s.chat_modes = _BASE_CHAT_MODES
            await cmd_mode(msg, language="en", db_user=db_user)
        msg.answer.assert_awaited_once()


# ── cb_profile_assistant ──────────────────────────────────────────────────────


class TestCbProfileAssistant:

    @pytest.mark.asyncio
    async def test_db_user_none_edits_error(self) -> None:
        from src.bot.routers.profile.assistant import cb_profile_assistant
        cb = _fake_callback()
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value="error"):
            mock_s.chat_modes = _BASE_CHAT_MODES
            await cb_profile_assistant(cb, language="ru", db_user=None)
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_db_user_edits_keyboard(self) -> None:
        from src.bot.routers.profile.assistant import cb_profile_assistant
        db_user = _fake_db_user("assistant")
        cb = _fake_callback(uid=db_user.id)
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value=""):
            mock_s.chat_modes = _BASE_CHAT_MODES
            await cb_profile_assistant(cb, language="en", db_user=db_user)
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_telegram_bad_request_silently_ignored(self) -> None:
        from aiogram.exceptions import TelegramBadRequest
        from src.bot.routers.profile.assistant import cb_profile_assistant
        db_user = _fake_db_user()
        cb = _fake_callback(uid=db_user.id)
        cb.message.edit_text = AsyncMock(
            side_effect=TelegramBadRequest(method=MagicMock(), message="message not modified")
        )
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.t", return_value=""):
            mock_s.chat_modes = _BASE_CHAT_MODES
            await cb_profile_assistant(cb, language="ru", db_user=db_user)
        # Не должно поднимать исключение


# ── cb_set_chat_mode ──────────────────────────────────────────────────────────


class TestCbSetChatMode:

    @pytest.mark.asyncio
    async def test_mode_not_in_chat_modes_answers_only(self) -> None:
        from src.bot.routers.profile.assistant import cb_set_chat_mode
        cb = _fake_callback(data="set_chat_mode|unknown_mode")
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.api") as mock_api:
            mock_s.chat_modes = _BASE_CHAT_MODES
            await cb_set_chat_mode(cb, language="ru", db_user=MagicMock())
        cb.answer.assert_awaited_once()
        mock_api.update_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_user_none_answers_only(self) -> None:
        from src.bot.routers.profile.assistant import cb_set_chat_mode
        cb = _fake_callback(data="set_chat_mode|assistant")
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.api") as mock_api:
            mock_s.chat_modes = _BASE_CHAT_MODES
            await cb_set_chat_mode(cb, language="ru", db_user=None)
        cb.answer.assert_awaited()
        mock_api.update_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_mode_answers_without_update(self) -> None:
        from src.bot.routers.profile.assistant import cb_set_chat_mode
        db_user = _fake_db_user("assistant")
        cb = _fake_callback(data="set_chat_mode|assistant", uid=db_user.id)
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.api") as mock_api:
            mock_s.chat_modes = _BASE_CHAT_MODES
            await cb_set_chat_mode(cb, language="ru", db_user=db_user)
        mock_api.update_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_different_mode_updates_and_refreshes(self) -> None:
        from src.bot.routers.profile.assistant import cb_set_chat_mode
        db_user = _fake_db_user("assistant")
        cb = _fake_callback(data="set_chat_mode|code_assistant", uid=db_user.id)
        with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
             patch("src.bot.routers.profile.assistant.api") as mock_api, \
             patch("src.bot.routers.profile.assistant.t", return_value=""):
            mock_s.chat_modes = _BASE_CHAT_MODES
            mock_api.update_user = AsyncMock()
            mock_api.ensure_dialog = AsyncMock()
            await cb_set_chat_mode(cb, language="en", db_user=db_user)
        mock_api.update_user.assert_awaited_once()
        mock_api.ensure_dialog.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_faker_random_mode_names(self) -> None:
        from src.bot.routers.profile.assistant import cb_set_chat_mode
        for _ in range(3):
            mode = fake.lexify("mode_????")
            cb = _fake_callback(data=f"set_chat_mode|{mode}")
            with patch("src.bot.routers.profile.assistant.settings") as mock_s, \
                 patch("src.bot.routers.profile.assistant.api"):
                mock_s.chat_modes = {}
                await cb_set_chat_mode(cb, language="ru", db_user=MagicMock())
            cb.answer.assert_awaited()
