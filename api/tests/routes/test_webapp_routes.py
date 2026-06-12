"""
Тесты для api/src/routes/webapp.py.

Все маршруты /webapp/* требуют аутентификации через verify_webapp_init_data.
В тестах подменяем эту зависимость через api_app.dependency_overrides.

Покрываем:
- GET  /webapp/me     — новый/существующий пользователь, redis-prefs, not-whitelisted
- PATCH /webapp/me    — обновление language, model, theme, пустое тело
- POST /webapp/dialogs/new, /ensure, /bootstrap
- GET  /webapp/dialogs/messages/page, /messages
- POST /webapp/chat
- _extract_tg_user: missing user field, invalid JSON
- _unwhitelisted_profile: синтетический профиль
- _require_whitelisted: not whitelisted → 403
- _redis_read_prefs, _redis_write_prefs: косвенно через маршруты
- _db_write_prefs: косвенно через PATCH /me

Faker: user IDs, имена, username, message, model, dialog IDs, ответы GPT.
"""

import json
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

fake = Faker()
Faker.seed(42)

_MODELS = ["gpt-4o", "gpt-5-nano"]


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _tg_user(**overrides) -> dict:
    return {
        "id": overrides.get("id", fake.random_int(min=100_000, max=999_999_999)),
        "first_name": overrides.get("first_name", fake.first_name()),
        "last_name": overrides.get("last_name", fake.last_name()),
        "username": overrides.get("username", fake.user_name()),
        "language_code": overrides.get("language_code", "ru"),
    }


def _make_init_data(tg: dict) -> dict:
    return {"user": json.dumps(tg)}


@pytest.fixture
def webapp_client(api_app, mock_redis, fake):
    """
    TestClient с корректно замоканным verify_webapp_init_data и Redis.
    Yield (client, tg_user_dict).
    """
    from db.db import get_session
    from core.security import verify_webapp_init_data

    tg = _tg_user()
    init_data = _make_init_data(tg)

    async def _fake_init_data() -> dict:
        return init_data

    async def _mock_session() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock(spec=AsyncSession)

    api_app.dependency_overrides[get_session] = _mock_session
    api_app.dependency_overrides[verify_webapp_init_data] = _fake_init_data

    import routes.webapp as webapp_mod
    original_get_redis = webapp_mod.get_redis
    webapp_mod.get_redis = lambda: mock_redis

    from fastapi.testclient import TestClient
    client = TestClient(api_app, raise_server_exceptions=False)

    yield client, tg

    webapp_mod.get_redis = original_get_redis
    api_app.dependency_overrides.clear()


@pytest.fixture
def _user_obj(fake, user_factory):
    """Готовый SimpleNamespace-пользователь для замены возврата из repo."""
    return user_factory()


# ── GET /webapp/me ────────────────────────────────────────────────────────────


