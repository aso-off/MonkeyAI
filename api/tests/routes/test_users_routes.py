"""Тесты для API роутов /users/* через FastAPI TestClient.

Зависимости мокируются через patch на уровне модулей:
- db.repositories.users — get_user, get_or_create_user, update_user
- db.repositories.dialogs — get_all_users_count, get_active_users_count, get_user_message_count
- core.redis.get_redis — mock из conftest
- verify_service_token — noop stub из api/tests/conftest.py

Реальная БД и Redis не нужны.
"""

from unittest.mock import AsyncMock, patch

import pytest


# GET /users/{user_id}


class TestGetUser:
    @pytest.mark.api
    def test_existing_user_returns_200(self, api_client, user_factory) -> None:
        user = user_factory()
        with patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)), \
             patch("routes.users._redis_write_user", new=AsyncMock()):
            resp = api_client.get(f"/users/{user.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == user.id

    @pytest.mark.api
    def test_nonexistent_user_returns_404(self, api_client, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        with patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=None)), \
             patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)):
            resp = api_client.get(f"/users/{uid}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.api
    def test_user_from_redis_cache_returns_200(self, api_client, user_factory) -> None:
        user = user_factory()
        from schemas.user import UserRead
        cached = UserRead.from_orm_user(user)
        with patch("routes.users._redis_read_user", new=AsyncMock(return_value=cached)):
            resp = api_client.get(f"/users/{user.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == user.id

    @pytest.mark.api
    def test_faker_batch_users_all_200(self, api_client, user_factory, fake) -> None:
        for _ in range(3):
            user = user_factory()
            with patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)), \
                 patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=user)), \
                 patch("routes.users._redis_write_user", new=AsyncMock()):
                resp = api_client.get(f"/users/{user.id}")
            assert resp.status_code == 200


# POST /users


class TestCreateUser:
    @pytest.mark.api
    def test_create_new_user_returns_201(self, api_client, user_factory) -> None:
        user = user_factory()
        with patch("routes.users.user_repo.get_or_create_user",
                   new=AsyncMock(return_value=(user, True))), \
             patch("routes.users._redis_write_user", new=AsyncMock()):
            resp = api_client.post("/users", json={
                "id": user.id,
                "chat_id": user.chat_id,
                "first_name": user.first_name,
                "language": "ru",
            })
        assert resp.status_code == 201
        assert resp.json()["id"] == user.id

    @pytest.mark.api
    def test_existing_user_returns_200(self, api_client, user_factory) -> None:
        user = user_factory()
        with patch("routes.users.user_repo.get_or_create_user",
                   new=AsyncMock(return_value=(user, False))), \
             patch("routes.users._redis_write_user", new=AsyncMock()):
            resp = api_client.post("/users", json={
                "id": user.id,
                "chat_id": user.chat_id,
                "first_name": user.first_name,
            })
        assert resp.status_code == 200

    @pytest.mark.api
    def test_missing_id_returns_422(self, api_client) -> None:
        resp = api_client.post("/users", json={"chat_id": 123, "first_name": "Test"})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_missing_chat_id_returns_422(self, api_client) -> None:
        resp = api_client.post("/users", json={"id": 123, "first_name": "Test"})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_faker_batch_create(self, api_client, user_factory, fake) -> None:
        for _ in range(3):
            user = user_factory()
            with patch("routes.users.user_repo.get_or_create_user",
                       new=AsyncMock(return_value=(user, True))), \
                 patch("routes.users._redis_write_user", new=AsyncMock()):
                resp = api_client.post("/users", json={
                    "id": user.id,
                    "chat_id": user.chat_id,
                    "first_name": fake.first_name(),
                    "username": fake.user_name(),
                    "language": "ru",
                })
            assert resp.status_code == 201


# PATCH /users/{user_id}


