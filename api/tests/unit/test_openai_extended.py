"""
Расширенные тесты для api/src/services/openai.py.

Покрываем то, что не захватывает test_openai_service.py:
- make_client()          — singleton + openai_api_base branch
- _encode_image()        — base64 + позиция буфера
- send_message()         — happy path, BadRequestError (trim), BadRequestError (empty)
- send_message_stream()  — streaming, BadRequestError trim
- send_vision_message()  — happy path, BadRequestError
- send_vision_message_stream() — streaming

Faker: messages, model names, chat_mode, dialog contents, answer texts.
"""

import base64
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker
from openai import BadRequestError

fake = Faker()
Faker.seed(42)

_VALID_MODES = ["assistant", "code_assistant"]

# Helpers

def _make_gpt(model: str = "gpt-4o"):
    """Создаём ChatGPT с мок-клиентом; не вызывает реальный AsyncOpenAI."""
    with patch("services.openai.make_client") as mock_make:
        mock_make.return_value = MagicMock()
        from services.openai import ChatGPT
        gpt = ChatGPT(model=model)
    return gpt

def _fake_message() -> str:
    return fake.sentence()

def _fake_dialog(n: int = 2) -> list:
    out = []
    for _ in range(n):
        out.append({"role": "user", "content": fake.sentence()})
        out.append({"role": "assistant", "content": fake.sentence()})
    return out

def _fake_answer() -> str:
    return fake.paragraph()

def _fake_completion(answer: str, n_in: int = 50, n_out: int = 20):
    """MagicMock для asyncopenai response."""
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = answer
    r.usage.prompt_tokens = n_in
    r.usage.completion_tokens = n_out
    return r

class FakeAsyncStream:
    """Имитирует async-итерируемый stream от OpenAI."""
    def __init__(self, chunks):
        self._iter = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

def _fake_responses_events(answer: str, reasoning: str = "", n_in: int = 50, n_out: int = 20):
    """Имитирует поток событий Responses API."""
    events = []
    for tok in reasoning.split():
        e = MagicMock()
        e.type = "response.reasoning_summary_text.delta"
        e.delta = tok + " "
        events.append(e)
    for w in answer.split():
        e = MagicMock()
        e.type = "response.output_text.delta"
        e.delta = w + " "
        events.append(e)
    comp = MagicMock()
    comp.type = "response.completed"
    comp.response.usage.input_tokens = n_in
    comp.response.usage.output_tokens = n_out
    events.append(comp)
    return events

def _bad_request_error():
    err = BadRequestError.__new__(BadRequestError)
    err.message = "context_length_exceeded"
    err.body = None
    err.response = MagicMock(status_code=400, headers={})
    err.request = MagicMock()
    err.status_code = 400
    return err

# make_client

class TestMakeClient:

    def test_creates_openai_client_when_none(self) -> None:
        import services.openai as oai_mod
        original = oai_mod._openai_client
        oai_mod._openai_client = None
        try:
            with patch("services.openai.AsyncOpenAI") as MockOpenAI:
                MockOpenAI.return_value = MagicMock()
                client = oai_mod.make_client()
            MockOpenAI.assert_called_once()
            assert client is not None
        finally:
            oai_mod._openai_client = original

    def test_returns_existing_client(self) -> None:
        import services.openai as oai_mod
        original = oai_mod._openai_client
        mock_existing = MagicMock()
        oai_mod._openai_client = mock_existing
        try:
            result = oai_mod.make_client()
            assert result is mock_existing
        finally:
            oai_mod._openai_client = original

    def test_sets_base_url_when_openai_api_base_is_set(self) -> None:
        import services.openai as oai_mod
        original = oai_mod._openai_client
        oai_mod._openai_client = None
        fake_url = fake.url()
        try:
            with patch("services.openai.settings") as mock_settings, \
                 patch("services.openai.AsyncOpenAI") as MockOpenAI:
                mock_settings.openai_api_key.get_secret_value.return_value = fake.sha256()[:32]
                mock_settings.openai_api_base = fake_url
                mock_instance = MagicMock()
                MockOpenAI.return_value = mock_instance
                oai_mod.make_client()
            assert mock_instance.base_url == fake_url
        finally:
            oai_mod._openai_client = original

    def test_client_created_successfully_when_no_base_url(self) -> None:
        """Когда openai_api_base=None — клиент создаётся без ошибок."""
        import services.openai as oai_mod
        original = oai_mod._openai_client
        oai_mod._openai_client = None
        try:
            with patch("services.openai.settings") as mock_settings, \
                 patch("services.openai.AsyncOpenAI") as MockOpenAI:
                mock_settings.openai_api_key.get_secret_value.return_value = "sk-test"
                mock_settings.openai_api_base = None
                mock_instance = MagicMock()
                MockOpenAI.return_value = mock_instance
                result = oai_mod.make_client()
            # Клиент создан без иск��ючений
            assert result is mock_instance
            # base_url устанавливается только в openai_api_base ветке — та не выполнилась
            MockOpenAI.assert_called_once()
        finally:
            oai_mod._openai_client = original