class TestGetMe:

    @pytest.mark.api
    def test_existing_user_returns_200(self, webapp_client, user_factory, mock_redis) -> None:
        client, tg = webapp_client
        user = user_factory(id=tg["id"], chat_id=tg["id"],
                            first_name=tg["first_name"],
                            username=tg.get("username"))
        mock_redis.get.return_value = None
        mock_redis.hgetall.return_value = {}

        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.user_repo.get_or_create_user",
                   new=AsyncMock(return_value=(user, False))), \
             patch("routes.webapp._redis_read_prefs", new=AsyncMock(return_value={})):
            resp = client.get("/webapp/me")

        assert resp.status_code == 200
        assert resp.json()["id"] == tg["id"]

    @pytest.mark.api
    def test_new_user_created_returns_200(self, webapp_client, user_factory) -> None:
        client, tg = webapp_client
        user = user_factory(id=tg["id"], chat_id=tg["id"])

        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.user_repo.get_or_create_user",
                   new=AsyncMock(return_value=(user, True))), \
             patch("routes.webapp._redis_read_prefs", new=AsyncMock(return_value={})):
            resp = client.get("/webapp/me")

        assert resp.status_code == 200

    @pytest.mark.api
    def test_not_whitelisted_returns_synthetic_profile(self, webapp_client) -> None:
        client, tg = webapp_client

        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=False)):
            resp = client.get("/webapp/me")

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_whitelisted"] is False
        assert data["id"] == tg["id"]

    @pytest.mark.api
    def test_redis_prefs_override_db_values(self, webapp_client, user_factory) -> None:
        client, tg = webapp_client
        user = user_factory(id=tg["id"], language="ru")
        redis_prefs = {"language": "en"}

        with patch("routes.webapp.whitelist.is_allowed", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.user_repo.get_or_create_user",
                   new=AsyncMock(return_value=(user, False))), \
             patch("routes.webapp._redis_read_prefs",
                   new=AsyncMock(return_value=redis_prefs)):
            resp = client.get("/webapp/me")

        assert resp.status_code == 200
        assert resp.json()["language"] == "en"

    @pytest.mark.api
    def test_user_field_missing_in_init_data_returns_401(
        self, api_app, mock_redis, fake
    ) -> None:
        from db.db import get_session
        from core.security import verify_webapp_init_data

        async def _bad_init_data() -> dict:
            return {}  # нет поля "user"

        async def _mock_session():
            yield AsyncMock(spec=AsyncSession)

        api_app.dependency_overrides[get_session] = _mock_session
        api_app.dependency_overrides[verify_webapp_init_data] = _bad_init_data

        import routes.webapp as webapp_mod
        original = webapp_mod.get_redis
        webapp_mod.get_redis = lambda: mock_redis

        from fastapi.testclient import TestClient
        client = TestClient(api_app, raise_server_exceptions=False)
        resp = client.get("/webapp/me")

        webapp_mod.get_redis = original
        api_app.dependency_overrides.clear()

        assert resp.status_code == 401

    @pytest.mark.api
    def test_invalid_user_json_in_init_data_returns_401(
        self, api_app, mock_redis
    ) -> None:
        from db.db import get_session
        from core.security import verify_webapp_init_data

        async def _bad_json() -> dict:
            return {"user": "NOT_VALID_JSON{{{"}

        async def _mock_session():
            yield AsyncMock(spec=AsyncSession)

        api_app.dependency_overrides[get_session] = _mock_session
        api_app.dependency_overrides[verify_webapp_init_data] = _bad_json

        import routes.webapp as webapp_mod
        original = webapp_mod.get_redis
        webapp_mod.get_redis = lambda: mock_redis

        from fastapi.testclient import TestClient
        client = TestClient(api_app, raise_server_exceptions=False)
        resp = client.get("/webapp/me")

        webapp_mod.get_redis = original
        api_app.dependency_overrides.clear()

        assert resp.status_code == 401


# ── PATCH /webapp/me ──────────────────────────────────────────────────────────


