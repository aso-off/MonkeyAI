import pytest

pytestmark = pytest.mark.security


async def test_identity_comes_from_signature(client, init_data):
    # id берётся из подписи, навязать чужой нельзя
    r = await client.get("/webapp/me", headers={"Authorization": f"tma {init_data.valid(777)}"})
    assert r.status_code == 200
    assert r.json()["id"] == 777


async def test_dialogs_isolated_between_users(client, init_data, seed):
    await seed(555, whitelisted=True)
    await seed(999, whitelisted=True)

    created = await client.post(
        "/webapp/dialogs/new", headers={"Authorization": f"tma {init_data.valid(555)}"}
    )
    assert created.status_code == 200

    own = await client.get("/webapp/dialogs", headers={"Authorization": f"tma {init_data.valid(555)}"})
    assert own.status_code == 200
    assert len(own.json()["dialogs"]) >= 1

    other = await client.get(
        "/webapp/dialogs", headers={"Authorization": f"tma {init_data.valid(999)}"}
    )
    assert other.status_code == 200
    assert other.json()["dialogs"] == []


async def test_non_whitelisted_blocked_from_new_dialog(client, init_data, seed):
    await seed(321, whitelisted=False)
    r = await client.post(
        "/webapp/dialogs/new", headers={"Authorization": f"tma {init_data.valid(321)}"}
    )
    assert r.status_code == 403


async def test_service_route_user_scoped(svc_client):
    r = await svc_client.get("/dialogs/888777/message-count")
    assert r.status_code == 200
    assert r.json()["count"] == 0
