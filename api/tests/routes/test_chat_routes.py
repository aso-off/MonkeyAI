"""
Тесты для api/src/routes/chat.py.

Покрываем:
- POST /chat/complete — text, image, flagged, invalid b64, skip_moderation
- POST /chat/stream   — SSE streaming, flagged, with image
- _persist_chat_result helper (через complete endpoint)

Все внешние зависимости мокируются; реальный OpenAI API не вызывается.
Faker используется для всех входных данных.
"""

import base64
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

_MODELS = ["gpt-4o", "gpt-5.4-nano", "gpt-5.4-mini"]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _chat_body(**overrides) -> dict:
    return {
        "user_id": overrides.get("user_id", fake.random_int(min=100_000, max=999_999_999)),
        "message": overrides.get("message", fake.sentence()),
        "model": overrides.get("model", fake.random_element(_MODELS)),
        "chat_mode": overrides.get("chat_mode", "assistant"),
        "dialog_messages": overrides.get("dialog_messages", []),
        "dialog_id": overrides.get("dialog_id", str(uuid.uuid4())),
        "image_b64": overrides.get("image_b64", None),
        "skip_moderation": overrides.get("skip_moderation", False),
    }


def _fake_image_b64() -> str:
    """Возвращает валидный base64 из случайных байт."""
    raw = fake.binary(length=64)
    return base64.b64encode(raw).decode()


def _mock_chatgpt(answer: str | None = None, n_in: int = 10, n_out: int = 20):
    """MagicMock для ChatGPT класса."""
    if answer is None:
        answer = fake.paragraph()

    instance = MagicMock()
    instance.send_message = AsyncMock(return_value=(answer, (n_in, n_out), 0))
    instance.send_vision_message = AsyncMock(return_value=(answer, (n_in, n_out), 0))

    async def _stream_gen(*a, **kw):
        chunk = fake.sentence()
        yield "not_finished", chunk, "", (0, 0), 0
        yield "finished", answer, "thinking summary", (n_in, n_out), 0

    instance.send_message_stream = MagicMock(side_effect=_stream_gen)
    instance.send_vision_message_stream = MagicMock(side_effect=_stream_gen)

    return MagicMock(return_value=instance)


# ── POST /chat/complete ───────────────────────────────────────────────────────


class TestChatComplete:

    @pytest.mark.api
    def test_text_message_returns_200(self, api_client) -> None:
        answer = fake.paragraph()
        gpt_cls = _mock_chatgpt(answer)

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/complete", json=_chat_body())

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == answer
        assert data["is_flagged"] is False

    @pytest.mark.api
    def test_text_message_returns_token_counts(self, api_client) -> None:
        n_in = fake.random_int(min=1, max=500)
        n_out = fake.random_int(min=1, max=200)
        gpt_cls = _mock_chatgpt(n_in=n_in, n_out=n_out)

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/complete", json=_chat_body())

        data = resp.json()
        assert data["usage"]["input_tokens"] == n_in
        assert data["usage"]["output_tokens"] == n_out
        assert data["usage"]["total_tokens"] == n_in + n_out

    @pytest.mark.api
    def test_flagged_content_returns_flagged_response(self, api_client) -> None:
        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(True, {}, {}))):
            resp = api_client.post("/chat/complete", json=_chat_body())

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_flagged"] is True
        assert data["answer"] == ""

    @pytest.mark.api
    def test_skip_moderation_bypasses_flag(self, api_client) -> None:
        """skip_moderation=True → flagged content всё равно обрабатывается."""
        answer = fake.paragraph()
        gpt_cls = _mock_chatgpt(answer)

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(True, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/complete",
                                   json=_chat_body(skip_moderation=True))

        assert resp.status_code == 200
        assert resp.json()["answer"] == answer

    @pytest.mark.api
    def test_invalid_base64_image_returns_400(self, api_client) -> None:
        # "a" — 1 символ без правильного padding → binascii.Error даже при validate=False
        body = _chat_body(image_b64="a")
        resp = api_client.post("/chat/complete", json=body)
        assert resp.status_code == 400

    @pytest.mark.api
    def test_valid_image_b64_triggers_vision(self, api_client) -> None:
        answer = fake.sentence()
        gpt_cls = _mock_chatgpt(answer)

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/complete",
                                   json=_chat_body(image_b64=_fake_image_b64()))

        assert resp.status_code == 200
        # send_vision_message должен был быть вызван
        gpt_cls.return_value.send_vision_message.assert_awaited_once()

    @pytest.mark.api
    def test_server_context_passed_to_gpt(self, api_client) -> None:
        """Контекст строится на сервере (get_context) и передаётся модели."""
        context = [
            {"role": "user", "content": fake.sentence()},
            {"role": "assistant", "content": fake.sentence()},
        ]
        gpt_cls = _mock_chatgpt()

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=context)), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/complete", json=_chat_body())

        assert resp.status_code == 200
        call_kwargs = gpt_cls.return_value.send_message.call_args
        assert call_kwargs[1].get("dialog_messages") == context

    @pytest.mark.api
    def test_faker_batch_requests_all_200(self, api_client) -> None:
        for _ in range(3):
            gpt_cls = _mock_chatgpt(fake.paragraph())
            with patch("routes.chat.moderate_content",
                       new=AsyncMock(return_value=(False, {}, {}))), \
                 patch("routes.chat.ChatGPT", gpt_cls), \
                 patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
                 patch("routes.chat._persist_chat_result", new=AsyncMock()):
                resp = api_client.post("/chat/complete", json=_chat_body())
            assert resp.status_code == 200

    @pytest.mark.api
    def test_missing_model_returns_422(self, api_client) -> None:
        body = _chat_body()
        del body["model"]
        resp = api_client.post("/chat/complete", json=body)
        assert resp.status_code == 422

    @pytest.mark.api
    def test_missing_message_returns_422(self, api_client) -> None:
        body = _chat_body()
        del body["message"]
        resp = api_client.post("/chat/complete", json=body)
        assert resp.status_code == 422