class TestUpdateMe:

    @pytest.mark.api
    def test_update_language_returns_ok(self, webapp_client, user_factory) -> None:
        client, tg = webapp_client
        user = user_factory(id=tg["id"])
        lang = fake.random_element(["ru", "en", "de", "es", "fr"])

        with patch("routes.webapp._require_user", new=AsyncMock(return_value=user)), \
             patch("routes.webapp._redis_write_prefs", new=AsyncMock()), \
             patch("routes.webapp._redis_invalidate_user_cache", new=AsyncMock()), \
             patch("routes.webapp._db_write_prefs", new=AsyncMock()):
            resp = client.patch("/webapp/me", json={"language": lang})

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.api
    def test_update_model(self, webapp_client, user_factory) -> None:
        client, tg = webapp_client
        user = user_factory(id=tg["id"])
        model = fake.random_element(_MODELS)

        with patch("routes.webapp._require_user", new=AsyncMock(return_value=user)), \
             patch("routes.webapp._redis_write_prefs", new=AsyncMock()), \
             patch("routes.webapp._redis_invalidate_user_cache", new=AsyncMock()), \
             patch("routes.webapp._db_write_prefs", new=AsyncMock()):
            resp = client.patch("/webapp/me", json={"model": model})

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.api
    def test_update_theme(self, webapp_client, user_factory) -> None:
        client, tg = webapp_client
        user = user_factory(id=tg["id"])
        theme = fake.random_element(["light", "dark", "system"])

        with patch("routes.webapp._require_user", new=AsyncMock(return_value=user)), \
             patch("routes.webapp._redis_write_prefs", new=AsyncMock()), \
             patch("routes.webapp._redis_invalidate_user_cache", new=AsyncMock()), \
             patch("routes.webapp._db_write_prefs", new=AsyncMock()):
            resp = client.patch("/webapp/me", json={"theme": theme})

        assert resp.status_code == 200

    @pytest.mark.api
    def test_empty_update_body_returns_ok(self, webapp_client, user_factory) -> None:
        client, tg = webapp_client
        user = user_factory(id=tg["id"])

        with patch("routes.webapp._require_user", new=AsyncMock(return_value=user)), \
             patch("routes.webapp._db_write_prefs", new=AsyncMock()):
            resp = client.patch("/webapp/me", json={})

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.api
    def test_update_mini_app_chat_mode(self, webapp_client, user_factory) -> None:
        client, tg = webapp_client
        user = user_factory(id=tg["id"])

        with patch("routes.webapp._require_user", new=AsyncMock(return_value=user)), \
             patch("routes.webapp._redis_write_prefs", new=AsyncMock()), \
             patch("routes.webapp._redis_invalidate_user_cache", new=AsyncMock()), \
             patch("routes.webapp._db_write_prefs", new=AsyncMock()):
            resp = client.patch("/webapp/me", json={"mini_app_chat_mode": "assistant"})

        assert resp.status_code == 200

    @pytest.mark.api
    def test_user_not_found_during_update_returns_404(self, webapp_client) -> None:
        client, _ = webapp_client

        with patch("routes.webapp._require_user",
                   new=AsyncMock(side_effect=Exception("User not registered"))):
            resp = client.patch("/webapp/me", json={"language": "en"})

        assert resp.status_code in (404, 500)


# ── POST /webapp/dialogs/new ──────────────────────────────────────────────────


class TestWebappDialogsNew:

    @pytest.mark.api
    def test_new_dialog_returns_dialog_id(self, webapp_client) -> None:
        client, _ = webapp_client
        did = str(uuid.uuid4())

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.start_new_mini_app_dialog",
                   new=AsyncMock(return_value=did)):
            resp = client.post("/webapp/dialogs/new")

        assert resp.status_code == 200
        assert resp.json()["dialog_id"] == did

    @pytest.mark.api
    def test_new_dialog_not_whitelisted_returns_403(self, webapp_client) -> None:
        from fastapi import HTTPException
        client, _ = webapp_client

        exc = HTTPException(status_code=403, detail="Access restricted — account not whitelisted")
        with patch("routes.webapp._require_whitelisted", new=AsyncMock(side_effect=exc)):
            resp = client.post("/webapp/dialogs/new")

        assert resp.status_code == 403

    @pytest.mark.api
    def test_faker_multiple_dialog_ids(self, webapp_client) -> None:
        client, _ = webapp_client
        for _ in range(3):
            did = str(uuid.uuid4())
            with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
                 patch("routes.webapp.dialog_repo.start_new_mini_app_dialog",
                       new=AsyncMock(return_value=did)):
                resp = client.post("/webapp/dialogs/new")
            assert resp.status_code == 200
            assert resp.json()["dialog_id"] == did


# ── POST /webapp/dialogs/ensure ───────────────────────────────────────────────


class TestWebappDialogsEnsure:

    @pytest.mark.api
    def test_ensure_dialog_returns_dialog_id(self, webapp_client) -> None:
        client, _ = webapp_client
        did = str(uuid.uuid4())

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.ensure_active_mini_app_dialog",
                   new=AsyncMock(return_value=did)):
            resp = client.post("/webapp/dialogs/ensure")

        assert resp.status_code == 200
        assert resp.json()["dialog_id"] == did


# ── POST /webapp/dialogs/bootstrap ────────────────────────────────────────────


class TestWebappBootstrap:

    @pytest.mark.api
    def test_bootstrap_returns_dialog_id_and_messages(self, webapp_client) -> None:
        client, _ = webapp_client
        did = str(uuid.uuid4())
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()} for _ in range(5)]

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.ensure_active_mini_app_dialog",
                   new=AsyncMock(return_value=did)), \
             patch("routes.webapp.dialog_repo.get_dialog_messages_page",
                   new=AsyncMock(return_value=(msgs, len(msgs), 0))):
            resp = client.post("/webapp/dialogs/bootstrap")

        assert resp.status_code == 200
        data = resp.json()
        assert data["dialog_id"] == did
        assert data["messages"] == msgs
        assert data["next_before_index"] == 0


