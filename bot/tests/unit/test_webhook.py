"""
Тесты для:
- bot/src/webhook/router.py  - POST /webhook endpoint
- bot/src/webhook/app.py     - create_app(), lifespan, /health, /metrics, /webhook_info

Стратегия: загружаем реальные модули через importlib, мокируя bot/dp.
TestClient для HTTP-тестов.

Faker: user IDs, update data.
"""

import importlib.util
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Предзагрузка реальных модулей: внутри фикстур router/app грузятся под
# patch.dict(sys.modules), который при выходе удаляет ключи, добавленные во
# время блока. Если fastapi/aiogram импортируются впервые там - они стираются,
# и тело теста получает второй экземпляр fastapi (isinstance ломается, 404).
import aiogram  # noqa: F401, E402
import fastapi  # noqa: F401, E402
import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

_BOT_SRC = Path(__file__).resolve().parents[2] / "src"
_ROUTER_FILE = _BOT_SRC / "webhook" / "router.py"
_APP_FILE = _BOT_SRC / "webhook" / "app.py"

# Helpers

def _fake_update_data() -> dict:
    uid = fake.random_int(min=100_000, max=999_999_999)
    return {
        "update_id": fake.random_int(min=1_000_000, max=9_999_999),
        "message": {
            "message_id": fake.random_int(min=1, max=9_999),
            "from": {
                "id": uid, "is_bot": False,
                "first_name": fake.first_name(),
                "username": fake.user_name(),
                "language_code": "ru",
            },
            "chat": {"id": uid, "type": "private", "first_name": fake.first_name()},
            "date": 1700000000,
            "text": fake.sentence(),
        },
    }

def _make_fake_bot_module():
    """Создаём fake src.core.bot module с mock bot/dp."""
    mock_bot = MagicMock()
    mock_bot.get_me = AsyncMock(return_value=MagicMock(username="testbot", id=123456))
    mock_bot.set_webhook = AsyncMock()
    mock_bot.delete_webhook = AsyncMock()
    mock_bot.get_webhook_info = AsyncMock(
        return_value=MagicMock(
            model_dump=lambda: {"url": "https://example.com/webhook", "pending_update_count": 0}
        )
    )

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()

    mock_dp = MagicMock()
    mock_dp.storage.redis = mock_redis
    mock_dp.feed_update = AsyncMock()

    fake_bot_mod = types.SimpleNamespace(bot=mock_bot, dp=mock_dp, fsm_redis=lambda: mock_redis)
    return fake_bot_mod, mock_bot, mock_dp, mock_redis

# webhook/router.py

@pytest.fixture(scope="module")
def webhook_router_module():
    fake_bot_mod, mock_bot, mock_dp, _ = _make_fake_bot_module()
    stub_settings = sys.modules["src.core.config"].settings

    # Создаём minimal prometheus mock
    fake_prom: Any = types.SimpleNamespace(
        tg_updates_total=MagicMock(),
        tg_webhook_requests_total=MagicMock(),
    )
    fake_prom.tg_updates_total.labels = MagicMock(return_value=MagicMock(inc=MagicMock()))
    fake_prom.tg_webhook_requests_total.labels = MagicMock(return_value=MagicMock(inc=MagicMock()))
    sys.modules.setdefault("src.monitoring.prometheus", fake_prom)

    spec = importlib.util.spec_from_file_location(
        f"_real_webhook_router_{fake.lexify('????')}", _ROUTER_FILE
    )
    assert spec and spec.loader
    module: Any = importlib.util.module_from_spec(spec)

    with patch.dict(sys.modules, {"src.core.bot": fake_bot_mod}):
        spec.loader.exec_module(module)

    module._mock_bot = mock_bot
    module._mock_dp = mock_dp
    return module

