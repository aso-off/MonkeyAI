"""Юнит-тесты для bot/src/utils/stickers.py — класс MonkeyStickers."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.utils.stickers import MonkeyStickers


@pytest.fixture
def stickers() -> MonkeyStickers:
    return MonkeyStickers()

@pytest.fixture
def mock_bot() -> MagicMock:
    bot = MagicMock(name="Bot")
    bot.send_chat_action = AsyncMock(return_value=None)
    bot.send_sticker = AsyncMock()
    bot.delete_message = AsyncMock(return_value=True)
    return bot

# get_random

class TestGetRandom:
    @pytest.mark.unit
    def test_returns_string(self, stickers) -> None:
        result = stickers.get_random()
        assert isinstance(result, str) and result.startswith("CAAC")

    @pytest.mark.unit
    @pytest.mark.parametrize("emotion", ["happy", "thinking", "surprised", "sad", "error", "hello", "loading", "generating", "processing"])
    def test_known_emotion_returns_sticker(self, stickers, emotion: str) -> None:
        result = stickers.get_random(emotion)
        assert isinstance(result, str) and len(result) > 0

    @pytest.mark.unit
    def test_none_emotion_returns_happy(self, stickers) -> None:
        # None > happy по умолчанию
        result = stickers.get_random(None)
        assert result in stickers.STICKERS["happy"]

    @pytest.mark.unit
    def test_unknown_emotion_falls_back_to_happy(self, stickers) -> None:
        result = stickers.get_random("nonexistent_emotion")
        assert result in stickers.STICKERS["happy"]

    @pytest.mark.unit
    def test_sticker_from_correct_pool(self, stickers) -> None:
        for _ in range(20):
            result = stickers.get_random("thinking")
            assert result in stickers.STICKERS["thinking"]

    @pytest.mark.unit
    def test_randomness(self, stickers) -> None:
        # happy имеет 4 стикера — за 50 вызовов должны встретиться как минимум 2 разных
        results = {stickers.get_random("happy") for _ in range(50)}
        assert len(results) >= 2

    @pytest.mark.unit
    def test_processing_categories_defined(self, stickers) -> None:
        for cat in stickers.PROCESSING_CATEGORIES:
            assert cat in stickers.STICKERS

# send

class TestSend:
    @pytest.mark.unit
    async def test_send_happy_returns_true(self, stickers, mock_bot, fake) -> None:
        sent_msg = MagicMock()
        sent_msg.message_id = fake.random_int(min=1, max=9_999_999)
        mock_bot.send_sticker.return_value = sent_msg

        result = await stickers.send(mock_bot, chat_id=123, emotion="happy")

        assert result is True
        mock_bot.send_chat_action.assert_awaited_once()
        mock_bot.send_sticker.assert_awaited_once()

    @pytest.mark.unit
    async def test_send_processing_stores_message_id(self, stickers, mock_bot, fake) -> None:
        msg_id = fake.random_int(min=1, max=9_999_999)
        mock_bot.send_sticker.return_value = MagicMock(message_id=msg_id)

        await stickers.send(mock_bot, chat_id=42, emotion="thinking")

        assert stickers._processing.get(42) == msg_id

    @pytest.mark.unit
    async def test_send_non_processing_deletes_existing(self, stickers, mock_bot, fake) -> None:
        # Предустановим "активный" процессинг-стикер
        stickers._processing[99] = 555
        mock_bot.send_sticker.return_value = MagicMock(message_id=111)

        await stickers.send(mock_bot, chat_id=99, emotion="happy")

        # delete_message должен был быть вызван для старого стикера
        mock_bot.delete_message.assert_awaited_once_with(chat_id=99, message_id=555)
        # processing запись должна быть удалена
        assert 99 not in stickers._processing

    @pytest.mark.unit
    async def test_send_telegram_error_returns_false(self, stickers, mock_bot) -> None:
        from aiogram.exceptions import TelegramAPIError
        mock_bot.send_sticker.side_effect = TelegramAPIError(method=MagicMock(), message="Bad Request")

        result = await stickers.send(mock_bot, chat_id=123, emotion="happy")

        assert result is False

    @pytest.mark.unit
    async def test_send_with_reply_to_message_id(self, stickers, mock_bot, fake) -> None:
        mock_bot.send_sticker.return_value = MagicMock(message_id=1)
        reply_id = fake.random_int(min=1, max=9_999_999)

        await stickers.send(mock_bot, chat_id=42, emotion="sad", reply_to_message_id=reply_id)

        call_kwargs = mock_bot.send_sticker.call_args[1]
        assert call_kwargs.get("reply_to_message_id") == reply_id

    @pytest.mark.unit
    @pytest.mark.parametrize("emotion", ["loading", "generating", "processing"])
    async def test_all_processing_categories_stored(self, emotion: str, mock_bot, fake) -> None:
        stickers = MonkeyStickers()
        msg_id = fake.random_int(min=1, max=9_999_999)
        mock_bot.send_sticker.return_value = MagicMock(message_id=msg_id)

        await stickers.send(mock_bot, chat_id=10, emotion=emotion)

        assert stickers._processing.get(10) == msg_id

# delete_processing

class TestDeleteProcessing:
    @pytest.mark.unit
    async def test_no_sticker_returns_false(self, stickers, mock_bot) -> None:
        result = await stickers.delete_processing(mock_bot, chat_id=999)
        assert result is False
        mock_bot.delete_message.assert_not_awaited()

    @pytest.mark.unit
    async def test_existing_sticker_deleted_returns_true(self, stickers, mock_bot) -> None:
        stickers._processing[77] = 42
        mock_bot.delete_message.return_value = None

        result = await stickers.delete_processing(mock_bot, chat_id=77)

        assert result is True
        mock_bot.delete_message.assert_awaited_once_with(chat_id=77, message_id=42)
        assert 77 not in stickers._processing

    @pytest.mark.unit
    async def test_delete_error_returns_false(self, stickers, mock_bot) -> None:
        from aiogram.exceptions import TelegramAPIError
        stickers._processing[55] = 99
        mock_bot.delete_message.side_effect = TelegramAPIError(method=MagicMock(), message="Message not found")

        result = await stickers.delete_processing(mock_bot, chat_id=55)

        assert result is False

    @pytest.mark.unit
    async def test_clears_tracking_on_success(self, stickers, mock_bot, fake) -> None:
        chat_id = fake.random_int(min=1, max=9_999_999)
        stickers._processing[chat_id] = 123
        await stickers.delete_processing(mock_bot, chat_id=chat_id)
        assert chat_id not in stickers._processing

# Синглтон monkey

class TestMonkeySingleton:
    @pytest.mark.unit
    def test_singleton_is_monkeystickers(self) -> None:
        from src.utils.stickers import monkey
        assert isinstance(monkey, MonkeyStickers)

    @pytest.mark.unit
    def test_singleton_has_empty_processing_initially(self) -> None:
        fresh = MonkeyStickers()
        assert fresh._processing == {}
