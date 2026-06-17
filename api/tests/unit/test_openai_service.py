"""Юнит-тесты для api/src/services/openai.py — класс ChatGPT.

AsyncOpenAI заменён AsyncMock.
Тестируем чистую логику: _options, _validate_mode, _build_messages.
"""

import types
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest

# Импортируем только то, что нужно — init_redis и реальный клиент не трогаем
from services.openai import BASE_OPTIONS, ChatGPT, _encode_image

_TEST_MODELS = {
    "available_text_models": ["gpt-5.4-nano", "gpt-4o", "gpt-5.4-mini"],
    "info": {
        "gpt-5.4-nano": {"options": {"max_completion_tokens": 8192, "reasoning_effort": "low"}},
        "gpt-5.4-mini": {"options": {"max_completion_tokens": 8192, "reasoning_effort": "medium"}},
        "gpt-4o": {"options": {"max_completion_tokens": 4000, "temperature": 0.3}},
    },
}
_MODEL_OPTIONS = {m: info["options"] for m, info in _TEST_MODELS["info"].items()}

# Фикстуры

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
        models=_TEST_MODELS,
    )
    mocker.patch("services.openai.settings", settings)
    return settings

@pytest.fixture
def gpt(mock_openai, mock_settings) -> ChatGPT:
    return ChatGPT(model="gpt-4o")

# __init__

class TestChatGPTInit:
    @pytest.mark.unit
    @pytest.mark.parametrize("model", list(_MODEL_OPTIONS.keys()))
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
        assert gpt.model == "gpt-5.4-nano"

# _options

class TestOptions:
    @pytest.mark.unit
    def test_includes_base_options(self, gpt) -> None:
        opts = gpt._options()
        for k, v in BASE_OPTIONS.items():
            assert opts[k] == v

    @pytest.mark.unit
    @pytest.mark.parametrize("model", list(_MODEL_OPTIONS.keys()))
    def test_model_specific_options_present(self, model: str, mock_openai, mock_settings) -> None:
        gpt = ChatGPT(model=model)
        opts = gpt._options()
        for k, v in _MODEL_OPTIONS[model].items():
            assert opts[k] == v

    @pytest.mark.unit
    def test_returns_new_dict_each_call(self, gpt) -> None:
        opts1 = gpt._options()
        opts2 = gpt._options()
        assert opts1 is not opts2
        opts1["extra"] = "value"
        assert "extra" not in opts2

# _validate_mode

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
            models=_TEST_MODELS,
        )
        mocker.patch("services.openai.settings", settings)
        gpt = ChatGPT(model="gpt-4o")
        with pytest.raises(ValueError):
            gpt._validate_mode("system_prompt")

# _build_messages

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
            {"role": "user", "content": fake.sentence()},
            {"role": "assistant", "content": fake.sentence()},
            {"role": "user", "content": fake.sentence()},
            {"role": "assistant", "content": fake.sentence()},
        ]
        msgs = gpt._build_messages("new msg", history, "assistant")
        # system + 4 истории + финальный user = 6
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
    def test_image_url_creates_vision_message(self, gpt) -> None:
        url = "https://i.ibb.co/abc/photo.jpg"
        msgs = gpt._build_messages("describe this", [], "assistant", image_url=url)
        last = msgs[-1]
        assert last["role"] == "user"
        assert isinstance(last["content"], list)
        img = next(i for i in last["content"] if i["type"] == "image_url")
        assert img["image_url"]["url"] == url
        assert img["image_url"]["detail"] == "auto"

    @pytest.mark.unit
    def test_image_url_takes_precedence_over_buffer(self, gpt) -> None:
        url = "https://i.ibb.co/abc/photo.jpg"
        buf = BytesIO(b"\xff\xd8\xff" + b"\x00" * 50)
        msgs = gpt._build_messages("hi", [], "assistant", image_buffer=buf, image_url=url)
        img = next(i for i in msgs[-1]["content"] if i["type"] == "image_url")
        assert img["image_url"]["url"] == url

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
        history = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A"},
        ]
        msgs = gpt._build_messages("new", history, "assistant")
        # skip system prompt
        roles = [m["role"] for m in msgs[1:]]
        assert roles == ["user", "assistant", "user"]

# _encode_image

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

# send_message (интеграционный, полный мок)

class TestSendMessage:
    @pytest.mark.unit
    async def test_returns_answer_and_tokens(self, gpt, mock_openai) -> None:
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
    async def test_empty_response_raises(self, gpt, mock_openai) -> None:
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