import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_chat_complete_persists_exchange(client, seed):
    uid, did = await seed()

    resp = await client.post(
        "/chat/complete",
        json={"user_id": uid, "dialog_id": did, "message": "привет", "model": "gpt-5.4-nano"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "E2E canned answer"
    assert body["is_flagged"] is False
    assert body["usage"]["total_tokens"] == 18

    from db.db import Session
    from db.models.user import Dialog, UserStatistics

    async with Session() as s:
        dialog = await s.get(Dialog, did)
        assert dialog is not None
        assert [m["role"] for m in dialog.messages] == ["user", "assistant"]
        assert dialog.messages[1]["content"] == "E2E canned answer"

        stats = await s.get(UserStatistics, uid)
        assert stats is not None
        assert stats.n_used_tokens  # обновился per-model счётчик


@pytest.mark.asyncio
async def test_chat_complete_flagged_blocks(client, seed, monkeypatch):
    uid, did = await seed()

    import routes.chat as chat_routes

    async def _flagged(text=None, image_buffer=None):
        return True, ["violence"], {"violence": 0.99}

    monkeypatch.setattr(chat_routes, "moderate_content", _flagged)

    resp = await client.post(
        "/chat/complete",
        json={"user_id": uid, "dialog_id": did, "message": "bad", "model": "gpt-5.4-nano"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_flagged"] is True
    assert body["answer"] == ""

    from db.db import Session
    from db.models.user import Dialog

    async with Session() as s:
        dialog = await s.get(Dialog, did)
        assert dialog is not None
        assert dialog.messages == []  # ничего не записали


@pytest.mark.asyncio
async def test_chat_complete_requires_service_token(client, seed):
    uid, did = await seed()

    resp = await client.post(
        "/chat/complete",
        json={"user_id": uid, "dialog_id": did, "message": "hi", "model": "gpt-5.4-nano"},
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert resp.status_code == 401
