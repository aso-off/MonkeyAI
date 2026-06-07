"""
Тесты для api/src/core/redis.py.

Стратегия: загружаем реальный модуль через importlib, инжектируем
mock-объект settings с redis_url. aioredis.from_url мокируется там,
где нужно проверить инициализацию.
"""

import importlib.util
from pathlib import Path
from unittest import mock

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

_API_SRC = Path(__file__).resolve().parents[2] / "src"
_REDIS_FILE = _API_SRC / "core" / "redis.py"


# ── Фикстура загрузки ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def redis_module():
    """
    Загружаем реальный redis.py. После загрузки инжектируем mock settings
    с атрибутом redis_url, чтобы init_redis() не падал на AttributeError.
    """
    spec = importlib.util.spec_from_file_location(
        f"_real_api_redis_{fake.lexify('????')}", _REDIS_FILE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    mock_settings = mock.MagicMock()
    mock_settings.redis_url = f"redis://localhost:{fake.random_int(min=6379, max=6399)}"
    module.settings = mock_settings

    mock_logger = mock.MagicMock()
    module.logger = mock_logger

    return module


@pytest.fixture(autouse=True)
def reset_redis_state(redis_module):
    """Сбрасываем _redis и _redis_binary перед каждым тестом."""
    redis_module._redis = None
    redis_module._redis_binary = None
    yield
    redis_module._redis = None
    redis_module._redis_binary = None


# ── get_redis / get_redis_binary: ошибки без инициализации ────────────────────


class TestGetRedisNotInitialized:

    def test_get_redis_raises_runtime_error(self, redis_module) -> None:
        with pytest.raises(RuntimeError, match="not initialized"):
            redis_module.get_redis()

    def test_get_redis_binary_raises_runtime_error(self, redis_module) -> None:
        with pytest.raises(RuntimeError, match="not initialized"):
            redis_module.get_redis_binary()

    def test_get_redis_error_message(self, redis_module) -> None:
        try:
            redis_module.get_redis()
        except RuntimeError as exc:
            assert "Redis" in str(exc) or "pool" in str(exc).lower()

    def test_get_redis_binary_error_message(self, redis_module) -> None:
        try:
            redis_module.get_redis_binary()
        except RuntimeError as exc:
            assert "Redis" in str(exc) or "pool" in str(exc).lower()


# ── init_redis ────────────────────────────────────────────────────────────────


class TestInitRedis:

    @pytest.mark.asyncio
    async def test_init_creates_redis_pool(self, redis_module) -> None:
        mock_redis_inst = mock.MagicMock()
        mock_binary_inst = mock.MagicMock()
        call_count = [0]

        def _from_url(url, **kwargs):
            call_count[0] += 1
            return mock_binary_inst if kwargs.get("decode_responses") is False else mock_redis_inst

        with mock.patch("redis.asyncio.from_url", side_effect=_from_url):
            await redis_module.init_redis()

        assert call_count[0] == 2
        assert redis_module._redis is mock_redis_inst
        assert redis_module._redis_binary is mock_binary_inst

    @pytest.mark.asyncio
    async def test_init_then_get_redis_returns_instance(self, redis_module) -> None:
        mock_inst = mock.MagicMock()
        with mock.patch("redis.asyncio.from_url", return_value=mock_inst):
            await redis_module.init_redis()
        result = redis_module.get_redis()
        assert result is mock_inst

    @pytest.mark.asyncio
    async def test_init_then_get_redis_binary_returns_instance(self, redis_module) -> None:
        mock_binary = mock.MagicMock()

        def _from_url(url, **kwargs):
            return mock_binary if not kwargs.get("decode_responses", True) else mock.MagicMock()

        with mock.patch("redis.asyncio.from_url", side_effect=_from_url):
            await redis_module.init_redis()
        result = redis_module.get_redis_binary()
        assert result is mock_binary

    @pytest.mark.asyncio
    async def test_init_uses_settings_redis_url(self, redis_module) -> None:
        redis_url = f"redis://:{fake.sha256()[:12]}@localhost:6379"
        redis_module.settings.redis_url = redis_url

        urls_called = []
        with mock.patch("redis.asyncio.from_url",
                        side_effect=lambda url, **kw: urls_called.append(url) or mock.MagicMock()):
            await redis_module.init_redis()

        assert all(url == redis_url for url in urls_called)

    @pytest.mark.asyncio
    async def test_init_logs_info(self, redis_module) -> None:
        with mock.patch("redis.asyncio.from_url", return_value=mock.MagicMock()):
            await redis_module.init_redis()
        redis_module.logger.info.assert_called()


# ── close_redis ───────────────────────────────────────────────────────────────


class TestCloseRedis:

    @pytest.mark.asyncio
    async def test_close_when_not_initialized_is_safe(self, redis_module) -> None:
        """close_redis() при _redis=None не должен падать."""
        await redis_module.close_redis()  # не должен поднимать исключение

    @pytest.mark.asyncio
    async def test_close_calls_aclose_on_both_pools(self, redis_module) -> None:
        mock_r = mock.AsyncMock()
        mock_rb = mock.AsyncMock()
        redis_module._redis = mock_r
        redis_module._redis_binary = mock_rb

        await redis_module.close_redis()

        mock_r.aclose.assert_awaited_once()
        mock_rb.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_sets_to_none(self, redis_module) -> None:
        redis_module._redis = mock.AsyncMock()
        redis_module._redis_binary = mock.AsyncMock()

        await redis_module.close_redis()

        assert redis_module._redis is None
        assert redis_module._redis_binary is None

    @pytest.mark.asyncio
    async def test_close_logs_info(self, redis_module) -> None:
        redis_module._redis = mock.AsyncMock()
        redis_module._redis_binary = mock.AsyncMock()

        await redis_module.close_redis()
        redis_module.logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_init_close_cycle(self, redis_module) -> None:
        """Полный цикл: init → get → close → get raises."""
        with mock.patch("redis.asyncio.from_url", return_value=mock.AsyncMock()):
            await redis_module.init_redis()

        assert redis_module.get_redis() is not None

        await redis_module.close_redis()

        with pytest.raises(RuntimeError):
            redis_module.get_redis()
