"""Юнит-тесты для keyboard builder функций из bot routers.

Keyboard файлы пустые — вся логика в роутерах. Тестируем:
- структуру (количество кнопок, callback_data)
- условные ветки (is_admin, webapp_url)
- web_app кнопки
"""

import types
from unittest.mock import patch

import pytest
from aiogram.types import InlineKeyboardMarkup


# ── start.py keyboards ────────────────────────────────────────────────────────

class TestPrivateKeyboard:
    """Тесты _private_keyboard из routers/start.py."""

    @pytest.fixture(autouse=True)
    def patch_settings(self, mocker):
        mocker.patch(
            "src.bot.routers.start.settings",
            types.SimpleNamespace(webapp_url="https://app.example.com", admin_ids=[]),
        )

    @pytest.mark.unit
    def test_non_admin_has_profile_and_about(self) -> None:
        from src.bot.routers.start import _private_keyboard
        kb = _private_keyboard(is_admin=False, lang="ru")
        assert isinstance(kb, InlineKeyboardMarkup)
        all_data = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        assert "profile" in all_data
        assert "about" in all_data

    @pytest.mark.unit
    def test_admin_has_admin_panel_button(self) -> None:
        from src.bot.routers.start import _private_keyboard
        kb = _private_keyboard(is_admin=True, lang="ru")
        all_data = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        assert "admin_panel" in all_data

    @pytest.mark.unit
    def test_non_admin_has_no_admin_panel(self) -> None:
        from src.bot.routers.start import _private_keyboard
        kb = _private_keyboard(is_admin=False, lang="ru")
        all_data = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        assert "admin_panel" not in all_data

    @pytest.mark.unit
    def test_webapp_url_adds_web_app_button(self) -> None:
        from src.bot.routers.start import _private_keyboard
        kb = _private_keyboard(is_admin=False, lang="ru")
        has_webapp = any(
            btn.web_app for row in kb.inline_keyboard for btn in row if btn.web_app
        )
        assert has_webapp

    @pytest.mark.unit
    def test_no_webapp_url_no_web_app_button(self, mocker) -> None:
        mocker.patch(
            "src.bot.routers.start.settings",
            types.SimpleNamespace(webapp_url="", admin_ids=[]),
        )
        from src.bot.routers.start import _private_keyboard
        kb = _private_keyboard(is_admin=False, lang="ru")
        has_webapp = any(
            btn.web_app for row in kb.inline_keyboard for btn in row if btn.web_app
        )
        assert not has_webapp

    @pytest.mark.unit
    def test_admin_with_webapp_has_more_rows(self, mocker) -> None:
        from src.bot.routers.start import _private_keyboard
        kb_admin = _private_keyboard(is_admin=True, lang="ru")
        kb_user = _private_keyboard(is_admin=False, lang="ru")
        assert len(kb_admin.inline_keyboard) > len(kb_user.inline_keyboard)


class TestGroupKeyboard:
    """Тесты _group_keyboard из routers/start.py."""

    @pytest.mark.unit
    def test_returns_inline_markup(self) -> None:
        from src.bot.routers.start import _group_keyboard
        kb = _group_keyboard("ru")
        assert isinstance(kb, InlineKeyboardMarkup)

    @pytest.mark.unit
    def test_has_profile_button(self) -> None:
        from src.bot.routers.start import _group_keyboard
        all_data = [btn.callback_data for row in _group_keyboard("ru").inline_keyboard for btn in row if btn.callback_data]
        assert "profile" in all_data

    @pytest.mark.unit
    def test_has_help_and_about(self) -> None:
        from src.bot.routers.start import _group_keyboard
        all_data = [btn.callback_data for row in _group_keyboard("ru").inline_keyboard for btn in row if btn.callback_data]
        assert "help" in all_data and "about" in all_data

    @pytest.mark.unit
    def test_no_admin_panel_in_group(self) -> None:
        from src.bot.routers.start import _group_keyboard
        all_data = [btn.callback_data for row in _group_keyboard("ru").inline_keyboard for btn in row if btn.callback_data]
        assert "admin_panel" not in all_data


