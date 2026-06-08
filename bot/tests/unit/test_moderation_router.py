"""
Тесты для bot/src/bot/routers/admin/moderation.py.

Покрываем:
- _moderation_keyboard() — builders при enabled/disabled
- _moderation_text()     — текст при enabled/disabled
- cb_admin_moderation    — admin видит экран / non-admin заблокирован
- cb_toggle_moderation   — toggle on→off, off→on / non-admin заблокирован
"""

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(2)


def _uid() -> int:
    return fake.random_int(min=100_000_000, max=999_999_999)


def _fake_db_user(is_admin: bool = True) -> MagicMock:
    u = MagicMock()
    u.id = _uid()
    u.is_admin = is_admin
    return u


@pytest.fixture(autouse=True)
def patch_settings():
    ns = types.SimpleNamespace(
        admin_ids=[123456789],
        enable_content_moderation=True,
    )
    with patch("src.bot.routers.admin.moderation.settings", ns):
        yield ns


# ── _moderation_keyboard / _moderation_text ───────────────────────────────────


class TestModerationBuilders:

    def test_keyboard_when_enabled(self, patch_settings) -> None:
        from src.bot.routers.admin.moderation import _moderation_keyboard
        patch_settings.enable_content_moderation = True
        kb = _moderation_keyboard("ru")
        buttons = [b for row in kb.inline_keyboard for b in row]
        assert any("toggle_moderation" in (b.callback_data or "") for b in buttons)

    def test_keyboard_when_disabled(self, patch_settings) -> None:
        from src.bot.routers.admin.moderation import _moderation_keyboard
        patch_settings.enable_content_moderation = False
        kb = _moderation_keyboard("en")
        buttons = [b for row in kb.inline_keyboard for b in row]
        assert any("admin_panel" in (b.callback_data or "") for b in buttons)

    def test_keyboard_all_langs(self) -> None:
        from src.bot.routers.admin.moderation import _moderation_keyboard
        for lang in ["ru", "en", "de"]:
            kb = _moderation_keyboard(lang)
            assert kb is not None

    def test_text_when_enabled(self, patch_settings) -> None:
        from src.bot.routers.admin.moderation import _moderation_text
        patch_settings.enable_content_moderation = True
        text = _moderation_text("ru")
        assert isinstance(text, str) and len(text) > 0

    def test_text_when_disabled(self, patch_settings) -> None:
        from src.bot.routers.admin.moderation import _moderation_text
        patch_settings.enable_content_moderation = False
        text = _moderation_text("ru")
        assert isinstance(text, str) and len(text) > 0

    def test_text_enabled_differs_from_disabled(self, patch_settings) -> None:
        from src.bot.routers.admin.moderation import _moderation_text
        patch_settings.enable_content_moderation = True
        text_on = _moderation_text("ru")
        patch_settings.enable_content_moderation = False
        text_off = _moderation_text("ru")
        assert text_on != text_off


# ── cb_admin_moderation ───────────────────────────────────────────────────────


class TestCbAdminModeration:

    @pytest.mark.asyncio
    async def test_admin_sees_moderation_screen(self, fake_callback) -> None:
        from src.bot.routers.admin.moderation import cb_admin_moderation
        cb = fake_callback(data="admin_moderation")
        with patch("src.bot.routers.admin.moderation.require_admin",
                   new=AsyncMock(return_value=True)):
            await cb_admin_moderation(cb, language="ru", db_user=_fake_db_user())
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_admin_blocked(self, fake_callback) -> None:
        from src.bot.routers.admin.moderation import cb_admin_moderation
        cb = fake_callback(data="admin_moderation")
        with patch("src.bot.routers.admin.moderation.require_admin",
                   new=AsyncMock(return_value=False)):
            await cb_admin_moderation(cb, language="ru", db_user=None)
        cb.answer.assert_not_awaited()
        cb.message.edit_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_all_langs_render(self, fake_callback) -> None:
        from src.bot.routers.admin.moderation import cb_admin_moderation
        for lang in ["ru", "en", "de"]:
            cb = fake_callback(data="admin_moderation")
            with patch("src.bot.routers.admin.moderation.require_admin",
                       new=AsyncMock(return_value=True)):
                await cb_admin_moderation(cb, language=lang, db_user=_fake_db_user())
            cb.message.edit_text.assert_awaited_once()


# ── cb_toggle_moderation ──────────────────────────────────────────────────────


class TestCbToggleModeration:

    @pytest.mark.asyncio
    async def test_toggle_on_to_off(self, fake_callback, patch_settings) -> None:
        from src.bot.routers.admin.moderation import cb_toggle_moderation
        patch_settings.enable_content_moderation = True
        cb = fake_callback(data="toggle_moderation")
        with patch("src.bot.routers.admin.moderation.require_admin",
                   new=AsyncMock(return_value=True)):
            await cb_toggle_moderation(cb, language="ru", db_user=_fake_db_user())
        assert patch_settings.enable_content_moderation is False
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_toggle_off_to_on(self, fake_callback, patch_settings) -> None:
        from src.bot.routers.admin.moderation import cb_toggle_moderation
        patch_settings.enable_content_moderation = False
        cb = fake_callback(data="toggle_moderation")
        with patch("src.bot.routers.admin.moderation.require_admin",
                   new=AsyncMock(return_value=True)):
            await cb_toggle_moderation(cb, language="ru", db_user=_fake_db_user())
        assert patch_settings.enable_content_moderation is True
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_admin_cannot_toggle(self, fake_callback) -> None:
        from src.bot.routers.admin.moderation import cb_toggle_moderation
        cb = fake_callback(data="toggle_moderation")
        with patch("src.bot.routers.admin.moderation.require_admin",
                   new=AsyncMock(return_value=False)):
            await cb_toggle_moderation(cb, language="ru", db_user=None)
        cb.answer.assert_not_awaited()
        cb.message.edit_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_toggle_twice_returns_to_original(self, fake_callback, patch_settings) -> None:
        from src.bot.routers.admin.moderation import cb_toggle_moderation
        original = patch_settings.enable_content_moderation
        for _ in range(2):
            cb = fake_callback(data="toggle_moderation")
            with patch("src.bot.routers.admin.moderation.require_admin",
                       new=AsyncMock(return_value=True)):
                await cb_toggle_moderation(cb, language="ru", db_user=_fake_db_user())
        assert patch_settings.enable_content_moderation == original

    @pytest.mark.asyncio
    async def test_answer_contains_status_text(self, fake_callback, patch_settings) -> None:
        from src.bot.routers.admin.moderation import cb_toggle_moderation
        patch_settings.enable_content_moderation = False
        cb = fake_callback(data="toggle_moderation")
        with patch("src.bot.routers.admin.moderation.require_admin",
                   new=AsyncMock(return_value=True)):
            await cb_toggle_moderation(cb, language="ru", db_user=_fake_db_user())
        answer_text = cb.answer.call_args[0][0]
        assert isinstance(answer_text, str) and len(answer_text) > 0
