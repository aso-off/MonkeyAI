"""Юнит-тесты для api/src/services/openai.py — класс ChatGPT.

AsyncOpenAI заменён AsyncMock. tiktoken мокируется для скорости.
Тестируем чистую логику: _options, _validate_mode, _build_messages, _count_tokens.
"""

import types
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Импортируем только то, что нужно — init_redis и реальный клиент не трогаем
from services.openai import BASE_OPTIONS, MODEL_FAMILY, MODEL_OPTIONS, ChatGPT, _encode_image


# ── Фикстуры ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_openai(mocker):
    """Мокируем AsyncOpenAI клиент и make_client()."""
    client = MagicMock()
    client.chat.completions.create = AsyncMock()
    mocker.patch("services.openai.make_client", return_value=client)
    return client


@pytest.fixture
def mock_settings(mocker):
    """Подставляем тестовые settings с набором chat_modes."""
    settings = types.SimpleNamespace(
        openai_api_key=types.SimpleNamespace(get_secret_value=lambda: "sk-test"),
        openai_api_base=None,
        chat_modes={
            "assistant": {"prompt_start": "You are a helpful assistant."},
            "code_assistant": {"prompt_start": "You are a coding expert."},
        },
    )
    mocker.patch("services.openai.settings", settings)
    return settings


@pytest.fixture
def mock_tiktoken(mocker):
    """Мокируем tiktoken чтобы не скачивал модели в CI."""
    enc = MagicMock()
    enc.encode.return_value = list(range(10))  # 10 токенов на каждую строку
    mocker.patch("services.openai._get_encoding", return_value=enc)
    return enc


@pytest.fixture
def gpt(mock_openai, mock_settings) -> ChatGPT:
    return ChatGPT(model="gpt-4o")


# ── __init__ ──────────────────────────────────────────────────────────────────


class TestChatGPTInit:
    @pytest.mark.unit
    @pytest.mark.parametrize("model", list(MODEL_FAMILY.keys()))
    def test_valid_models_accepted(self, model: str, mock_openai, mock_settings) -> None:
        gpt = ChatGPT(model=model)
        assert gpt.model == model

    @pytest.mark.unit
    def test_unknown_model_raises_value_error(self, mock_openai, mock_settings) -> None:
        with pytest.raises(ValueError, match="Unknown model"):
            ChatGPT(model="gpt-99-ultra")

    @pytest.mark.unit
    def test_default_model_is_gpt5_nano(self, mock_openai, mock_settings) -> None:
        gpt = ChatGPT()
        assert gpt.model == "gpt-5-nano"


# ── _options ──────────────────────────────────────────────────────────────────


class TestOptions:
    @pytest.mark.unit
    def test_includes_base_options(self, gpt) -> None:
        opts = gpt._options()
        for k, v in BASE_OPTIONS.items():
            assert opts[k] == v

    @pytest.mark.unit
    @pytest.mark.parametrize("model", list(MODEL_OPTIONS.keys()))
    def test_model_specific_options_present(self, model: str, mock_openai, mock_settings) -> None:
        gpt = ChatGPT(model=model)
        opts = gpt._options()
        for k, v in MODEL_OPTIONS[model].items():
            assert opts[k] == v

    @pytest.mark.unit
    def test_returns_new_dict_each_call(self, gpt) -> None:
        opts1 = gpt._options()
        opts2 = gpt._options()
        assert opts1 is not opts2
        opts1["extra"] = "value"
        assert "extra" not in opts2


# ── _validate_mode ────────────────────────────────────────────────────────────


class TestValidateMode:
    @pytest.mark.unit
    def test_valid_mode_no_exception(self, gpt) -> None:
        gpt._validate_mode("assistant")  # не должно упасть

    @pytest.mark.unit
    def test_another_valid_mode(self, gpt) -> None:
        gpt._validate_mode("code_assistant")

    @pytest.mark.unit
    def test_invalid_mode_raises_value_error(self, gpt, fake) -> None:
        with pytest.raises(ValueError, match="not supported"):
            gpt._validate_mode(f"invalid_{fake.lexify('????')}")

    @pytest.mark.unit
    def test_system_prompt_key_not_a_mode(self, mock_openai, mocker) -> None:
        # "system_prompt" — специальный ключ, не режим — должен вызывать ошибку
        settings = types.SimpleNamespace(
            openai_api_key=types.SimpleNamespace(get_secret_value=lambda: "sk"),
            openai_api_base=None,
            chat_modes={
                "system_prompt": "global system prompt",
                "assistant": {"prompt_start": "You are helpful."},
            },
        )
        mocker.patch("services.openai.settings", settings)
        gpt = ChatGPT(model="gpt-4o")
        with pytest.raises(ValueError):
            gpt._validate_mode("system_prompt")


# ── _build_messages ───────────────────────────────────────────────────────────