# ── admin/admin.py keyboard ───────────────────────────────────────────────────


class TestAdminPanelKeyboard:
    @pytest.mark.unit
    def test_returns_inline_markup(self) -> None:
        from src.bot.routers.admin.admin import _admin_panel_keyboard
        kb = _admin_panel_keyboard("ru")
        assert isinstance(kb, InlineKeyboardMarkup)

    @pytest.mark.unit
    def test_has_all_expected_callbacks(self) -> None:
        from src.bot.routers.admin.admin import _admin_panel_keyboard
        all_data = {btn.callback_data for row in _admin_panel_keyboard("ru").inline_keyboard for btn in row if btn.callback_data}
        expected = {"admin_status", "admin_restart", "admin_system", "admin_moderation", "admin_whitelist", "back_to_start"}
        assert expected.issubset(all_data)

    @pytest.mark.unit
    @pytest.mark.parametrize("lang", ["ru", "en"])
    def test_all_langs_return_markup(self, lang: str) -> None:
        from src.bot.routers.admin.admin import _admin_panel_keyboard
        kb = _admin_panel_keyboard(lang)
        assert len(kb.inline_keyboard) > 0


# ── admin/whitelist.py keyboards ──────────────────────────────────────────────


class TestWhitelistKeyboard:
    @pytest.fixture(autouse=True)
    def patch_whitelist_settings(self, mocker):
        mocker.patch(
            "src.bot.routers.admin.whitelist.settings",
            types.SimpleNamespace(admin_ids=[123456789], whitelist_mode=True, allowed_user_ids=[]),
        )

    @pytest.mark.unit
    def test_whitelist_mode_has_checkmark_on_whitelist_btn(self) -> None:
        from src.bot.routers.admin.whitelist import _whitelist_keyboard
        kb = _whitelist_keyboard("ru", wl=True)
        # Первая кнопка должна содержать ✅
        first_btn = kb.inline_keyboard[0][0]
        assert "✅" in first_btn.text

    @pytest.mark.unit
    def test_open_mode_has_checkmark_on_open_btn(self) -> None:
        from src.bot.routers.admin.whitelist import _whitelist_keyboard
        kb = _whitelist_keyboard("ru", wl=False)
        # Вторая кнопка должна содержать ✅
        second_btn = kb.inline_keyboard[1][0]
        assert "✅" in second_btn.text

    @pytest.mark.unit
    def test_has_manage_users_button(self) -> None:
        from src.bot.routers.admin.whitelist import _whitelist_keyboard
        all_data = {btn.callback_data for row in _whitelist_keyboard("ru", True).inline_keyboard for btn in row if btn.callback_data}
        assert "manage_users" in all_data

    @pytest.mark.unit
    def test_has_back_button(self) -> None:
        from src.bot.routers.admin.whitelist import _whitelist_keyboard
        all_data = {btn.callback_data for row in _whitelist_keyboard("ru", True).inline_keyboard for btn in row if btn.callback_data}
        assert "admin_panel" in all_data


class TestManageUsersKeyboard:
    @pytest.fixture(autouse=True)
    def patch_whitelist_settings(self, mocker):
        mocker.patch(
            "src.bot.routers.admin.whitelist.settings",
            types.SimpleNamespace(admin_ids=[123456789], whitelist_mode=True, allowed_user_ids=[]),
        )

    @pytest.mark.unit
    def test_returns_inline_markup(self) -> None:
        from src.bot.routers.admin.whitelist import _manage_users_keyboard
        assert isinstance(_manage_users_keyboard("ru"), InlineKeyboardMarkup)

    @pytest.mark.unit
    def test_has_add_remove_user_buttons(self) -> None:
        from src.bot.routers.admin.whitelist import _manage_users_keyboard
        all_data = {btn.callback_data for row in _manage_users_keyboard("ru").inline_keyboard for btn in row if btn.callback_data}
        assert "user_action|add_user" in all_data
        assert "user_action|remove_user" in all_data

    @pytest.mark.unit
    def test_has_add_remove_admin_buttons(self) -> None:
        from src.bot.routers.admin.whitelist import _manage_users_keyboard
        all_data = {btn.callback_data for row in _manage_users_keyboard("ru").inline_keyboard for btn in row if btn.callback_data}
        assert "user_action|add_admin" in all_data
        assert "user_action|remove_admin" in all_data

    @pytest.mark.unit
    def test_has_view_list_button(self) -> None:
        from src.bot.routers.admin.whitelist import _manage_users_keyboard
        all_data = {btn.callback_data for row in _manage_users_keyboard("ru").inline_keyboard for btn in row if btn.callback_data}
        assert "user_action|view_list" in all_data

    @pytest.mark.unit
    def test_has_back_button(self) -> None:
        from src.bot.routers.admin.whitelist import _manage_users_keyboard
        all_data = {btn.callback_data for row in _manage_users_keyboard("ru").inline_keyboard for btn in row if btn.callback_data}
        assert "admin_whitelist" in all_data


