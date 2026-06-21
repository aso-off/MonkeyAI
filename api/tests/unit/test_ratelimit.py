"""Юнит-тесты лимитера: fixed-window от первого сообщения, tier-aware, admin-bypass."""
from typing import cast
from unittest.mock import AsyncMock, patch

import core.ratelimit as rl
import pytest
from fastapi import HTTPException


class TestLimitFor:
    @pytest.mark.unit
    def test_msg_tiers(self) -> None:
        assert rl.limit_for("msg", False) == 15
        assert rl.limit_for("msg", True) == 30

    @pytest.mark.unit
    def test_image_tiers(self) -> None:
        assert rl.limit_for("image_gen", False) == 5
        assert rl.limit_for("image_gen", True) == 5


class TestConsume:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_under_limit_allows(self) -> None:
        r = AsyncMock()
        r.eval.return_value = [0, 3600]  # not limited, ttl
        with patch("core.ratelimit.get_redis", return_value=r):
            assert await rl.consume_rate_limit("msg", 1) is None
        r.eval.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_over_limit_returns_retry_after(self) -> None:
        r = AsyncMock()
        r.eval.return_value = [1, 1234]  # limited, ttl
        with patch("core.ratelimit.get_redis", return_value=r):
            retry = await rl.consume_rate_limit("msg", 1)
        assert retry == 1234

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_passes_premium_limit_to_script(self) -> None:
        r = AsyncMock()
        r.eval.return_value = [0, 3600]
        with patch("core.ratelimit.get_redis", return_value=r):
            await rl.consume_rate_limit("msg", 1, is_premium=True)
        # premium msg limit (30) передан скрипту как ARGV[1]
        assert 30 in r.eval.call_args[0]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_admin_bypass_no_redis_call(self) -> None:
        r = AsyncMock()
        with patch("core.ratelimit.get_redis", return_value=r):
            assert await rl.consume_rate_limit("msg", 1, is_admin=True) is None
        r.eval.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self) -> None:
        with patch("core.ratelimit.get_redis", side_effect=RuntimeError("down")):
            assert await rl.consume_rate_limit("msg", 1) is None


class TestPeek:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_peek_over_limit_does_not_consume(self) -> None:
        r = AsyncMock()
        r.get.return_value = "15"
        r.ttl.return_value = 999
        with patch("core.ratelimit.get_redis", return_value=r):
            assert await rl.peek_rate_limit("msg", 1) == 999
        r.incr.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_peek_under_limit_returns_none(self) -> None:
        r = AsyncMock()
        r.get.return_value = "3"
        with patch("core.ratelimit.get_redis", return_value=r):
            assert await rl.peek_rate_limit("msg", 1) is None


class TestReadUsage:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_percent_and_reset(self) -> None:
        r = AsyncMock()
        r.get.return_value = "9"
        r.ttl.return_value = 1800
        with patch("core.ratelimit.get_redis", return_value=r):
            usage = await rl.read_usage("msg", 1)
        assert usage == {"used": 9, "limit": 15, "percent": 60, "reset_in": 1800}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_usage(self) -> None:
        r = AsyncMock()
        r.get.return_value = None
        with patch("core.ratelimit.get_redis", return_value=r):
            usage = await rl.read_usage("image_gen", 1, is_premium=True)
        assert usage == {"used": 0, "limit": 5, "percent": 0, "reset_in": 0}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_admin_unlimited(self) -> None:
        r = AsyncMock()
        with patch("core.ratelimit.get_redis", return_value=r):
            usage = await rl.read_usage("msg", 1, is_admin=True)
        assert usage == {"used": 0, "limit": 0, "percent": 0, "reset_in": 0}
        r.get.assert_not_called()


class TestEnforce:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_429_with_structured_detail(self) -> None:
        r = AsyncMock()
        r.eval.return_value = [1, 100]  # limited, ttl
        with patch("core.ratelimit.get_redis", return_value=r):
            with pytest.raises(HTTPException) as exc:
                await rl.enforce_rate_limit("msg", 1)
        assert exc.value.status_code == 429
        detail = cast(dict, exc.value.detail)
        assert detail["kind"] == "msg"
        assert detail["limit"] == 15
        assert detail["retry_after"] == 100

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_peek_mode_does_not_consume(self) -> None:
        r = AsyncMock()
        r.get.return_value = "2"
        with patch("core.ratelimit.get_redis", return_value=r):
            await rl.enforce_rate_limit("msg", 1, consume=False)
        r.eval.assert_not_called()


class _FakeRedis:
    """Имитация Redis с серверной семантикой Lua-скрипта (INCR + TTL + откат)."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def eval(self, script, numkeys, *args):
        key = str(args[0])
        limit = int(args[1])
        window = int(args[2])
        c = self.counts.get(key, 0) + 1
        self.counts[key] = c
        ttl = self.ttls.get(key, -1)
        if ttl < 0:
            self.ttls[key] = window
            ttl = window
        if c > limit:
            self.counts[key] = c - 1
            return [1, ttl]
        return [0, ttl]

    async def get(self, key):
        c = self.counts.get(str(key))
        return None if c is None else str(c)

    async def ttl(self, key):
        return self.ttls.get(str(key), -2)


class TestReachingLimits:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_default_messages_15_then_blocked(self) -> None:
        r = _FakeRedis()
        with patch("core.ratelimit.get_redis", return_value=r):
            for _ in range(15):  # текст / анализ / голос - всё счётчик msg
                assert await rl.consume_rate_limit("msg", 1) is None
            assert await rl.consume_rate_limit("msg", 1) is not None  # 16-е - лимит

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_premium_messages_30_then_blocked(self) -> None:
        r = _FakeRedis()
        with patch("core.ratelimit.get_redis", return_value=r):
            for _ in range(30):
                assert await rl.consume_rate_limit("msg", 1, is_premium=True) is None
            assert await rl.consume_rate_limit("msg", 1, is_premium=True) is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_image_gen_5_then_blocked(self) -> None:
        r = _FakeRedis()
        with patch("core.ratelimit.get_redis", return_value=r):
            for _ in range(5):
                assert await rl.consume_rate_limit("image_gen", 1) is None
            assert await rl.consume_rate_limit("image_gen", 1) is not None  # 6-я - лимит

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_msg_and_image_counters_independent(self) -> None:
        r = _FakeRedis()
        with patch("core.ratelimit.get_redis", return_value=r):
            for _ in range(15):
                await rl.consume_rate_limit("msg", 1)
            assert await rl.consume_rate_limit("msg", 1) is not None  # msg исчерпан
            assert await rl.consume_rate_limit("image_gen", 1) is None  # картинки свободны

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_over_limit_count_does_not_run_away(self) -> None:
        r = _FakeRedis()
        with patch("core.ratelimit.get_redis", return_value=r):
            for _ in range(20):
                await rl.consume_rate_limit("msg", 1)
            usage = await rl.read_usage("msg", 1)
        assert usage["used"] == 15  # счётчик стоит на лимите, не убегает
        assert usage["percent"] == 100

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_admin_never_blocked(self) -> None:
        r = _FakeRedis()
        with patch("core.ratelimit.get_redis", return_value=r):
            for _ in range(50):
                assert await rl.consume_rate_limit("msg", 1, is_admin=True) is None
