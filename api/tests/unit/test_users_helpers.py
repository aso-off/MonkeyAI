"""
Тесты для helpers в api/src/routes/users.py.

Покрываем недостающие ветки:
- _redis_write_stats()  — success, exception (pass)
- _redis_read_stats()   — cache hit, miss, raw=None, exception
- _db_update_user()     — success, exception
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

class TestRedisWriteStats:

    @pytest.mark.asyncio
    async def test_writes_stats_to_redis(self) -> None:
        from routes.users import _redis_write_stats
        mock_r = AsyncMock()
        with patch("routes.users.get_redis", return_value=mock_r):
            await _redis_write_stats({"all_users_count": 10, "active_users_count": 3})
        mock_r.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_silently_ignored(self) -> None:
        from routes.users import _redis_write_stats
        mock_r = AsyncMock()
        mock_r.set = AsyncMock(side_effect=Exception("redis error"))
        with patch("routes.users.get_redis", return_value=mock_r):
            await _redis_write_stats({"all_users_count": 0})
        # не упало

class TestRedisReadStats:

    @pytest.mark.asyncio
    async def test_returns_parsed_dict_on_hit(self) -> None:
        from routes.users import _redis_read_stats
        data = {"all_users_count": 42, "active_users_count": 7}
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=json.dumps(data).encode())
        with patch("routes.users.get_redis", return_value=mock_r):
            result = await _redis_read_stats()
        assert result == data

    @pytest.mark.asyncio
    async def test_returns_none_on_miss(self) -> None:
        from routes.users import _redis_read_stats
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        with patch("routes.users.get_redis", return_value=mock_r):
            result = await _redis_read_stats()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        from routes.users import _redis_read_stats
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(side_effect=Exception("timeout"))
        with patch("routes.users.get_redis", return_value=mock_r):
            result = await _redis_read_stats()
        assert result is None

    @pytest.mark.asyncio
    async def test_faker_various_counts(self) -> None:
        from routes.users import _redis_read_stats
        for _ in range(3):
            count = fake.random_int(min=0, max=50000)
            data = {"all_users_count": count, "active_users_count": count // 2}
            mock_r = AsyncMock()
            mock_r.get = AsyncMock(return_value=json.dumps(data).encode())
            with patch("routes.users.get_redis", return_value=mock_r):
                result = await _redis_read_stats()
            assert result is not None
            assert result["all_users_count"] == count

class TestDbUpdateUser:

    @pytest.mark.asyncio
    async def test_calls_user_repo_update(self) -> None:
        from routes.users import _db_update_user
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with patch("routes.users.Session", return_value=mock_session), \
             patch("routes.users.user_repo.update_user", new=AsyncMock()) as mock_update:
            await _db_update_user(uid, language="en")
        mock_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_logged_not_raised(self) -> None:
        from routes.users import _db_update_user
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(side_effect=Exception("db down"))
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with patch("routes.users.Session", return_value=mock_session):
            await _db_update_user(uid, language="de")