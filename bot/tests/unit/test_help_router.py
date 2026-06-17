"""
Тесты для bot/src/bot/routers/help.py.

Покрываем:
- _help_text()           — обычный пользователь + администратор
- cmd_help               — Message handler
- cb_help                — CallbackQuery handler
- cmd_help_group_chat    — приватный чат (видео есть / нет), не-приватный чат
"""

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(1)

_ADMIN_ID = 123456789


@pytest.fixture(autouse=True)
def patch_settings():
    ns = types.SimpleNamespace(admin_ids=[_ADMIN_ID])
    with patch("src.bot.routers.help.settings", ns):
        yield ns


# _help_text


class TestHelpText:

    def test_regular_user_no_admin_section(self) -> None:
        from src.bot.routers.help import _help_text
        text = _help_text(is_admin=False, lang="ru")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_admin_includes_admin_commands(self) -> None:
        from src.bot.routers.help import _help_text
        text = _help_text(is_admin=True, lang="ru")
        assert isinstance(text, str)
        # Текст для админа длиннее, чем для пользователя
        user_text = _help_text(is_admin=False, lang="ru")
        assert len(text) > len(user_text)

    def test_all_supported_languages(self) -> None:
        from src.bot.routers.help import _help_text
        for lang in ["ru", "en", "de", "es", "fr", "pl", "pt", "tr"]:
            text = _help_text(is_admin=False, lang=lang)
            assert isinstance(text, str) and len(text) > 0

    def test_admin_text_all_langs(self) -> None:
        from src.bot.routers.help import _help_text
        for lang in ["ru", "en"]:
            admin_text = _help_text(is_admin=True, lang=lang)
            user_text = _help_text(is_admin=False, lang=lang)
            assert len(admin_text) > len(user_text)


# cmd_help


class TestCmdHelp:

    @pytest.mark.asyncio
    async def test_regular_user_gets_help(self, fake_message) -> None:
        from src.bot.routers.help import cmd_help
        msg = fake_message(user_id=fake.random_int(min=200_000_000, max=999_999_999))
        db_user = MagicMock()
        db_user.is_admin = False
        await cmd_help(msg, language="ru", db_user=db_user)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_admin_by_db_flag_gets_admin_section(self, fake_message) -> None:
        from src.bot.routers.help import cmd_help
        msg = fake_message(user_id=fake.random_int(min=200_000_000, max=999_999_999))
        db_user = MagicMock()
        db_user.is_admin = True
        await cmd_help(msg, language="ru", db_user=db_user)
        msg.answer.assert_awaited_once()
        called_text = msg.answer.call_args[0][0]
        user_text = msg.answer.call_args[0][0]
        # Верификация: текст для is_admin=True длиннее
        from src.bot.routers.help import _help_text
        assert called_text == _help_text(is_admin=True, lang="ru")

    @pytest.mark.asyncio
    async def test_admin_by_settings_ids_gets_admin_section(self, fake_message) -> None:
        from src.bot.routers.help import cmd_help
        msg = fake_message(user_id=_ADMIN_ID)
        await cmd_help(msg, language="en", db_user=None)
        msg.answer.assert_awaited_once()
        called_text = msg.answer.call_args[0][0]
        from src.bot.routers.help import _help_text
        assert called_text == _help_text(is_admin=True, lang="en")

    @pytest.mark.asyncio
    async def test_no_db_user_non_admin(self, fake_message) -> None:
        from src.bot.routers.help import cmd_help
        msg = fake_message(user_id=fake.random_int(min=200_000_000, max=999_999_999))
        await cmd_help(msg, language="ru", db_user=None)
        msg.answer.assert_awaited_once()
        from src.bot.routers.help import _help_text
        assert msg.answer.call_args[0][0] == _help_text(is_admin=False, lang="ru")


# cb_help


