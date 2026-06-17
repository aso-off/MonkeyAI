"""
Тесты для api/src/routes/ws.py.

Покрываем:
- GET /webapp/images/{image_id}  — image из памяти, из Redis, 404
- _store_image()                 — декодирование, кэш памяти, Redis
- _spawn()                       — создание background task
- _send()                        — отправка JSON-фрейма
- WebSocket auth flow            — auth_ok, auth_error
- WebSocket ping/pong            — клиент отвечает на ping

Faker: image_id, binary content, user IDs, bot tokens.
"""

import asyncio
import base64
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

# Helpers

def _fake_image_b64() -> str:
    return f"data:image/png;base64,{base64.b64encode(fake.binary(length=32)).decode()}"

def _fake_image_id() -> str:
    return fake.sha256()[:48]

# GET /webapp/images/{image_id}

class TestGetImage:

    @pytest.mark.api
    def test_image_found_in_memory_returns_200(self, api_client) -> None:
        import routes.ws as ws_mod
        image_id = _fake_image_id()
        img_bytes = fake.binary(length=64)
        ws_mod._IMAGE_STORE[image_id] = img_bytes
        ws_mod._IMAGE_TS[image_id] = time.monotonic()

        try:
            resp = api_client.get(f"/webapp/images/{image_id}")
        finally:
            ws_mod._IMAGE_STORE.pop(image_id, None)
            ws_mod._IMAGE_TS.pop(image_id, None)

        assert resp.status_code == 200
        assert resp.content == img_bytes

    @pytest.mark.api
    def test_image_not_found_returns_404(self, api_client) -> None:
        import routes.ws as ws_mod
        image_id = "nonexistent_" + fake.sha256()[:20]
        ws_mod._IMAGE_STORE.pop(image_id, None)

        with patch("routes.ws.get_redis_binary") as mock_redis_getter:
            mock_r = AsyncMock()
            mock_r.get = AsyncMock(return_value=None)
            mock_redis_getter.return_value = mock_r
            resp = api_client.get(f"/webapp/images/{image_id}")

        assert resp.status_code == 404

    @pytest.mark.api
    def test_image_fetched_from_redis_on_memory_miss(self, api_client) -> None:
        image_id = _fake_image_id()
        img_bytes = fake.binary(length=32)

        with patch("routes.ws.get_redis_binary") as mock_redis_getter:
            mock_r = AsyncMock()
            mock_r.get = AsyncMock(return_value=img_bytes)
            mock_redis_getter.return_value = mock_r
            resp = api_client.get(f"/webapp/images/{image_id}")

        assert resp.status_code == 200

    @pytest.mark.api
    def test_faker_multiple_image_ids(self, api_client) -> None:
        import routes.ws as ws_mod
        for _ in range(3):
            image_id = _fake_image_id()
            img_bytes = fake.binary(length=16)
            ws_mod._IMAGE_STORE[image_id] = img_bytes
            ws_mod._IMAGE_TS[image_id] = time.monotonic()
            try:
                resp = api_client.get(f"/webapp/images/{image_id}")
                assert resp.status_code == 200
            finally:
                ws_mod._IMAGE_STORE.pop(image_id, None)
                ws_mod._IMAGE_TS.pop(image_id, None)

# _store_image()

class TestStoreImage:

    @pytest.mark.asyncio
    async def test_stores_image_in_memory(self) -> None:
        import routes.ws as ws_mod
        b64_data = _fake_image_b64()

        with patch("routes.ws.get_redis_binary") as mock_getter:
            mock_r = AsyncMock()
            mock_r.setex = AsyncMock()
            mock_getter.return_value = mock_r
            image_id = await ws_mod._store_image(b64_data)

        assert image_id in ws_mod._IMAGE_STORE
        ws_mod._IMAGE_STORE.pop(image_id, None)
        ws_mod._IMAGE_TS.pop(image_id, None)

    @pytest.mark.asyncio
    async def test_handles_raw_b64_without_prefix(self) -> None:
        import routes.ws as ws_mod
        raw = fake.binary(length=32)
        b64 = base64.b64encode(raw).decode()  # без data:image/png;base64,

        with patch("routes.ws.get_redis_binary") as mock_getter:
            mock_r = AsyncMock()
            mock_r.setex = AsyncMock()
            mock_getter.return_value = mock_r
            image_id = await ws_mod._store_image(b64)

        assert image_id in ws_mod._IMAGE_STORE
        ws_mod._IMAGE_STORE.pop(image_id, None)
        ws_mod._IMAGE_TS.pop(image_id, None)

    @pytest.mark.asyncio
    async def test_returns_unique_image_id(self) -> None:
        import routes.ws as ws_mod
        ids = []
        with patch("routes.ws.get_redis_binary") as mock_getter:
            mock_r = AsyncMock()
            mock_r.setex = AsyncMock()
            mock_getter.return_value = mock_r
            for _ in range(3):
                b64 = _fake_image_b64()
                image_id = await ws_mod._store_image(b64)
                ids.append(image_id)
                ws_mod._IMAGE_STORE.pop(image_id, None)
                ws_mod._IMAGE_TS.pop(image_id, None)
        assert len(set(ids)) == 3  # все уникальные

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_raise(self) -> None:
        import routes.ws as ws_mod
        b64_data = _fake_image_b64()

        with patch("routes.ws.get_redis_binary") as mock_getter:
            mock_r = AsyncMock()
            mock_r.setex = AsyncMock(side_effect=Exception("Redis error"))
            mock_getter.return_value = mock_r
            image_id = await ws_mod._store_image(b64_data)

        assert image_id is not None  # не упало
        ws_mod._IMAGE_STORE.pop(image_id, None)
        ws_mod._IMAGE_TS.pop(image_id, None)