# ── POST /chat/stream ─────────────────────────────────────────────────────────


class TestChatStream:

    @pytest.mark.api
    def test_stream_returns_200(self, api_client) -> None:
        answer = fake.paragraph()
        gpt_cls = _mock_chatgpt(answer)

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/stream", json=_chat_body())

        assert resp.status_code == 200

    @pytest.mark.api
    def test_stream_contains_sse_data_lines(self, api_client) -> None:
        answer = fake.paragraph()
        gpt_cls = _mock_chatgpt(answer)

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/stream", json=_chat_body())

        assert "data: " in resp.text

    @pytest.mark.api
    def test_stream_contains_finished_status(self, api_client) -> None:
        answer = fake.paragraph()
        gpt_cls = _mock_chatgpt(answer)

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/stream", json=_chat_body())

        lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
        payloads = [json.loads(l[6:]) for l in lines]
        assert any(p["status"] == "finished" for p in payloads)

    @pytest.mark.api
    def test_stream_contains_answer_in_finished_chunk(self, api_client) -> None:
        answer = fake.paragraph()
        gpt_cls = _mock_chatgpt(answer)

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/stream", json=_chat_body())

        lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
        payloads = [json.loads(l[6:]) for l in lines]
        finished = [p for p in payloads if p["status"] == "finished"]
        assert finished[0]["text"] == answer
        assert finished[0]["reasoning"] == "thinking summary"

    @pytest.mark.api
    def test_stream_flagged_content_returns_flagged_event(self, api_client) -> None:
        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(True, {}, {}))):
            resp = api_client.post("/chat/stream", json=_chat_body())

        assert resp.status_code == 200
        lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
        payloads = [json.loads(l[6:]) for l in lines]
        assert any(p["status"] == "flagged" for p in payloads)

    @pytest.mark.api
    def test_stream_invalid_b64_image_returns_error_event(self, api_client) -> None:
        # "a" — некорректный padding → binascii.Error
        body = _chat_body(image_b64="a")
        resp = api_client.post("/chat/stream", json=body)

        assert resp.status_code == 200
        lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
        payloads = [json.loads(l[6:]) for l in lines]
        assert any(p["status"] == "error" for p in payloads)

    @pytest.mark.api
    def test_stream_with_image_uses_vision_stream(self, api_client) -> None:
        answer = fake.paragraph()
        gpt_cls = _mock_chatgpt(answer)

        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/stream",
                                   json=_chat_body(image_b64=_fake_image_b64()))

        assert resp.status_code == 200
        assert "data: " in resp.text

    @pytest.mark.api
    def test_stream_media_type_is_text_event_stream(self, api_client) -> None:
        gpt_cls = _mock_chatgpt()
        with patch("routes.chat.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.chat.ChatGPT", gpt_cls), \
             patch("routes.chat.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.chat._persist_chat_result", new=AsyncMock()):
            resp = api_client.post("/chat/stream", json=_chat_body())

        assert "text/event-stream" in resp.headers.get("content-type", "")
