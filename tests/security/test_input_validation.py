import pytest

pytestmark = pytest.mark.security


async def test_non_int_user_id_is_422(svc_client):
    r = await svc_client.get("/users/not-a-number")
    assert r.status_code == 422


async def test_chat_complete_missing_required_is_422(svc_client):
    r = await svc_client.post("/chat/complete", json={"user_id": 1})
    assert r.status_code == 422


async def test_unknown_model_is_not_500(svc_client):
    body = {"user_id": 1, "message": "hi", "model": "evil-model-9000"}
    r = await svc_client.post("/chat/complete", json=body)
    assert r.status_code < 500


async def test_bad_limit_query_is_422(client, init_data):
    r = await client.get(
        "/webapp/dialogs?limit=not-int", headers={"Authorization": f"tma {init_data.valid()}"}
    )
    assert r.status_code == 422


async def test_huge_user_id_handled(svc_client):
    r = await svc_client.get("/users/999999999999999999")
    assert r.status_code in (404, 422)
