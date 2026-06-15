"""
Тесты для bot/src/services/api_client.py.

Стратегия: патчим src.services.api_client._request на уровне модуля,
возвращая mock httpx.Response с нужными status_code и content.
Для chat_stream — мокируем get_client().stream() как async context manager.

Faker: user_id, имена, сообщения, model, URL, prompt, ответы.
"""

import json
import uuid
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


def _did() -> str:
    return str(uuid.uuid4())


def _fake_user_dict(uid: int | None = None) -> dict:
    uid = uid or _uid()
    return {
        "id": uid,
        "chat_id": uid,
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "username": fake.user_name(),
        "language": fake.random_element(["ru", "en", "de"]),
        "current_chat_mode": "assistant",
        "current_model": "gpt-4o",
        "is_admin": False,
        "is_whitelisted": True,
        "n_used_tokens": {},
        "n_generated_images": fake.random_int(min=0, max=100),
        "n_transcribed_seconds": float(fake.random_int(min=0, max=3600)),
        "current_dialog_id": None,
        "first_seen": None,
        "last_interaction": None,
    }


def _resp(data: Any = None, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    if data is not None:
        r.content = json.dumps(data).encode()
    r.raise_for_status = MagicMock()
    return r


def _patch_request(return_value):
    return patch("src.services.api_client._request", new=AsyncMock(return_value=return_value))


# ── get_client / close_client ─────────────────────────────────────────────────


class TestGetClient:

    def test_creates_client_when_none(self) -> None:
        import src.services.api_client as ac
        original = ac._client
        ac._client = None
        try:
            with patch("src.services.api_client.httpx.AsyncClient") as MockClient:
                mock_instance = MagicMock()
                mock_instance.is_closed = False
                MockClient.return_value = mock_instance
                result = ac.get_client()
            assert result is mock_instance
        finally:
            ac._client = original

    def test_returns_existing_open_client(self) -> None:
        import src.services.api_client as ac
        original = ac._client
        mock_client = MagicMock()
        mock_client.is_closed = False
        ac._client = mock_client
        try:
            result = ac.get_client()
            assert result is mock_client
        finally:
            ac._client = original

    def test_recreates_client_when_closed(self) -> None:
        import src.services.api_client as ac
        original = ac._client
        closed_client = MagicMock()
        closed_client.is_closed = True
        ac._client = closed_client
        try:
            with patch("src.services.api_client.httpx.AsyncClient") as MockClient:
                new_inst = MagicMock()
                new_inst.is_closed = False
                MockClient.return_value = new_inst
                result = ac.get_client()
            assert result is new_inst
        finally:
            ac._client = original


class TestCloseClient:

    @pytest.mark.asyncio
    async def test_closes_and_nones_client(self) -> None:
        import src.services.api_client as ac
        original = ac._client
        mock_client = AsyncMock()
        mock_client.is_closed = False
        ac._client = mock_client
        try:
            await ac.close_client()
            mock_client.aclose.assert_awaited_once()
            assert ac._client is None
        finally:
            ac._client = original

    @pytest.mark.asyncio
    async def test_safe_when_client_is_none(self) -> None:
        import src.services.api_client as ac
        original = ac._client
        ac._client = None
        try:
            await ac.close_client()  # не должен падать
        finally:
            ac._client = original


# ── _decode ───────────────────────────────────────────────────────────────────


class TestDecode:

    def test_decodes_user_response(self) -> None:
        from src.services.api_client import _decode, UserResponse
        data = _fake_user_dict()
        result = _decode(json.dumps(data).encode(), UserResponse)
        assert result.id == data["id"]
        assert result.first_name == data["first_name"]

    def test_decodes_chat_complete_response(self) -> None:
        from src.services.api_client import _decode, ChatCompleteResponse
        n_in = fake.random_int(min=10, max=500)
        n_out = fake.random_int(min=5, max=200)
        data = {
            "answer": fake.sentence(),
            "usage": {"input_tokens": n_in, "output_tokens": n_out, "total_tokens": n_in + n_out},
            "n_first_removed": 0,
            "is_flagged": False,
        }
        result = _decode(json.dumps(data).encode(), ChatCompleteResponse)
        assert result.answer == data["answer"]
        assert result.usage.input_tokens == n_in
        assert result.usage.total_tokens == n_in + n_out


# ── Users ─────────────────────────────────────────────────────────────────────


class TestGetOrCreateUser:

    @pytest.mark.asyncio
    async def test_returns_user_response(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        data = _fake_user_dict(uid)

        with _patch_request(_resp(data)):
            result = await ac.get_or_create_user(
                user_id=uid,
                chat_id=uid,
                first_name=fake.first_name(),
                username=fake.user_name(),
                language="ru",
            )

        assert result.id == uid

    @pytest.mark.asyncio
    async def test_faker_batch_users(self) -> None:
        from src.services import api_client as ac
        for _ in range(3):
            uid = _uid()
            data = _fake_user_dict(uid)
            with _patch_request(_resp(data)):
                result = await ac.get_or_create_user(uid, uid, first_name=fake.first_name())
            assert result.id == uid


class TestGetUser:

    @pytest.mark.asyncio
    async def test_returns_user_when_found(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        data = _fake_user_dict(uid)
        with _patch_request(_resp(data, 200)):
            result = await ac.get_user(uid)
        assert result is not None
        assert result.id == uid

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self) -> None:
        from src.services import api_client as ac
        with _patch_request(_resp(status=404)):
            result = await ac.get_user(_uid())
        assert result is None


class TestUpdateUser:

    @pytest.mark.asyncio
    async def test_returns_updated_user(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        data = _fake_user_dict(uid)
        data["language"] = "en"
        with _patch_request(_resp(data)):
            result = await ac.update_user(uid, language="en")
        assert result.language == "en"


# ── Dialogs ───────────────────────────────────────────────────────────────────


class TestStartNewDialog:

    @pytest.mark.asyncio
    async def test_returns_dialog_id(self) -> None:
        from src.services import api_client as ac
        did = _did()
        with _patch_request(_resp({"dialog_id": did})):
            result = await ac.start_new_dialog(_uid())
        assert result == did


class TestEnsureDialog:

    @pytest.mark.asyncio
    async def test_returns_ensure_dialog_response(self) -> None:
        from src.services import api_client as ac
        did = _did()
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}]
        with _patch_request(_resp({"dialog_id": did, "messages": msgs})):
            result = await ac.ensure_dialog(_uid())
        assert result.dialog_id == did
        assert result.messages == msgs


class TestGetDialogMessages:

    @pytest.mark.asyncio
    async def test_returns_messages_with_dialog_id(self) -> None:
        from src.services import api_client as ac
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}]
        did = _did()
        with _patch_request(_resp({"messages": msgs})):
            result = await ac.get_dialog_messages(_uid(), dialog_id=did)
        assert result == msgs

    @pytest.mark.asyncio
    async def test_uses_ensure_dialog_when_no_dialog_id(self) -> None:
        from src.services import api_client as ac
        did = _did()
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}]
        with _patch_request(_resp({"dialog_id": did, "messages": msgs})):
            result = await ac.get_dialog_messages(_uid(), dialog_id=None)
        assert result == msgs


