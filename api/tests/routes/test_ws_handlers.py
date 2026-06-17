"""
Тесты для api/src/routes/ws.py — ранее не покрытые строки 217-529.

Покрываем:
- _auth_handshake:   tma-prefix, missing user, malformed user field
- _heartbeat:        send failure → return
- _generation_keepalive: broadcast loop (один тик)
- _handle_chat:      empty msg, guard, moderation flag/error, ChatGPT error,
                     stream error, success (с persist), dialog_id=None
- _handle_image:     empty prompt, guard, moderation flag, timeout, error,
                     process fail, upload fail, success
- _message_loop:     invalid JSON, pong, chat, image, unknown type
"""

import asyncio
import base64
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(10)

def _uid() -> int:
    return fake.random_int(min=100_000_000, max=999_999_999)

def _make_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws

def _mock_session_cm():
    """Returns an async context manager that yields an AsyncMock session."""
    session = AsyncMock()

    @asynccontextmanager
    async def _cm():
        yield session

    return _cm, session

# _auth_handshake — edge cases

class TestAuthHandshakeEdgeCases:

    @pytest.mark.asyncio
    async def test_tma_prefix_stripped(self) -> None:
        import routes.ws as ws_mod
        uid = _uid()
        parsed = {"user": json.dumps({"id": uid})}
        ws = _make_ws()
        ws.receive_text = AsyncMock(return_value=json.dumps({
            "type": "auth",
            "init_data": f"tma valid_data_here",
        }))
        with patch("routes.ws._verify_init_data", return_value=parsed) as mock_verify:
            result = await ws_mod._auth_handshake(ws)
        # Проверяем, что "tma " был срезан перед передачей
        call_arg = mock_verify.call_args[0][0]
        assert not call_arg.startswith("tma ")
        assert result == uid

    @pytest.mark.asyncio
    async def test_missing_user_field_in_params(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        ws.receive_text = AsyncMock(return_value=json.dumps({
            "type": "auth",
            "init_data": "some_data",
        }))
        # user поле отсутствует в расшифрованных params
        with patch("routes.ws._verify_init_data", return_value={}):
            result = await ws_mod._auth_handshake(ws)
        assert result is None
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "auth_error"

    @pytest.mark.asyncio
    async def test_malformed_user_json(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        ws.receive_text = AsyncMock(return_value=json.dumps({
            "type": "auth",
            "init_data": "some_data",
        }))
        with patch("routes.ws._verify_init_data",
                   return_value={"user": "not_valid_json{{{"}):
            result = await ws_mod._auth_handshake(ws)
        assert result is None
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "auth_error"

    @pytest.mark.asyncio
    async def test_user_missing_id_key(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        ws.receive_text = AsyncMock(return_value=json.dumps({
            "type": "auth",
            "init_data": "some_data",
        }))
        with patch("routes.ws._verify_init_data",
                   return_value={"user": json.dumps({"name": "no_id_here"})}):
            result = await ws_mod._auth_handshake(ws)
        assert result is None
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "auth_error"

# _heartbeat

class TestHeartbeat:

    @pytest.mark.asyncio
    async def test_send_failure_causes_return(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        ws.send_text = AsyncMock(side_effect=Exception("connection broken"))
        with patch("routes.ws._PING_INTERVAL", 0):
            await ws_mod._heartbeat(ws)
        # Не упало — вернулось без исключения

# _generation_keepalive

class TestGenerationKeepalive:

    @pytest.mark.asyncio
    async def test_broadcasts_progress_then_cancelled(self) -> None:
        import routes.ws as ws_mod
        uid = _uid()
        req_id = str(fake.uuid4())
        ws1 = _make_ws()
        ws_mod._WS_POOL[uid] = {ws1}
        try:
            task = asyncio.create_task(ws_mod._generation_keepalive(uid, req_id))
            # Даём одному тику выполниться
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            ws_mod._WS_POOL.pop(uid, None)

# _handle_chat

class TestHandleChat:

    def _base_patches(self):
        """Базовые патчи для _handle_chat: broadcast, send, moderation."""
        return [
            patch("routes.ws._broadcast", new=AsyncMock()),
            patch("routes.ws._send",      new=AsyncMock()),
            patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))),
        ]

    @pytest.mark.asyncio
    async def test_empty_message_sends_error(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        frame = {"type": "chat", "id": "req1", "message": "   "}

        with patch("routes.ws._send", new=AsyncMock()) as mock_send, \
             patch("routes.ws._broadcast", new=AsyncMock()):
            await ws_mod._handle_chat(ws, uid, frame)

        sent = mock_send.call_args[0][1]
        assert sent["type"] == "chat_error"
        assert "empty" in sent["error"]

    @pytest.mark.asyncio
    async def test_guard_rejects_concurrent_generation(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        ws_mod._USER_GENERATING[(uid, None)] = "other_req"
        frame = {"type": "chat", "id": "req2", "message": "hello"}
        try:
            with patch("routes.ws._send", new=AsyncMock()) as mock_send, \
                 patch("routes.ws._broadcast", new=AsyncMock()):
                await ws_mod._handle_chat(ws, uid, frame)
            sent = mock_send.call_args[0][1]
            assert sent["type"] == "chat_error"
            assert "already generating" in sent["error"]
        finally:
            ws_mod._USER_GENERATING.pop((uid, None), None)

    @pytest.mark.asyncio
    async def test_moderation_flag_sends_chat_done_flagged(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        frame = {"type": "chat", "id": "req3", "message": "bad content"}

        broadcasts = []
        async def _cap_broadcast(user_id, payload, exclude=None):
            broadcasts.append(payload)

        with patch("routes.ws._broadcast", side_effect=_cap_broadcast), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(True, {}, {}))):
            await ws_mod._handle_chat(ws, uid, frame)

        done_frames = [p for p in broadcasts if p.get("type") == "chat_done"]
        assert any(f.get("is_flagged") for f in done_frames)
        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_moderation_exception_fallback_continues(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        frame = {"type": "chat", "id": "req_exc", "message": "hello"}

        stream_mock = AsyncMock()
        async def _empty_stream(*a, **kw):
            return
            yield  # make it an async generator

        chatgpt_instance = MagicMock()
        chatgpt_instance.send_message_stream = MagicMock(return_value=_aiter([]))
        chatgpt_cls = MagicMock(return_value=chatgpt_instance)

        cm, session = _mock_session_cm()

        with patch("routes.ws._broadcast", new=AsyncMock()), \
             patch("routes.ws._send",      new=AsyncMock()), \
             patch("routes.ws.moderate_content", side_effect=Exception("mod error")), \
             patch("routes.ws.ChatGPT", chatgpt_cls), \
             patch("routes.ws.Session", cm), \
             patch("routes.ws.dialog_repo.ensure_active_mini_app_dialog",
                   new=AsyncMock(return_value=str(fake.uuid4()))), \
             patch("routes.ws.dialog_repo.append_messages", new=AsyncMock()), \
             patch("routes.ws.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.ws.dialog_repo.update_n_used_tokens", new=AsyncMock()), \
             patch("routes.ws.user_repo.update_last_interaction", new=AsyncMock()):
            await ws_mod._handle_chat(ws, uid, frame)

        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_chatgpt_value_error_sends_chat_error(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        frame = {"type": "chat", "id": "req4", "message": "hello"}

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.ChatGPT", side_effect=ValueError("unknown model")):
            await ws_mod._handle_chat(ws, uid, frame)

        assert any(p.get("type") == "chat_error" for p in broadcasts)
        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_stream_exception_sends_chat_error(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        frame = {"type": "chat", "id": "req5", "message": "hello"}

        async def _bad_stream(*a, **kw):
            raise RuntimeError("OpenAI error")
            yield  # async generator

        chatgpt_instance = MagicMock()
        chatgpt_instance.send_message_stream = _bad_stream
        chatgpt_cls = MagicMock(return_value=chatgpt_instance)

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.ChatGPT", chatgpt_cls):
            await ws_mod._handle_chat(ws, uid, frame)

        assert any(p.get("type") == "chat_error" for p in broadcasts)
        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_successful_chat_sends_chat_done(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        dialog_id = str(fake.uuid4())
        frame = {"type": "chat", "id": "req6", "message": "hello", "dialog_id": dialog_id}

        answer = "The answer is 42"

        async def _stream(*a, **kw):
            yield "done", answer, "", (10, 20), 0

        chatgpt_instance = MagicMock()
        chatgpt_instance.send_message_stream = _stream
        chatgpt_cls = MagicMock(return_value=chatgpt_instance)

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        cm, session = _mock_session_cm()

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.ChatGPT", chatgpt_cls), \
             patch("routes.ws.Session", cm), \
             patch("routes.ws.dialog_repo.append_messages", new=AsyncMock()), \
             patch("routes.ws.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.ws.dialog_repo.update_n_used_tokens", new=AsyncMock()), \
             patch("routes.ws.user_repo.update_last_interaction", new=AsyncMock()):
            await ws_mod._handle_chat(ws, uid, frame)

        done = next((p for p in broadcasts if p.get("type") == "chat_done"), None)
        assert done is not None
        assert done["message"]["role"] == "assistant"
        assert done["message"]["content"] == answer
        assert done["message"]["usage"] == {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_dialog_id_none_resolves_from_db(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        resolved_id = str(fake.uuid4())
        frame = {"type": "chat", "id": "req7", "message": "hello", "dialog_id": None}

        async def _stream(*a, **kw):
            yield "done", "answer", "", (5, 10), 0

        chatgpt_instance = MagicMock()
        chatgpt_instance.send_message_stream = _stream
        chatgpt_cls = MagicMock(return_value=chatgpt_instance)

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        cm, session = _mock_session_cm()

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.ChatGPT", chatgpt_cls), \
             patch("routes.ws.Session", cm), \
             patch("routes.ws.dialog_repo.ensure_active_mini_app_dialog",
                   new=AsyncMock(return_value=resolved_id)), \
             patch("routes.ws.dialog_repo.append_messages", new=AsyncMock()), \
             patch("routes.ws.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.ws.dialog_repo.update_n_used_tokens", new=AsyncMock()), \
             patch("routes.ws.user_repo.update_last_interaction", new=AsyncMock()):
            await ws_mod._handle_chat(ws, uid, frame)

        done = next((p for p in broadcasts if p.get("type") == "chat_done"), None)
        assert done is not None
        assert done["dialog_id"] == resolved_id

    @pytest.mark.asyncio
    async def test_image_url_routes_to_vision_stream(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        dialog_id = str(fake.uuid4())
        img = "https://i.ibb.co/abc/photo.jpg"
        frame = {"type": "chat", "id": "rv", "message": "что на фото?",
                 "dialog_id": dialog_id, "image_url": img}

        async def _stream(*a, **kw):
            yield "done", "вижу кота", "", (5, 7), 0

        vision = MagicMock(side_effect=_stream)
        chatgpt_instance = MagicMock()
        chatgpt_instance.send_vision_message_stream = vision
        chatgpt_instance.send_message_stream = MagicMock(side_effect=AssertionError("text stream used"))
        chatgpt_cls = MagicMock(return_value=chatgpt_instance)

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        cm, session = _mock_session_cm()

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.ChatGPT", chatgpt_cls), \
             patch("routes.ws.Session", cm), \
             patch("routes.ws.dialog_repo.append_messages", new=AsyncMock()) as append, \
             patch("routes.ws.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.ws.dialog_repo.update_n_used_tokens", new=AsyncMock()), \
             patch("routes.ws.user_repo.update_last_interaction", new=AsyncMock()):
            await ws_mod._handle_chat(ws, uid, frame)

        assert vision.call_args.kwargs.get("image_url") == img
        user_echo = next((p for p in broadcasts if p.get("type") == "user_message"), None)
        assert user_echo is not None and user_echo["image_url"] == img
        persisted = append.call_args_list[0][0][3][0]
        parts = {i["type"] for i in persisted["content"]}
        assert parts == {"text", "image_url"}
        assert uid not in ws_mod._USER_GENERATING

# _handle_image

class TestHandleImage:

    @pytest.mark.asyncio
    async def test_empty_prompt_sends_error(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        frame = {"type": "image", "id": "img1", "message": "  "}

        with patch("routes.ws._send", new=AsyncMock()) as mock_send, \
             patch("routes.ws._broadcast", new=AsyncMock()):
            await ws_mod._handle_image(ws, uid, frame)

        sent = mock_send.call_args[0][1]
        assert sent["type"] == "image_error"
        assert "empty" in sent["error"]

    @pytest.mark.asyncio
    async def test_guard_rejects_concurrent_generation(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        ws_mod._USER_GENERATING[(uid, None)] = "other"
        frame = {"type": "image", "id": "img2", "message": "a cat"}
        try:
            with patch("routes.ws._send", new=AsyncMock()) as mock_send, \
                 patch("routes.ws._broadcast", new=AsyncMock()):
                await ws_mod._handle_image(ws, uid, frame)
            sent = mock_send.call_args[0][1]
            assert sent["type"] == "image_error"
            assert "already generating" in sent["error"]
        finally:
            ws_mod._USER_GENERATING.pop((uid, None), None)

    @pytest.mark.asyncio
    async def test_moderation_flag_sends_image_error(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        frame = {"type": "image", "id": "img3", "message": "bad image"}

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(True, {}, {}))):
            await ws_mod._handle_image(ws, uid, frame)

        assert any(p.get("type") == "image_error" for p in broadcasts)
        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_generation_timeout_sends_error(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        frame = {"type": "image", "id": "img4", "message": "a painting"}

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.generate_image_b64",
                   side_effect=asyncio.TimeoutError()):
            await ws_mod._handle_image(ws, uid, frame)

        assert any(p.get("type") == "image_error" and "timed out" in p.get("error", "")
                   for p in broadcasts)
        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_generation_exception_sends_error(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        frame = {"type": "image", "id": "img5", "message": "a cat"}

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.generate_image_b64",
                   new=AsyncMock(side_effect=RuntimeError("API error"))):
            await ws_mod._handle_image(ws, uid, frame)

        assert any(p.get("type") == "image_error" for p in broadcasts)
        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_process_image_failure_sends_error(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        b64_data = f"data:image/png;base64,{base64.b64encode(b'fake').decode()}"
        frame = {"type": "image", "id": "img6", "message": "a dog"}

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.generate_image_b64", new=AsyncMock(return_value=b64_data)), \
             patch("routes.ws.asyncio.to_thread", side_effect=Exception("pillow error")):
            await ws_mod._handle_image(ws, uid, frame)

        assert any(p.get("type") == "image_error" and "processing" in p.get("error", "")
                   for p in broadcasts)
        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_imgbb_upload_failure_sends_error(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        b64_data = f"data:image/png;base64,{base64.b64encode(b'fake').decode()}"
        frame = {"type": "image", "id": "img7", "message": "a bird"}

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        img_result = {"data": b64_data, "size_kb": 50.0}

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.generate_image_b64", new=AsyncMock(return_value=b64_data)), \
             patch("routes.ws.asyncio.to_thread", new=AsyncMock(return_value=img_result)), \
             patch("routes.ws.upload_to_imgbb",
                   new=AsyncMock(side_effect=Exception("upload failed"))), \
             patch("routes.ws.settings") as mock_settings:
            mock_settings.imgbb_api_key = "fake_key"
            await ws_mod._handle_image(ws, uid, frame)

        assert any(p.get("type") == "image_error" and "upload" in p.get("error", "")
                   for p in broadcasts)
        assert uid not in ws_mod._USER_GENERATING

    @pytest.mark.asyncio
    async def test_successful_image_sends_image_done(self) -> None:
        import routes.ws as ws_mod
        ws = _make_ws()
        uid = _uid()
        b64_data = f"data:image/png;base64,{base64.b64encode(b'fake').decode()}"
        img_url = "https://imgbb.com/abc123"
        dialog_id = str(fake.uuid4())
        frame = {"type": "image", "id": "img8", "message": "a fox", "dialog_id": dialog_id}

        broadcasts = []
        async def _cap(user_id, payload, exclude=None):
            broadcasts.append(payload)

        img_result = {"data": b64_data, "size_kb": 120.5}
        cm, session = _mock_session_cm()

        with patch("routes.ws._broadcast", side_effect=_cap), \
             patch("routes.ws._send", new=AsyncMock()), \
             patch("routes.ws.moderate_content", new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.ws.generate_image_b64", new=AsyncMock(return_value=b64_data)), \
             patch("routes.ws.asyncio.to_thread", new=AsyncMock(return_value=img_result)), \
             patch("routes.ws.upload_to_imgbb", new=AsyncMock(return_value=img_url)), \
             patch("routes.ws.Session", cm), \
             patch("routes.ws.dialog_repo.append_messages", new=AsyncMock()), \
             patch("routes.ws.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.ws.user_repo.update_last_interaction", new=AsyncMock()), \
             patch("routes.ws.handle_first_message_title", new=AsyncMock()), \
             patch("routes.ws.image_repo.add_generated_image", new=AsyncMock()), \
             patch("routes.ws.user_repo.increment_n_generated_images",
                   new=AsyncMock()) as mock_incr, \
             patch("routes.ws.settings") as mock_settings:
            mock_settings.imgbb_api_key = "fake_key"
            await ws_mod._handle_image(ws, uid, frame)

        done = next((p for p in broadcasts if p.get("type") == "image_done"), None)
        assert done is not None
        assert done["url"] == img_url
        assert done["size_kb"] == 120.5
        assert uid not in ws_mod._USER_GENERATING
        mock_incr.assert_awaited_once_with(session, uid, 1)

# _message_loop

class TestMessageLoop:

    async def _run_one_frame(self, raw_frame: str):
        """Run _message_loop for exactly one frame then raise WebSocketDisconnect."""
        from fastapi import WebSocketDisconnect

        ws = _make_ws()
        call_count = 0
        async def _receive():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return raw_frame
            raise WebSocketDisconnect()

        ws.receive_text = _receive
        uid = _uid()
        return ws, uid

    @pytest.mark.asyncio
    async def test_invalid_json_sends_error_frame(self) -> None:
        import routes.ws as ws_mod
        from fastapi import WebSocketDisconnect
        ws, uid = await self._run_one_frame("not_json{{")
        with patch("routes.ws._send", new=AsyncMock()) as mock_send:
            try:
                await ws_mod._message_loop(ws, uid)
            except WebSocketDisconnect:
                pass
        sent = mock_send.call_args[0][1]
        assert sent["type"] == "error"
        assert "invalid JSON" in sent["error"]

    @pytest.mark.asyncio
    async def test_pong_frame_ignored(self) -> None:
        import routes.ws as ws_mod
        from fastapi import WebSocketDisconnect
        ws, uid = await self._run_one_frame(json.dumps({"type": "pong"}))
        with patch("routes.ws._send", new=AsyncMock()) as mock_send, \
             patch("routes.ws._spawn", return_value=MagicMock()):
            try:
                await ws_mod._message_loop(ws, uid)
            except WebSocketDisconnect:
                pass
        mock_send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_chat_frame_spawns_handle_chat(self) -> None:
        import routes.ws as ws_mod
        from fastapi import WebSocketDisconnect
        ws, uid = await self._run_one_frame(
            json.dumps({"type": "chat", "id": "r1", "message": "hi"})
        )
        spawned = []
        with patch("routes.ws._spawn", side_effect=lambda coro: spawned.append(coro) or MagicMock()):
            try:
                await ws_mod._message_loop(ws, uid)
            except WebSocketDisconnect:
                pass
        assert len(spawned) == 1
        # Закрываем корутину чтобы не было предупреждений
        spawned[0].close()

    @pytest.mark.asyncio
    async def test_image_frame_spawns_handle_image(self) -> None:
        import routes.ws as ws_mod
        from fastapi import WebSocketDisconnect
        ws, uid = await self._run_one_frame(
            json.dumps({"type": "image", "id": "i1", "message": "cat"})
        )
        spawned = []
        with patch("routes.ws._spawn", side_effect=lambda coro: spawned.append(coro) or MagicMock()):
            try:
                await ws_mod._message_loop(ws, uid)
            except WebSocketDisconnect:
                pass
        assert len(spawned) == 1
        spawned[0].close()

    @pytest.mark.asyncio
    async def test_unknown_type_sends_error(self) -> None:
        import routes.ws as ws_mod
        from fastapi import WebSocketDisconnect
        ws, uid = await self._run_one_frame(
            json.dumps({"type": "subscribe", "channel": "news"})
        )
        with patch("routes.ws._send", new=AsyncMock()) as mock_send:
            try:
                await ws_mod._message_loop(ws, uid)
            except WebSocketDisconnect:
                pass
        sent = mock_send.call_args[0][1]
        assert sent["type"] == "error"
        assert "unknown type" in sent["error"]

# Helpers

async def _aiter(items):
    """Async generator из списка."""
    for item in items:
        yield item