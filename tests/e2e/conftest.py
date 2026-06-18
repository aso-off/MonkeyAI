import asyncio
import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest
import pytest_asyncio

_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"
_API_SRC = _API / "src"

# env должен быть проставлен ДО импорта приложения (core.config/logger читают его на импорте)
os.environ.setdefault("MONKEY_CONFIGS_DIR", str(_ROOT / "configs"))
os.environ.setdefault("MONKEY_LOG_DIR", tempfile.mkdtemp(prefix="e2e-logs-"))
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "monkey_test")
os.environ.setdefault("POSTGRES_USER", "monkey_test")
os.environ.setdefault("POSTGRES_PASSWORD", "monkey_test")
os.environ.setdefault("OPENAI_API_KEY", "sk-e2e")
os.environ.setdefault("TELEGRAM_TOKEN", "123456:e2e-token")
os.environ.setdefault("API_SERVICE_TOKEN", "e2e-service-token")

for _p in (str(_API), str(_API_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SERVICE_TOKEN = os.environ["API_SERVICE_TOKEN"]
_BOT_TOKEN = os.environ["TELEGRAM_TOKEN"]
_TABLES = "users, user_states, user_statistics, dialogs, reactions, generated_images"


def _db_reachable() -> bool:
    # реальное подключение тестовыми кредами к тестовой БД - TCP-проверки мало
    import asyncpg

    async def _check() -> bool:
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(
                    host=os.environ["POSTGRES_HOST"],
                    port=int(os.environ["POSTGRES_PORT"]),
                    user=os.environ["POSTGRES_USER"],
                    password=os.environ["POSTGRES_PASSWORD"],
                    database=os.environ["POSTGRES_DB"],
                ),
                timeout=3.0,
            )
            await conn.close()
            return True
        except Exception:
            return False

    try:
        return asyncio.run(_check())
    except Exception:
        return False


_DB_OK = _db_reachable()


def pytest_collection_modifyitems(config, items):
    if _DB_OK:
        return
    skip = pytest.mark.skip(reason="e2e: тестовый Postgres недоступен")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


async def _truncate_all() -> None:
    from db.db import engine
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def app(monkeypatch):
    """Реальный API: lifespan + миграции на тестовой БД, Redis → fakeredis, OpenAI замокан, чистые таблицы."""
    import core.redis as core_redis
    import fakeredis.aioredis

    fake_server = fakeredis.FakeServer()

    def _fake_from_url(_url, **kwargs):
        return fakeredis.aioredis.FakeRedis(
            server=fake_server, decode_responses=kwargs.get("decode_responses", False)
        )

    monkeypatch.setattr(core_redis.aioredis, "from_url", _fake_from_url)

    import routes.chat as chat_routes

    class _FakeChatGPT:
        def __init__(self, model: str = "gpt-5.4-nano") -> None:
            self.model = model

        async def send_message(self, message, dialog_messages=None, chat_mode="assistant"):
            return "E2E canned answer", (11, 7), 0

        async def send_vision_message(
            self, message, dialog_messages=None, chat_mode="assistant", image_buffer=None
        ):
            return "E2E vision answer", (11, 7), 0

    async def _no_moderation(text=None, image_buffer=None):
        return False, [], {}

    monkeypatch.setattr(chat_routes, "ChatGPT", _FakeChatGPT)
    monkeypatch.setattr(chat_routes, "moderate_content", _no_moderation)

    from asgi_lifespan import LifespanManager
    from main import create_app

    application = create_app()
    async with LifespanManager(application):
        await _truncate_all()
        yield application


@pytest_asyncio.fixture
async def client(app):
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://e2e",
        headers={"Authorization": f"Bearer {_SERVICE_TOKEN}"},
    ) as http_client:
        yield http_client


@pytest.fixture
def seed():
    async def _seed(user_id=1001, dialog_id="11111111-1111-1111-1111-111111111111", *, whitelisted=True):
        from db.db import Session
        from db.models.user import Dialog, User, UserState, UserStatistics

        async with Session() as s:
            user = User(id=user_id, chat_id=user_id, first_name="E2E", is_whitelisted=whitelisted)
            user.state = UserState(user_id=user_id)
            user.statistics = UserStatistics(user_id=user_id)
            s.add(user)
            await s.flush()
            s.add(Dialog(id=dialog_id, user_id=user_id, chat_mode="assistant", model="gpt-5.4-nano", messages=[]))
            await s.commit()
        return user_id, dialog_id

    return _seed


@pytest.fixture
def make_init_data():
    def _make(user_id=1001, **extra):
        user = json.dumps({"id": user_id, "first_name": "E2E", "username": "e2e"}, separators=(",", ":"))
        params = {"auth_date": str(int(time.time())), "user": user, **extra}
        data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
        secret = hmac.new(b"WebAppData", _BOT_TOKEN.encode(), hashlib.sha256).digest()
        params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        return "&".join(f"{k}={v}" for k, v in params.items())

    return _make