class TestPopLastExchange:

    @pytest.mark.asyncio
    async def test_returns_removed_user_message(self) -> None:
        from src.services import api_client as ac
        removed = {"id": "msg_1", "role": "user", "content": fake.sentence()}
        with _patch_request(_resp({"message": removed})):
            result = await ac.pop_last_exchange(_uid(), dialog_id=_did())
        assert result == removed

    @pytest.mark.asyncio
    async def test_returns_none_when_dialog_empty(self) -> None:
        from src.services import api_client as ac
        with _patch_request(_resp({"message": None})):
            result = await ac.pop_last_exchange(_uid())
        assert result is None


class TestAppendExchange:

    @pytest.mark.asyncio
    async def test_executes_post_request(self) -> None:
        from src.services import api_client as ac
        mock_req = AsyncMock(return_value=_resp({"ok": True}))
        with patch("src.services.api_client._request", mock_req):
            await ac.append_exchange(_uid(), "промпт", "https://img", dialog_id=_did())
        mock_req.assert_awaited_once()
        assert mock_req.await_args is not None
        assert mock_req.await_args.kwargs["json"]["user"] == "промпт"


# ── Chat ──────────────────────────────────────────────────────────────────────


class TestChatComplete:

    @pytest.mark.asyncio
    async def test_returns_chat_complete_response(self) -> None:
        from src.services import api_client as ac
        answer = fake.paragraph()
        data = {
            "answer": answer,
            "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            "n_first_removed": 0,
            "is_flagged": False,
        }
        with _patch_request(_resp(data)):
            result = await ac.chat_complete(
                user_id=_uid(),
                dialog_id=_did(),
                message=fake.sentence(),
                chat_mode="assistant",
                model="gpt-4o",
            )
        assert result.answer == answer
        assert result.is_flagged is False

    @pytest.mark.asyncio
    async def test_flagged_response(self) -> None:
        from src.services import api_client as ac
        data = {
            "answer": "",
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "n_first_removed": 0,
            "is_flagged": True,
        }
        with _patch_request(_resp(data)):
            result = await ac.chat_complete(
                user_id=_uid(), dialog_id=None,
                message=fake.sentence(),
                chat_mode="assistant", model="gpt-4o",
            )
        assert result.is_flagged is True