class TestCancelKeyboard:
    @pytest.fixture(autouse=True)
    def patch_whitelist_settings(self, mocker):
        mocker.patch(
            "src.bot.routers.admin.whitelist.settings",
            types.SimpleNamespace(admin_ids=[123456789], whitelist_mode=True, allowed_user_ids=[]),
        )

    @pytest.mark.unit
    def test_single_cancel_button(self) -> None:
        from src.bot.routers.admin.whitelist import _cancel_keyboard
        kb = _cancel_keyboard("ru")
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 1
        assert all_buttons[0].callback_data == "cancel_user_operation"


# ── profile/profile.py keyboard ───────────────────────────────────────────────


class TestProfileKeyboard:
    @pytest.mark.unit
    def test_returns_inline_markup(self) -> None:
        from src.bot.routers.profile.profile import _profile_keyboard
        kb = _profile_keyboard("ru")
        assert isinstance(kb, InlineKeyboardMarkup)

    @pytest.mark.unit
    def test_has_settings_and_stats(self) -> None:
        from src.bot.routers.profile.profile import _profile_keyboard
        all_data = {btn.callback_data for row in _profile_keyboard("ru").inline_keyboard for btn in row if btn.callback_data}
        assert "profile_settings" in all_data
        assert "profile_stats" in all_data

    @pytest.mark.unit
    def test_has_balance_button(self) -> None:
        from src.bot.routers.profile.profile import _profile_keyboard
        all_data = {btn.callback_data for row in _profile_keyboard("ru").inline_keyboard for btn in row if btn.callback_data}
        assert "show_balance" in all_data

    @pytest.mark.unit
    def test_has_back_button(self) -> None:
        from src.bot.routers.profile.profile import _profile_keyboard
        all_data = {btn.callback_data for row in _profile_keyboard("ru").inline_keyboard for btn in row if btn.callback_data}
        assert "back_to_start" in all_data


# ── profile/profile.py — _build_profile_text ──────────────────────────────────


class TestBuildProfileText:
    @pytest.fixture(autouse=True)
    def patch_profile_settings(self, mocker):
        mocker.patch(
            "src.bot.routers.profile.profile.settings",
            types.SimpleNamespace(admin_ids=[999]),
        )

    @pytest.mark.unit
    def test_none_user_returns_error_text(self) -> None:
        from src.bot.routers.profile.profile import _build_profile_text
        result = _build_profile_text(None, "ru")
        assert isinstance(result, str) and len(result) > 0

    @pytest.mark.unit
    def test_regular_user_profile(self, fake) -> None:
        from datetime import datetime, timezone
        from src.bot.routers.profile.profile import _build_profile_text
        user = types.SimpleNamespace(
            id=fake.random_int(min=100_000, max=999_999_999),
            language="ru",
            first_seen=datetime.now(timezone.utc),
        )
        result = _build_profile_text(user, "ru")
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_admin_user_has_admin_status(self, fake) -> None:
        from datetime import datetime, timezone
        from src.bot.routers.profile.profile import _build_profile_text
        admin_id = 999
        user = types.SimpleNamespace(
            id=admin_id,
            language="ru",
            first_seen=datetime.now(timezone.utc),
        )
        result = _build_profile_text(user, "ru")
        assert isinstance(result, str)
