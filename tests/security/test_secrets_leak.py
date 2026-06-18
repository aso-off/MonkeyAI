import os

import pytest

pytestmark = pytest.mark.security

_TOKEN = os.environ.get("API_SERVICE_TOKEN", "sec-service-token")
_INTERNALS = ("Traceback", "/app/", "site-packages", "asyncpg", "sqlalchemy.exc")


async def test_token_not_reflected_on_401(client):
    body = {"user_id": 1, "message": "hi", "model": "gpt-5.4-nano"}
    r = await client.post("/chat/complete", json=body, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    assert _TOKEN not in r.text


async def test_health_exposes_only_status(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert set(r.json().keys()) <= {"status", "redis"}


async def test_404_has_no_internals(client):
    r = await client.get("/this-route-does-not-exist")
    assert r.status_code == 404
    assert not any(m in r.text for m in _INTERNALS)


async def test_malformed_json_is_422_not_500(svc_client):
    r = await svc_client.post(
        "/chat/complete", content=b"{not valid json", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 422
    assert not any(m in r.text for m in _INTERNALS)


async def test_validation_error_hides_internals(svc_client):
    r = await svc_client.post("/chat/complete", json={"user_id": 1, "message": "hi"})
    assert r.status_code == 422
    assert not any(m in r.text for m in _INTERNALS)
