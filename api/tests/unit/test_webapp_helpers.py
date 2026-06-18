"""
Тесты для helpers в api/src/routes/webapp.py.

Покрываем недостающие ветки:
- _prefs_key()                   — формат ключа
- _redis_write_prefs()           — hset + expire
- _redis_read_prefs()            — hit, exception > {}
- _db_write_prefs()              — success, exception
- _redis_invalidate_user_cache() — success, exception (pass)
- _resolve_mini_app_dialog_id()  — с body_dialog_id, без
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

class TestPrefsKey:

    def test_format_contains_user_id(self) -> None:
        from routes.webapp import _prefs_key
        uid = fake.random_int(min=100_000, max=999_999_999)
        assert str(uid) in _prefs_key(uid)
        assert _prefs_key(uid).startswith("webapp:user_prefs:")

class TestRedisWritePrefs:

    @pytest.mark.asyncio
    async def test_calls_hset_and_expire(self) -> None:
        from routes.webapp import _redis_write_prefs
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_r = AsyncMock()
        with patch("routes.webapp.get_redis", return_value=mock_r):
            await _redis_write_prefs(uid, {"language": "ru", "theme": "dark"})
        mock_r.hset.assert_awaited_once()
        mock_r.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_faker_various_prefs(self) -> None:
        from routes.webapp import _redis_write_prefs
        for lang in ["ru", "en", "de"]:
            uid = fake.random_int(min=100_000, max=999_999_999)
            mock_r = AsyncMock()
            with patch("routes.webapp.get_redis", return_value=mock_r):
                await _redis_write_prefs(uid, {"language": lang})
            mock_r.hset.assert_awaited_once()

class TestRedisReadPrefs:

    @pytest.mark.asyncio
    async def test_returns_dict_on_hit(self) -> None:
        from routes.webapp import _redis_read_prefs
        uid = fake.random_int(min=100_000, max=999_999_999)
        prefs = {b"language": b"fr", b"theme": b"light"}
        mock_r = AsyncMock()
        mock_r.hgetall = AsyncMock(return_value=prefs)
        with patch("routes.webapp.get_redis", return_value=mock_r):
            result = await _redis_read_prefs(uid)
        assert result == prefs

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_exception(self) -> None:
        from routes.webapp import _redis_read_prefs
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_r = AsyncMock()
        mock_r.hgetall = AsyncMock(side_effect=Exception("timeout"))
        with patch("routes.webapp.get_redis", return_value=mock_r):
            result = await _redis_read_prefs(uid)
        assert result == {}

class TestDbWritePrefs:

    @pytest.mark.asyncio
    async def test_calls_update_user(self) -> None:
        from routes.webapp import _db_write_prefs
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with patch("routes.webapp.Session", return_value=mock_session), \
             patch("routes.webapp.user_repo.update_user", new=AsyncMock()) as mock_upd:
            await _db_write_prefs(uid, {"language": "de"})
        mock_upd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_logged_not_raised(self) -> None:
        from routes.webapp import _db_write_prefs
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(side_effect=Exception("db down"))
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with patch("routes.webapp.Session", return_value=mock_session):
            await _db_write_prefs(uid, {"theme": "dark"})
        # не упало

class TestRedisInvalidateUserCache:

    @pytest.mark.asyncio
    async def test_deletes_both_keys(self) -> None:
        from routes.webapp import _redis_invalidate_user_cache
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_r = AsyncMock()
        with patch("routes.webapp.get_redis", return_value=mock_r):
            await _redis_invalidate_user_cache(uid)
        mock_r.delete.assert_awaited_once()
        call_args = mock_r.delete.call_args[0]
        assert f"user:{uid}" in call_args
        assert f"user_full:{uid}" in call_args

    @pytest.mark.asyncio
    async def test_exception_silently_ignored(self) -> None:
        from routes.webapp import _redis_invalidate_user_cache
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_r = AsyncMock()
        mock_r.delete = AsyncMock(side_effect=Exception("redis down"))
        with patch("routes.webapp.get_redis", return_value=mock_r):
            await _redis_invalidate_user_cache(uid)
        # не упало

class TestResolveMiniAppDialogId:

    @pytest.mark.asyncio
    async def test_returns_body_dialog_id_when_provided(self) -> None:
        from routes.webapp import _resolve_mini_app_dialog_id
        did = fake.uuid4()
        session = MagicMock()
        result = await _resolve_mini_app_dialog_id(session, 123, body_dialog_id=did)
        assert result == did

    @pytest.mark.asyncio
    async def test_ensures_dialog_when_no_body_id(self) -> None:
        from routes.webapp import _resolve_mini_app_dialog_id
        uid = fake.random_int(min=100_000, max=999_999_999)
        new_did = fake.uuid4()
        session = MagicMock()
        with patch("routes.webapp.dialog_repo.ensure_active_mini_app_dialog",
                   new=AsyncMock(return_value=new_did)):
            result = await _resolve_mini_app_dialog_id(session, uid, body_dialog_id=None)
        assert result == new_did
