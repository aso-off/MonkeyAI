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

os.environ.setdefault("MONKEY_CONFIGS_DIR", str(_ROOT / "configs"))
os.environ.setdefault("MONKEY_LOG_DIR", tempfile.mkdtemp(prefix="sec-logs-"))
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "monkey_test")
os.environ.setdefault("POSTGRES_USER", "monkey_test")
os.environ.setdefault("POSTGRES_PASSWORD", "monkey_test")
os.environ.setdefault("OPENAI_API_KEY", "sk-sec")
os.environ.setdefault("TELEGRAM_TOKEN", "123456:sec-token")
os.environ.setdefault("API_SERVICE_TOKEN", "sec-service-token")

for _p in (str(_API), str(_API_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SERVICE_TOKEN = os.environ["API_SERVICE_TOKEN"]
_BOT_TOKEN = os.environ["TELEGRAM_TOKEN"]
_TABLES = "users, user_states, user_statistics, dialogs, reactions, generated_images"


def _db_reachable() -> bool:
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
    skip = pytest.mark.skip(reason="security: тестовый Postgres недоступен")
    for item in items:
        if "security" in item.keywords:
            item.add_marker(skip)


def _sign(params: dict) -> str:
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", _BOT_TOKEN.encode(), hashlib.sha256).digest()
    params = {**params, "hash": hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()}
    return "&".join(f"{k}={v}" for k, v in params.items())


@pytest.fixture
def init_data():
    def _user(user_id: int) -> str:
        return json.dumps({"id": user_id, "first_name": "Sec", "username": "sec"}, separators=(",", ":"))

    class _Factory:
        @staticmethod
        def valid(user_id: int = 555, **extra) -> str:
            return _sign({"auth_date": str(int(time.time())), "user": _user(user_id), **extra})

        @staticmethod
        def expired(user_id: int = 555) -> str:
            old = str(int(time.time()) - 86_400)
            return _sign({"auth_date": old, "user": _user(user_id)})

        @staticmethod
        def bad_hash(user_id: int = 555) -> str:
            return _Factory.valid(user_id)[:-8] + "deadbeef"

        @staticmethod
        def no_hash(user_id: int = 555) -> str:
            params = {"auth_date": str(int(time.time())), "user": _user(user_id)}
            return "&".join(f"{k}={v}" for k, v in params.items())

        @staticmethod
        def tampered(user_id: int = 555, other_id: int = 999) -> str:
            # подпись для user_id, но user-поле подменено -> hash не сойдётся
            return _Factory.valid(user_id).replace(f'"id":{user_id}', f'"id":{other_id}')

    return _Factory


@pytest_asyncio.fixture
async def app(monkeypatch):
    import core.redis as core_redis
    import fakeredis.aioredis

    fake_server = fakeredis.FakeServer()

    def _fake_from_url(_url, **kwargs):
        return fakeredis.aioredis.FakeRedis(
            server=fake_server, decode_responses=kwargs.get("decode_responses", False)
        )

    monkeypatch.setattr(core_redis.aioredis, "from_url", _fake_from_url)

    import routes.chat as chat_routes
    import routes.webapp as webapp_routes

    class _FakeChatGPT:
        def __init__(self, model: str = "gpt-5.4-nano") -> None:
            self.model = model

        async def send_message(self, message, dialog_messages=None, chat_mode="assistant"):
            return "sec answer", (11, 7), 0

    async def _no_moderation(text=None, image_buffer=None):
        return False, [], {}

    monkeypatch.setattr(chat_routes, "ChatGPT", _FakeChatGPT)
    monkeypatch.setattr(chat_routes, "moderate_content", _no_moderation)
    monkeypatch.setattr(webapp_routes, "ChatGPT", _FakeChatGPT)
    monkeypatch.setattr(webapp_routes, "moderate_content", _no_moderation)

    from asgi_lifespan import LifespanManager
    from main import create_app

    application = create_app()
    async with LifespanManager(application):
        from db.db import engine
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
        yield application


@pytest_asyncio.fixture
async def client(app):
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://sec") as c:
        yield c


@pytest_asyncio.fixture
async def svc_client(app):
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://sec",
        headers={"Authorization": f"Bearer {_SERVICE_TOKEN}"},
    ) as c:
        yield c


@pytest.fixture
def seed():
    async def _seed(user_id: int, *, whitelisted: bool = True):
        from db.db import Session
        from db.models.user import User, UserState, UserStatistics
        from services import whitelist

        async with Session() as s:
            user = User(id=user_id, chat_id=user_id, first_name="Sec", is_whitelisted=whitelisted)
            user.state = UserState(user_id=user_id)
            user.statistics = UserStatistics(user_id=user_id)
            s.add(user)
            await s.commit()

        # whitelist-гейт читает Redis-сет раньше БД
        if whitelisted:
            await whitelist.add(user_id)
        return user_id

    return _seed
