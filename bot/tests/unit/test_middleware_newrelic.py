"""
Тесты для bot/src/bot/middleware/newrelic.py.

Покрываем NewRelicMiddleware.__call__:
- event.message: команда, обычный текст, voice, photo, document, sticker, other
- event.callback_query: с data (prefix по ":"), без data
- event.my_chat_member
- fallback (event_type)
- исключение при разборе update → tx_name "update/unknown"
- исключение в handler → nr_notice_error вызван, исключение ре-рейзится
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Update
from faker import Faker

fake = Faker()
Faker.seed(42)


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


def _make_event(
    message=None,
    callback_query=None,
    my_chat_member=None,
    event_type: str = "message",
) -> MagicMock:
    event = MagicMock(spec=Update)
    event.message = message
    event.callback_query = callback_query
    event.my_chat_member = my_chat_member
    event.event_type = event_type
    return event


def _make_message(
    text: str | None = None,
    has_voice: bool = False,
    has_photo: bool = False,
    has_document: bool = False,
    has_sticker: bool = False,
) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = _uid()
    msg.from_user.username = fake.user_name()
    msg.chat = MagicMock()
    msg.chat.id = msg.from_user.id
    msg.text = text
    msg.voice = MagicMock() if has_voice else None
    msg.photo = MagicMock() if has_photo else None
    msg.document = MagicMock() if has_document else None
    msg.sticker = MagicMock() if has_sticker else None
    return msg


def _nr_patches():
    return (
        patch("src.bot.middleware.newrelic.nr_transaction_name"),
        patch("src.bot.middleware.newrelic.nr_add_custom_parameter"),
        patch("src.bot.middleware.newrelic.nr_notice_error"),
    )


class TestNewRelicMiddleware:

    @pytest.mark.asyncio
    async def test_command_sets_command_tx_name(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock(return_value="ok")
        msg = _make_message(text="/start arg1")
        event = _make_event(message=msg)
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert any("command" in n and "start" in n for n in captured)

    @pytest.mark.asyncio
    async def test_text_message_sets_text_tx_name(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock(return_value="ok")
        msg = _make_message(text="hello world")
        event = _make_event(message=msg)
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert "message/text" in captured

    @pytest.mark.asyncio
    async def test_voice_message_sets_voice_tx_name(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        msg = _make_message(has_voice=True)
        event = _make_event(message=msg)
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert "message/voice" in captured

    @pytest.mark.asyncio
    async def test_photo_message_sets_photo_tx_name(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        msg = _make_message(has_photo=True)
        event = _make_event(message=msg)
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert "message/photo" in captured

    @pytest.mark.asyncio
    async def test_document_message_sets_document_tx_name(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        msg = _make_message(has_document=True)
        event = _make_event(message=msg)
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert "message/document" in captured

    @pytest.mark.asyncio
    async def test_sticker_message_sets_sticker_tx_name(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        msg = _make_message(has_sticker=True)
        event = _make_event(message=msg)
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert "message/sticker" in captured

    @pytest.mark.asyncio
    async def test_other_message_type_sets_other(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        msg = _make_message()  # no text, no voice, no photo, etc.
        event = _make_event(message=msg)
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert "message/other" in captured

    @pytest.mark.asyncio
    async def test_callback_query_with_prefix(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        cb = MagicMock()
        cb.from_user = MagicMock()
        cb.from_user.id = _uid()
        cb.from_user.username = fake.user_name()
        cb.message = MagicMock()
        cb.message.chat.id = _uid()
        cb.data = "select_model:gpt-4o"
        event = _make_event(callback_query=cb, event_type="callback_query")
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert "callback/select_model" in captured

    @pytest.mark.asyncio
    async def test_callback_query_without_data(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        cb = MagicMock()
        cb.from_user = MagicMock()
        cb.from_user.id = _uid()
        cb.from_user.username = None
        cb.message = MagicMock()
        cb.message.chat.id = _uid()
        cb.data = None
        event = _make_event(callback_query=cb, event_type="callback_query")
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert any("callback" in n for n in captured)

    @pytest.mark.asyncio
    async def test_my_chat_member_event(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        member = MagicMock()
        member.from_user = MagicMock()
        member.from_user.id = _uid()
        event = _make_event(my_chat_member=member, event_type="my_chat_member")
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert "my_chat_member" in captured

    @pytest.mark.asyncio
    async def test_fallback_uses_event_type(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        event = _make_event(event_type="inline_query")
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert any("inline_query" in n for n in captured)

    @pytest.mark.asyncio
    async def test_parse_exception_uses_unknown_name(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        # message truthy, но text.startswith поднимает → попадаем в except
        msg = MagicMock()
        msg.from_user = None
        msg.chat = None
        bad_text = MagicMock()
        bad_text.__bool__ = MagicMock(return_value=True)
        bad_text.startswith = MagicMock(side_effect=RuntimeError("parse error"))
        msg.text = bad_text
        msg.voice = None
        msg.photo = None
        msg.document = None
        msg.sticker = None
        event = MagicMock(spec=Update)
        event.message = msg
        event.callback_query = None
        event.my_chat_member = None
        captured = []
        with patch("src.bot.middleware.newrelic.nr_transaction_name",
                   side_effect=lambda n: captured.append(n)), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert "update/unknown" in captured

    @pytest.mark.asyncio
    async def test_handler_exception_calls_nr_notice_error_and_reraises(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock(side_effect=RuntimeError(fake.sentence()))
        msg = _make_message(text="hello")
        event = _make_event(message=msg)
        nr_notice_mock = MagicMock()
        with patch("src.bot.middleware.newrelic.nr_transaction_name"), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error", nr_notice_mock):
            with pytest.raises(RuntimeError):
                await mw(handler, event, {})
        nr_notice_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_id_passed_as_custom_parameter(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock()
        uid = _uid()
        msg = _make_message(text="hello")
        msg.from_user.id = uid
        event = _make_event(message=msg)
        params = {}
        with patch("src.bot.middleware.newrelic.nr_transaction_name"), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter",
                   side_effect=lambda k, v: params.update({k: v})), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            await mw(handler, event, {})
        assert params.get("telegram_user_id") == uid

    @pytest.mark.asyncio
    async def test_handler_result_returned(self) -> None:
        from src.bot.middleware.newrelic import NewRelicMiddleware
        mw = NewRelicMiddleware()
        handler = AsyncMock(return_value="expected_result")
        msg = _make_message(text="/test")
        event = _make_event(message=msg)
        with patch("src.bot.middleware.newrelic.nr_transaction_name"), \
             patch("src.bot.middleware.newrelic.nr_add_custom_parameter"), \
             patch("src.bot.middleware.newrelic.nr_notice_error"):
            result = await mw(handler, event, {})
        assert result == "expected_result"