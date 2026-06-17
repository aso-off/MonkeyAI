"""
Тесты для bot/src/bot/routers/chat.py.

Покрываем:
- set_bot_meta / _get_bot_meta
- _is_busy
- _is_bot_mentioned      — private chat, group @mention, group reply-to-bot
- _last_user_text_from_dialog_entry
- _mode_welcome
- cmd_new                — busy, user=None, с welcome, без welcome
- cmd_cancel             — активная задача, нет задачи
- cmd_retry              — busy, db_user=None, ensure_dialog фейл,
                           пустые messages, нет текста, с изображением,
                           set_dialog_messages фейл
- generate_image         — успех, HTTP 400/422, HTTP 429, HTTP other, generic error
- _handle_text_or_vision — streaming (done/flagged), non-streaming,
                           artist mode, пустой текст, exception, cancelled,
                           context_removed_one, context_removed_many, markdownv2
- _run_handle            — лок захвачен, лок занят, CancelledError
- msg_text               — не упомянут, busy, group cleanup, private
- msg_photo              — не упомянут, busy, с caption, без caption
- msg_voice              — не упомянут, busy, transcription error, пустой
- msg_unsupported / msg_edited
"""

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)

# helpers

def _fake_settings(**overrides):
    s = MagicMock()
    s.chat_modes = {
        "assistant": {"welcome_message": "", "parse_mode": "html"},
        "artist": {"welcome_message": "", "parse_mode": "html"},
        "coder": {"welcome_message": "Hello from coder!", "parse_mode": "html"},
        "md_mode": {"welcome_message": "", "parse_mode": "markdown_v2"},
    }
    s.dialog_context_limit = 5
    s.enable_message_streaming = False
    s.draft_throttle_seconds = 0.4
    s.message_max_length = 4096
    s.enable_rich_messages = False
    s.rich_message_max_length = 32768
    s.enable_thinking_block = False
    s.message_effect_id = ""
    s.models = {}
    s.busy_lock_ttl_seconds = 300
    s.return_n_generated_images = 1
    s.image_size = "1024x1024"
    s.image_quality = "medium"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s

def _fake_message(uid: int | None = None, chat_type: str = "private", text: str | None = None) -> MagicMock:
    from aiogram.enums import ChatType
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = uid or _uid()
    msg.from_user.language_code = "ru"
    msg.chat = MagicMock()
    msg.chat.id = msg.from_user.id
    msg.chat.type = ChatType.PRIVATE if chat_type == "private" else ChatType.GROUP
    msg.message_id = fake.random_int(min=1, max=9_999_999)
    msg.text = text or fake.sentence()
    msg.caption = None
    msg.photo = None
    msg.voice = None
    msg.reply_to_message = None
    msg.answer = AsyncMock()
    msg.answer_rich = AsyncMock(return_value=MagicMock(message_id=777))
    msg.reply = AsyncMock()
    return msg

def _fake_bot() -> MagicMock:
    bot = MagicMock()
    bot.get_me = AsyncMock(return_value=MagicMock(username="testbot", id=999))
    bot.send_chat_action = AsyncMock()
    bot.send_rich_message_draft = AsyncMock()
    bot.send_rich_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.get_file = AsyncMock(return_value=MagicMock(file_path="test/path"))
    bot.download_file = AsyncMock()
    return bot

def _fake_redis() -> AsyncMock:
    r = AsyncMock()
    r.exists = AsyncMock(return_value=0)
    r.set = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=1)
    return r

def _fake_db_user(mode: str = "assistant", model: str = "gpt-4o") -> MagicMock:
    u = MagicMock()
    u.id = _uid()
    u.current_chat_mode = mode
    u.current_model = model
    return u

def _fake_ensure(messages: list | None = None) -> MagicMock:
    e = MagicMock()
    e.dialog_id = fake.uuid4()
    e.messages = messages or []
    return e

def _fake_chat_result(answer: str = "response", flagged: bool = False, n_removed: int = 0) -> MagicMock:
    r = MagicMock()
    r.is_flagged = flagged
    r.answer = answer
    r.n_first_removed = n_removed
    return r

async def _mock_stream(*chunks):
    for chunk in chunks:
        yield chunk

def _stream_chunk(
    text: str = "hello", flagged: bool = False, status: str = "finished", reasoning: str = ""
) -> MagicMock:
    c = MagicMock()
    c.is_flagged = flagged
    c.text = text
    c.usage = MagicMock(input_tokens=1, output_tokens=1, total_tokens=2)
    c.n_first_removed = 0
    c.status = status
    c.reasoning = reasoning
    return c

# set_bot_meta / _get_bot_meta

class TestSetBotMeta:

    def test_sets_globals(self) -> None:
        import src.bot.routers.chat as chat_mod
        chat_mod.set_bot_meta("mybot", 42)
        assert chat_mod._bot_username == "mybot"
        assert chat_mod._bot_id == 42

    def test_set_none_clears_cache(self) -> None:
        import src.bot.routers.chat as chat_mod
        chat_mod.set_bot_meta(None, None)
        assert chat_mod._bot_username is None
        assert chat_mod._bot_id is None

