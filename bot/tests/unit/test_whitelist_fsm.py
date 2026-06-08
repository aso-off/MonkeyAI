"""
FSM-флоу тесты для bot/src/bot/routers/admin/whitelist.py.

Покрываем строки 148-276 (ранее не покрытые):
- cb_user_action        — все действия + суперадмин-проверка + view_list
- cb_cancel_user_operation — сброс состояния
- msg_user_id_input     — невалидный ID, add/remove user/admin (все ветки)
"""

import types
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from faker import Faker

fake = Faker()
Faker.seed(0)

_SUPERADMIN_ID = 999_000_001
_REGULAR_ADMIN_ID = 999_000_002


def _uid() -> int:
    return fake.random_int(min=100_000_000, max=999_999_999)


def _fake_db_user(is_admin: bool = True):
    u = MagicMock()
    u.id = _uid()
    u.is_admin = is_admin
    return u


def _fake_state(action: str = "add_user"):
    s = AsyncMock()
    s.clear = AsyncMock()
    s.set_state = AsyncMock()
    s.update_data = AsyncMock()
    s.get_data = AsyncMock(return_value={"action": action})
    return s


def _fake_message(text: str = "123456789"):
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = _SUPERADMIN_ID
    msg.text = text
    msg.answer = AsyncMock()
    return msg


@pytest.fixture(autouse=True)
def patch_settings():
    ns = types.SimpleNamespace(
        admin_ids=[_SUPERADMIN_ID],
        whitelist_mode=True,
        allowed_user_ids=[],
    )
    with patch("src.bot.routers.admin.whitelist.settings", ns), \
         patch("src.bot.routers.admin.whitelist._SUPERADMIN_ID", _SUPERADMIN_ID):
        yield ns


# ── cb_user_action ────────────────────────────────────────────────────────────


class TestCbUserAction:

    @pytest.mark.asyncio
    async def test_non_admin_blocked(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_user_action
        cb = fake_callback(data="user_action|add_user")
        state = _fake_state()
        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=False)):
            await cb_user_action(cb, state=state, language="ru", db_user=None)
        cb.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_superadmin_cannot_add_admin(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_user_action
        cb = fake_callback(data="user_action|add_admin", user_id=_REGULAR_ADMIN_ID)
        state = _fake_state()
        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=True)):
            await cb_user_action(cb, state=state, language="ru", db_user=_fake_db_user())
        cb.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_non_superadmin_cannot_remove_admin(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_user_action
        cb = fake_callback(data="user_action|remove_admin", user_id=_REGULAR_ADMIN_ID)
        state = _fake_state()
        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=True)):
            await cb_user_action(cb, state=state, language="ru", db_user=_fake_db_user())
        cb.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_view_list_shows_users(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_user_action
        uid1, uid2 = _uid(), _uid()
        cb = fake_callback(data="user_action|view_list", user_id=_SUPERADMIN_ID)
        state = _fake_state()
        yaml_data = {"admin_user_ids": [uid1], "allowed_user_ids": [uid2]}
        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=True)), \
             patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=yaml_data)):
            await cb_user_action(cb, state=state, language="ru", db_user=_fake_db_user())
        cb.answer.assert_awaited()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_view_list_empty_lists(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_user_action
        cb = fake_callback(data="user_action|view_list", user_id=_SUPERADMIN_ID)
        state = _fake_state()
        yaml_data = {"admin_user_ids": [], "allowed_user_ids": []}
        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=True)), \
             patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=yaml_data)):
            await cb_user_action(cb, state=state, language="ru", db_user=_fake_db_user())
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action,prompt_key", [
        ("add_user",    "enter_user_id_to_add"),
        ("remove_user", "enter_user_id_to_remove"),
        ("add_admin",   "enter_user_id_to_add_admin"),
        ("remove_admin","enter_user_id_to_remove_admin"),
    ])
    async def test_action_sets_fsm_state(self, fake_callback, action, prompt_key) -> None:
        from src.bot.routers.admin.whitelist import cb_user_action
        cb = fake_callback(data=f"user_action|{action}", user_id=_SUPERADMIN_ID)
        state = _fake_state()
        with patch("src.bot.routers.admin.whitelist.require_admin",
                   new=AsyncMock(return_value=True)):
            await cb_user_action(cb, state=state, language="ru", db_user=_fake_db_user())
        state.set_state.assert_awaited_once()
        state.update_data.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()


# ── cb_cancel_user_operation ──────────────────────────────────────────────────


class TestCbCancelUserOperation:

    @pytest.mark.asyncio
    async def test_cancel_clears_state_and_shows_keyboard(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_cancel_user_operation
        cb = fake_callback(data="cancel_user_operation")
        state = _fake_state()
        await cb_cancel_user_operation(cb, state=state, language="ru")
        state.clear.assert_awaited_once()
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cancel_all_langs(self, fake_callback) -> None:
        from src.bot.routers.admin.whitelist import cb_cancel_user_operation
        for lang in ["ru", "en", "de"]:
            cb = fake_callback(data="cancel_user_operation")
            state = _fake_state()
            await cb_cancel_user_operation(cb, state=state, language=lang)
            state.clear.assert_awaited_once()


# ── msg_user_id_input — невалидные ID ─────────────────────────────────────────


class TestMsgUserIdInputValidation:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_input", [
        "abc",
        "1234567",       # 7 цифр — мало
        "12345678901234",# 14 цифр — много
        "",
        "12 34567890",
    ])
    async def test_invalid_id_sends_error(self, bad_input: str) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        msg = _fake_message(text=bad_input)
        state = _fake_state()
        await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()
        state.clear.assert_not_awaited()


