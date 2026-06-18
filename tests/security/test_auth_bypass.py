import pytest

pytestmark = pytest.mark.security


async def test_no_auth_header_rejected(client):
    r = await client.get("/webapp/me")
    assert r.status_code == 401


async def test_wrong_scheme_rejected(client, init_data):
    r = await client.get("/webapp/me", headers={"Authorization": f"Bearer {init_data.valid()}"})
    assert r.status_code == 401


async def test_bad_hash_rejected(client, init_data):
    r = await client.get("/webapp/me", headers={"Authorization": f"tma {init_data.bad_hash()}"})
    assert r.status_code == 401


async def test_missing_hash_rejected(client, init_data):
    r = await client.get("/webapp/me", headers={"Authorization": f"tma {init_data.no_hash()}"})
    assert r.status_code == 401


async def test_expired_init_data_rejected(client, init_data):
    r = await client.get("/webapp/me", headers={"Authorization": f"tma {init_data.expired()}"})
    assert r.status_code == 401


async def test_tampered_user_rejected(client, init_data):
    r = await client.get("/webapp/me", headers={"Authorization": f"tma {init_data.tampered()}"})
    assert r.status_code == 401


async def test_valid_init_data_accepted(client, init_data):
    r = await client.get("/webapp/me", headers={"Authorization": f"tma {init_data.valid()}"})
    assert r.status_code == 200