class TestGetBotMeta:

    @pytest.mark.asyncio
    async def test_fetches_and_caches_from_bot(self) -> None:
        import src.bot.routers.chat as chat_mod
        chat_mod._bot_username = None
        chat_mod._bot_id = None
        bot = _fake_bot()
        bot.get_me.return_value = MagicMock(username="freshbot", id=777)
        username, bot_id = await chat_mod._get_bot_meta(bot)
        assert username == "freshbot"
        assert bot_id == 777
        bot.get_me.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_cached_without_api_call(self) -> None:
        import src.bot.routers.chat as chat_mod
        chat_mod._bot_username = "cachedbot"
        chat_mod._bot_id = 111
        bot = _fake_bot()
        username, bot_id = await chat_mod._get_bot_meta(bot)
        assert username == "cachedbot"
        assert bot_id == 111
        bot.get_me.assert_not_awaited()

# _is_busy

class TestIsBusy:

    @pytest.mark.asyncio
    async def test_not_busy_returns_false(self) -> None:
        from src.bot.routers.chat import _is_busy
        redis = _fake_redis()
        redis.exists = AsyncMock(return_value=0)
        msg = _fake_message()
        with patch("src.bot.routers.chat._redis", return_value=redis):
            result = await _is_busy(_uid(), msg, "ru")
        assert result is False
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_busy_replies_and_returns_true(self) -> None:
        from src.bot.routers.chat import _is_busy
        redis = _fake_redis()
        redis.exists = AsyncMock(return_value=1)
        msg = _fake_message()
        with patch("src.bot.routers.chat._redis", return_value=redis), \
             patch("src.bot.routers.chat.t", return_value="wait"):
            result = await _is_busy(_uid(), msg, "ru")
        assert result is True
        msg.answer.assert_awaited_once()

# _is_bot_mentioned

class TestIsBotMentioned:

    @pytest.mark.asyncio
    async def test_private_chat_always_true(self) -> None:
        from src.bot.routers.chat import _is_bot_mentioned
        msg = _fake_message(chat_type="private")
        bot = _fake_bot()
        result = await _is_bot_mentioned(msg, bot)
        assert result is True

    @pytest.mark.asyncio
    async def test_group_with_mention_returns_true(self) -> None:
        import src.bot.routers.chat as chat_mod
        from src.bot.routers.chat import _is_bot_mentioned
        from aiogram.enums import ChatType
        chat_mod._bot_username = "testbot"
        chat_mod._bot_id = 999
        msg = _fake_message(chat_type="group", text="@testbot привет")
        msg.chat.type = ChatType.GROUP
        bot = _fake_bot()
        result = await _is_bot_mentioned(msg, bot)
        assert result is True

    @pytest.mark.asyncio
    async def test_group_reply_to_bot_returns_true(self) -> None:
        import src.bot.routers.chat as chat_mod
        from src.bot.routers.chat import _is_bot_mentioned
        from aiogram.enums import ChatType
        chat_mod._bot_username = "testbot"
        chat_mod._bot_id = 999
        msg = _fake_message(chat_type="group", text="just text")
        msg.chat.type = ChatType.GROUP
        msg.reply_to_message = MagicMock()
        msg.reply_to_message.from_user = MagicMock()
        msg.reply_to_message.from_user.id = 999
        bot = _fake_bot()
        result = await _is_bot_mentioned(msg, bot)
        assert result is True

    @pytest.mark.asyncio
    async def test_group_no_mention_no_reply_returns_false(self) -> None:
        import src.bot.routers.chat as chat_mod
        from src.bot.routers.chat import _is_bot_mentioned
        from aiogram.enums import ChatType
        chat_mod._bot_username = "testbot"
        chat_mod._bot_id = 999
        msg = _fake_message(chat_type="group", text="обычный текст")
        msg.chat.type = ChatType.GROUP
        msg.reply_to_message = None
        bot = _fake_bot()
        result = await _is_bot_mentioned(msg, bot)
        assert result is False

    @pytest.mark.asyncio
    async def test_group_get_bot_meta_exception_returns_true(self) -> None:
        import src.bot.routers.chat as chat_mod
        from src.bot.routers.chat import _is_bot_mentioned
        from aiogram.enums import ChatType
        chat_mod._bot_username = None
        msg = _fake_message(chat_type="group")
        msg.chat.type = ChatType.GROUP
        bot = _fake_bot()
        bot.get_me = AsyncMock(side_effect=RuntimeError("network"))
        result = await _is_bot_mentioned(msg, bot)
        assert result is True

# _last_user_text_from_dialog_entry