class TestChatStream:

    @pytest.mark.asyncio
    async def test_yields_chunks_from_sse_stream(self) -> None:
        from src.services import api_client as ac
        answer = fake.paragraph()
        chunk_data = {
            "status": "finished",
            "text": answer,
            "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            "n_first_removed": 0,
            "is_flagged": False,
        }
        sse_line = f"data: {json.dumps(chunk_data)}"

        mock_stream_resp = AsyncMock()
        mock_stream_resp.raise_for_status = MagicMock()

        async def _fake_aiter_lines():
            yield sse_line
            yield "some irrelevant line"

        mock_stream_resp.aiter_lines = _fake_aiter_lines

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_stream_cm)

        with patch("src.services.api_client.get_client", return_value=mock_client):
            chunks = []
            async for chunk in ac.chat_stream(
                user_id=_uid(), dialog_id=_did(),
                message=fake.sentence(),
                chat_mode="assistant", model="gpt-4o",
            ):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].text == answer
        assert chunks[0].status == "finished"


# ── Media ─────────────────────────────────────────────────────────────────────


class TestGenerateImages:

    @pytest.mark.asyncio
    async def test_returns_buffers_and_urls(self) -> None:
        from src.services import api_client as ac
        import base64
        raw = fake.binary(length=64)
        b64 = base64.b64encode(raw).decode()
        imgbb_url = fake.url()
        data = {"images_b64": [b64], "imgbb_urls": [imgbb_url]}

        with _patch_request(_resp(data)):
            buffers, urls = await ac.generate_images(
                prompt=fake.sentence(),
                n_images=1,
                user_id=_uid(),
            )

        assert len(buffers) == 1
        buffers[0].seek(0)
        assert buffers[0].read() == raw
        assert urls == [imgbb_url]


class TestTranscribeAudio:

    @pytest.mark.asyncio
    async def test_returns_text_and_duration(self) -> None:
        from src.services import api_client as ac
        text = fake.sentence()
        dur = fake.pyfloat(min_value=0.5, max_value=60.0, right_digits=2)
        data = {"text": text, "duration_seconds": dur}

        with _patch_request(_resp(data)):
            audio_buf = BytesIO(fake.binary(length=512))
            audio_buf.name = "voice.ogg"
            result_text, result_dur = await ac.transcribe_audio(
                audio_buf=audio_buf, user_id=_uid(), lang="ru"
            )

        assert result_text == text
        assert abs(result_dur - dur) < 0.01


# ── User helpers ──────────────────────────────────────────────────────────────


