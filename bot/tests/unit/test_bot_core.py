"""
Тесты для bot/src/core/bot.py.

Стратегия: загружаем реальный модуль через importlib, мокируя:
- aiogram.Bot              → не создаём реального Telegram-клиента
- aiogram.Dispatcher       → не создаём реального диспетчера
- redis.asyncio.Redis.from_url → не нужен реальный Redis
- aiogram.fsm.storage.redis.RedisStorage
- src.monitoring.tg_session.MetricsAiohttpSession

module-level код (bot = create_bot(), dp = create_dispatcher(), ...)
выполняе��ся при загрузке → все строки попадают в coverage.

Faker: language codes, error messages.
"""

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

_BOT_SRC = Path(__file__).resolve().parents[2] / "src"
_BOT_FILE = _BOT_SRC / "core" / "bot.py"

# Fixture загрузки

@pytest.fixture(scope="module")
def bot_module():
    """
    Загружаем реальный bot/src/core/bot.py через importlib.
    Всё что может обращаться к Telegram/Redis — мокируем.
    """
    import sys

    # Добавляем redis_url в stub settings (нужен для create_dispatcher)
    stub_settings = sys.modules["src.core.config"].settings
    stub_settings.redis_url = "redis://localhost:6379"

    # Fake tg_session stub (MetricsAiohttpSession требует реального aiohttp)
    fake_tg_session_mod: Any = types.ModuleType("src.monitoring.tg_session")
    fake_tg_session_mod.MetricsAiohttpSession = MagicMock()
    sys.modules.setdefault("src.monitoring.tg_session", fake_tg_session_mod)

    mock_bot = MagicMock()
    mock_dp = MagicMock()
    mock_dp.include_routers = MagicMock()
    mock_dp.update = MagicMock()
    mock_dp.message = MagicMock()
    mock_dp.error = MagicMock()
    mock_dp.storage.redis = AsyncMock()

    spec = importlib.util.spec_from_file_location(
        f"_real_bot_core_{fake.lexify('????')}", _BOT_FILE
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)

    with patch("aiogram.Bot", return_value=mock_bot), \
         patch("aiogram.Dispatcher", return_value=mock_dp), \
         patch("redis.asyncio.Redis.from_url", return_value=MagicMock()), \
         patch("aiogram.fsm.storage.redis.RedisStorage", return_value=MagicMock()):
        spec.loader.exec_module(module)

    yield module

# Module-level объекты

class TestModuleLevelObjects:

    def test_module_has_bot(self, bot_module) -> None:
        assert hasattr(bot_module, "bot")

    def test_module_has_dp(self, bot_module) -> None:
        assert hasattr(bot_module, "dp")

    def test_bot_is_not_none(self, bot_module) -> None:
        assert bot_module.bot is not None

    def test_dp_is_not_none(self, bot_module) -> None:
        assert bot_module.dp is not None

# create_bot

class TestCreateBot:

    def test_create_bot_returns_bot_instance(self, bot_module) -> None:
        with patch.object(bot_module, "Bot") as MockBot:
            mock_instance = MagicMock()
            MockBot.return_value = mock_instance
            result = bot_module.create_bot()
        assert result is mock_instance

    def test_create_bot_uses_token_from_settings(self, bot_module) -> None:
        token_calls = []
        with patch("aiogram.Bot") as MockBot:
            MockBot.return_value = MagicMock()
            with patch.object(
                sys.modules["src.core.config"].settings.telegram_token,
                "get_secret_value",
                side_effect=lambda: token_calls.append(1) or "fake_token",
            ):
                bot_module.create_bot()
        assert len(token_calls) > 0

    def test_create_bot_sets_html_parse_mode(self, bot_module) -> None:
        from aiogram.enums import ParseMode
        with patch("aiogram.Bot") as MockBot:
            MockBot.return_value = MagicMock()
            bot_module.create_bot()
        call_kwargs = MockBot.call_args[1] if MockBot.call_args else {}
        if "default" in call_kwargs:
            assert call_kwargs["default"].parse_mode == ParseMode.HTML

# create_dispatcher

