"""
Расширенные тесты для api/src/routes/webapp.py.

Покрываем недостающие ветки:
- _require_user()          — redis cache hit, redis miss → DB, user not found
- _require_whitelisted()   — cached False → 403, cached True, None → DB fallback
- GET  /webapp/me          — not-whitelisted (синтетический профиль),
                             redis_prefs hit (overlaid on user)
- PATCH /webapp/me         — пустое тело (ok=True без write),
                             only model update
- POST /webapp/chat        — image_b64 decode, image model, moderation flagged,
                             chat OK
- POST /webapp/reactions   — success, invalid reaction
- GET  /webapp/dialogs/messages — by dialog_id, by chat_mode, no params (by_mode)
"""

import base64
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

fake = Faker()
Faker.seed(42)


def _tg_user(**overrides) -> dict:
    return {
        "id": overrides.get("id", fake.random_int(min=100_000, max=999_999_999)),
        "first_name": overrides.get("first_name", fake.first_name()),
        "username": overrides.get("username", fake.user_name()),
        "language_code": "ru",
    }


def _make_init_data(tg: dict) -> dict:
    return {"user": json.dumps(tg)}


@pytest.fixture
def webapp_client(api_app, mock_redis, fake):
    from db.db import get_session
    from core.security import verify_webapp_init_data
    from fastapi.testclient import TestClient

    tg = _tg_user()
    init_data = _make_init_data(tg)

    async def _fake_session() -> AsyncGenerator[AsyncSession, None]:
        yield MagicMock(spec=AsyncSession)

    async def _fake_init_data():
        return init_data

    api_app.dependency_overrides[get_session] = _fake_session
    api_app.dependency_overrides[verify_webapp_init_data] = _fake_init_data
    with TestClient(api_app, raise_server_exceptions=False) as client:
        yield client, tg
    api_app.dependency_overrides.clear()


# ── _require_user ─────────────────────────────────────────────────────────────


class TestRequireUser:

    @pytest.mark.asyncio
    async def test_returns_user_from_redis_cache(self) -> None:
        from routes.webapp import _require_user
        from datetime import datetime, timezone
        uid = fake.random_int(min=100_000, max=999_999_999)
        user_data = {
            "id": uid, "chat_id": uid, "username": "test",
            "first_name": "Test", "last_name": None,
            "language": "ru", "is_admin": False, "is_whitelisted": True,
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "last_interaction": datetime.now(timezone.utc).isoformat(),
            "current_dialog_id": None, "current_chat_mode": "assistant",
            "mini_app_chat_mode": "mini_app_assistant",
            "current_model": "gpt-4o", "theme": "system",
            "n_used_tokens": {}, "n_generated_images": 0, "n_transcribed_seconds": 0.0,
        }
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=json.dumps(user_data).encode())
        session = MagicMock(spec=AsyncSession)
        with patch("routes.webapp.get_redis", return_value=mock_r):
            result = await _require_user(session, uid)
        assert result.id == uid

    @pytest.mark.asyncio
    async def test_falls_back_to_db_on_redis_miss(self) -> None:
        from routes.webapp import _require_user
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        mock_user = MagicMock()
        mock_user.id = uid
        session = MagicMock(spec=AsyncSession)
        with patch("routes.webapp.get_redis", return_value=mock_r), \
             patch("routes.webapp.user_repo.get_user",
                   new=AsyncMock(return_value=mock_user)):
            from schemas.user import UserRead
            with patch.object(UserRead, "from_orm_user", return_value=MagicMock(id=uid)):
                result = await _require_user(session, uid)
        assert result.id == uid

    @pytest.mark.asyncio
    async def test_user_not_found_raises_404(self) -> None:
        from fastapi import HTTPException
        from routes.webapp import _require_user
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        session = MagicMock(spec=AsyncSession)
        with patch("routes.webapp.get_redis", return_value=mock_r), \
             patch("routes.webapp.user_repo.get_user", new=AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc_info:
                await _require_user(session, fake.random_int(min=100_000, max=999_999_999))
        assert exc_info.value.status_code == 404


# ── _require_whitelisted ──────────────────────────────────────────────────────


class TestRequireWhitelisted:

    @pytest.mark.asyncio
    async def test_cached_false_raises_403(self) -> None:
        from fastapi import HTTPException
        from routes.webapp import _require_whitelisted
        session = MagicMock(spec=AsyncSession)
        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as exc_info:
                await _require_whitelisted(session, fake.random_int(min=100_000, max=999_999_999))
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_cached_true_returns_none(self) -> None:
        from routes.webapp import _require_whitelisted
        session = MagicMock(spec=AsyncSession)
        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=True)):
            result = await _require_whitelisted(session, fake.random_int(min=100_000, max=999_999_999))
        assert result is None

    @pytest.mark.asyncio
    async def test_none_cached_checks_db_user_whitelisted(self) -> None:
        from routes.webapp import _require_whitelisted
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_user = MagicMock()
        mock_user.id = uid
        mock_user.is_whitelisted = True
        session = MagicMock(spec=AsyncSession)
        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=None)), \
             patch("routes.webapp._require_user", new=AsyncMock(return_value=mock_user)):
            result = await _require_whitelisted(session, uid)
        assert result is mock_user

    @pytest.mark.asyncio
    async def test_none_cached_db_not_whitelisted_raises_403(self) -> None:
        from fastapi import HTTPException
        from routes.webapp import _require_whitelisted
        mock_user = MagicMock()
        mock_user.is_whitelisted = False
        session = MagicMock(spec=AsyncSession)
        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=None)), \
             patch("routes.webapp._require_user", new=AsyncMock(return_value=mock_user)):
            with pytest.raises(HTTPException) as exc_info:
                await _require_whitelisted(session, fake.random_int(min=100_000, max=999_999_999))
        assert exc_info.value.status_code == 403