class TestLastUserTextFromDialogEntry:

    def test_string_input_returns_string(self) -> None:
        from src.bot.routers.chat import _last_user_text_from_dialog_entry
        text = fake.sentence()
        assert _last_user_text_from_dialog_entry(text) == text

    def test_none_input_returns_empty(self) -> None:
        from src.bot.routers.chat import _last_user_text_from_dialog_entry
        assert _last_user_text_from_dialog_entry(None) == ""

    def test_list_with_text_item_returns_text(self) -> None:
        from src.bot.routers.chat import _last_user_text_from_dialog_entry
        text = fake.sentence()
        result = _last_user_text_from_dialog_entry([
            {"type": "image_url", "image_url": {"url": "data:..."}},
            {"type": "text", "text": text},
        ])
        assert result == text

    def test_list_without_text_item_returns_empty(self) -> None:
        from src.bot.routers.chat import _last_user_text_from_dialog_entry
        result = _last_user_text_from_dialog_entry([
            {"type": "image_url", "image_url": {"url": "data:..."}}
        ])
        assert result == ""

    def test_empty_list_returns_empty(self) -> None:
        from src.bot.routers.chat import _last_user_text_from_dialog_entry
        assert _last_user_text_from_dialog_entry([]) == ""

# _mode_welcome

class TestModeWelcome:

    def test_empty_template_returns_empty(self) -> None:
        from src.bot.routers.chat import _mode_welcome
        with patch("src.bot.routers.chat.settings") as mock_s:
            mock_s.chat_modes = {"assistant": {"welcome_message": ""}}
            assert _mode_welcome("assistant", "ru") == ""

    def test_static_template_returned_directly(self) -> None:
        from src.bot.routers.chat import _mode_welcome
        with patch("src.bot.routers.chat.settings") as mock_s:
            mock_s.chat_modes = {"coder": {"welcome_message": "Hello!"}}
            assert _mode_welcome("coder", "en") == "Hello!"

    def test_i18n_key_resolved_via_t(self) -> None:
        from src.bot.routers.chat import _mode_welcome
        with patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.t", return_value="Привет!"):
            mock_s.chat_modes = {"assistant": {"welcome_message": "{assistant_welcome}"}}
            result = _mode_welcome("assistant", "ru")
        assert result == "Привет!"

    def test_unknown_mode_returns_empty(self) -> None:
        from src.bot.routers.chat import _mode_welcome
        with patch("src.bot.routers.chat.settings") as mock_s:
            mock_s.chat_modes = {}
            assert _mode_welcome("nonexistent", "ru") == ""

# cmd_new

class TestCmdNew:

    @pytest.mark.asyncio
    async def test_busy_returns_early(self) -> None:
        from src.bot.routers.chat import cmd_new
        msg = _fake_message()
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat.api") as mock_api:
            await cmd_new(msg, language="ru")
        mock_api.get_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_not_found_returns_early(self) -> None:
        from src.bot.routers.chat import cmd_new
        msg = _fake_message()
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api:
            mock_api.get_user = AsyncMock(return_value=None)
            await cmd_new(msg, language="ru")
        msg.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sends_new_chat_message_without_welcome(self) -> None:
        from src.bot.routers.chat import cmd_new
        msg = _fake_message()
        db_user = _fake_db_user()
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.t", return_value="new chat"):
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.start_new_dialog = AsyncMock()
            mock_s.chat_modes = {"assistant": {"welcome_message": ""}}
            await cmd_new(msg, language="ru")
        mock_api.start_new_dialog.assert_awaited_once()
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sends_welcome_when_present(self) -> None:
        from src.bot.routers.chat import cmd_new
        msg = _fake_message()
        db_user = _fake_db_user(mode="coder")
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.t", return_value="msg"):
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.start_new_dialog = AsyncMock()
            mock_s.chat_modes = {"coder": {"welcome_message": "Hello coder!"}}
            await cmd_new(msg, language="en")
        assert msg.answer.await_count == 2

# cmd_cancel

class TestCmdCancel:

    @pytest.mark.asyncio
    async def test_cancels_active_task(self) -> None:
        import src.bot.routers.chat as chat_mod
        from src.bot.routers.chat import cmd_cancel
        uid = _uid()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        chat_mod.user_tasks[uid] = mock_task
        msg = _fake_message(uid=uid)
        await cmd_cancel(msg, language="ru")
        mock_task.cancel.assert_called_once()
        msg.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_active_task_sends_message(self) -> None:
        import src.bot.routers.chat as chat_mod
        from src.bot.routers.chat import cmd_cancel
        uid = _uid()
        chat_mod.user_tasks.pop(uid, None)
        msg = _fake_message(uid=uid)
        with patch("src.bot.routers.chat.t", return_value="nothing to cancel"):
            await cmd_cancel(msg, language="ru")
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_done_task_sends_message(self) -> None:
        import src.bot.routers.chat as chat_mod
        from src.bot.routers.chat import cmd_cancel
        uid = _uid()
        mock_task = MagicMock()
        mock_task.done.return_value = True
        chat_mod.user_tasks[uid] = mock_task
        msg = _fake_message(uid=uid)
        with patch("src.bot.routers.chat.t", return_value="nothing"):
            await cmd_cancel(msg, language="ru")
        msg.answer.assert_awaited_once()

