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

    api_main_path = Path(__file__).resolve().parents[2] / "main.py"
    spec = importlib.util.spec_from_file_location("api_test_main", api_main_path)
    assert spec and spec.loader
    api_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api_main)
    db_module = importlib.import_module("db.db")

    # Force auth ON for security tests.
    monkeypatch.setattr("core.security._SERVICE_TOKEN", "test-token")

    app = api_main.create_app()

    # Disable app lifespan side effects (DB init/sync) for unit API tests.
    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan

    async def _fake_session():
        yield object()

    app.dependency_overrides[db_module.get_session] = _fake_session
    return TestClient(app)


@pytest.mark.api
def test_health_is_public_and_returns_json(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.security
def test_users_requires_service_token(client: TestClient) -> None:
    response = client.get("/users/1")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid service token"


@pytest.mark.api
def test_users_get_returns_404_when_user_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    users_routes = importlib.import_module("routes.users")

    async def _missing_user(_session, _user_id):
        return None

    monkeypatch.setattr(users_routes.user_repo, "get_user", _missing_user)
    response = client.get("/users/123", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.api
def test_users_patch_empty_payload_returns_400(client: TestClient) -> None:
    response = client.patch("/users/123", json={}, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Nothing to update"


@pytest.mark.security
def test_dialogs_requires_service_token(client: TestClient) -> None:
    response = client.get("/dialogs/1/messages")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid service token"


@pytest.mark.api
def test_new_dialog_returns_404_when_user_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialogs_routes = importlib.import_module("routes.dialogs")

    async def _missing_user(_session, _user_id):
        return None

    monkeypatch.setattr(dialogs_routes.user_repo, "get_user", _missing_user)
    response = client.post("/dialogs/999/new", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.api
def test_dialogs_messages_returns_all_modes_shape(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialogs_routes = importlib.import_module("routes.dialogs")

    async def _messages_by_mode(_session, _user_id):
        return {"assistant": [{"user": "u", "bot": "b"}], "code_assistant": []}

    monkeypatch.setattr(dialogs_routes.dialog_repo, "get_dialog_messages_by_mode", _messages_by_mode)
    response = client.get("/dialogs/1/messages", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert "messages_by_mode" in data
    assert isinstance(data["messages_by_mode"], dict)
