import os
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

_BOT_DIR = str(Path(__file__).resolve().parents[2] / "bot")


def _load_api_client():
    """Импортируем реальный bot.api_client, застабив только bot-конфиг (env/yaml бота не нужны)."""
    fake_cfg = types.ModuleType("src.core.config")
    fake_cfg.settings = types.SimpleNamespace(
        api_request_timeout_seconds=30.0,
        enable_content_moderation=True,
    )
    sys.modules["src.core.config"] = fake_cfg
    if _BOT_DIR not in sys.path:
        sys.path.insert(0, _BOT_DIR)
    import src.services.api_client as api_client

    return api_client


@pytest.mark.asyncio
async def test_bot_api_client_chat_complete_persists(app, seed, monkeypatch):
    import httpx

    api_client = _load_api_client()

    token = os.environ["API_SERVICE_TOKEN"]
    bot_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://api",
        headers={"Authorization": f"Bearer {token}"},
    )
    monkeypatch.setattr(api_client, "get_client", lambda: bot_client)

    uid, did = await seed()
    try:
        resp = await api_client.chat_complete(
            user_id=uid, dialog_id=did, message="привет", chat_mode="assistant", model="gpt-5.4-nano"
        )
    finally:
        await bot_client.aclose()

    # контракт bot↔api: ответ декодируется msgspec-структурой бота
    assert resp.answer == "E2E canned answer"
    assert resp.is_flagged is False

    from db.db import Session
    from db.models.user import Dialog

    async with Session() as s:
        dialog = await s.get(Dialog, did)
        assert [m["role"] for m in dialog.messages] == ["user", "assistant"]
