import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_me_valid_init_data(client, make_init_data):
    init = make_init_data(user_id=4242)

    resp = await client.get("/webapp/me", headers={"Authorization": f"tma {init}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 4242
    assert "is_whitelisted" in body


@pytest.mark.asyncio
async def test_me_rejects_bad_init_data(client):
    resp = await client.get("/webapp/me", headers={"Authorization": "tma auth_date=1&user=x&hash=deadbeef"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_tma_scheme(client):
    resp = await client.get("/webapp/me", headers={"Authorization": "Bearer something"})
    assert resp.status_code == 401
