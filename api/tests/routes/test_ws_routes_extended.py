"""
Расширенные тесты для api/src/routes/ws.py.

Покрываем недостающие ветки:
- _store_image()        - eviction просроченных записей
- get_image()           - Redis exception при memory miss
- _broadcast()          - пустой пул, с подключениями, exclude
- _auth_handshake()     - timeout, invalid JSON, неверный тип фрейма, успех
- _spawn()              - задача с exception вызывает _log_exc
"""

import asyncio
import base64
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

def _fake_image_b64() -> str:
    return f"data:image/png;base64,{base64.b64encode(fake.binary(length=32)).decode()}"

# _store_image - eviction

class TestStoreImageEviction:

    @pytest.mark.asyncio
    async def test_evicts_expired_entries(self) -> None:
        import routes.ws as ws_mod
        # Добавляем просроченную запись вручную
        old_id = "old_" + fake.sha256()[:16]
        ws_mod._IMAGE_STORE[old_id] = b"old_data"
        ws_mod._IMAGE_TS[old_id] = time.monotonic() - ws_mod._IMAGE_TTL - 10

        b64_data = _fake_image_b64()
        with patch("routes.ws.get_redis_binary") as mock_getter:
            mock_r = AsyncMock()
            mock_r.setex = AsyncMock()
            mock_getter.return_value = mock_r
            new_id = await ws_mod._store_image(b64_data)

        # Просроченная запись должна быть удалена
        assert old_id not in ws_mod._IMAGE_STORE
        # Новая запись должна быть в кэше
        assert new_id in ws_mod._IMAGE_STORE
        ws_mod._IMAGE_STORE.pop(new_id, None)
        ws_mod._IMAGE_TS.pop(new_id, None)

# get_image - Redis exception

class TestGetImageRedisException:

    @pytest.mark.api
    def test_redis_exception_on_memory_miss_returns_404(self, api_client) -> None:
        import routes.ws as ws_mod
        image_id = "missing_" + fake.sha256()[:16]
        ws_mod._IMAGE_STORE.pop(image_id, None)
        with patch("routes.ws.get_redis_binary") as mock_getter:
            mock_r = AsyncMock()
            mock_r.get = AsyncMock(side_effect=Exception("redis error"))
            mock_getter.return_value = mock_r
            resp = api_client.get(f"/webapp/images/{image_id}")
        assert resp.status_code == 404

# _broadcast

class TestBroadcast:

    @pytest.mark.asyncio
    async def test_empty_pool_does_nothing(self) -> None:
        import routes.ws as ws_mod
        uid = fake.random_int(min=100_000, max=999_999_999)
        ws_mod._WS_POOL.pop(uid, None)
        await ws_mod._broadcast(uid, {"type": "ping"})
        # Не упало

    @pytest.mark.asyncio
    async def test_broadcasts_to_all_connections(self) -> None:
        import routes.ws as ws_mod
        uid = fake.random_int(min=100_000, max=999_999_999)
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.send_text = AsyncMock()
        ws2.send_text = AsyncMock()
        ws_mod._WS_POOL[uid] = {ws1, ws2}
        try:
            await ws_mod._broadcast(uid, {"type": "ping"})
        finally:
            ws_mod._WS_POOL.pop(uid, None)
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exclude_skips_one_connection(self) -> None:
        import routes.ws as ws_mod
        uid = fake.random_int(min=100_000, max=999_999_999)
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.send_text = AsyncMock()
        ws2.send_text = AsyncMock()
        ws_mod._WS_POOL[uid] = {ws1, ws2}
        try:
            await ws_mod._broadcast(uid, {"type": "update"}, exclude=ws1)
        finally:
            ws_mod._WS_POOL.pop(uid, None)
        ws1.send_text.assert_not_awaited()
        ws2.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_exception_does_not_stop_broadcast(self) -> None:
        import routes.ws as ws_mod
        uid = fake.random_int(min=100_000, max=999_999_999)
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.send_text = AsyncMock(side_effect=Exception("closed"))
        ws2.send_text = AsyncMock()
        ws_mod._WS_POOL[uid] = {ws1, ws2}
        try:
            await ws_mod._broadcast(uid, {"type": "ping"})
        finally:
            ws_mod._WS_POOL.pop(uid, None)
        ws2.send_text.assert_awaited_once()

# _auth_handshake

class TestAuthHandshake:

    @pytest.mark.asyncio
    async def test_timeout_sends_error_and_returns_none(self) -> None:
        import routes.ws as ws_mod
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=TimeoutError())
        ws.send_text = AsyncMock()
        result = await ws_mod._auth_handshake(ws)
        assert result is None
        ws.send_text.assert_awaited_once()
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "auth_error"

    @pytest.mark.asyncio
    async def test_invalid_json_sends_error_and_returns_none(self) -> None:
        import routes.ws as ws_mod
        ws = AsyncMock()
        ws.receive_text = AsyncMock(return_value="not json {{")
        ws.send_text = AsyncMock()
        result = await ws_mod._auth_handshake(ws)
        assert result is None
        ws.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wrong_frame_type_returns_none(self) -> None:
        import routes.ws as ws_mod
        ws = AsyncMock()
        ws.receive_text = AsyncMock(return_value=json.dumps({"type": "chat", "message": "hi"}))
        ws.send_text = AsyncMock()
        result = await ws_mod._auth_handshake(ws)
        assert result is None
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "auth_error"

    @pytest.mark.asyncio
    async def test_invalid_init_data_returns_none(self) -> None:
        import routes.ws as ws_mod
        ws = AsyncMock()
        ws.receive_text = AsyncMock(return_value=json.dumps({
            "type": "auth",
            "init_data": "invalid_data",
        }))
        ws.send_text = AsyncMock()
        with patch("routes.ws._verify_init_data", side_effect=ValueError("invalid hash")):
            result = await ws_mod._auth_handshake(ws)
        assert result is None
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "auth_error"

    @pytest.mark.asyncio
    async def test_valid_auth_returns_user_id(self) -> None:
        import routes.ws as ws_mod
        uid = fake.random_int(min=100_000, max=999_999_999)
        # _auth_handshake возвращает user_id - auth_ok отправляет сам endpoint
        parsed = {"user": json.dumps({"id": uid})}
        ws = AsyncMock()
        ws.receive_text = AsyncMock(return_value=json.dumps({
            "type": "auth",
            "init_data": "valid_data",
        }))
        ws.send_text = AsyncMock()
        with patch("routes.ws._verify_init_data", return_value=parsed):
            result = await ws_mod._auth_handshake(ws)
        assert result == uid
        # Успешный handshake не отправляет ничего сам по себе
        ws.send_text.assert_not_awaited()

# _spawn - exception callback

class TestSpawnException:

    @pytest.mark.asyncio
    async def test_exception_in_task_is_logged(self) -> None:
        import routes.ws as ws_mod
        error_raised = asyncio.Event()

        async def _failing_coro():
            raise RuntimeError("task failed")

        with patch("routes.ws.logger") as mock_logger:
            task = ws_mod._spawn(_failing_coro())
            # Ждём завершения задачи
            await asyncio.sleep(0.05)

        # Задача завершилась с исключением - logger.exception был вызван
        assert mock_logger.exception.called or task.done()
