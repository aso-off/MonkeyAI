import importlib
import sys
import types
from types import SimpleNamespace

import pytest


def _prepare_fake_bot_config() -> None:
    fake_settings = types.SimpleNamespace(
        whitelist_mode=True,
        admin_ids=[],
        allowed_user_ids=[],
        locales={
            "ru": {"access_denied": "Доступ запрещён"},
            "en": {"access_denied": "Access denied"},
        },
    )
    fake_module = types.ModuleType("src.core.config")
    fake_module.settings = fake_settings
    fake_module.get_settings = lambda: fake_settings
    sys.modules["src.core.config"] = fake_module


def _import_bot_modules():
    _prepare_fake_bot_config()
    auth_module = importlib.import_module("src.bot.middleware.auth")
    admin_module = importlib.import_module("src.utils.admin")
    return auth_module, admin_module


@pytest.mark.security
@pytest.mark.asyncio
async def test_require_admin_returns_false_for_non_admin_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, admin_module = _import_bot_modules()
    answered: dict = {"called": False}

    class _FakeCallback:
        def __init__(self) -> None:
            self.from_user = SimpleNamespace(id=123)

        async def answer(self, _text: str, show_alert: bool = False) -> None:
            answered["called"] = True
            answered["show_alert"] = show_alert

    async def _is_admin(_user_id: int) -> bool:
        return False

    monkeypatch.setattr(admin_module.api, "is_user_admin", _is_admin)
    monkeypatch.setattr(admin_module, "CallbackQuery", _FakeCallback)
    ok = await admin_module.require_admin(_FakeCallback(), "ru")
    assert ok is False
    assert answered["called"] is True
    assert answered["show_alert"] is True


@pytest.mark.security
@pytest.mark.asyncio
async def test_require_admin_returns_true_for_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, admin_module = _import_bot_modules()

    class _FakeMessage:
        def __init__(self) -> None:
            self.from_user = SimpleNamespace(id=777)

    async def _is_admin(_user_id: int) -> bool:
        return True

    monkeypatch.setattr(admin_module.api, "is_user_admin", _is_admin)
    ok = await admin_module.require_admin(_FakeMessage(), "ru")
    assert ok is True


@pytest.mark.security
@pytest.mark.asyncio
async def test_auth_middleware_blocks_user_in_whitelist_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth_module, _ = _import_bot_modules()
    middleware = auth_module.AuthMiddleware()

    async def _get_user(_user_id: int):
        return None

    monkeypatch.setattr(auth_module.api, "get_user", _get_user)
    monkeypatch.setattr(auth_module.settings, "whitelist_mode", True)
    monkeypatch.setattr(auth_module.settings, "admin_ids", [])
    monkeypatch.setattr(auth_module.settings, "allowed_user_ids", [])

    called = {"value": False}

    async def _handler(_event, _data):
        called["value"] = True
        return "ok"

    data = {"event_from_user": SimpleNamespace(id=55, username="u")}
    result = await middleware(_handler, SimpleNamespace(), data)
    assert result is None
    assert called["value"] is False


@pytest.mark.security
@pytest.mark.asyncio
async def test_auth_middleware_allows_whitelisted_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth_module, _ = _import_bot_modules()
    middleware = auth_module.AuthMiddleware()

    async def _get_user(_user_id: int):
        return SimpleNamespace(is_admin=False, is_whitelisted=True)

    monkeypatch.setattr(auth_module.api, "get_user", _get_user)
    monkeypatch.setattr(auth_module.settings, "whitelist_mode", True)
    monkeypatch.setattr(auth_module.settings, "admin_ids", [])
    monkeypatch.setattr(auth_module.settings, "allowed_user_ids", [])

    async def _handler(_event, _data):
        return "ok"

    data = {"event_from_user": SimpleNamespace(id=56, username="w")}
    result = await middleware(_handler, SimpleNamespace(), data)
    assert result == "ok"