# cmd_retry

class TestCmdRetry:

    @pytest.mark.asyncio
    async def test_busy_returns_early(self) -> None:
        from src.bot.routers.chat import cmd_retry
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat.api") as mock_api:
            await cmd_retry(msg, language="ru", bot=bot, db_user=None)
        mock_api.get_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_user_none_from_api_returns_early(self) -> None:
        from src.bot.routers.chat import cmd_retry
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.t", return_value="no retry"):
            mock_api.get_user = AsyncMock(return_value=None)
            await cmd_retry(msg, language="ru", bot=bot, db_user=None)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ensure_dialog_failure_sends_error(self) -> None:
        from src.bot.routers.chat import cmd_retry
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="error"):
            mock_api.ensure_dialog = AsyncMock(side_effect=RuntimeError("fail"))
            mock_monkey.send = AsyncMock()
            await cmd_retry(msg, language="ru", bot=bot, db_user=db_user)
        mock_monkey.send.assert_awaited()
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_empty_dialog_messages_sends_no_retry(self) -> None:
        from src.bot.routers.chat import cmd_retry
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.t", return_value="no messages"):
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure([]))
            mock_api.pop_last_exchange = AsyncMock(return_value=None)
            await cmd_retry(msg, language="ru", bot=bot, db_user=db_user)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_text_in_last_message_sends_no_retry(self) -> None:
        from src.bot.routers.chat import cmd_retry
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        removed = {"id": "msg_1", "role": "user", "content": "   "}
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.t", return_value="no retry"):
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure([]))
            mock_api.pop_last_exchange = AsyncMock(return_value=removed)
            await cmd_retry(msg, language="ru", bot=bot, db_user=db_user)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pop_last_failure_sends_error(self) -> None:
        from src.bot.routers.chat import cmd_retry
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="error"):
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure([]))
            mock_api.pop_last_exchange = AsyncMock(side_effect=RuntimeError("db fail"))
            mock_monkey.send = AsyncMock()
            await cmd_retry(msg, language="ru", bot=bot, db_user=db_user)
        mock_monkey.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_with_image_in_retry_decodes_base64(self) -> None:
        import base64
        from src.bot.routers.chat import cmd_retry
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        raw_bytes = b"fake_image_bytes"
        b64_data = "data:image/jpeg;base64," + base64.b64encode(raw_bytes).decode()
        removed = {
            "id": "msg_1",
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": b64_data}},
                {"type": "text", "text": "describe"},
            ],
        }
        with patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run, \
             patch("src.bot.routers.chat._pop_answer_id", AsyncMock(return_value=None)), \
             patch("src.bot.routers.chat.t", return_value=""):
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure([]))
            mock_api.pop_last_exchange = AsyncMock(return_value=removed)
            await cmd_retry(msg, language="ru", bot=bot, db_user=db_user)
        mock_run.assert_awaited_once()
        _, _, _, _, text, image_buffer = mock_run.call_args[0]
        assert image_buffer is not None

# generate_image

