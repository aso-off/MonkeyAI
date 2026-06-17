"""
Тесты для bot/src/bot/routers/admin/admin.py.

Покрываем:
- _admin_panel_keyboard()  — builder с 5 строками кнопок
- cmd_admin()              — admin → показывает панель, non-admin → ignore
- cb_admin_panel()         — callback_query "admin_panel"

Faker: user IDs, language.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)

def _fake_db_user(is_admin: bool = False):
    u = MagicMock()
    u.id = _uid()
    u.is_admin = is_admin
    return u

# _admin_panel_keyboard

class TestAdminPanelKeyboard:

    def test_keyboard_has_multiple_rows(self) -> None:
        from src.bot.routers.admin.admin import _admin_panel_keyboard
        kb = _admin_panel_keyboard("ru")
        assert len(kb.inline_keyboard) >= 4

    def test_keyboard_contains_back_button(self) -> None:
        from src.bot.routers.admin.admin import _admin_panel_keyboard
        kb = _admin_panel_keyboard("ru")
        buttons = [b for row in kb.inline_keyboard for b in row]
        assert any(b.callback_data == "back_to_start" for b in buttons)

    def test_keyboard_contains_whitelist_button(self) -> None:
        from src.bot.routers.admin.admin import _admin_panel_keyboard
        kb = _admin_panel_keyboard("ru")
        buttons = [b for row in kb.inline_keyboard for b in row]
        assert any("whitelist" in (b.callback_data or "") for b in buttons)

    def test_keyboard_different_langs(self) -> None:
        from src.bot.routers.admin.admin import _admin_panel_keyboard
        for lang in ["ru", "en", "de"]:
            kb = _admin_panel_keyboard(lang)
            assert kb is not None

    def test_faker_keyboard_buttons_have_callbacks(self) -> None:
        from src.bot.routers.admin.admin import _admin_panel_keyboard
        kb = _admin_panel_keyboard("ru")
        buttons = [b for row in kb.inline_keyboard for b in row]
        for btn in buttons:
            assert btn.callback_data is not None or btn.web_app is not None

# cmd_admin

class TestCmdAdmin:

    @pytest.mark.asyncio
    async def test_admin_user_gets_admin_panel(self, fake_message) -> None:
        from src.bot.routers.admin.admin import cmd_admin
        uid = _uid()
        msg = fake_message(user_id=uid)
        db_user = _fake_db_user(is_admin=True)

        with patch("src.bot.routers.admin.admin.settings") as mock_settings:
            mock_settings.admin_ids = [uid]
            await cmd_admin(msg, language="ru", db_user=db_user)

        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_admin_user_gets_no_response(self, fake_message) -> None:
        from src.bot.routers.admin.admin import cmd_admin
        uid = _uid()
        msg = fake_message(user_id=uid)
        msg.from_user.id = uid
        db_user = _fake_db_user(is_admin=False)

        with patch("src.bot.routers.admin.admin.settings") as mock_settings:
            mock_settings.admin_ids = []
            await cmd_admin(msg, language="ru", db_user=db_user)

        msg.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_by_settings_admin_ids(self, fake_message) -> None:
        from src.bot.routers.admin.admin import cmd_admin
        uid = _uid()
        msg = fake_message(user_id=uid)
        msg.from_user.id = uid
        db_user = _fake_db_user(is_admin=False)  # не admin по БД

        with patch("src.bot.routers.admin.admin.settings") as mock_settings:
            mock_settings.admin_ids = [uid]  # но admin по settings
            await cmd_admin(msg, language="ru", db_user=db_user)

        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_none_db_user_uses_settings(self, fake_message) -> None:
        from src.bot.routers.admin.admin import cmd_admin
        uid = _uid()
        msg = fake_message(user_id=uid)
        msg.from_user.id = uid

        with patch("src.bot.routers.admin.admin.settings") as mock_settings:
            mock_settings.admin_ids = [uid]
            await cmd_admin(msg, language="en", db_user=None)

        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_faker_batch_admin_users(self, fake_message) -> None:
        from src.bot.routers.admin.admin import cmd_admin
        for _ in range(3):
            uid = _uid()
            msg = fake_message(user_id=uid)
            msg.from_user.id = uid
            db_user = _fake_db_user(is_admin=True)
            with patch("src.bot.routers.admin.admin.settings") as mock_settings:
                mock_settings.admin_ids = []
                await cmd_admin(msg, language="ru", db_user=db_user)
            msg.answer.assert_awaited_once()

# cb_admin_panel

class TestCbAdminPanel:

    @pytest.mark.asyncio
    async def test_admin_callback_edits_message(self, fake_callback) -> None:
        from src.bot.routers.admin.admin import cb_admin_panel
        cb = fake_callback(data="admin_panel")
        db_user = _fake_db_user(is_admin=True)

        with patch("src.bot.routers.admin.admin.require_admin",
                   new=AsyncMock(return_value=True)):
            await cb_admin_panel(cb, language="ru", db_user=db_user)

        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_admin_callback_blocked(self, fake_callback) -> None:
        from src.bot.routers.admin.admin import cb_admin_panel
        cb = fake_callback(data="admin_panel")

        with patch("src.bot.routers.admin.admin.require_admin",
                   new=AsyncMock(return_value=False)):
            await cb_admin_panel(cb, language="ru", db_user=None)

        cb.answer.assert_not_awaited()
        cb.message.edit_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_faker_multiple_languages(self, fake_callback) -> None:
        from src.bot.routers.admin.admin import cb_admin_panel
        for lang in ["ru", "en", "de"]:
            cb = fake_callback(data="admin_panel")
            with patch("src.bot.routers.admin.admin.require_admin",
                       new=AsyncMock(return_value=True)):
                await cb_admin_panel(cb, language=lang, db_user=_fake_db_user(True))
            cb.answer.assert_awaited_once()