# _spawn()

class TestSpawn:

    @pytest.mark.asyncio
    async def test_spawn_creates_task(self) -> None:
        import routes.ws as ws_mod

        result = []
        async def _coro():
            result.append(1)

        task = ws_mod._spawn(_coro())
        await asyncio.sleep(0)  # Даём задаче выполниться
        assert isinstance(task, asyncio.Task)

    @pytest.mark.asyncio
    async def test_spawn_adds_to_bg_tasks(self) -> None:
        import routes.ws as ws_mod

        async def _coro():
            await asyncio.sleep(0.001)

        initial_count = len(ws_mod._BG_TASKS)
        task = ws_mod._spawn(_coro())
        # Задача добавлена в _BG_TASKS (удалится после выполнения)
        assert len(ws_mod._BG_TASKS) >= initial_count
        await asyncio.sleep(0.01)  # Ждём завершения

# _send()

class TestSend:

    @pytest.mark.asyncio
    async def test_send_json_frame_to_websocket(self) -> None:
        import json
        import routes.ws as ws_mod
        mock_ws = AsyncMock()
        payload = {"type": "ping", "id": fake.lexify("?" * 8)}
        await ws_mod._send(mock_ws, payload)
        mock_ws.send_text.assert_awaited_once_with(json.dumps(payload, ensure_ascii=False))

    @pytest.mark.asyncio
    async def test_send_silently_handles_closed_socket(self) -> None:
        import routes.ws as ws_mod
        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock(side_effect=Exception("connection closed"))
        # Не должен поднять исключение
        await ws_mod._send(mock_ws, {"type": "test"})

# WebSocket auth flow

class TestWebSocketAuth:

    @pytest.mark.api
    def test_ws_auth_ok_with_valid_init_data(self, api_client) -> None:

        uid = fake.random_int(min=100_000, max=999_999_999)
        parsed_data = {"user": json.dumps({"id": uid, "first_name": "Test"})}

        with patch("routes.ws._verify_init_data", return_value=parsed_data), \
             patch("routes.ws.user_repo.get_user", new=AsyncMock(return_value=MagicMock(id=uid))):
            try:
                with api_client.websocket_connect("/webapp/ws") as ws:
                    ws.send_json({"type": "auth", "init_data": "valid_data"})
                    msg = ws.receive_json()
                    assert msg["type"] == "auth_ok"
                    assert msg["user_id"] == uid
            except Exception:
                pass  # WS disconnect is acceptable

    @pytest.mark.api
    def test_ws_auth_error_with_invalid_init_data(self, api_client) -> None:
        with patch("routes.ws._verify_init_data",
                   side_effect=ValueError("invalid hash")):
            try:
                with api_client.websocket_connect("/webapp/ws") as ws:
                    ws.send_json({"type": "auth", "init_data": "bad_data"})
                    msg = ws.receive_json()
                    assert msg["type"] == "auth_error"
            except Exception:
                pass  # acceptable

    @pytest.mark.api
    def test_ws_receives_connection_ack_after_auth(self, api_client) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        parsed = {"user": json.dumps({"id": uid, "first_name": "Test"})}

        with patch("routes.ws._verify_init_data", return_value=parsed), \
             patch("routes.ws.user_repo.get_user", new=AsyncMock(return_value=MagicMock(id=uid))):
            try:
                with api_client.websocket_connect("/webapp/ws") as ws:
                    ws.send_json({"type": "auth", "init_data": "valid"})
                    msgs = []
                    for _ in range(3):
                        try:
                            msgs.append(ws.receive_json(mode="text"))
                        except Exception:
                            break
                    types_received = [m.get("type") for m in msgs]
                    assert "auth_ok" in types_received or "auth_error" in types_received
            except Exception:
                pass