class TestGenerateImage:

    @pytest.mark.asyncio
    async def test_success_sends_photo(self) -> None:
        from src.bot.routers.chat import generate_image
        msg = _fake_message()
        bot = _fake_bot()
        buf = BytesIO(b"image_data")
        msg.answer_photo = AsyncMock()
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_s.return_n_generated_images = 1
            mock_s.image_size = "1024x1024"
            mock_s.image_quality = "medium"
            mock_api.generate_images = AsyncMock(return_value=([buf], ["http://imgbb.com/img1"]))
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure([]))
            mock_api.set_dialog_messages = AsyncMock()
            mock_monkey.send = AsyncMock()
            bot.send_chat_action = AsyncMock()
            await generate_image(msg, bot, "ru", _uid(), fake.sentence())
        msg.answer_photo.assert_awaited_once()
        mock_monkey.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_http_400_content_policy_sends_sad(self) -> None:
        import httpx
        from src.bot.routers.chat import generate_image
        msg = _fake_message()
        bot = _fake_bot()
        response = MagicMock()
        response.status_code = 400
        response.text = "content_policy_violation"
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="rejected"):
            mock_s.return_n_generated_images = 1
            mock_s.image_size = "1024x1024"
            mock_s.image_quality = "medium"
            mock_api.generate_images = AsyncMock(
                side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=response)
            )
            mock_monkey.send = AsyncMock()
            await generate_image(msg, bot, "ru", _uid(), fake.sentence())
        mock_monkey.send.assert_awaited()
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_http_429_rate_limit_sends_sad(self) -> None:
        import httpx
        from src.bot.routers.chat import generate_image
        msg = _fake_message()
        bot = _fake_bot()
        response = MagicMock()
        response.status_code = 429
        response.text = "too many requests"
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="rate limit"):
            mock_s.return_n_generated_images = 1
            mock_s.image_size = "1024x1024"
            mock_s.image_quality = "medium"
            mock_api.generate_images = AsyncMock(
                side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=response)
            )
            mock_monkey.send = AsyncMock()
            await generate_image(msg, bot, "ru", _uid(), fake.sentence())
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_http_500_other_error_sends_error(self) -> None:
        import httpx
        from src.bot.routers.chat import generate_image
        msg = _fake_message()
        bot = _fake_bot()
        response = MagicMock()
        response.status_code = 500
        response.text = "internal server error"
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="error"):
            mock_s.return_n_generated_images = 1
            mock_s.image_size = "1024x1024"
            mock_s.image_quality = "medium"
            mock_api.generate_images = AsyncMock(
                side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=response)
            )
            mock_monkey.send = AsyncMock()
            await generate_image(msg, bot, "ru", _uid(), fake.sentence())
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_generic_exception_sends_error(self) -> None:
        from src.bot.routers.chat import generate_image
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="error"):
            mock_s.return_n_generated_images = 1
            mock_s.image_size = "1024x1024"
            mock_s.image_quality = "medium"
            mock_api.generate_images = AsyncMock(side_effect=RuntimeError(fake.sentence()))
            mock_monkey.send = AsyncMock()
            await generate_image(msg, bot, "ru", _uid(), fake.sentence())
        msg.answer.assert_awaited()

# _handle_text_or_vision

