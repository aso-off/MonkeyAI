"""Юнит-тесты для api/src/services/whitelist.py.

Redis полностью заменён AsyncMock - реальный сервер не нужен.
"""

from unittest.mock import patch

import pytest
from services.whitelist import ALLOWED_KEY, add, is_allowed, rebuild, remove


@pytest.fixture
def redis(mock_redis):
    """Патчим get_redis в пространстве имён whitelist, возвращаем AsyncMock."""
    with patch("services.whitelist.get_redis", return_value=mock_redis):
        yield mock_redis

# is_allowed

class TestIsAllowed:
    @pytest.mark.unit
    async def test_user_in_set_returns_true(self, redis) -> None:
        redis.sismember.return_value = True
        assert await is_allowed(123) is True
        redis.sismember.assert_awaited_once_with(ALLOWED_KEY, 123)

    @pytest.mark.unit
    async def test_user_not_in_set_but_exists_returns_false(self, redis) -> None:
        redis.sismember.return_value = False
        redis.exists.return_value = 1  # сет существует
        assert await is_allowed(456) is False

    @pytest.mark.unit
    async def test_set_not_built_returns_none(self, redis) -> None:
        redis.sismember.return_value = False
        redis.exists.return_value = 0  # сет ещё не создан
        assert await is_allowed(789) is None

    @pytest.mark.unit
    async def test_redis_connection_error_returns_none(self, redis) -> None:
        redis.sismember.side_effect = ConnectionError("Redis unavailable")
        assert await is_allowed(999) is None

    @pytest.mark.unit
    async def test_generic_exception_returns_none(self, redis) -> None:
        redis.sismember.side_effect = RuntimeError("unexpected")
        assert await is_allowed(1) is None

    @pytest.mark.unit
    async def test_faker_multiple_user_ids(self, redis, fake) -> None:
        redis.sismember.return_value = True
        for _ in range(5):
            uid = fake.random_int(min=100_000, max=999_999_999)
            result = await is_allowed(uid)
            assert result is True

    @pytest.mark.unit
    @pytest.mark.parametrize("exists_return,expected", [
        (1, False),   # сет есть, пользователя нет > False
        (0, None),    # сет не построен > None
    ])
    async def test_exists_variants(self, redis, exists_return: int, expected) -> None:
        redis.sismember.return_value = False
        redis.exists.return_value = exists_return
        assert await is_allowed(42) is expected

# add

class TestAdd:
    @pytest.mark.unit
    async def test_calls_sadd_with_correct_args(self, redis) -> None:
        await add(111)
        redis.sadd.assert_awaited_once_with(ALLOWED_KEY, 111)

    @pytest.mark.unit
    async def test_faker_user_id(self, redis, fake) -> None:
        uid = fake.random_int(min=1, max=999_999_999)
        await add(uid)
        redis.sadd.assert_awaited_once_with(ALLOWED_KEY, uid)

    @pytest.mark.unit
    async def test_does_not_call_srem(self, redis) -> None:
        await add(42)
        redis.srem.assert_not_awaited()

# remove

class TestRemove:
    @pytest.mark.unit
    async def test_calls_srem_with_correct_args(self, redis) -> None:
        await remove(222)
        redis.srem.assert_awaited_once_with(ALLOWED_KEY, 222)

    @pytest.mark.unit
    async def test_does_not_call_sadd(self, redis) -> None:
        await remove(22)
        redis.sadd.assert_not_awaited()

    @pytest.mark.unit
    async def test_faker_user_id(self, redis, fake) -> None:
        uid = fake.random_int(min=1, max=999_999_999)
        await remove(uid)
        redis.srem.assert_awaited_once_with(ALLOWED_KEY, uid)

# rebuild

class TestRebuild:
    @pytest.mark.unit
    async def test_empty_set_only_deletes(self, redis) -> None:
        await rebuild(set())
        redis.delete.assert_awaited_once_with(ALLOWED_KEY)
        redis.sadd.assert_not_awaited()

    @pytest.mark.unit
    async def test_nonempty_deletes_then_adds(self, redis) -> None:
        ids = {1, 2, 3}
        await rebuild(ids)
        redis.delete.assert_awaited_once_with(ALLOWED_KEY)
        redis.sadd.assert_awaited_once()
        # Проверяем ключ и состав аргументов
        call_args = redis.sadd.call_args[0]
        assert call_args[0] == ALLOWED_KEY
        assert set(call_args[1:]) == ids

    @pytest.mark.unit
    async def test_single_id(self, redis) -> None:
        await rebuild({999})
        redis.sadd.assert_awaited_once_with(ALLOWED_KEY, 999)

    @pytest.mark.unit
    async def test_faker_large_set(self, redis, fake) -> None:
        ids = {fake.random_int(min=1, max=999_999) for _ in range(50)}
        await rebuild(ids)
        redis.delete.assert_awaited_once()
        redis.sadd.assert_awaited_once()

    @pytest.mark.unit
    async def test_delete_called_before_sadd(self, redis) -> None:
        call_order: list[str] = []

        async def _track_delete(*a):
            call_order.append("delete")
            return 1

        async def _track_sadd(*a):
            call_order.append("sadd")
            return 1

        redis.delete.side_effect = _track_delete
        redis.sadd.side_effect = _track_sadd
        await rebuild({1, 2})
        assert call_order[0] == "delete"