class TestWebhookRouter:

    def test_router_is_created(self, webhook_router_module) -> None:
        from fastapi import APIRouter
        assert isinstance(webhook_router_module.router, APIRouter)

    def test_webhook_valid_token_returns_ok(self, webhook_router_module) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(webhook_router_module.router)

        stub_settings = sys.modules["src.core.config"].settings
        secret = "test_webhook_secret"
        stub_settings.webhook_secret = MagicMock()
        stub_settings.webhook_secret.get_secret_value = lambda: secret

        client = TestClient(app, raise_server_exceptions=False)
        data = _fake_update_data()

        with patch.object(
            webhook_router_module._mock_dp, "feed_update", new=AsyncMock()
        ):
            resp = client.post(
                "/webhook",
                json=data,
                headers={"X-Telegram-Bot-Api-Secret-Token": secret},
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_webhook_wrong_token_returns_403(self, webhook_router_module) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(webhook_router_module.router)

        stub_settings = sys.modules["src.core.config"].settings
        stub_settings.webhook_secret = MagicMock()
        stub_settings.webhook_secret.get_secret_value = lambda: "real_secret"

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/webhook",
            json=_fake_update_data(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"},
        )

        assert resp.status_code == 403

    def test_webhook_missing_token_returns_403(self, webhook_router_module) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(webhook_router_module.router)

        stub_settings = sys.modules["src.core.config"].settings
        stub_settings.webhook_secret = MagicMock()
        stub_settings.webhook_secret.get_secret_value = lambda: "secret"

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/webhook", json=_fake_update_data())

        assert resp.status_code == 403

    def test_faker_different_update_types(self, webhook_router_module) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(webhook_router_module.router)
        secret = fake.sha256()[:24]
        stub_settings = sys.modules["src.core.config"].settings
        stub_settings.webhook_secret = MagicMock()
        stub_settings.webhook_secret.get_secret_value = lambda: secret

        client = TestClient(app, raise_server_exceptions=False)

        for _ in range(3):
            with patch.object(
                webhook_router_module._mock_dp, "feed_update", new=AsyncMock()
            ):
                resp = client.post(
                    "/webhook",
                    json=_fake_update_data(),
                    headers={"X-Telegram-Bot-Api-Secret-Token": secret},
                )
            assert resp.status_code == 200

# webhook/app.py - create_app()

@pytest.fixture(scope="module")
def webhook_app_module():
    fake_bot_mod, mock_bot, mock_dp, mock_redis = _make_fake_bot_module()

    # Stub all heavy imports that app.py uses
    fake_heartbeat = types.SimpleNamespace(
        _heartbeat=AsyncMock(),
        REDIS_KEY_START_TIME="bot:start_time",
        REDIS_KEY_ALIVE="bot:alive",
        ALIVE_TTL=60,
    )
    fake_sysinfo = types.SimpleNamespace(_system_info_loop=AsyncMock())
    fake_restart = types.SimpleNamespace(check_restart_notification=AsyncMock())
    fake_commands = types.SimpleNamespace(_set_commands=AsyncMock())
    fake_chat_router_mod = types.SimpleNamespace(set_bot_meta=MagicMock())

    stub_settings = sys.modules["src.core.config"].settings
    stub_settings.webhook_url = "https://example.com/webhook"
    stub_settings.webhook_secret = MagicMock()
    stub_settings.webhook_secret.get_secret_value = lambda: "secret"

    spec = importlib.util.spec_from_file_location(
        f"_real_webhook_app_{fake.lexify('????')}", _APP_FILE
    )
    assert spec and spec.loader
    module: Any = importlib.util.module_from_spec(spec)

    extras = {
        "src.core.bot": fake_bot_mod,
        "src.monitoring.heartbeat": fake_heartbeat,
        "src.monitoring.system_info": fake_sysinfo,
        "src.monitoring.restart": fake_restart,
        "src.bot.commands": fake_commands,
        "src.bot.routers.chat": fake_chat_router_mod,
    }

    with patch.dict(sys.modules, extras):
        spec.loader.exec_module(module)

    module._mock_bot = mock_bot
    module._mock_dp = mock_dp
    module._mock_redis = mock_redis
    return module

class TestCreateApp:

    def test_create_app_returns_fastapi_instance(self, webhook_app_module) -> None:
        from fastapi import FastAPI
        app = webhook_app_module.create_app()
        assert isinstance(app, FastAPI)

    def test_health_endpoint_returns_ok(self, webhook_app_module) -> None:
        from fastapi.testclient import TestClient

        app = webhook_app_module.create_app()

        @asynccontextmanager
        async def _noop_lifespan(app):
            yield

        app.router.lifespan_context = _noop_lifespan
        client = TestClient(app)
        resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_metrics_endpoint_returns_200(self, webhook_app_module) -> None:
        from fastapi.testclient import TestClient

        app = webhook_app_module.create_app()

        @asynccontextmanager
        async def _noop_lifespan(app):
            yield

        app.router.lifespan_context = _noop_lifespan
        client = TestClient(app)
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_webhook_info_endpoint_returns_200(self, webhook_app_module) -> None:
        from fastapi.testclient import TestClient

        app = webhook_app_module.create_app()

        @asynccontextmanager
        async def _noop_lifespan(app):
            yield

        app.router.lifespan_context = _noop_lifespan
        client = TestClient(app)
        resp = client.get("/webhook_info")
        assert resp.status_code == 200

    def test_app_has_webhook_router_included(self, webhook_app_module) -> None:
        app = webhook_app_module.create_app()
        routes = [r.path for r in app.routes]
        assert any("/webhook" in p for p in routes)

class TestLifespan:

    @pytest.mark.asyncio
    async def test_lifespan_startup_and_shutdown(self, webhook_app_module) -> None:
        """lifespan выполняет startup (до yield) и shutdown (после yield)."""
        from fastapi import FastAPI

        mock_bot = webhook_app_module._mock_bot
        mock_redis = webhook_app_module._mock_redis

        mock_bot.set_webhook = AsyncMock()
        mock_bot.delete_webhook = AsyncMock()
        mock_bot.get_me = AsyncMock(return_value=MagicMock(username="test", id=123))

        app = FastAPI()
        # Создаём новый app с реальным lifespan и вызываем его напрямую
        async with webhook_app_module.lifespan(app):
            # Проверяем что startup прошёл
            mock_bot.set_webhook.assert_awaited()

        # Проверяем что shutdown прошёл
        mock_bot.delete_webhook.assert_awaited()
