"""Shared fixtures для api/tests/routes/ — TestClient с мокнутыми зависимостями."""

import importlib.util
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

import types

def _make_user_ns(fake, **overrides) -> types.SimpleNamespace:
    """Фабрика: ORM-совместимый объект (users + state + statistics) для UserRead.from_orm_user()."""
    state = types.SimpleNamespace(
        current_dialog_id=overrides.get("current_dialog_id", None),
        current_dialog_ids=overrides.get("current_dialog_ids", {}),
        current_chat_mode=overrides.get("current_chat_mode", "assistant"),
        mini_app_chat_mode=overrides.get("mini_app_chat_mode", "assistant"),
        mini_app_dialog_ids=overrides.get("mini_app_dialog_ids", {}),
        current_model=overrides.get("current_model", "gpt-4o"),
        theme=overrides.get("theme", "light"),
    )
    statistics = types.SimpleNamespace(
        n_used_tokens=overrides.get("n_used_tokens", {}),
        n_generated_images=overrides.get("n_generated_images", 0),
        n_transcribed_seconds=overrides.get("n_transcribed_seconds", 0.0),
        last_updated=overrides.get("last_updated", datetime.now(timezone.utc)),
    )
    return types.SimpleNamespace(
        id=overrides.get("id", fake.random_int(min=100_000, max=999_999_999)),
        chat_id=overrides.get("chat_id", fake.random_int(min=100_000, max=999_999_999)),
        username=overrides.get("username", fake.user_name()),
        first_name=overrides.get("first_name", fake.first_name()),
        last_name=overrides.get("last_name", fake.last_name()),
        language=overrides.get("language", "ru"),
        is_admin=overrides.get("is_admin", False),
        is_whitelisted=overrides.get("is_whitelisted", True),
        first_seen=overrides.get("first_seen", datetime.now(timezone.utc)),
        last_interaction=overrides.get("last_interaction", datetime.now(timezone.utc)),
        state=state,
        statistics=statistics,
    )

@pytest.fixture(scope="module")
def api_app():
    """Создаём FastAPI app один раз для всего модуля."""
    api_main_path = Path(__file__).resolve().parents[2] / "main.py"
    spec = importlib.util.spec_from_file_location("_api_routes_test_main", api_main_path)
    assert spec and spec.loader
    api_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api_main)
    app = api_main.create_app()

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan
    return app

@pytest.fixture
def api_client(api_app, mock_redis):
    """
    TestClient с переопределёнными зависимостями:
    - get_session → AsyncMock (нет реальной БД)
    - get_redis патчится на уровне routes.users
    """
    from db.db import get_session

    async def _mock_session() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock(spec=AsyncSession)

    api_app.dependency_overrides[get_session] = _mock_session

    # Патчим get_redis в routes.users чтобы возвращал mock_redis
    import routes.users as users_mod
    original_get_redis = users_mod.get_redis
    users_mod.get_redis = lambda: mock_redis

    client = TestClient(api_app, raise_server_exceptions=False)
    yield client

    # Восстанавливаем
    users_mod.get_redis = original_get_redis
    api_app.dependency_overrides.clear()

@pytest.fixture
def user_factory(fake):
    def _make(**overrides) -> types.SimpleNamespace:
        return _make_user_ns(fake, **overrides)
    return _make