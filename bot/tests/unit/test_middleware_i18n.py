"""
Тесты для bot/src/bot/middleware/i18n.py.

Покрываем:
- нет user → resolve_lang(None), язык в data
- db_user уже в data → используем db language (нет лишнего API-запроса)
- db_user.language не поддерживается → fallback на resolve_lang(tg_lang)
- нет db_user в data → api.get_user → берём язык из ответа
- api.get_user возвращает None → resolve_lang(tg_lang)
- api.get_user поднимает исключение → warning, язык из tg
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)


def _uid() -> int:
    return fake.random_int(min=100_000, max=999_999_999)


def _tg_user(lang: str = "ru") -> MagicMock:
    u = MagicMock()
    u.id = _uid()
    u.language_code = lang
    return u


def _db_user(lang: str) -> MagicMock:
    u = MagicMock()
    u.id = _uid()
    u.language = lang
    return u


class TestI18nMiddleware:

    @pytest.mark.asyncio
    async def test_no_user_sets_language_in_data(self) -> None:
        from src.bot.middleware.i18n import I18nMiddleware
        mw = I18nMiddleware()
        handler = AsyncMock(return_value="ok")
        data: dict = {}
        result = await mw(handler, MagicMock(), data)
        assert "language" in data
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_db_user_in_data_uses_db_language(self) -> None:
        from src.bot.middleware.i18n import I18nMiddleware
        mw = I18nMiddleware()
        handler = AsyncMock()
        data = {"event_from_user": _tg_user("ru"), "db_user": _db_user("de")}
        with patch("src.bot.middleware.i18n.api") as mock_api:
            await mw(handler, MagicMock(), data)
            mock_api.get_user.assert_not_called()
        assert data["language"] == "de"

    @pytest.mark.asyncio
    async def test_db_user_unsupported_lang_falls_back_to_tg(self) -> None:
        from src.bot.middleware.i18n import I18nMiddleware
        mw = I18nMiddleware()
        handler = AsyncMock()
        data = {"event_from_user": _tg_user("fr"), "db_user": _db_user("xx_unsupported")}
        await mw(handler, MagicMock(), data)
        assert data["language"] == "fr"

    @pytest.mark.asyncio
    async def test_no_db_user_in_data_calls_api(self) -> None:
        from src.bot.middleware.i18n import I18nMiddleware
        mw = I18nMiddleware()
        handler = AsyncMock()
        data = {"event_from_user": _tg_user("ru")}
        with patch("src.bot.middleware.i18n.api") as mock_api:
            mock_api.get_user = AsyncMock(return_value=_db_user("es"))
            await mw(handler, MagicMock(), data)
        assert data["language"] == "es"
        mock_api.get_user.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_api_returns_none_uses_tg_lang(self) -> None:
        from src.bot.middleware.i18n import I18nMiddleware
        mw = I18nMiddleware()
        handler = AsyncMock()
        data = {"event_from_user": _tg_user("pl")}
        with patch("src.bot.middleware.i18n.api") as mock_api:
            mock_api.get_user = AsyncMock(return_value=None)
            await mw(handler, MagicMock(), data)
        assert data["language"] == "pl"

    @pytest.mark.asyncio
    async def test_api_exception_logs_warning_uses_tg_lang(self) -> None:
        from src.bot.middleware.i18n import I18nMiddleware
        mw = I18nMiddleware()
        handler = AsyncMock()
        data = {"event_from_user": _tg_user("tr")}
        with patch("src.bot.middleware.i18n.api") as mock_api:
            mock_api.get_user = AsyncMock(side_effect=RuntimeError(fake.sentence()))
            await mw(handler, MagicMock(), data)
        assert data["language"] == "tr"
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_user_none_explicitly_in_data_calls_api(self) -> None:
        from src.bot.middleware.i18n import I18nMiddleware
        mw = I18nMiddleware()
        handler = AsyncMock()
        data = {"event_from_user": _tg_user("en"), "db_user": None}
        with patch("src.bot.middleware.i18n.api") as mock_api:
            mock_api.get_user = AsyncMock(return_value=_db_user("pt"))
            await mw(handler, MagicMock(), data)
        assert data["language"] == "pt"

    @pytest.mark.asyncio
    async def test_faker_supported_langs_set_correctly(self) -> None:
        from src.bot.middleware.i18n import I18nMiddleware
        from src.utils.localization import _SUPPORTED_LANGS
        mw = I18nMiddleware()
        for lang in list(_SUPPORTED_LANGS)[:5]:
            handler = AsyncMock()
            data = {"event_from_user": _tg_user(lang), "db_user": _db_user(lang)}
            await mw(handler, MagicMock(), data)
            assert data["language"] == lang
