import pytest

pytestmark = pytest.mark.security


async def test_chat_complete_requires_token(client):
    body = {"user_id": 1, "message": "hi", "model": "gpt-5.4-nano"}
    r = await client.post("/chat/complete", json=body)
    assert r.status_code == 401


async def test_chat_complete_wrong_token(client):
    body = {"user_id": 1, "message": "hi", "model": "gpt-5.4-nano"}
    r = await client.post("/chat/complete", json=body, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


async def test_users_route_requires_token(client):
    r = await client.get("/users/1")
    assert r.status_code == 401


async def test_dialogs_route_requires_token(client):
    r = await client.get("/dialogs/1/messages")
    assert r.status_code == 401


async def test_debug_500_requires_token(client):
    r = await client.get("/health/debug/500")
    assert r.status_code == 401


async def test_health_is_public(client):
    r = await client.get("/health")
    assert r.status_code == 200


async def test_valid_token_passes(svc_client):
    # 404 — это бизнес-логика, не отказ авторизации
    r = await svc_client.get("/users/424242")
    assert r.status_code == 404
