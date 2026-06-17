"""Юнит-тесты для bot/src/utils/admin.py — функция require_admin.

Важно: admin.py делает `from src.core.config import settings` ВНУТРИ функции.
Поэтому патчить `src.utils.admin.settings` нельзя — такого атрибута нет.
Патчим через sys.modules["src.core.config"].settings напрямую.
"""

import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message

from src.utils.admin import require_admin

# Stub-модуль конфига из conftest — через него требует_admin получает settings
_STUB_CONFIG: Any = sys.modules["src.core.config"]


# Helpers

def _make_msg(user_id: int) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    return msg


def _make_cb(user_id: int) -> MagicMock:
    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = MagicMock()
    cb.from_user.id = user_id
    cb.answer = AsyncMock()
    return cb


@pytest.fixture
def stub_settings(request):
    """
    Контекстная замена settings в stub-модуле конфига.
    Принимает admin_ids через косвенный параметр или использует дефолт [999_000_000].
    """
    admin_ids = getattr(request, "param", [999_000_000])
    original = _STUB_CONFIG.settings
    _STUB_CONFIG.settings = types.SimpleNamespace(admin_ids=admin_ids)
    yield _STUB_CONFIG.settings
    _STUB_CONFIG.settings = original


# С db_user


class TestRequireAdminWithDbUser:
    @pytest.mark.unit
    async def test_db_user_is_admin_returns_true(self, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        db_user = types.SimpleNamespace(is_admin=True)
        result = await require_admin(_make_msg(uid), "ru", db_user=db_user)
        assert result is True

    @pytest.mark.unit
    @pytest.mark.parametrize("stub_settings", [[123456789]], indirect=True)
    async def test_db_user_not_admin_but_in_admin_ids_returns_true(
        self, stub_settings, fake
    ) -> None:
        # uid совпадает с admin_ids[0] = 123456789
        db_user = types.SimpleNamespace(is_admin=False)
        result = await require_admin(_make_msg(123456789), "ru", db_user=db_user)
        assert result is True

    @pytest.mark.unit
    @pytest.mark.parametrize("stub_settings", [[]], indirect=True)
    async def test_db_user_not_admin_empty_admin_ids_returns_false(
        self, stub_settings, fake
    ) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        db_user = types.SimpleNamespace(is_admin=False)
        result = await require_admin(_make_msg(uid), "ru", db_user=db_user)
        assert result is False

    @pytest.mark.unit
    @pytest.mark.parametrize("stub_settings", [[]], indirect=True)
    async def test_non_admin_message_does_not_call_answer(
        self, stub_settings, fake
    ) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        db_user = types.SimpleNamespace(is_admin=False)
        msg = _make_msg(uid)
        await require_admin(msg, "ru", db_user=db_user)
        # Message не получает ответа (только CallbackQuery)
        msg.answer.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.parametrize("stub_settings", [[]], indirect=True)
    async def test_non_admin_callback_answers_with_alert(
        self, stub_settings, fake
    ) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        db_user = types.SimpleNamespace(is_admin=False)
        cb = _make_cb(uid)
        result = await require_admin(cb, "ru", db_user=db_user)
        assert result is False
        cb.answer.assert_awaited_once()
        assert cb.answer.call_args[1].get("show_alert") is True

    @pytest.mark.unit
    async def test_admin_callback_returns_true_no_denied_answer(self, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        db_user = types.SimpleNamespace(is_admin=True)
        cb = _make_cb(uid)
        result = await require_admin(cb, "ru", db_user=db_user)
        assert result is True
        cb.answer.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.parametrize("stub_settings", [[]], indirect=True)
    @pytest.mark.parametrize("lang", ["ru", "en", "de"])
    async def test_denied_answer_uses_provided_language(
        self, stub_settings, fake, lang: str
    ) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        db_user = types.SimpleNamespace(is_admin=False)
        cb = _make_cb(uid)
        await require_admin(cb, lang, db_user=db_user)
        cb.answer.assert_awaited_once()


# Без db_user (API-запрос)


class TestRequireAdminWithoutDbUser:
    @pytest.mark.unit
    async def test_api_returns_is_admin_true(self, mocker, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        mocker.patch("src.utils.admin.api.is_user_admin", new=AsyncMock(return_value=True))
        result = await require_admin(_make_msg(uid), "ru")
        assert result is True

    @pytest.mark.unit
    async def test_api_returns_is_admin_false_message(self, mocker, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        mocker.patch("src.utils.admin.api.is_user_admin", new=AsyncMock(return_value=False))
        result = await require_admin(_make_msg(uid), "ru")
        assert result is False

    @pytest.mark.unit
    async def test_api_returns_is_admin_false_callback_answers(self, mocker, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        mocker.patch("src.utils.admin.api.is_user_admin", new=AsyncMock(return_value=False))
        cb = _make_cb(uid)
        result = await require_admin(cb, "ru")
        assert result is False
        cb.answer.assert_awaited_once()

    @pytest.mark.unit
    async def test_api_called_with_correct_user_id(self, mocker, fake) -> None:
        uid = fake.random_int(min=100_000, max=999_999_999)
        mock_api = AsyncMock(return_value=True)
        mocker.patch("src.utils.admin.api.is_user_admin", new=mock_api)
        await require_admin(_make_msg(uid), "ru")
        mock_api.assert_awaited_once_with(uid)

    @pytest.mark.unit
    async def test_faker_batch_non_admin(self, mocker, fake) -> None:
        mocker.patch("src.utils.admin.api.is_user_admin", new=AsyncMock(return_value=False))
        for _ in range(5):
            result = await require_admin(
                _make_msg(fake.random_int(min=100_000, max=999_999_999)), "ru"
            )
            assert result is False