# _encode_image

class TestEncodeImage:

    def test_encodes_buffer_to_base64(self) -> None:
        from services.openai import _encode_image
        raw = fake.binary(length=32)
        buf = BytesIO(raw)
        result = _encode_image(buf)
        assert result == base64.b64encode(raw).decode("utf-8")

    def test_restores_buffer_position(self) -> None:
        from services.openai import _encode_image
        raw = fake.binary(length=64)
        buf = BytesIO(raw)
        buf.seek(10)
        _encode_image(buf)
        assert buf.tell() == 10

    def test_reads_from_beginning_regardless_of_position(self) -> None:
        from services.openai import _encode_image
        raw = fake.binary(length=32)
        buf = BytesIO(raw)
        buf.seek(16)
        result = _encode_image(buf)
        assert result == base64.b64encode(raw).decode("utf-8")

    def test_faker_batch_buffers(self) -> None:
        from services.openai import _encode_image
        for _ in range(5):
            raw = fake.binary(length=fake.random_int(min=16, max=128))
            buf = BytesIO(raw)
            result = _encode_image(buf)
            assert base64.b64decode(result) == raw

# send_message

class TestSendMessage:

    @pytest.mark.asyncio
    async def test_happy_path_returns_answer_and_tokens(self) -> None:
        gpt = _make_gpt()
        answer = _fake_answer()
        completion = _fake_completion(answer, n_in=100, n_out=30)
        gpt.client.chat.completions.create = AsyncMock(return_value=completion)

        result, (n_in, n_out), n_removed = await gpt.send_message(
            _fake_message(), dialog_messages=_fake_dialog(), chat_mode="assistant"
        )

        assert result == answer.strip()
        assert n_in == 100
        assert n_out == 30
        assert n_removed == 0

    @pytest.mark.asyncio
    async def test_bad_request_trims_dialog_and_retries(self) -> None:
        gpt = _make_gpt()
        answer = _fake_answer()
        completion = _fake_completion(answer)

        call_count = [0]
        async def _create(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                raise _bad_request_error()
            return completion

        setattr(gpt.client.chat.completions, "create", _create)
        dialog = _fake_dialog(3)

        result, _, n_removed = await gpt.send_message(
            _fake_message(), dialog_messages=dialog, chat_mode="assistant"
        )

        assert result == answer.strip()
        assert n_removed == 1

    @pytest.mark.asyncio
    async def test_bad_request_with_empty_dialog_raises_value_error(self) -> None:
        gpt = _make_gpt()
        gpt.client.chat.completions.create = AsyncMock(side_effect=_bad_request_error())

        with pytest.raises(ValueError, match="Dialog reduced to zero"):
            await gpt.send_message(_fake_message(), dialog_messages=[], chat_mode="assistant")

    @pytest.mark.asyncio
    async def test_no_dialog_messages_still_works(self) -> None:
        gpt = _make_gpt()
        answer = _fake_answer()
        gpt.client.chat.completions.create = AsyncMock(return_value=_fake_completion(answer))

        result, _, _ = await gpt.send_message(_fake_message(), chat_mode="assistant")
        assert result == answer.strip()

    @pytest.mark.asyncio
    async def test_faker_batch_messages(self) -> None:
        gpt = _make_gpt()
        for _ in range(3):
            answer = fake.paragraph()
            gpt.client.chat.completions.create = AsyncMock(
                return_value=_fake_completion(answer)
            )
            result, _, _ = await gpt.send_message(fake.sentence(), chat_mode="assistant")
            assert isinstance(result, str)

# send_message_stream

class TestSendMessageStream:

    @pytest.mark.asyncio
    async def test_yields_not_finished_then_finished(self) -> None:
        gpt = _make_gpt()
        answer = _fake_answer()
        stream = FakeAsyncStream(_fake_responses_events(answer))
        gpt.client.responses.create = AsyncMock(return_value=stream)

        events = []
        async for status, text, _reasoning, tokens, n_removed in gpt.send_message_stream(
            _fake_message(), dialog_messages=[], chat_mode="assistant"
        ):
            events.append((status, text))

        statuses = [e[0] for e in events]
        assert "finished" in statuses
        assert events[-1][0] == "finished"

    @pytest.mark.asyncio
    async def test_stream_emits_reasoning_summary(self) -> None:
        gpt = _make_gpt()
        stream = FakeAsyncStream(_fake_responses_events("final answer", reasoning="think hard"))
        gpt.client.responses.create = AsyncMock(return_value=stream)

        reasonings = []
        async for status, _text, reasoning, _tokens, _n in gpt.send_message_stream(
            _fake_message(), chat_mode="assistant"
        ):
            reasonings.append(reasoning)

        assert any("think" in r for r in reasonings)
        assert reasonings[-1] == "think hard "

    @pytest.mark.asyncio
    async def test_stream_bad_request_propagates(self) -> None:
        # truncation=auto закрывает длину, ручного retry-trim больше нет — ошибка пробрасывается
        gpt = _make_gpt()
        gpt.client.responses.create = AsyncMock(side_effect=_bad_request_error())
        with pytest.raises(BadRequestError):
            async for _ in gpt.send_message_stream(
                _fake_message(), dialog_messages=_fake_dialog(2), chat_mode="assistant"
            ):
                pass

    @pytest.mark.asyncio
    async def test_stream_usage_from_final_chunk(self) -> None:
        gpt = _make_gpt()
        stream = FakeAsyncStream(_fake_responses_events("a b c", n_in=11, n_out=7))
        gpt.client.responses.create = AsyncMock(return_value=stream)

        final = None
        async for status, _, _reasoning, tokens, _ in gpt.send_message_stream(
            _fake_message(), chat_mode="assistant"
        ):
            if status == "finished":
                final = tokens

        assert final == (11, 7)

    @pytest.mark.asyncio
    async def test_stream_delivers_incremental_text(self) -> None:
        gpt = _make_gpt()
        answer = _fake_answer()
        stream = FakeAsyncStream(_fake_responses_events(answer))
        gpt.client.responses.create = AsyncMock(return_value=stream)

        texts = []
        async for status, text, _reasoning, _, _ in gpt.send_message_stream(
            _fake_message(), chat_mode="assistant"
        ):
            texts.append(text)

        # Последний текст должен содержать весь ответ
        assert texts[-1].strip() != ""

# send_vision_message

class TestSendVisionMessage:

    @pytest.mark.asyncio
    async def test_returns_answer_with_image(self) -> None:
        gpt = _make_gpt()
        answer = _fake_answer()
        img = BytesIO(fake.binary(length=32))
        gpt.client.chat.completions.create = AsyncMock(return_value=_fake_completion(answer))

        result, (n_in, n_out), n_removed = await gpt.send_vision_message(
            _fake_message(), dialog_messages=[], chat_mode="assistant", image_buffer=img
        )

        assert result == answer.strip()

    @pytest.mark.asyncio
    async def test_vision_bad_request_trims_dialog(self) -> None:
        gpt = _make_gpt()
        answer = _fake_answer()
        img = BytesIO(fake.binary(length=32))
        call_count = [0]

        async def _create(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                raise _bad_request_error()
            return _fake_completion(answer)

        setattr(gpt.client.chat.completions, "create", _create)
        dialog = _fake_dialog(2)

        result, _, n_removed = await gpt.send_vision_message(
            _fake_message(), dialog_messages=dialog, chat_mode="assistant", image_buffer=img
        )
        assert result == answer.strip()
        assert n_removed == 1

    @pytest.mark.asyncio
    async def test_vision_bad_request_empty_dialog_raises(self) -> None:
        gpt = _make_gpt()
        img = BytesIO(fake.binary(length=32))
        gpt.client.chat.completions.create = AsyncMock(side_effect=_bad_request_error())

        with pytest.raises(ValueError):
            await gpt.send_vision_message(
                _fake_message(), dialog_messages=[], chat_mode="assistant", image_buffer=img
            )

# send_vision_message_stream

class TestSendVisionMessageStream:

    @pytest.mark.asyncio
    async def test_stream_yields_finished_event(self) -> None:
        gpt = _make_gpt()
        answer = _fake_answer()
        img = BytesIO(fake.binary(length=32))
        stream = FakeAsyncStream(_fake_responses_events(answer))
        gpt.client.responses.create = AsyncMock(return_value=stream)

        events = []
        async for status, text, _reasoning, _, _ in gpt.send_vision_message_stream(
            _fake_message(), dialog_messages=[], chat_mode="assistant", image_buffer=img
        ):
            events.append(status)

        assert "finished" in events

    @pytest.mark.asyncio
    async def test_vision_stream_bad_request_propagates(self) -> None:
        gpt = _make_gpt()
        img = BytesIO(fake.binary(length=32))
        gpt.client.responses.create = AsyncMock(side_effect=_bad_request_error())
        with pytest.raises(BadRequestError):
            async for _ in gpt.send_vision_message_stream(
                _fake_message(), dialog_messages=_fake_dialog(2), chat_mode="assistant", image_buffer=img
            ):
                pass