# ── msg_user_id_input — add_user ──────────────────────────────────────────────


class TestMsgAddUser:

    @pytest.mark.asyncio
    async def test_add_new_user_success(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="add_user")
        cfg = {"admin_user_ids": [], "allowed_user_ids": []}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)), \
             patch("src.bot.routers.admin.whitelist._save_user_ids", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.auth_state.reload", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.api.set_user_whitelisted",
                   new=AsyncMock()):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()
        assert uid in cfg["allowed_user_ids"]

    @pytest.mark.asyncio
    async def test_add_user_already_in_list(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="add_user")
        cfg = {"admin_user_ids": [], "allowed_user_ids": [uid]}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()


# ── msg_user_id_input — remove_user ──────────────────────────────────────────


class TestMsgRemoveUser:

    @pytest.mark.asyncio
    async def test_remove_user_success(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="remove_user")
        cfg = {"admin_user_ids": [], "allowed_user_ids": [uid]}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)), \
             patch("src.bot.routers.admin.whitelist._save_user_ids", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.auth_state.reload", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.api.set_user_whitelisted",
                   new=AsyncMock()):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()
        assert uid not in cfg["allowed_user_ids"]

    @pytest.mark.asyncio
    async def test_remove_user_not_in_list(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="remove_user")
        cfg = {"admin_user_ids": [], "allowed_user_ids": []}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_user_who_is_admin_rejected(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="remove_user")
        cfg = {"admin_user_ids": [uid], "allowed_user_ids": [uid]}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()
        assert uid in cfg["allowed_user_ids"]

    @pytest.mark.asyncio
    async def test_remove_user_api_404_ignored(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="remove_user")
        cfg = {"admin_user_ids": [], "allowed_user_ids": [uid]}

        response_mock = MagicMock()
        response_mock.status_code = 404
        http_404 = httpx.HTTPStatusError("not found", request=MagicMock(), response=response_mock)

        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)), \
             patch("src.bot.routers.admin.whitelist._save_user_ids", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.auth_state.reload", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.api.set_user_whitelisted",
                   new=AsyncMock(side_effect=http_404)):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()


# ── msg_user_id_input — add_admin ─────────────────────────────────────────────


class TestMsgAddAdmin:

    @pytest.mark.asyncio
    async def test_add_admin_success(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="add_admin")
        cfg = {"admin_user_ids": [], "allowed_user_ids": [uid]}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)), \
             patch("src.bot.routers.admin.whitelist._save_user_ids", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.auth_state.reload", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.api.set_user_admin",
                   new=AsyncMock()):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()
        assert uid in cfg["admin_user_ids"]

    @pytest.mark.asyncio
    async def test_add_admin_not_in_whitelist(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="add_admin")
        cfg = {"admin_user_ids": [], "allowed_user_ids": []}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()
        assert uid not in cfg["admin_user_ids"]

    @pytest.mark.asyncio
    async def test_add_admin_already_admin(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="add_admin")
        cfg = {"admin_user_ids": [uid], "allowed_user_ids": [uid]}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()
        assert cfg["admin_user_ids"].count(uid) == 1


# ── msg_user_id_input — remove_admin ─────────────────────────────────────────


class TestMsgRemoveAdmin:

    @pytest.mark.asyncio
    async def test_remove_admin_success(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="remove_admin")
        cfg = {"admin_user_ids": [uid], "allowed_user_ids": [uid]}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)), \
             patch("src.bot.routers.admin.whitelist._save_user_ids", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.auth_state.reload", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.api.set_user_admin",
                   new=AsyncMock()):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()
        assert uid not in cfg["admin_user_ids"]

    @pytest.mark.asyncio
    async def test_remove_admin_not_in_list(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="remove_admin")
        cfg = {"admin_user_ids": [], "allowed_user_ids": [uid]}
        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_admin_api_404_ignored(self) -> None:
        from src.bot.routers.admin.whitelist import msg_user_id_input
        uid = _uid()
        msg = _fake_message(text=str(uid))
        state = _fake_state(action="remove_admin")
        cfg = {"admin_user_ids": [uid], "allowed_user_ids": [uid]}

        response_mock = MagicMock()
        response_mock.status_code = 404
        http_404 = httpx.HTTPStatusError("not found", request=MagicMock(), response=response_mock)

        with patch("src.bot.routers.admin.whitelist._load_user_ids",
                   new=AsyncMock(return_value=cfg)), \
             patch("src.bot.routers.admin.whitelist._save_user_ids", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.auth_state.reload", new=AsyncMock()), \
             patch("src.bot.routers.admin.whitelist.api.set_user_admin",
                   new=AsyncMock(side_effect=http_404)):
            await msg_user_id_input(msg, state=state, language="ru")
        msg.answer.assert_awaited_once()
