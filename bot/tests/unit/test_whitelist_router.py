"""
Тесты для bot/src/bot/routers/admin/whitelist.py.

Покрываем:
- _whitelist_keyboard(), _manage_users_keyboard(), _cancel_keyboard() - builders
- _whitelist_md()           - формирует текст с данными YAML
- _read_user_ids / _write_user_ids - вспомогательные функции
- cb_admin_whitelist()        - главная точка входа whitelist
- cb_set_access_mode()        - переключение whitelist/open
- cb_manage_users()           - экран управления пользователями
- Keyboard builders are called, callbacks answer and edit_text

Faker: user IDs, language.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

def _uid() -> int:
    return fake.random_int(min=100_000_000, max=999_999_999)

def _fake_db_user(is_admin: bool = True):
    u = MagicMock()
    u.id = _uid()
    u.is_admin = is_admin
    return u

def _fake_state():
    s = AsyncMock()
    s.clear = AsyncMock()
    s.set_state = AsyncMock()
    s.get_data = AsyncMock(return_value={})
    return s

def _mock_yaml_data(admin_ids=None, allowed_ids=None) -> dict:
    return {
        "admin_user_ids": admin_ids or [_uid()],
        "allowed_user_ids": allowed_ids or [_uid()],
    }

# Keyboard / text builders

class TestKeyboardBuilders:

    def test_whitelist_keyboard_whitelist_mode(self) -> None:
        from src.bot.routers.admin.whitelist import _whitelist_keyboard
        kb = _whitelist_keyboard(lang="ru", wl=True)
        assert kb is not None
        buttons = [b for row in kb.inline_keyboard for b in row]
        assert any("set_access_mode" in (b.callback_data or "") for b in buttons)

    def test_whitelist_keyboard_open_mode(self) -> None:
        from src.bot.routers.admin.whitelist import _whitelist_keyboard
        kb = _whitelist_keyboard(lang="en", wl=False)
        assert kb is not None

    def test_manage_users_keyboard(self) -> None:
        from src.bot.routers.admin.whitelist import _manage_users_keyboard
        kb = _manage_users_keyboard(lang="ru")
        buttons = [b for row in kb.inline_keyboard for b in row]
        callbacks = [b.callback_data for b in buttons if b.callback_data]
        assert any("user_action" in c for c in callbacks)

    def test_cancel_keyboard(self) -> None:
        from src.bot.routers.admin.whitelist import _cancel_keyboard
        kb = _cancel_keyboard(lang="ru")
        buttons = [b for row in kb.inline_keyboard for b in row]
        assert any("cancel_user_operation" in (b.callback_data or "") for b in buttons)

    def test_faker_keyboards_all_langs(self) -> None:
        from src.bot.routers.admin.whitelist import _cancel_keyboard, _manage_users_keyboard, _whitelist_keyboard
        for lang in ["ru", "en", "de"]:
            assert _whitelist_keyboard(lang, True) is not None
            assert _manage_users_keyboard(lang) is not None
            assert _cancel_keyboard(lang) is not None

# _whitelist_md

class TestWhitelistText:

    @pytest.mark.asyncio
    async def test_returns_non_empty_string(self) -> None:
        from src.bot.routers.admin.whitelist import _whitelist_md
        yaml_data = _mock_yaml_data(admin_ids=[_uid()], allowed_ids=[_uid()])

        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=yaml_data)), \
             patch("src.bot.routers.admin.whitelist.settings") as mock_settings:
            mock_settings.whitelist_mode = True
            text = await _whitelist_md("ru")

        assert isinstance(text, str)
        assert len(text) > 0

    @pytest.mark.asyncio
    async def test_shows_open_mode_text_when_open(self) -> None:
        from src.bot.routers.admin.whitelist import _whitelist_md
        yaml_data = _mock_yaml_data()

        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=yaml_data)), \
             patch("src.bot.routers.admin.whitelist.settings") as mock_settings:
            mock_settings.whitelist_mode = False
            text = await _whitelist_md("en")

        assert isinstance(text, str)

# _read_user_ids / _write_user_ids

class TestReadWriteUserIds:

    def test_read_returns_empty_when_file_missing(self) -> None:
        from src.bot.routers.admin.whitelist import _read_user_ids
        with patch("src.bot.routers.admin.whitelist.USER_IDS_PATH") as mock_path:
            mock_path.exists.return_value = False
            result = _read_user_ids()
        assert result == {"admin_user_ids": [], "allowed_user_ids": []}

    def test_read_parses_yaml_correctly(self) -> None:
        from src.bot.routers.admin.whitelist import _read_user_ids
        admin_id = _uid()
        yaml_content = f"admin_user_ids:\n- {admin_id}\nallowed_user_ids: []\n"
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = yaml_content

        with patch("src.bot.routers.admin.whitelist.USER_IDS_PATH", mock_path):
            result = _read_user_ids()

        assert admin_id in result["admin_user_ids"]

    def test_write_creates_yaml(self) -> None:
        from src.bot.routers.admin.whitelist import _write_user_ids
        data = _mock_yaml_data()
        mock_path = MagicMock()

        with patch("src.bot.routers.admin.whitelist.USER_IDS_PATH", mock_path):
            _write_user_ids(data)

        mock_path.write_text.assert_called_once()

# cb_admin_whitelist

class TestCbAdminWhitelist:

    @pytest.mark.asyncio
    async def test_admin_sees_whitelist_screen(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_admin_whitelist
        cb = fake_callback(data="admin_whitelist")
        state = _fake_state()
        db_user = _fake_db_user(is_admin=True)

        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=True)), \
             patch("src.bot.routers.admin.whitelist._whitelist_md",
                   new=AsyncMock(return_value="whitelist text")), \
             patch("src.bot.routers.admin.whitelist.settings") as mock_settings:
            mock_settings.whitelist_mode = True
            await cb_admin_whitelist(cb, state=state, language="ru", db_user=db_user)

        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_admin_blocked(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_admin_whitelist
        cb = fake_callback(data="admin_whitelist")
        state = _fake_state()

        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=False)):
            await cb_admin_whitelist(cb, state=state, language="ru", db_user=None)

        cb.answer.assert_not_awaited()
        cb.message.edit_text.assert_not_awaited()

# cb_set_access_mode

class TestCbSetAccessMode:

    @pytest.mark.asyncio
    async def test_set_whitelist_mode(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_set_access_mode
        cb = fake_callback(data="set_access_mode|whitelist")
        db_user = _fake_db_user(is_admin=True)

        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=True)), \
             patch("src.bot.routers.admin.whitelist._whitelist_md",
                   new=AsyncMock(return_value="text")), \
             patch("src.bot.routers.admin.whitelist.settings") as mock_settings:
            mock_settings.whitelist_mode = False
            await cb_set_access_mode(cb, language="ru", db_user=db_user)

        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_open_mode(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_set_access_mode
        cb = fake_callback(data="set_access_mode|open")
        db_user = _fake_db_user(is_admin=True)

        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=True)), \
             patch("src.bot.routers.admin.whitelist._whitelist_md",
                   new=AsyncMock(return_value="text")), \
             patch("src.bot.routers.admin.whitelist.settings") as mock_settings:
            mock_settings.whitelist_mode = True
            await cb_set_access_mode(cb, language="en", db_user=db_user)

        cb.message.edit_text.assert_awaited_once()

# cb_manage_users

class TestCbManageUsers:

    @pytest.mark.asyncio
    async def test_manage_users_shows_keyboard(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_manage_users
        cb = fake_callback(data="manage_users")
        db_user = _fake_db_user(is_admin=True)
        state = _fake_state()

        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=True)):
            await cb_manage_users(cb, state=state, language="ru", db_user=db_user)

        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_admin_blocked_from_manage(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_manage_users
        cb = fake_callback(data="manage_users")
        state = _fake_state()

        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=False)):
            await cb_manage_users(cb, state=state, language="ru", db_user=None)

        cb.message.edit_text.assert_not_awaited()

# _load_user_ids / _save_user_ids

class TestLoadSaveUserIds:

    @pytest.mark.asyncio
    async def test_load_user_ids_calls_thread(self) -> None:
        from src.bot.routers.admin.whitelist import _load_user_ids
        data = _mock_yaml_data()

        with patch("asyncio.to_thread", new=AsyncMock(return_value=data)) as mock_thread:
            result = await _load_user_ids()

        assert result == data

    @pytest.mark.asyncio
    async def test_save_user_ids_calls_thread(self) -> None:
        from src.bot.routers.admin.whitelist import _save_user_ids
        data = _mock_yaml_data()

        with patch("asyncio.to_thread", new=AsyncMock()) as mock_thread:
            await _save_user_ids(data)

        mock_thread.assert_awaited_once()
