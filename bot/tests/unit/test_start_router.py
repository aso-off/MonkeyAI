"""
Тесты для bot/src/bot/routers/start.py.

Покрываем:
- _private_keyboard()      — с is_admin=True/False, с webapp_url
- _group_keyboard()        — базовый случай
- cmd_start()              — private chat, group chat, с/без db_user
- cmd_menu()               — private chat, group chat
- cb_back_to_start()       — private chat

Faker: user IDs, имена, language codes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)

def _fake_db_user(is_admin: bool = False, is_whitelisted: bool = True):
    u = MagicMock()
    u.id = _uid()
    u.is_admin = is_admin
    u.is_whitelisted = is_whitelisted
    u.language = "ru"
    u.current_chat_mode = "assistant"
    u.current_model = "gpt-4o"
    return u

# Keyboard builders

class TestPrivateKeyboard:

    def test_builds_keyboard_for_regular_user(self) -> None:
        from src.bot.routers.start import _private_keyboard
        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.webapp_url = ""
            kb = _private_keyboard(is_admin=False, lang="ru")
        assert kb is not None
        assert len(kb.inline_keyboard) >= 1

    def test_includes_admin_button_for_admin(self) -> None:
        from src.bot.routers.start import _private_keyboard
        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.webapp_url = ""
            kb = _private_keyboard(is_admin=True, lang="ru")
        # Строк должно быть больше (добавляется кнопка admin_panel)
        rows_admin = len(kb.inline_keyboard)
        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.webapp_url = ""
            kb_no_admin = _private_keyboard(is_admin=False, lang="ru")
        assert rows_admin > len(kb_no_admin.inline_keyboard)

    def test_includes_webapp_button_when_url_set(self) -> None:
        from src.bot.routers.start import _private_keyboard
        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.webapp_url = fake.url()
            kb = _private_keyboard(is_admin=False, lang="en")
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert any("open_mini_app" in (b.callback_data or "") or b.web_app for b in all_buttons)

    def test_faker_different_languages(self) -> None:
        from src.bot.routers.start import _private_keyboard
        for lang in ["ru", "en", "de", "es"]:
            with patch("src.bot.routers.start.settings") as mock_settings:
                mock_settings.webapp_url = ""
                kb = _private_keyboard(is_admin=False, lang=lang)
            assert kb is not None

class TestGroupKeyboard:

    def test_builds_group_keyboard(self) -> None:
        from src.bot.routers.start import _group_keyboard
        kb = _group_keyboard(lang="ru")
        assert kb is not None
        assert len(kb.inline_keyboard) >= 1

    def test_faker_different_languages(self) -> None:
        from src.bot.routers.start import _group_keyboard
        for lang in ["ru", "en", "de"]:
            kb = _group_keyboard(lang=lang)
            assert kb is not None

# cmd_start

class TestCmdStart:

    @pytest.mark.asyncio
    async def test_start_private_chat_with_db_user(self, fake_message) -> None:
        from src.bot.routers.start import cmd_start
        uid = _uid()
        msg = fake_message(user_id=uid, chat_id=uid)
        msg.chat.type = "private"

        state = AsyncMock()
        db_user = _fake_db_user(is_admin=False)
        bot = MagicMock()
        bot.send_message = AsyncMock()

        with patch("src.bot.routers.start.monkey") as mock_monkey, \
             patch("src.bot.routers.start.settings") as mock_settings:
            mock_monkey.send = AsyncMock()
            mock_settings.admin_ids = []
            mock_settings.webapp_url = ""
            await cmd_start(msg, state=state, language="ru", bot=bot, db_user=db_user)

        state.clear.assert_awaited_once()
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_private_chat_creates_user_when_none(self, fake_message) -> None:
        from src.bot.routers.start import cmd_start
        uid = _uid()
        msg = fake_message(user_id=uid, chat_id=uid)
        msg.chat.type = "private"

        state = AsyncMock()
        bot = MagicMock()
        db_user = _fake_db_user()

        with patch("src.bot.routers.start.api") as mock_api, \
             patch("src.bot.routers.start.monkey") as mock_monkey, \
             patch("src.bot.routers.start.settings") as mock_settings:
            mock_api.get_or_create_user = AsyncMock(return_value=db_user)
            mock_monkey.send = AsyncMock()
            mock_settings.admin_ids = []
            mock_settings.webapp_url = ""
            await cmd_start(msg, state=state, language="ru", bot=bot, db_user=None)

        mock_api.get_or_create_user.assert_awaited_once()
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_group_chat(self, fake_message) -> None:
        from src.bot.routers.start import cmd_start
        uid = _uid()
        msg = fake_message(user_id=uid)
        msg.chat.type = "group"
        msg.chat.id = fake.random_int(min=1, max=999_999_999) * -1  # group chat IDs are negative

        state = AsyncMock()
        bot = MagicMock()

        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.admin_ids = []
            mock_settings.webapp_url = ""
            await cmd_start(msg, state=state, language="ru", bot=bot, db_user=_fake_db_user())

        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_admin_user_gets_admin_keyboard(self, fake_message) -> None:
        from src.bot.routers.start import cmd_start
        uid = _uid()
        msg = fake_message(user_id=uid, chat_id=uid)
        msg.chat.type = "private"
        msg.from_user.id = uid

        state = AsyncMock()
        bot = MagicMock()
        db_user = _fake_db_user(is_admin=True)

        with patch("src.bot.routers.start.monkey") as mock_monkey, \
             patch("src.bot.routers.start.settings") as mock_settings:
            mock_monkey.send = AsyncMock()
            mock_settings.admin_ids = [uid]
            mock_settings.webapp_url = ""
            await cmd_start(msg, state=state, language="ru", bot=bot, db_user=db_user)

        msg.answer.assert_awaited_once()
        call_args = msg.answer.call_args
        markup = call_args[1].get("reply_markup") or call_args[0][1] if len(call_args[0]) > 1 else None
        # admin должен видеть кнопку admin_panel
        if markup:
            all_buttons = [b for row in markup.inline_keyboard for b in row]
            assert any("admin_panel" in (b.callback_data or "") for b in all_buttons)

# cmd_menu

class TestCmdMenu:

    @pytest.mark.asyncio
    async def test_menu_private_chat(self, fake_message) -> None:
        from src.bot.routers.start import cmd_menu
        uid = _uid()
        msg = fake_message(user_id=uid, chat_id=uid)
        msg.chat.type = "private"
        msg.from_user.id = uid

        state = AsyncMock()
        db_user = _fake_db_user()

        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.admin_ids = []
            mock_settings.webapp_url = ""
            await cmd_menu(msg, state=state, language="ru", db_user=db_user)

        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_menu_group_chat(self, fake_message) -> None:
        from src.bot.routers.start import cmd_menu
        uid = _uid()
        msg = fake_message(user_id=uid)
        msg.chat.type = "group"

        state = AsyncMock()

        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.admin_ids = []
            mock_settings.webapp_url = ""
            await cmd_menu(msg, state=state, language="en", db_user=None)

        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_menu_clears_state(self, fake_message) -> None:
        from src.bot.routers.start import cmd_menu
        msg = fake_message()
        msg.chat.type = "private"
        state = AsyncMock()

        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.admin_ids = []
            mock_settings.webapp_url = ""
            await cmd_menu(msg, state=state, language="ru", db_user=_fake_db_user())

        state.clear.assert_awaited_once()

# cb_back_to_start

class TestCbBackToStart:

    @pytest.mark.asyncio
    async def test_back_to_start_private_chat(self, fake_callback) -> None:
        from src.bot.routers.start import cb_back_to_start
        uid = _uid()
        cb = fake_callback(user_id=uid, data="back_to_start")
        cb.message.chat.type = "private"
        cb.from_user.id = uid

        state = AsyncMock()
        db_user = _fake_db_user()

        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.admin_ids = []
            mock_settings.webapp_url = ""
            await cb_back_to_start(cb, state=state, language="ru", db_user=db_user)

        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_back_to_start_group_chat(self, fake_callback) -> None:
        from src.bot.routers.start import cb_back_to_start
        cb = fake_callback(data="back_to_start")
        cb.message.chat.type = "group"

        state = AsyncMock()

        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.admin_ids = []
            mock_settings.webapp_url = ""
            await cb_back_to_start(cb, state=state, language="ru", db_user=None)

        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_back_to_start_clears_state(self, fake_callback) -> None:
        from src.bot.routers.start import cb_back_to_start
        cb = fake_callback(data="back_to_start")
        cb.message.chat.type = "private"
        cb.from_user.id = _uid()

        state = AsyncMock()
        with patch("src.bot.routers.start.settings") as mock_settings:
            mock_settings.admin_ids = []
            mock_settings.webapp_url = ""
            await cb_back_to_start(cb, state=state, language="ru", db_user=_fake_db_user())

        state.clear.assert_awaited_once()