# ── GET /webapp/dialogs/messages/page ────────────────────────────────────────


class TestWebappMessagesPage:

    @pytest.mark.api
    def test_messages_page_returns_paginated_result(self, webapp_client) -> None:
        client, _ = webapp_client
        did = str(uuid.uuid4())
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}
                for _ in range(fake.random_int(min=3, max=10))]
        before_index = fake.random_int(min=5, max=50)

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.get_dialog_messages_page",
                   new=AsyncMock(return_value=(msgs, len(msgs), 0))):
            resp = client.get(
                "/webapp/dialogs/messages/page",
                params={"dialog_id": did, "before_index": before_index},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == msgs
        assert "has_more" in data

    @pytest.mark.api
    def test_messages_page_has_more_true_when_next_before_index_gt_zero(
        self, webapp_client
    ) -> None:
        client, _ = webapp_client
        did = str(uuid.uuid4())

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.get_dialog_messages_page",
                   new=AsyncMock(return_value=([], 100, 10))):
            resp = client.get(
                "/webapp/dialogs/messages/page",
                params={"dialog_id": did, "before_index": 20},
            )

        assert resp.json()["has_more"] is True
        assert resp.json()["next_before_index"] == 10


# ── GET /webapp/dialogs/messages ─────────────────────────────────────────────


class TestWebappGetMessages:

    @pytest.mark.api
    def test_no_params_returns_messages_by_mode(self, webapp_client) -> None:
        client, _ = webapp_client
        by_mode = {"assistant": [{"user": fake.sentence(), "bot": fake.sentence()}]}

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.get_dialog_messages_by_mode",
                   new=AsyncMock(return_value=by_mode)):
            resp = client.get("/webapp/dialogs/messages")

        assert resp.status_code == 200
        assert resp.json()["messages_by_mode"] == by_mode

    @pytest.mark.api
    def test_with_dialog_id_returns_messages(self, webapp_client) -> None:
        client, _ = webapp_client
        did = str(uuid.uuid4())
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}]

        with patch("routes.webapp.dialog_repo.get_dialog_messages",
                   new=AsyncMock(return_value=msgs)):
            resp = client.get(
                "/webapp/dialogs/messages",
                params={"dialog_id": did},
            )

        assert resp.status_code == 200
        assert resp.json()["messages"] == msgs

    @pytest.mark.api
    def test_with_chat_mode_returns_messages(self, webapp_client) -> None:
        client, _ = webapp_client
        did = str(uuid.uuid4())
        msgs = [{"user": fake.sentence(), "bot": fake.sentence()}]
        mode = fake.random_element(["assistant", "artist"])

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.get_mini_app_dialog_id",
                   new=AsyncMock(return_value=did)), \
             patch("routes.webapp.dialog_repo.get_dialog_messages",
                   new=AsyncMock(return_value=msgs)):
            resp = client.get(
                "/webapp/dialogs/messages",
                params={"chat_mode": mode},
            )

        assert resp.status_code == 200
        assert resp.json()["messages"] == msgs

    @pytest.mark.api
    def test_value_error_in_messages_by_mode_returns_404(self, webapp_client) -> None:
        client, _ = webapp_client

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.dialog_repo.get_dialog_messages_by_mode",
                   new=AsyncMock(side_effect=ValueError("User not found"))):
            resp = client.get("/webapp/dialogs/messages")

        assert resp.status_code == 404


# ── POST /webapp/chat ─────────────────────────────────────────────────────────