class TestHandleTextOrVision:

    @pytest.mark.asyncio
    async def test_user_not_found_returns_early(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", _fake_settings()):
            mock_api.get_user = AsyncMock(return_value=None)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            await _handle_text_or_vision(msg, bot, "ru", msg.from_user.id, "hello")
        msg.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_artist_mode_calls_generate_image(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user(mode="artist")
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", _fake_settings()), \
             patch("src.bot.routers.chat.generate_image", AsyncMock()) as mock_gen:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "draw a cat")
        mock_gen.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_text_sends_empty_message_error(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", _fake_settings()), \
             patch("src.bot.routers.chat.t", return_value="empty"):
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "   ")
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_non_streaming_sends_answer(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        result = _fake_chat_result(answer=fake.sentence())
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", _fake_settings(enable_message_streaming=False)), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_complete = AsyncMock(return_value=result)
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hello")
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_non_streaming_flagged_sends_moderation_message(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        result = _fake_chat_result(flagged=True)
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", _fake_settings(enable_message_streaming=False)), \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="moderation"):
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_complete = AsyncMock(return_value=result)
            mock_monkey.send = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hello")
        mock_monkey.send.assert_awaited()
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_non_streaming_context_removed_one(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        result = _fake_chat_result(answer="ok", n_removed=1)
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", _fake_settings(enable_message_streaming=False)), \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="removed"):
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_complete = AsyncMock(return_value=result)
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hello")
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_streaming_context_removed_many(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        result = _fake_chat_result(answer="ok", n_removed=3)
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", _fake_settings(enable_message_streaming=False)), \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="removed {0}"):
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_complete = AsyncMock(return_value=result)
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hello")
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_streaming_markdownv2_mode(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user(mode="md_mode")
        s = _fake_settings(enable_message_streaming=False)
        s.chat_modes = {"md_mode": {"parse_mode": "markdown_v2", "welcome_message": ""}}
        result = _fake_chat_result(answer="*bold*")
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.convert_to_markdownv2", return_value="*bold*"):
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_complete = AsyncMock(return_value=result)
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hello")
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_exception_sends_error_message(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", _fake_settings(enable_message_streaming=False)), \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="error {0}"):
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_complete = AsyncMock(side_effect=RuntimeError(fake.sentence()))
            mock_monkey.send = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hello")
        mock_monkey.send.assert_awaited()
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_streaming_normal_chunk(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        chunk = _stream_chunk(text=fake.sentence(), status="finished")
        s = _fake_settings(enable_message_streaming=True)

        async def mock_stream(*args, **kwargs):
            yield chunk

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hello")
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_streaming_flagged_sends_moderation(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user()
        chunk = _stream_chunk(flagged=True)
        s = _fake_settings(enable_message_streaming=True)

        async def mock_stream(*args, **kwargs):
            yield chunk

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="moderation"):
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.send = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hello")
        mock_monkey.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_unknown_chat_mode_defaults_to_assistant(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message()
        bot = _fake_bot()
        db_user = _fake_db_user(mode="nonexistent_mode")
        result = _fake_chat_result()
        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", _fake_settings(enable_message_streaming=False)), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_complete = AsyncMock(return_value=result)
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hello")
        call_kwargs = mock_api.chat_complete.call_args[1]
        assert call_kwargs.get("chat_mode") == "assistant"

# rich messages

_REASONING_MODELS = {"info": {"gpt-5.4-mini": {"options": {"reasoning_effort": "medium"}}}}

class TestRichMessages:

    @pytest.mark.asyncio
    async def test_private_final_uses_answer_rich(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message(chat_type="private")
        bot = _fake_bot()
        db_user = _fake_db_user(model="gpt-4o")
        s = _fake_settings(enable_message_streaming=True, enable_rich_messages=True)

        async def mock_stream(*args, **kwargs):
            yield _stream_chunk(text="**hi**", status="finished")

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hi")
        msg.answer_rich.assert_awaited_once()
        msg.answer.assert_not_awaited()
        # финал — ответ-цитата на сообщение пользователя
        rp = msg.answer_rich.await_args.kwargs["reply_parameters"]
        assert rp.message_id == msg.message_id

    @pytest.mark.asyncio
    async def test_group_falls_back_to_legacy(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message(chat_type="group")
        bot = _fake_bot()
        db_user = _fake_db_user(model="gpt-4o")
        s = _fake_settings(enable_message_streaming=True, enable_rich_messages=True)

        async def mock_stream(*args, **kwargs):
            yield _stream_chunk(text="hi", status="finished")

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hi")
        msg.answer.assert_awaited_once()
        msg.answer_rich.assert_not_awaited()
        bot.send_rich_message_draft.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_thinking_draft_for_reasoning_model(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message(chat_type="private")
        bot = _fake_bot()
        db_user = _fake_db_user(model="gpt-5.4-mini")
        s = _fake_settings(
            enable_message_streaming=True,
            enable_rich_messages=True,
            enable_thinking_block=True,
            models=_REASONING_MODELS,
        )

        async def mock_stream(*args, **kwargs):
            yield _stream_chunk(text="", status="not_finished")
            yield _stream_chunk(text="partial", status="not_finished")
            yield _stream_chunk(text="full answer", status="finished")

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hi")
        assert bot.send_rich_message_draft.await_count == 2
        first_html = bot.send_rich_message_draft.await_args_list[0].kwargs["rich_message"].html
        assert "tg-thinking" in first_html
        msg.answer_rich.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_live_reasoning_shown_in_thinking(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message(chat_type="private")
        bot = _fake_bot()
        db_user = _fake_db_user(model="gpt-5.4-mini")
        s = _fake_settings(
            enable_message_streaming=True,
            enable_rich_messages=True,
            enable_thinking_block=True,
            models=_REASONING_MODELS,
        )

        async def mock_stream(*args, **kwargs):
            yield _stream_chunk(text="", status="not_finished", reasoning="step one")
            yield _stream_chunk(text="answer", status="finished", reasoning="step one")

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hi")
        html = bot.send_rich_message_draft.await_args_list[0].kwargs["rich_message"].html
        assert "step one" in html

    @pytest.mark.asyncio
    async def test_no_thinking_for_non_reasoning_model(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message(chat_type="private")
        bot = _fake_bot()
        db_user = _fake_db_user(model="gpt-4o")
        s = _fake_settings(
            enable_message_streaming=True,
            enable_rich_messages=True,
            enable_thinking_block=True,
            models=_REASONING_MODELS,
        )

        async def mock_stream(*args, **kwargs):
            yield _stream_chunk(text="", status="not_finished")
            yield _stream_chunk(text="partial", status="not_finished")
            yield _stream_chunk(text="full", status="finished")

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hi")
        assert bot.send_rich_message_draft.await_count == 1
        html = bot.send_rich_message_draft.await_args_list[0].kwargs["rich_message"].html
        assert html is None

    @pytest.mark.asyncio
    async def test_answer_rich_failure_falls_back_to_legacy(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message(chat_type="private")
        msg.answer_rich = AsyncMock(side_effect=RuntimeError("bad markdown"))
        bot = _fake_bot()
        db_user = _fake_db_user(model="gpt-4o")
        s = _fake_settings(enable_message_streaming=True, enable_rich_messages=True)

        async def mock_stream(*args, **kwargs):
            yield _stream_chunk(text="hi", status="finished")

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.delete_processing = AsyncMock()
            await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hi")
        # все rich-варианты (reply+эффект, reply, голый) упали → legacy
        assert msg.answer_rich.await_count == 3
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retry_edits_previous_answer_in_place(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message(chat_type="private")
        bot = _fake_bot()
        db_user = _fake_db_user(model="gpt-4o")
        s = _fake_settings(enable_message_streaming=True, enable_rich_messages=True)

        async def mock_stream(*args, **kwargs):
            yield _stream_chunk(text="updated", status="finished")

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.delete_processing = AsyncMock()
            sent_id = await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hi", edit_message_id=555)
        bot.edit_message_text.assert_awaited_once()
        assert bot.edit_message_text.await_args.kwargs["message_id"] == 555
        msg.answer_rich.assert_not_awaited()
        bot.send_rich_message_draft.assert_not_awaited()
        assert sent_id == 555

    @pytest.mark.asyncio
    async def test_retry_edit_failure_falls_back_to_new(self) -> None:
        from src.bot.routers.chat import _handle_text_or_vision
        msg = _fake_message(chat_type="private")
        bot = _fake_bot()
        bot.edit_message_text = AsyncMock(side_effect=RuntimeError("message too old"))
        db_user = _fake_db_user(model="gpt-4o")
        s = _fake_settings(enable_message_streaming=True, enable_rich_messages=True)

        async def mock_stream(*args, **kwargs):
            yield _stream_chunk(text="updated", status="finished")

        with patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.settings", s), \
             patch("src.bot.routers.chat.monkey") as mock_monkey:
            mock_api.get_user = AsyncMock(return_value=db_user)
            mock_api.ensure_dialog = AsyncMock(return_value=_fake_ensure())
            mock_api.chat_stream = mock_stream
            mock_monkey.delete_processing = AsyncMock()
            sent_id = await _handle_text_or_vision(msg, bot, "ru", db_user.id, "hi", edit_message_id=555)
        msg.answer_rich.assert_awaited_once()
        assert sent_id == 777

# _run_handle

class TestRunHandle:

    @pytest.mark.asyncio
    async def test_lock_not_acquired_replies_and_returns(self) -> None:
        from src.bot.routers.chat import _run_handle
        msg = _fake_message()
        bot = _fake_bot()
        redis = _fake_redis()
        redis.set = AsyncMock(return_value=None)
        with patch("src.bot.routers.chat._redis", return_value=redis), \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.t", return_value="wait"), \
             patch("src.bot.routers.chat._handle_text_or_vision", AsyncMock()) as mock_handle:
            mock_s.busy_lock_ttl_seconds = 300
            await _run_handle(msg, bot, "ru", msg.from_user.id, "hello")
        mock_handle.assert_not_awaited()
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lock_acquired_runs_handler(self) -> None:
        from src.bot.routers.chat import _run_handle
        msg = _fake_message()
        bot = _fake_bot()
        redis = _fake_redis()
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock()
        with patch("src.bot.routers.chat._redis", return_value=redis), \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat._handle_text_or_vision", AsyncMock()) as mock_handle:
            mock_s.busy_lock_ttl_seconds = 300
            await _run_handle(msg, bot, "ru", msg.from_user.id, "hello")
        mock_handle.assert_awaited_once()
        redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cancelled_error_sends_cancelled_message(self) -> None:
        from src.bot.routers.chat import _run_handle
        msg = _fake_message()
        bot = _fake_bot()
        redis = _fake_redis()
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock()
        with patch("src.bot.routers.chat._redis", return_value=redis), \
             patch("src.bot.routers.chat.settings") as mock_s, \
             patch("src.bot.routers.chat.t", return_value="cancelled"), \
             patch("src.bot.routers.chat._handle_text_or_vision", AsyncMock(side_effect=asyncio.CancelledError())):
            mock_s.busy_lock_ttl_seconds = 300
            await _run_handle(msg, bot, "ru", msg.from_user.id, "hello")
        msg.answer.assert_awaited()
        redis.delete.assert_awaited_once()

# msg_text

class TestMsgText:

    @pytest.mark.asyncio
    async def test_not_mentioned_returns_early(self) -> None:
        from src.bot.routers.chat import msg_text
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            await msg_text(msg, language="ru", bot=bot)
        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_busy_returns_early(self) -> None:
        from src.bot.routers.chat import msg_text
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            await msg_text(msg, language="ru", bot=bot)
        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_private_chat_runs_handle(self) -> None:
        from src.bot.routers.chat import msg_text
        msg = _fake_message(chat_type="private", text=fake.sentence())
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            await msg_text(msg, language="ru", bot=bot)
        mock_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_group_strips_bot_mention_from_text(self) -> None:
        from aiogram.enums import ChatType
        import src.bot.routers.chat as chat_mod
        from src.bot.routers.chat import msg_text
        chat_mod._bot_username = "testbot"
        msg = _fake_message(chat_type="group", text="@testbot напиши код")
        msg.chat.type = ChatType.GROUP
        bot = _fake_bot()
        captured_text = []
        async def mock_run(m, b, lang, uid, text, *args, **kwargs):
            captured_text.append(text)
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat._run_handle", mock_run):
            await msg_text(msg, language="ru", bot=bot)
        assert captured_text and "@testbot" not in captured_text[0]

# msg_photo

class TestMsgPhoto:

    @pytest.mark.asyncio
    async def test_not_mentioned_returns_early(self) -> None:
        from src.bot.routers.chat import msg_photo
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            await msg_photo(msg, language="ru", bot=bot)
        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_busy_returns_early(self) -> None:
        from src.bot.routers.chat import msg_photo
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            await msg_photo(msg, language="ru", bot=bot)
        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_with_caption_uses_caption_as_text(self) -> None:
        from src.bot.routers.chat import msg_photo
        caption = fake.sentence()
        msg = _fake_message(chat_type="private")
        msg.caption = caption
        msg.photo = [MagicMock(file_id="file123")]
        bot = _fake_bot()
        captured_text = []
        async def mock_run(m, b, lang, uid, text, image_buffer=None):
            captured_text.append(text)
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat._run_handle", mock_run):
            mock_monkey.send = AsyncMock()
            await msg_photo(msg, language="ru", bot=bot)
        assert captured_text and captured_text[0] == caption

    @pytest.mark.asyncio
    async def test_no_caption_uses_default_prompt(self) -> None:
        from src.bot.routers.chat import msg_photo
        msg = _fake_message(chat_type="private")
        msg.caption = None
        msg.photo = [MagicMock(file_id="file456")]
        bot = _fake_bot()
        captured_text = []
        async def mock_run(m, b, lang, uid, text, image_buffer=None):
            captured_text.append(text)
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="describe image"), \
             patch("src.bot.routers.chat._run_handle", mock_run):
            mock_monkey.send = AsyncMock()
            await msg_photo(msg, language="ru", bot=bot)
        assert captured_text and captured_text[0] == "describe image"

# msg_voice

class TestMsgVoice:

    @pytest.mark.asyncio
    async def test_not_mentioned_returns_early(self) -> None:
        from src.bot.routers.chat import msg_voice
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            await msg_voice(msg, language="ru", bot=bot)
        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_busy_returns_early(self) -> None:
        from src.bot.routers.chat import msg_voice
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            await msg_voice(msg, language="ru", bot=bot)
        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_transcription_success_runs_handle(self) -> None:
        from src.bot.routers.chat import msg_voice
        transcribed = fake.sentence()
        msg = _fake_message()
        msg.voice = MagicMock(file_id="voice123")
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            mock_api.transcribe_audio = AsyncMock(return_value=(transcribed, None))
            mock_monkey.send = AsyncMock()
            await msg_voice(msg, language="ru", bot=bot)
        mock_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transcription_failure_sends_error(self) -> None:
        from src.bot.routers.chat import msg_voice
        msg = _fake_message()
        msg.voice = MagicMock(file_id="voice456")
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="failed"), \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            mock_api.transcribe_audio = AsyncMock(side_effect=RuntimeError("network"))
            mock_monkey.send = AsyncMock()
            await msg_voice(msg, language="ru", bot=bot)
        mock_run.assert_not_awaited()
        msg.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_empty_transcription_sends_error(self) -> None:
        from src.bot.routers.chat import msg_voice
        msg = _fake_message()
        msg.voice = MagicMock(file_id="voice789")
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat._is_busy", AsyncMock(return_value=False)), \
             patch("src.bot.routers.chat.api") as mock_api, \
             patch("src.bot.routers.chat.monkey") as mock_monkey, \
             patch("src.bot.routers.chat.t", return_value="failed"), \
             patch("src.bot.routers.chat._run_handle", AsyncMock()) as mock_run:
            mock_api.transcribe_audio = AsyncMock(return_value=("", None))
            mock_monkey.send = AsyncMock()
            await msg_voice(msg, language="ru", bot=bot)
        mock_run.assert_not_awaited()
        msg.answer.assert_awaited()

# msg_unsupported / msg_edited

class TestMsgUnsupportedAndEdited:

    @pytest.mark.asyncio
    async def test_unsupported_sends_error_message(self) -> None:
        from src.bot.routers.chat import msg_unsupported
        msg = _fake_message()
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=True)), \
             patch("src.bot.routers.chat.t", return_value="unsupported"):
            await msg_unsupported(msg, language="ru", bot=bot)
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unsupported_ignored_when_not_mentioned(self) -> None:
        from src.bot.routers.chat import msg_unsupported
        msg = _fake_message(chat_type="group")
        bot = _fake_bot()
        with patch("src.bot.routers.chat._is_bot_mentioned", AsyncMock(return_value=False)):
            await msg_unsupported(msg, language="ru", bot=bot)
        msg.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_edited_in_private_sends_notice(self) -> None:
        from src.bot.routers.chat import msg_edited
        msg = _fake_message(chat_type="private")
        with patch("src.bot.routers.chat.t", return_value="editing unsupported"):
            await msg_edited(msg, language="ru")
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_edited_in_group_does_nothing(self) -> None:
        from aiogram.enums import ChatType
        from src.bot.routers.chat import msg_edited
        msg = _fake_message(chat_type="group")
        msg.chat.type = ChatType.GROUP
        await msg_edited(msg, language="ru")
        msg.answer.assert_not_awaited()