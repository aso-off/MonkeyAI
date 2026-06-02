"""Minimal health smoke test for API (no DB, no external services)."""

from contextlib import asynccontextmanager
import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    fake_settings = types.SimpleNamespace(
        database_url="postgresql+asyncpg://u:p@localhost:5432/db",
        telegram_token=types.SimpleNamespace(get_secret_value=lambda: "token"),
        chat_modes={"assistant": {"prompt_start": "x"}},
        models={},
        admin_ids=[],
        allowed_user_ids=[],
        enable_content_moderation=True,
        moderation_thresholds={},
        openai_api_base=None,
        return_n_generated_images=1,
        image_size="1024x1024",
        image_quality="medium",
    )
    fake_core_config = types.ModuleType("core.config")
    fake_core_config.settings = fake_settings
    sys.modules["core.config"] = fake_core_config

    api_main_path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("api_test_main", api_main_path)
    assert spec and spec.loader
    api_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api_main)

    app = api_main.create_app()

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan
    return TestClient(app)


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