class TestCbHelp:

    @pytest.mark.asyncio
    async def test_regular_user_callback(self, fake_callback) -> None:
        from src.bot.routers.help import cb_help
        cb = fake_callback(data="help", user_id=fake.random_int(min=200_000_000, max=999_999_999))
        db_user = MagicMock()
        db_user.is_admin = False
        await cb_help(cb, language="ru", db_user=db_user)
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_admin_callback_sends_admin_section(self, fake_callback) -> None:
        from src.bot.routers.help import cb_help
        cb = fake_callback(data="help", user_id=_ADMIN_ID)
        await cb_help(cb, language="ru", db_user=None)
        cb.answer.assert_awaited_once()
        cb.message.edit_text.assert_awaited_once()
        from src.bot.routers.help import _help_text
        called_text = cb.message.edit_text.call_args[0][0]
        assert called_text == _help_text(is_admin=True, lang="ru")

    @pytest.mark.asyncio
    async def test_admin_by_db_flag_callback(self, fake_callback) -> None:
        from src.bot.routers.help import cb_help
        cb = fake_callback(data="help",
                           user_id=fake.random_int(min=200_000_000, max=999_999_999))
        db_user = MagicMock()
        db_user.is_admin = True
        await cb_help(cb, language="en", db_user=db_user)
        cb.message.edit_text.assert_awaited_once()
        from src.bot.routers.help import _help_text
        called_text = cb.message.edit_text.call_args[0][0]
        assert called_text == _help_text(is_admin=True, lang="en")


# cmd_help_group_chat


class TestCmdHelpGroupChat:

    def _make_private_msg(self, user_id: int | None = None) -> MagicMock:
        msg = MagicMock()
        msg.from_user = MagicMock()
        msg.from_user.id = user_id or fake.random_int(min=100_000_000, max=999_999_999)
        msg.chat = MagicMock()
        msg.chat.type = "private"
        msg.answer = AsyncMock()
        msg.answer_video = AsyncMock()
        return msg

    def _make_bot(self, username: str = "monkey_ai_bot") -> MagicMock:
        bot = MagicMock()
        bot_info = MagicMock()
        bot_info.username = username
        bot.get_me = AsyncMock(return_value=bot_info)
        return bot

    @pytest.mark.asyncio
    async def test_private_chat_with_video(self, fake_message) -> None:
        from src.bot.routers.help import cmd_help_group_chat
        msg = self._make_private_msg()
        bot = self._make_bot()
        with patch("src.bot.routers.help._VIDEO_PATH") as mock_path:
            mock_path.exists.return_value = True
            await cmd_help_group_chat(msg, language="ru", bot=bot)
        msg.answer.assert_awaited_once()
        msg.answer_video.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_private_chat_video_missing(self, fake_message) -> None:
        from src.bot.routers.help import cmd_help_group_chat
        msg = self._make_private_msg()
        bot = self._make_bot()
        with patch("src.bot.routers.help._VIDEO_PATH") as mock_path:
            mock_path.exists.return_value = False
            await cmd_help_group_chat(msg, language="ru", bot=bot)
        msg.answer.assert_awaited()
        msg.answer_video.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_private_chat_returns_silently(self) -> None:
        from src.bot.routers.help import cmd_help_group_chat
        msg = self._make_private_msg()
        msg.chat.type = "supergroup"
        bot = self._make_bot()
        await cmd_help_group_chat(msg, language="ru", bot=bot)
        msg.answer.assert_not_awaited()
        bot.get_me.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bot_get_me_is_called(self) -> None:
        from src.bot.routers.help import cmd_help_group_chat
        msg = self._make_private_msg()
        bot = self._make_bot(username="monkey_bot")
        with patch("src.bot.routers.help._VIDEO_PATH") as mock_path:
            mock_path.exists.return_value = False
            await cmd_help_group_chat(msg, language="ru", bot=bot)
        bot.get_me.assert_awaited_once()
        msg.answer.assert_awaited()