"""
Расширенные тесты для api/src/routes/users.py.

Покрываем недостающие ветки:
- GET  /users/stats            — cached / uncached
- GET  /users/{id}/full        — redis cached / cache miss (found / not found)
- PATCH /users/{id}            — is_whitelisted=False → whitelist.remove
- Helpers: _redis_write_user, _redis_read_user, _redis_write_stats,
           _redis_read_stats, _redis_sync_webapp_prefs (косвенно через роуты)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# GET /users/stats

class TestUsersStats:

    @pytest.mark.api
    def test_stats_from_cache_returns_cached(self, api_client, fake) -> None:
        cached = {"all_users_count": 100, "active_users_count": 10}
        with patch("routes.users._redis_read_stats", new=AsyncMock(return_value=cached)):
            resp = api_client.get("/users/stats")
        assert resp.status_code == 200
        assert resp.json()["all_users_count"] == 100

    @pytest.mark.api
    def test_stats_from_db_when_cache_miss(self, api_client, fake) -> None:
        with patch("routes.users._redis_read_stats", new=AsyncMock(return_value=None)), \
             patch("routes.users.dialog_repo.get_all_users_count",
                   new=AsyncMock(return_value=50)), \
             patch("routes.users.dialog_repo.get_active_users_count",
                   new=AsyncMock(return_value=5)), \
             patch("routes.users._redis_write_stats", new=AsyncMock()):
            resp = api_client.get("/users/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_users_count"] == 50
        assert data["active_users_count"] == 5

    @pytest.mark.api
    def test_stats_written_to_cache_after_db_fetch(self, api_client) -> None:
        write_mock = AsyncMock()
        with patch("routes.users._redis_read_stats", new=AsyncMock(return_value=None)), \
             patch("routes.users.dialog_repo.get_all_users_count",
                   new=AsyncMock(return_value=0)), \
             patch("routes.users.dialog_repo.get_active_users_count",
                   new=AsyncMock(return_value=0)), \
             patch("routes.users._redis_write_stats", new=write_mock):
            api_client.get("/users/stats")
        write_mock.assert_awaited_once()

    @pytest.mark.api
    def test_stats_faker_large_counts(self, api_client, fake) -> None:
        total = fake.random_int(min=1000, max=50000)
        active = fake.random_int(min=100, max=total)
        with patch("routes.users._redis_read_stats", new=AsyncMock(return_value=None)), \
             patch("routes.users.dialog_repo.get_all_users_count",
                   new=AsyncMock(return_value=total)), \
             patch("routes.users.dialog_repo.get_active_users_count",
                   new=AsyncMock(return_value=active)), \
             patch("routes.users._redis_write_stats", new=AsyncMock()):
            resp = api_client.get("/users/stats")
        assert resp.json()["all_users_count"] == total

# GET /users/{user_id}/full

class TestGetUserFull:

    @pytest.mark.api
    def test_full_from_redis_cache_returns_200(self, api_client, user_factory, fake) -> None:
        import json
        user = user_factory()
        from schemas.user import UserRead
        user_read = UserRead.from_orm_user(user)
        cached_payload = json.dumps({
            "user": json.loads(user_read.model_dump_json()),
            "message_count": 42,
        })
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=cached_payload.encode())
        with patch("routes.users.get_redis", return_value=mock_r):
            resp = api_client.get(f"/users/{user.id}/full")
        assert resp.status_code == 200
        assert resp.json()["message_count"] == 42

    @pytest.mark.api
    def test_full_from_db_when_cache_miss(self, api_client, user_factory, fake) -> None:
        user = user_factory()
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        mock_r.set = AsyncMock()
        with patch("routes.users.get_redis", return_value=mock_r), \
             patch("routes.users._get_user_cached",
                   new=AsyncMock(return_value=__import__(
                       "schemas.user", fromlist=["UserRead"]
                   ).UserRead.from_orm_user(user))), \
             patch("routes.users.dialog_repo.get_user_message_count",
                   new=AsyncMock(return_value=7)):
            resp = api_client.get(f"/users/{user.id}/full")
        assert resp.status_code == 200
        assert resp.json()["message_count"] == 7

    @pytest.mark.api
    def test_full_not_found_returns_404(self, api_client, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        with patch("routes.users.get_redis", return_value=mock_r), \
             patch("routes.users._get_user_cached", new=AsyncMock(return_value=None)), \
             patch("routes.users.dialog_repo.get_user_message_count",
                   new=AsyncMock(return_value=0)):
            resp = api_client.get(f"/users/{uid}/full")
        assert resp.status_code == 404

    @pytest.mark.api
    def test_full_redis_exception_falls_back_to_db(self, api_client, user_factory, fake) -> None:
        user = user_factory()
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(side_effect=Exception("redis timeout"))
        mock_r.set = AsyncMock()
        from schemas.user import UserRead
        user_read = UserRead.from_orm_user(user)
        with patch("routes.users.get_redis", return_value=mock_r), \
             patch("routes.users._get_user_cached", new=AsyncMock(return_value=user_read)), \
             patch("routes.users.dialog_repo.get_user_message_count",
                   new=AsyncMock(return_value=3)):
            resp = api_client.get(f"/users/{user.id}/full")
        assert resp.status_code == 200

# PATCH /users/{id} — whitelist branches

class TestUpdateUserWhitelist:

    @pytest.mark.api
    def test_set_whitelisted_false_calls_whitelist_remove(self, api_client, user_factory) -> None:
        user = user_factory(is_whitelisted=True)
        mock_remove = AsyncMock()
        with patch("services.whitelist.remove", new=mock_remove), \
             patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)), \
             patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.users._redis_write_user", new=AsyncMock()), \
             patch("routes.users._redis_sync_webapp_prefs", new=AsyncMock()), \
             patch("routes.users._db_update_user", new=AsyncMock()):
            resp = api_client.patch(f"/users/{user.id}", json={"is_whitelisted": False})
        assert resp.status_code == 200
        mock_remove.assert_awaited_once_with(user.id)

    @pytest.mark.api
    def test_update_model_syncs_webapp_prefs(self, api_client, user_factory) -> None:
        user = user_factory()
        sync_mock = AsyncMock()
        with patch("routes.users._redis_read_user", new=AsyncMock(return_value=None)), \
             patch("routes.users.user_repo.get_user", new=AsyncMock(return_value=user)), \
             patch("routes.users._redis_write_user", new=AsyncMock()), \
             patch("routes.users._redis_sync_webapp_prefs", new=sync_mock), \
             patch("routes.users._db_update_user", new=AsyncMock()):
            resp = api_client.patch(f"/users/{user.id}", json={"current_model": "gpt-5"})
        assert resp.status_code == 200
        sync_mock.assert_awaited_once()

# Helper: _redis_sync_webapp_prefs

class TestRedisSyncWebappPrefs:

    @pytest.mark.asyncio
    async def test_skips_when_no_relevant_fields(self) -> None:
        from routes.users import _redis_sync_webapp_prefs
        mock_r = MagicMock()
        with patch("routes.users.get_redis", return_value=mock_r):
            # current_chat_mode is not in _BOT_TO_WEBAPP_PREFS
            await _redis_sync_webapp_prefs(1, {"current_chat_mode": "artist"})
        mock_r.exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_existing_key(self) -> None:
        from routes.users import _redis_sync_webapp_prefs
        mock_r = AsyncMock()
        mock_r.exists = AsyncMock(return_value=True)
        with patch("routes.users.get_redis", return_value=mock_r):
            await _redis_sync_webapp_prefs(42, {"language": "de", "theme": "dark"})
        mock_r.hset.assert_awaited_once()
        mock_r.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_key_absent(self) -> None:
        from routes.users import _redis_sync_webapp_prefs
        mock_r = AsyncMock()
        mock_r.exists = AsyncMock(return_value=False)
        with patch("routes.users.get_redis", return_value=mock_r):
            await _redis_sync_webapp_prefs(42, {"language": "en"})
        mock_r.hset.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_redis_exception_silently_ignored(self) -> None:
        from routes.users import _redis_sync_webapp_prefs
        mock_r = AsyncMock()
        mock_r.exists = AsyncMock(side_effect=Exception("redis error"))
        with patch("routes.users.get_redis", return_value=mock_r):
            await _redis_sync_webapp_prefs(99, {"language": "ru"})
        # не упало

# Helper: _redis_write_user / _redis_read_user

class TestRedisUserHelpers:

    @pytest.mark.asyncio
    async def test_redis_write_user_uses_pipeline(self, user_factory) -> None:
        from routes.users import _redis_write_user
        from schemas.user import UserRead
        user = user_factory()
        user_read = UserRead.from_orm_user(user)
        pipe = MagicMock()
        pipe.execute = AsyncMock()
        mock_r = MagicMock()
        mock_r.pipeline = MagicMock(return_value=pipe)
        with patch("routes.users.get_redis", return_value=mock_r):
            await _redis_write_user(user_read)
        pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_write_user_exception_logs_warning(self, user_factory) -> None:
        from routes.users import _redis_write_user
        from schemas.user import UserRead
        user = user_factory()
        user_read = UserRead.from_orm_user(user)
        mock_r = MagicMock()
        mock_r.pipeline = MagicMock(side_effect=Exception("boom"))
        with patch("routes.users.get_redis", return_value=mock_r):
            await _redis_write_user(user_read)  # не упало

    @pytest.mark.asyncio
    async def test_redis_read_user_returns_parsed_user(self, user_factory) -> None:
        from routes.users import _redis_read_user
        from schemas.user import UserRead
        user = user_factory()
        user_read = UserRead.from_orm_user(user)
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=user_read.model_dump_json().encode())
        with patch("routes.users.get_redis", return_value=mock_r):
            result = await _redis_read_user(user_read.id)
        assert result is not None
        assert result.id == user_read.id

    @pytest.mark.asyncio
    async def test_redis_read_user_returns_none_on_miss(self) -> None:
        from routes.users import _redis_read_user
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        with patch("routes.users.get_redis", return_value=mock_r):
            result = await _redis_read_user(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_read_user_exception_returns_none(self) -> None:
        from routes.users import _redis_read_user
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(side_effect=Exception("timeout"))
        with patch("routes.users.get_redis", return_value=mock_r):
            result = await _redis_read_user(999)
        assert result is None