class TestUpdateUser:
    @pytest.mark.api
    def test_update_language_returns_200(self, api_client, user_factory) -> None:
        user = user_factory(language="ru")
        updated = type(user)(**{**vars(user), "language": "en"})
        with patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)), \
             patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.users._redis_write_user", new=AsyncMock()), \
             patch("routes.users._redis_sync_webapp_prefs", new=AsyncMock()), \
             patch("routes.users._db_update_user", new=AsyncMock()):
            resp = api_client.patch(f"/users/{user.id}", json={"language": "en"})
        assert resp.status_code == 200
        assert resp.json()["language"] == "en"

    @pytest.mark.api
    def test_update_empty_body_returns_400(self, api_client, user_factory) -> None:
        user = user_factory()
        with patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)), \
             patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=user)):
            resp = api_client.patch(f"/users/{user.id}", json={})
        assert resp.status_code == 400

    @pytest.mark.api
    def test_update_nonexistent_user_returns_404(self, api_client, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        with patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)), \
             patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=None)):
            resp = api_client.patch(f"/users/{uid}", json={"language": "en"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_update_chat_mode(self, api_client, user_factory) -> None:
        user = user_factory(current_chat_mode="assistant")
        with patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)), \
             patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.users._redis_write_user", new=AsyncMock()), \
             patch("routes.users._redis_sync_webapp_prefs", new=AsyncMock()), \
             patch("routes.users._db_update_user", new=AsyncMock()):
            resp = api_client.patch(f"/users/{user.id}", json={"current_chat_mode": "code_assistant"})
        assert resp.status_code == 200
        assert resp.json()["current_chat_mode"] == "code_assistant"

    @pytest.mark.api
    def test_update_is_whitelisted_calls_whitelist_service(self, api_client, user_factory) -> None:
        user = user_factory(is_whitelisted=False)
        mock_add = AsyncMock()
        with patch("services.whitelist.add", new=mock_add), \
             patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)), \
             patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.users._redis_write_user", new=AsyncMock()), \
             patch("routes.users._redis_sync_webapp_prefs", new=AsyncMock()), \
             patch("routes.users._db_update_user", new=AsyncMock()):
            resp = api_client.patch(f"/users/{user.id}", json={"is_whitelisted": True})
        assert resp.status_code == 200
        mock_add.assert_awaited_once_with(user.id)


# GET /users/stats


class TestUsersStats:
    @pytest.mark.api
    def test_stats_returns_200(self, api_client) -> None:
        with patch("routes.users.dialog_repo.get_all_users_count", new=AsyncMock(return_value=100)), \
             patch("routes.users.dialog_repo.get_active_users_count", new=AsyncMock(return_value=30)), \
             patch("routes.users._redis_read_stats", new=AsyncMock(return_value=None)), \
             patch("routes.users._redis_write_stats", new=AsyncMock()):
            resp = api_client.get("/users/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_users_count"] == 100
        assert data["active_users_count"] == 30

    @pytest.mark.api
    def test_stats_from_redis_cache(self, api_client) -> None:
        cached = {"all_users_count": 50, "active_users_count": 10}
        with patch("routes.users._redis_read_stats", new=AsyncMock(return_value=cached)):
            resp = api_client.get("/users/stats")
        assert resp.status_code == 200
        assert resp.json() == cached

    @pytest.mark.api
    def test_stats_faker_values(self, api_client, fake) -> None:
        total = fake.random_int(min=1, max=10_000)
        active = fake.random_int(min=1, max=total)
        with patch("routes.users.dialog_repo.get_all_users_count", new=AsyncMock(return_value=total)), \
             patch("routes.users.dialog_repo.get_active_users_count", new=AsyncMock(return_value=active)), \
             patch("routes.users._redis_read_stats", new=AsyncMock(return_value=None)), \
             patch("routes.users._redis_write_stats", new=AsyncMock()):
            resp = api_client.get("/users/stats")
        assert resp.json()["all_users_count"] == total
        assert resp.json()["active_users_count"] == active


# GET /health (базовая проверка роутера)


class TestHealthRoute:
    @pytest.mark.api
    def test_health_returns_ok(self, api_client, mock_redis) -> None:
        mock_redis.ping.return_value = True
        resp = api_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("ok", "degraded")

    @pytest.mark.api
    def test_health_redis_down_returns_degraded(self, api_client, mock_redis) -> None:
        # routes/health.py имеет свой локальный get_redis (from core.redis import get_redis)
        # Патчим именно в этом пространстве имён
        with patch("routes.health.get_redis", return_value=mock_redis):
            mock_redis.ping.side_effect = Exception("Redis unavailable")
            resp = api_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"
        assert resp.json()["redis"] == "down"