class TestBuildMessages:
    @pytest.mark.unit
    def test_system_prompt_first(self, gpt) -> None:
        msgs = gpt._build_messages("hello", [], "assistant")
        assert msgs[0]["role"] == "system"
        assert "assistant" in msgs[0]["content"].lower() or msgs[0]["content"]

    @pytest.mark.unit
    def test_user_message_last(self, gpt) -> None:
        msgs = gpt._build_messages("hello", [], "assistant")
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "hello"

    @pytest.mark.unit
    def test_dialog_history_appended(self, gpt, fake) -> None:
        history = [
            {"user": fake.sentence(), "bot": fake.sentence()},
            {"user": fake.sentence(), "bot": fake.sentence()},
        ]
        msgs = gpt._build_messages("new msg", history, "assistant")
        # system + 2 pairs (user/bot) + final user = 6 messages
        assert len(msgs) == 6

    @pytest.mark.unit
    def test_image_buffer_creates_vision_message(self, gpt) -> None:
        buf = BytesIO(b"\xff\xd8\xff" + b"\x00" * 50)
        msgs = gpt._build_messages("describe this", [], "assistant", image_buffer=buf)
        last = msgs[-1]
        assert last["role"] == "user"
        assert isinstance(last["content"], list)
        types_in_content = [item["type"] for item in last["content"]]
        assert "text" in types_in_content and "image_url" in types_in_content

    @pytest.mark.unit
    def test_no_image_creates_text_message(self, gpt, fake) -> None:
        text = fake.sentence()
        msgs = gpt._build_messages(text, [], "assistant")
        last = msgs[-1]
        assert last["content"] == text
        assert isinstance(last["content"], str)

    @pytest.mark.unit
    def test_empty_dialog_history(self, gpt) -> None:
        msgs = gpt._build_messages("hi", [], "assistant")
        # system + user = 2
        assert len(msgs) == 2

    @pytest.mark.unit
    def test_history_alternates_roles(self, gpt) -> None:
        history = [{"user": "Q", "bot": "A"}]
        msgs = gpt._build_messages("new", history, "assistant")
        # skip system prompt
        roles = [m["role"] for m in msgs[1:]]
        assert roles == ["user", "assistant", "user"]


# ── _count_tokens ─────────────────────────────────────────────────────────────


class TestCountTokens:
    @pytest.mark.unit
    def test_returns_tuple_of_two_ints(self, gpt, mock_tiktoken) -> None:
        result = gpt._count_tokens([{"role": "user", "content": "hello"}], "world")
        assert isinstance(result, tuple) and len(result) == 2
        n_total, n_out = result
        assert isinstance(n_total, int) and isinstance(n_out, int)

    @pytest.mark.unit
    def test_output_tokens_counted(self, gpt, mock_tiktoken) -> None:
        answer = "This is a test answer"
        mock_tiktoken.encode.return_value = list(range(5))  # 5 токенов
        _, n_out = gpt._count_tokens([], answer)
        assert n_out == 5

    @pytest.mark.unit
    def test_fallback_on_encoding_error(self, gpt, mocker) -> None:
        mocker.patch("services.openai._get_encoding", side_effect=Exception("tiktoken error"))
        answer = "short"
        total, out = gpt._count_tokens([{"role": "user", "content": "hi"}], answer)
        assert total == 500
        assert out == len(answer) // 4

    @pytest.mark.unit
    def test_more_messages_more_tokens(self, gpt, mock_tiktoken) -> None:
        mock_tiktoken.encode.return_value = list(range(10))
        one_msg = [{"role": "user", "content": "hi"}]
        many_msgs = [{"role": "user", "content": "hi"}] * 5
        t1, _ = gpt._count_tokens(one_msg, "ok")
        t5, _ = gpt._count_tokens(many_msgs, "ok")
        assert t5 > t1


# ── _encode_image ─────────────────────────────────────────────────────────────


class TestEncodeImage:
    @pytest.mark.unit
    def test_returns_base64_string(self) -> None:
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 50
        buf = BytesIO(data)
        result = _encode_image(buf)
        assert isinstance(result, str)
        # base64 не содержит пробелов и переносов
        assert " " not in result and "\n" not in result

    @pytest.mark.unit
    def test_buffer_position_restored(self) -> None:
        buf = BytesIO(b"\x00" * 100)
        buf.seek(20)
        _encode_image(buf)
        assert buf.tell() == 20

    @pytest.mark.unit
    def test_encode_decode_roundtrip(self) -> None:
        import base64
        data = b"test image data"
        buf = BytesIO(data)
        encoded = _encode_image(buf)
        decoded = base64.b64decode(encoded)
        assert decoded == data


# ── send_message (интеграционный, полный мок) ─────────────────────────────────


class TestSendMessage:
    @pytest.mark.unit
    async def test_returns_answer_and_tokens(self, gpt, mock_openai, mock_tiktoken) -> None:
        choice = MagicMock()
        choice.message.content = "  Hello World  "
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[choice], usage=usage
        )
        answer, tokens, dropped = await gpt.send_message("hi", chat_mode="assistant")
        assert answer == "Hello World"
        assert tokens == (10, 5)
        assert isinstance(dropped, int)

    @pytest.mark.unit
    async def test_empty_response_raises(self, gpt, mock_openai, mock_tiktoken) -> None:
        choice = MagicMock()
        choice.message.content = "   "  # пустой ответ
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[choice], usage=MagicMock(prompt_tokens=5, completion_tokens=0)
        )
        with pytest.raises(ValueError, match="empty response"):
            await gpt.send_message("hi", chat_mode="assistant")

    @pytest.mark.unit
    async def test_invalid_chat_mode_raises(self, gpt) -> None:
        with pytest.raises(ValueError, match="not supported"):
            await gpt.send_message("hi", chat_mode="nonexistent_mode")