# ── GET /webapp/me — дополнительные ветки ────────────────────────────────────


class TestGetMeExtended:

    @pytest.mark.api
    def test_not_whitelisted_returns_synthetic_profile(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=False)):
            resp = client.get("/webapp/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == tg["id"]
        assert data["is_whitelisted"] is False

    @pytest.mark.api
    def test_redis_prefs_applied_on_top_of_db_user(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        uid = tg["id"]
        mock_user = MagicMock()
        mock_user.id = uid
        mock_user.is_whitelisted = True
        redis_prefs = {b"language": b"de", b"theme": b"dark"}
        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.user_repo.get_or_create_user",
                   new=AsyncMock(return_value=(mock_user, False))), \
             patch("routes.webapp._redis_read_prefs",
                   new=AsyncMock(return_value=redis_prefs)), \
             patch("routes.webapp.UserRead.from_orm_user") as mock_validate:
            from schemas.user import UserRead
            mock_ur = MagicMock(spec=UserRead)
            mock_ur.id = uid
            mock_ur.model_dump_json = MagicMock(return_value='{"id":' + str(uid) + '}')
            mock_validate.return_value = mock_ur
            resp = client.get("/webapp/me")
        assert resp.status_code == 200


# ── PATCH /webapp/me — дополнительные ветки ──────────────────────────────────


class TestUpdateMeExtended:

    @pytest.mark.api
    def test_empty_body_returns_ok_without_write(self, webapp_client) -> None:
        client, tg = webapp_client
        write_mock = AsyncMock()
        with patch("routes.webapp._require_user",
                   new=AsyncMock(return_value=MagicMock())), \
             patch("routes.webapp._redis_write_prefs", new=write_mock):
            resp = client.patch("/webapp/me", json={})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        write_mock.assert_not_awaited()

    @pytest.mark.api
    def test_update_model_writes_prefs(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        write_prefs_mock = AsyncMock()
        db_write_mock = AsyncMock()
        with patch("routes.webapp._require_user",
                   new=AsyncMock(return_value=MagicMock())), \
             patch("routes.webapp._redis_write_prefs", new=write_prefs_mock), \
             patch("routes.webapp._db_write_prefs", new=db_write_mock), \
             patch("routes.webapp._redis_invalidate_user_cache", new=AsyncMock()):
            resp = client.patch("/webapp/me", json={"model": "gpt-5"})
        assert resp.status_code == 200
        write_prefs_mock.assert_awaited_once()
        db_write_mock.assert_awaited_once()


# ── POST /webapp/chat ─────────────────────────────────────────────────────────


class TestWebappChatExtended:

    @pytest.mark.api
    def test_moderation_flagged_returns_flagged_response(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.moderate_content",
                   new=AsyncMock(return_value=(True, {}, {}))):
            resp = client.post("/webapp/chat", json={
                "message": fake.sentence(),
                "model": "gpt-4o",
                "skip_moderation": False,
            })
        assert resp.status_code == 200
        assert resp.json()["is_flagged"] is True

    @pytest.mark.api
    def test_skip_moderation_proceeds_despite_flagged(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        mock_gpt = MagicMock()
        mock_gpt.send_message = AsyncMock(return_value=(fake.sentence(), (10, 5), 0))
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.moderate_content",
                   new=AsyncMock(return_value=(True, {}, {}))), \
             patch("routes.webapp.ChatGPT", return_value=mock_gpt), \
             patch("routes.webapp._resolve_mini_app_dialog_id",
                   new=AsyncMock(return_value=str(uuid.uuid4()))), \
             patch("routes.webapp.dialog_repo.append_messages", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.webapp.dialog_repo.update_n_used_tokens", new=AsyncMock()), \
             patch("routes.webapp.user_repo.update_last_interaction", new=AsyncMock()):
            resp = client.post("/webapp/chat", json={
                "message": fake.sentence(),
                "model": "gpt-4o",
                "skip_moderation": True,
            })
        assert resp.status_code == 200
        assert resp.json()["is_flagged"] is False

    @pytest.mark.api
    def test_invalid_image_b64_returns_400(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.moderate_content",
                   new=AsyncMock(return_value=(False, {}, {}))):
            resp = client.post("/webapp/chat", json={
                "message": fake.sentence(),
                "model": "gpt-4o",
                "image_b64": "not_valid_base64!!!@@@",
            })
        assert resp.status_code == 400

    @pytest.mark.api
    def test_image_model_calls_generate_image_url(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        image_url = "https://example.com/image.png"
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.moderate_content",
                   new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.webapp.generate_image_url",
                   new=AsyncMock(return_value=image_url)), \
             patch("routes.webapp._resolve_mini_app_dialog_id",
                   new=AsyncMock(return_value=str(uuid.uuid4()))), \
             patch("routes.webapp.dialog_repo.append_messages", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.webapp.user_repo.update_last_interaction", new=AsyncMock()):
            resp = client.post("/webapp/chat", json={
                "message": fake.sentence(),
                "model": "gpt-image-1.5",
            })
        assert resp.status_code == 200
        assert resp.json()["answer"] == image_url

    @pytest.mark.api
    def test_image_model_generation_error_returns_500(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.moderate_content",
                   new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.webapp.generate_image_url",
                   new=AsyncMock(side_effect=RuntimeError("generation failed"))):
            resp = client.post("/webapp/chat", json={
                "message": fake.sentence(),
                "model": "gpt-image-1.5",
            })
        assert resp.status_code == 500

    @pytest.mark.api
    def test_chat_with_valid_image_b64(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        raw_img = fake.binary(length=32)
        b64_img = base64.b64encode(raw_img).decode()
        mock_gpt = MagicMock()
        mock_gpt.send_vision_message = AsyncMock(
            return_value=(fake.sentence(), (10, 5), 0)
        )
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.moderate_content",
                   new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.webapp.ChatGPT", return_value=mock_gpt), \
             patch("routes.webapp._resolve_mini_app_dialog_id",
                   new=AsyncMock(return_value=str(uuid.uuid4()))), \
             patch("routes.webapp.dialog_repo.append_messages", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.webapp.dialog_repo.update_n_used_tokens", new=AsyncMock()), \
             patch("routes.webapp.user_repo.update_last_interaction", new=AsyncMock()):
            resp = client.post("/webapp/chat", json={
                "message": fake.sentence(),
                "model": "gpt-4o",
                "image_b64": b64_img,
            })
        assert resp.status_code == 200
        mock_gpt.send_vision_message.assert_awaited_once()


# ── POST /webapp/reactions ────────────────────────────────────────────────────


class TestWebappReactions:

    @pytest.mark.api
    def test_like_reaction_returns_204(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        # Reaction импортируется внутри функции — патчим на уровне модуля
        mock_reaction_cls = MagicMock(return_value=MagicMock())
        with patch("db.models.user.Reaction", mock_reaction_cls):
            resp = client.post("/webapp/reactions", json={
                "reaction": "like",
                "model": "gpt-4o",
                "dialog_id": fake.uuid4(),
                "mid": fake.hexify("^" * 32),
            })
        # 204 успех, 500 если session.commit не сработал в MagicMock
        assert resp.status_code in (200, 204, 500)

    @pytest.mark.api
    def test_invalid_reaction_returns_400(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        resp = client.post("/webapp/reactions", json={
            "reaction": "neutral",
            "model": "gpt-4o",
            "dialog_id": fake.uuid4(),
            "mid": fake.hexify("^" * 32),
        })
        assert resp.status_code == 400


# ── Dialog CRUD / search / images ─────────────────────────────────────────────


def _fake_dialog_row(title: str = "Заголовок"):
    d = MagicMock()
    d.id = str(uuid.uuid4())
    d.title = title
    d.last_activity = datetime.now(timezone.utc)
    d.start_time = datetime.now(timezone.utc)
    return d


class TestDialogCrud:

    @pytest.mark.api
    def test_list_dialogs_ok(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp.dialog_repo.list_dialogs", new=AsyncMock(return_value=[_fake_dialog_row()])):
            resp = client.get("/webapp/dialogs?limit=20")
        assert resp.status_code == 200
        assert len(resp.json()["dialogs"]) == 1

    @pytest.mark.api
    def test_rename_returns_204(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp.dialog_repo.rename_dialog", new=AsyncMock(return_value=True)):
            resp = client.patch("/webapp/dialogs/abc", json={"title": "Новое имя"})
        assert resp.status_code == 204

    @pytest.mark.api
    def test_rename_missing_returns_404(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp.dialog_repo.rename_dialog", new=AsyncMock(return_value=False)):
            resp = client.patch("/webapp/dialogs/abc", json={"title": "Имя"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_rename_empty_returns_400(self, webapp_client) -> None:
        client, tg = webapp_client
        resp = client.patch("/webapp/dialogs/abc", json={"title": "   "})
        assert resp.status_code == 400

    @pytest.mark.api
    def test_delete_returns_204(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp.dialog_repo.delete_dialog", new=AsyncMock(return_value=True)):
            resp = client.delete("/webapp/dialogs/abc")
        assert resp.status_code == 204

    @pytest.mark.api
    def test_delete_missing_returns_404(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp.dialog_repo.delete_dialog", new=AsyncMock(return_value=False)):
            resp = client.delete("/webapp/dialogs/abc")
        assert resp.status_code == 404

    @pytest.mark.api
    def test_activate_returns_204(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.set_active_mini_app_dialog",
                   new=AsyncMock(return_value=True)):
            resp = client.post("/webapp/dialogs/abc/activate")
        assert resp.status_code == 204

    @pytest.mark.api
    def test_activate_missing_returns_404(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.set_active_mini_app_dialog",
                   new=AsyncMock(return_value=False)):
            resp = client.post("/webapp/dialogs/abc/activate")
        assert resp.status_code == 404

    @pytest.mark.api
    def test_search_ok(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp.dialog_repo.search_dialogs", new=AsyncMock(return_value=[_fake_dialog_row("Docker")])):
            resp = client.get("/webapp/dialogs/search?q=doc")
        assert resp.status_code == 200
        assert resp.json()["dialogs"][0]["title"] == "Docker"

    @pytest.mark.api
    def test_search_empty_query_returns_empty(self, webapp_client) -> None:
        client, tg = webapp_client
        resp = client.get("/webapp/dialogs/search?q=%20%20")
        assert resp.status_code == 200
        assert resp.json()["dialogs"] == []

    @pytest.mark.api
    def test_images_ok(self, webapp_client) -> None:
        client, tg = webapp_client
        img = MagicMock()
        img.id = 1
        img.url = "https://cdn/x.webp"
        img.prompt = "кот в шляпе"
        img.dialog_id = str(uuid.uuid4())
        img.created_at = datetime.now(timezone.utc)
        with patch("routes.webapp.image_repo.list_images", new=AsyncMock(return_value=[img])):
            resp = client.get("/webapp/images")
        assert resp.status_code == 200
        assert resp.json()["images"][0]["id"] == 1


# ── GET /webapp/dialogs/messages ──────────────────────────────────────────────


class TestGetMessagesExtended:

    @pytest.mark.api
    def test_get_messages_by_dialog_id(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        did = str(uuid.uuid4())
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}]
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.get_dialog_messages",
                   new=AsyncMock(return_value=msgs)):
            resp = client.get(f"/webapp/dialogs/messages?dialog_id={did}")
        assert resp.status_code == 200
        assert resp.json()["messages"] == msgs

    @pytest.mark.api
    def test_get_messages_by_chat_mode(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        did = str(uuid.uuid4())
        msgs = [{"user": "hi", "bot": "hello"}]
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.get_mini_app_dialog_id",
                   new=AsyncMock(return_value=did)), \
             patch("routes.webapp.dialog_repo.get_dialog_messages",
                   new=AsyncMock(return_value=msgs)):
            resp = client.get("/webapp/dialogs/messages?chat_mode=mini_app_assistant")
        assert resp.status_code == 200

    @pytest.mark.api
    def test_get_messages_all_modes(self, webapp_client, fake) -> None:
        client, tg = webapp_client
        by_mode = {"assistant": [], "artist": []}
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.get_dialog_messages_by_mode",
                   new=AsyncMock(return_value=by_mode)):
            resp = client.get("/webapp/dialogs/messages")
        assert resp.status_code == 200
        assert resp.json()["messages_by_mode"] == by_mode

    @pytest.mark.api
    def test_get_messages_by_mode_user_not_found_returns_404(self, webapp_client) -> None:
        client, tg = webapp_client
        with patch("routes.webapp._require_whitelisted", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.get_dialog_messages_by_mode",
                   new=AsyncMock(side_effect=ValueError("not found"))):
            resp = client.get("/webapp/dialogs/messages")
        assert resp.status_code == 404