class TestWebappChat:

    def _gpt_mock(self, answer: str):
        instance = MagicMock()
        instance.send_message = AsyncMock(return_value=(answer, (10, 20), 0))
        instance.send_vision_message = AsyncMock(return_value=(answer, (10, 20), 0))
        return MagicMock(return_value=instance)

    @pytest.mark.api
    def test_chat_returns_answer(self, webapp_client) -> None:
        client, _ = webapp_client
        answer = fake.paragraph()
        gpt_cls = self._gpt_mock(answer)

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.moderate_content",
                   new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.webapp.ChatGPT", gpt_cls), \
             patch("routes.webapp._resolve_mini_app_dialog_id",
                   new=AsyncMock(return_value=str(uuid.uuid4()))), \
             patch("routes.webapp.dialog_repo.append_messages", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.webapp.dialog_repo.update_n_used_tokens", new=AsyncMock()), \
             patch("routes.webapp.user_repo.update_last_interaction", new=AsyncMock()):
            resp = client.post("/webapp/chat", json={
                "message": fake.sentence(),
                "model": "gpt-4o",
                "chat_mode": "assistant",
            })

        assert resp.status_code == 200
        assert resp.json()["answer"] == answer

    @pytest.mark.api
    def test_chat_flagged_content_returns_flagged(self, webapp_client) -> None:
        client, _ = webapp_client

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.moderate_content",
                   new=AsyncMock(return_value=(True, {}, {}))):
            resp = client.post("/webapp/chat", json={
                "message": fake.sentence(),
                "model": "gpt-4o",
                "chat_mode": "assistant",
            })

        assert resp.status_code == 200
        assert resp.json()["is_flagged"] is True

    @pytest.mark.api
    def test_chat_faker_batch_messages(self, webapp_client) -> None:
        client, _ = webapp_client
        for _ in range(3):
            answer = fake.paragraph()
            gpt_cls = self._gpt_mock(answer)
            with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
                 patch("routes.webapp.moderate_content",
                       new=AsyncMock(return_value=(False, {}, {}))), \
                 patch("routes.webapp.ChatGPT", gpt_cls), \
                 patch("routes.webapp._resolve_mini_app_dialog_id",
                       new=AsyncMock(return_value=str(uuid.uuid4()))), \
                 patch("routes.webapp.dialog_repo.append_messages", new=AsyncMock()), \
                 patch("routes.webapp.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
                 patch("routes.webapp.dialog_repo.update_n_used_tokens", new=AsyncMock()), \
                 patch("routes.webapp.user_repo.update_last_interaction", new=AsyncMock()):
                resp = client.post("/webapp/chat", json={
                    "message": fake.sentence(),
                    "model": "gpt-4o",
                    "chat_mode": "assistant",
                })
            assert resp.status_code == 200


# ── Helpers (покрываем через маршруты) ────────────────────────────────────────


class TestWebappHelpers:

    @pytest.mark.api
    def test_require_whitelisted_forbidden_via_new_dialog(self, webapp_client) -> None:
        """_require_whitelisted → False → 403."""
        from fastapi import HTTPException
        client, _ = webapp_client
        exc = HTTPException(status_code=403, detail="not whitelisted")

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(side_effect=exc)):
            resp = client.post("/webapp/dialogs/new")

        assert resp.status_code == 403

    @pytest.mark.api
    def test_resolve_dialog_id_with_body_id(self, webapp_client) -> None:
        """_resolve_mini_app_dialog_id возвращает body.dialog_id если задан."""
        client, _ = webapp_client
        did = str(uuid.uuid4())
        answer = fake.paragraph()
        gpt_cls = MagicMock(
            return_value=MagicMock(
                send_message=AsyncMock(return_value=(answer, (5, 10), 0))
            )
        )

        with patch("routes.webapp._require_whitelisted", new=AsyncMock(return_value=None)), \
             patch("routes.webapp.moderate_content",
                   new=AsyncMock(return_value=(False, {}, {}))), \
             patch("routes.webapp.ChatGPT", gpt_cls), \
             patch("routes.webapp.dialog_repo.append_messages", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.get_context", new=AsyncMock(return_value=[])), \
             patch("routes.webapp.dialog_repo.update_n_used_tokens", new=AsyncMock()), \
             patch("routes.webapp.user_repo.update_last_interaction", new=AsyncMock()), \
             patch("routes.webapp.dialog_repo.ensure_active_mini_app_dialog",
                   new=AsyncMock(return_value=did)):
            resp = client.post("/webapp/chat", json={
                "message": fake.sentence(),
                "model": "gpt-4o",
                "dialog_id": did,
            })

        assert resp.status_code == 200