class TestIsUserAdmin:

    @pytest.mark.asyncio
    async def test_true_when_in_settings_admin_ids(self) -> None:
        from src.services import api_client as ac
        import sys
        uid = _uid()
        # is_user_admin делает re-import: `from src.core.config import settings`
        # Патчим stub settings.admin_ids напрямую
        stub_settings = sys.modules["src.core.config"].settings
        original_admin_ids = stub_settings.admin_ids
        stub_settings.admin_ids = [uid]
        try:
            result = await ac.is_user_admin(uid)
        finally:
            stub_settings.admin_ids = original_admin_ids
        assert result is True

    @pytest.mark.asyncio
    async def test_true_when_db_user_is_admin(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        data = {**_fake_user_dict(uid), "is_admin": True}
        with patch("src.services.api_client.settings") as mock_settings, \
             _patch_request(_resp(data)):
            mock_settings.admin_ids = []
            result = await ac.is_user_admin(uid)
        assert result is True

    @pytest.mark.asyncio
    async def test_false_when_not_admin(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        data = {**_fake_user_dict(uid), "is_admin": False}
        with patch("src.services.api_client.settings") as mock_settings, \
             _patch_request(_resp(data)):
            mock_settings.admin_ids = []
            result = await ac.is_user_admin(uid)
        assert result is False


class TestSetUserAdmin:

    @pytest.mark.asyncio
    async def test_set_admin_true_creates_if_not_exists(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        user_data = _fake_user_dict(uid)
        resp_update = _resp({**user_data, "is_admin": True})

        call_count = [0]
        async def _mock_req(method, url, **kw):
            call_count[0] += 1
            if method.upper() == "GET":
                return _resp(status=404)  # user not exists
            return resp_update

        with patch("src.services.api_client._request", _mock_req):
            await ac.set_user_admin(uid, True)

        assert call_count[0] >= 2  # GET + POST + PATCH

    @pytest.mark.asyncio
    async def test_set_admin_false_skips_create(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        user_data = _fake_user_dict(uid)
        with _patch_request(_resp(user_data)):
            await ac.set_user_admin(uid, False)


class TestSetUserWhitelisted:

    @pytest.mark.asyncio
    async def test_set_whitelisted_true(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        user_data = _fake_user_dict(uid)

        async def _mock_req(method, url, **kw):
            if method.upper() == "GET":
                return _resp(status=404)
            return _resp(user_data)

        with patch("src.services.api_client._request", _mock_req):
            await ac.set_user_whitelisted(uid, True)

    @pytest.mark.asyncio
    async def test_set_whitelisted_false_skips_create(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        data = _fake_user_dict(uid)
        with _patch_request(_resp(data)):
            await ac.set_user_whitelisted(uid, False)


class TestGetUsersStats:

    @pytest.mark.asyncio
    async def test_get_all_users_count(self) -> None:
        from src.services import api_client as ac
        total = fake.random_int(min=1, max=10000)
        data = {"all_users_count": total, "active_users_count": fake.random_int(min=1, max=total)}
        with _patch_request(_resp(data)):
            result = await ac.get_all_users_count()
        assert result == total

    @pytest.mark.asyncio
    async def test_get_users_stats_returns_struct(self) -> None:
        from src.services import api_client as ac
        total = fake.random_int(min=1, max=10000)
        active = fake.random_int(min=1, max=total)
        data = {"all_users_count": total, "active_users_count": active}
        with _patch_request(_resp(data)):
            result = await ac.get_users_stats()
        assert result.all_users_count == total
        assert result.active_users_count == active


class TestApiHealthCheck:

    @pytest.mark.asyncio
    async def test_returns_ms_on_success(self) -> None:
        from src.services import api_client as ac
        with _patch_request(_resp({"status": "ok"})):
            result = await ac.api_health_check()
        assert isinstance(result, float)
        assert result >= 0

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        from src.services import api_client as ac
        with patch("src.services.api_client._request",
                   new=AsyncMock(side_effect=Exception("connection refused"))):
            result = await ac.api_health_check()
        assert result is None


class TestGetUserMessageCount:

    @pytest.mark.asyncio
    async def test_returns_count(self) -> None:
        from src.services import api_client as ac
        count = fake.random_int(min=0, max=5000)
        with _patch_request(_resp({"count": count})):
            result = await ac.get_user_message_count(_uid())
        assert result == count


class TestGetUserFull:

    @pytest.mark.asyncio
    async def test_returns_user_full_response(self) -> None:
        from src.services import api_client as ac
        uid = _uid()
        data = {
            "user": _fake_user_dict(uid),
            "message_count": fake.random_int(min=0, max=1000),
        }
        with _patch_request(_resp(data)):
            result = await ac.get_user_full(uid)
        assert result is not None
        assert result.user.id == uid

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self) -> None:
        from src.services import api_client as ac
        with _patch_request(_resp(status=404)):
            result = await ac.get_user_full(_uid())
        assert result is None


# ── _b64_to_buf ───────────────────────────────────────────────────────────────


class TestB64ToBuf:

    def test_decodes_base64_to_bytesio(self) -> None:
        import base64
        from src.services.api_client import _b64_to_buf
        raw = fake.binary(length=32)
        b64 = base64.b64encode(raw).decode()
        buf = _b64_to_buf(b64, "test.png")
        buf.seek(0)
        assert buf.read() == raw
        assert buf.name == "test.png"

    def test_buffer_starts_at_zero(self) -> None:
        import base64
        from src.services.api_client import _b64_to_buf
        raw = fake.binary(length=16)
        b64 = base64.b64encode(raw).decode()
        buf = _b64_to_buf(b64, "img.png")
        assert buf.tell() == 0