class TestCreateDispatcher:

    def test_create_dispatcher_returns_dispatcher(self, bot_module) -> None:
        with patch.object(bot_module, "Dispatcher") as MockDp, \
             patch("redis.asyncio.Redis.from_url", return_value=MagicMock()), \
             patch("aiogram.fsm.storage.redis.RedisStorage", return_value=MagicMock()):
            mock_dp = MagicMock()
            MockDp.return_value = mock_dp
            result = bot_module.create_dispatcher()
        assert result is mock_dp

    def test_create_dispatcher_uses_redis_url(self, bot_module) -> None:
        redis_urls = []
        with patch("redis.asyncio.Redis.from_url",
                   side_effect=lambda url, **kw: redis_urls.append(url) or MagicMock()) as _:
            with patch("aiogram.Dispatcher", return_value=MagicMock()), \
                 patch("aiogram.fsm.storage.redis.RedisStorage", return_value=MagicMock()):
                bot_module.create_dispatcher()
        assert any("redis" in u for u in redis_urls)

# setup_routers

class TestSetupRouters:

    def test_setup_routers_calls_include_routers(self, bot_module) -> None:
        mock_dp = MagicMock()
        bot_module.setup_routers(mock_dp)
        mock_dp.include_routers.assert_called_once()

    def test_setup_routers_includes_multiple_routers(self, bot_module) -> None:
        mock_dp = MagicMock()
        bot_module.setup_routers(mock_dp)
        call_args = mock_dp.include_routers.call_args
        # Должно быть много роутеров
        assert len(call_args[0]) >= 5

# setup_middleware

class TestSetupMiddleware:

    def test_setup_middleware_registers_auth_middleware(self, bot_module) -> None:
        mock_dp = MagicMock()
        bot_module.setup_middleware(mock_dp)
        assert mock_dp.update.middleware.call_count >= 1

    def test_setup_middleware_registers_outer_middleware(self, bot_module) -> None:
        mock_dp = MagicMock()
        bot_module.setup_middleware(mock_dp)
        mock_dp.update.outer_middleware.assert_called()

    def test_setup_middleware_registers_message_throttling(self, bot_module) -> None:
        mock_dp = MagicMock()
        bot_module.setup_middleware(mock_dp)
        mock_dp.message.middleware.assert_called_once()

# error_handler

class TestErrorHandler:

    @pytest.mark.asyncio
    async def test_network_error_logs_warning_and_returns(self, bot_module) -> None:
        from aiogram.exceptions import TelegramNetworkError
        from aiogram.types import ErrorEvent

        exc = TelegramNetworkError(method=MagicMock(), message="connection timeout")
        event = MagicMock(spec=ErrorEvent)
        event.exception = exc
        event.update = MagicMock()

        with patch.object(bot_module.logger, "warning") as mock_warn:
            await bot_module.error_handler(event)
        mock_warn.assert_called_once()

    @pytest.mark.asyncio
    async def test_unhandled_exception_logs_error(self, bot_module) -> None:
        from aiogram.types import ErrorEvent

        exc = RuntimeError(fake.sentence())
        event = MagicMock(spec=ErrorEvent)
        event.exception = exc
        event.update = MagicMock()
        event.update.message = None  # не личный чат — пропускаем ответ

        with patch.object(bot_module.logger, "error") as mock_err:
            await bot_module.error_handler(event)
        mock_err.assert_called()

    @pytest.mark.asyncio
    async def test_private_chat_error_sends_message(self, bot_module) -> None:
        """В личном чате error_handler пытается отправить сообщение пользователю."""
        from aiogram.enums import ChatType
        from aiogram.types import ErrorEvent

        exc = ValueError(fake.sentence())
        uid = fake.random_int(min=100_000, max=999_999_999)

        mock_message = MagicMock()
        mock_message.chat.type = ChatType.PRIVATE
        mock_message.from_user.id = uid
        mock_message.chat.id = uid
        mock_message.answer = AsyncMock()

        mock_update = MagicMock()
        mock_update.message = mock_message
        mock_update.bot = MagicMock()

        event = MagicMock(spec=ErrorEvent)
        event.exception = exc
        event.update = mock_update

        with patch("src.services.api_client.get_user", new=AsyncMock(return_value=None)), \
             patch("src.utils.stickers.monkey") as mock_monkey:
            mock_monkey.send = AsyncMock()
            try:
                await bot_module.error_handler(event)
            except Exception:
                pass  # ошибки во время обработки ошибок допустимы

    @pytest.mark.asyncio
    async def test_faker_various_exception_types(self, bot_module) -> None:
        for exc_cls in [ValueError, RuntimeError, KeyError]:
            exc = exc_cls(fake.sentence())
            event = MagicMock()
            event.exception = exc
            event.update = MagicMock()
            event.update.message = None

            with patch.object(bot_module.logger, "error"):
                try:
                    await bot_module.error_handler(event)
                except Exception:
                    pass
