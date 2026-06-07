"""
Общий conftest для api/tests/.

Порядок важен: module-level stubs прописываются в sys.modules ДО того,
как pytest начинает коллекцию тестов, чтобы любой импорт api-модуля
(core.config, core.redis, core.logger) не упал на отсутствующих .env / БД.
"""

import logging
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker

# ── sys.path ──────────────────────────────────────────────────────────────────

_API_DIR = Path(__file__).resolve().parents[1]
_API_SRC = _API_DIR / "src"
for _p in (str(_API_DIR), str(_API_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_fake_settings() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        database_url="postgresql+asyncpg://u:p@localhost:5432/testdb",
        telegram_token=types.SimpleNamespace(get_secret_value=lambda: "1234567890:test_token"),
        openai_api_key=types.SimpleNamespace(get_secret_value=lambda: "sk-test-key"),
        chat_modes={
            "assistant": {"prompt_start": "You are a helpful assistant."},
            "code_assistant": {"prompt_start": "You are a coding expert."},
        },
        models={},
        admin_ids=[123456789],
        allowed_user_ids=[],
        enable_content_moderation=True,
        moderation_thresholds={"harassment": 0.7, "violence": 0.8},
        openai_api_base=None,
        return_n_generated_images=1,
        image_size="1024x1024",
        image_quality="medium",
        whitelist_mode=True,
        dialog_context_limit=20,
        message_max_length=4096,
    )


# ── Module-level stubs (выполняются при импорте conftest, до коллекции тестов) ─

_stub_logger = types.ModuleType("core.logger")
_stub_logger.logger = logging.getLogger("api_test")
sys.modules.setdefault("core.logger", _stub_logger)

_stub_config = types.ModuleType("core.config")
_stub_config.settings = _make_fake_settings()
sys.modules.setdefault("core.config", _stub_config)


class _SyncFakeRedis:
    async def ping(self): return True
    async def get(self, *a, **kw): return None
    async def set(self, *a, **kw): return True
    async def delete(self, *a): return 0
    async def exists(self, *a): return 0
    async def sadd(self, *a): return 0
    async def srem(self, *a): return 0
    async def sismember(self, *a): return False
    async def hset(self, *a, **kw): return 0
    async def expire(self, *a): return True
    def pipeline(self): return self
    async def execute(self): return []


_stub_redis_instance = _SyncFakeRedis()
_stub_redis = types.ModuleType("core.redis")
_stub_redis.init_redis = lambda: None
_stub_redis.close_redis = lambda: None
_stub_redis.get_redis = lambda: _stub_redis_instance
_stub_redis.get_redis_binary = lambda: _stub_redis_instance
sys.modules.setdefault("core.redis", _stub_redis)

# core.security — нужен routes.health и другим роутерам при импорте
_stub_security = types.ModuleType("core.security")


async def _noop_verify_service_token() -> None:
    """Noop: без параметров — FastAPI не пытается распарсить *args из запроса."""
    return None


async def _noop_verify_webapp_init_data() -> dict:
    return {}


_stub_security.verify_service_token = _noop_verify_service_token
_stub_security.verify_webapp_init_data = _noop_verify_webapp_init_data
_stub_security._verify_init_data = None  # unit tests загружают реальный модуль через importlib
sys.modules.setdefault("core.security", _stub_security)

# ── Fixtures ──────────────────────────────────────────────────────────────────

Faker.seed(42)


@pytest.fixture(scope="session")
def fake() -> Faker:
    """Faker с ru_RU + en_US локалями. Session-scoped — создаётся один раз."""
    return Faker(["ru_RU", "en_US"])


@pytest.fixture
def fake_settings() -> types.SimpleNamespace:
    """Свежий экземпляр fake settings для каждого теста."""
    return _make_fake_settings()


@pytest.fixture
def mock_redis() -> AsyncMock:
    """
    AsyncMock, имитирующий redis.Redis.
    Тест-кейс может переопределить return_value любого метода:
        mock_redis.get.return_value = b'{"id": 1}'
    """
    r = AsyncMock()
    r.ping.return_value = True
    r.get.return_value = None
    r.set.return_value = True
    r.delete.return_value = 1
    r.exists.return_value = 0
    r.sadd.return_value = 1
    r.srem.return_value = 1
    r.sismember.return_value = False
    r.hset.return_value = 0
    r.expire.return_value = True

    pipe = AsyncMock()
    pipe.set.return_value = pipe
    pipe.delete.return_value = pipe
    pipe.execute.return_value = [True, 1]
    r.pipeline.return_value = pipe

    return r


@pytest.fixture
def mock_openai_client() -> MagicMock:
    """MagicMock для AsyncOpenAI."""
    client = MagicMock()
    client.moderations.create = AsyncMock()
    client.chat.completions.create = AsyncMock()
    client.images.generate = AsyncMock()
    return client
