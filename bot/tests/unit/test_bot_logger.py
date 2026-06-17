"""
Тесты для bot/src/core/logger.py.

Покрываем:
- _setup()             — настройка логгера, уровни, фильтры
- _NoiseFilter.filter  — /webhook, /health фильтруются
- _handle_unhandled    — KeyboardInterrupt vs обычные исключения
- Async-функции        — log_user_action, log_api_call, log_system_event,
                          log_exception, log_performance
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import cast
from unittest import mock

import pytest
from faker import Faker

fake = Faker()
Faker.seed(42)

_BOT_SRC = Path(__file__).resolve().parents[2] / "src"
_LOGGER_FILE = _BOT_SRC / "core" / "logger.py"

# Фикстура загрузки

@pytest.fixture(scope="module")
def bot_logger_module():
    """
    Загружаем реальный bot/src/core/logger.py:
    - Path.mkdir блокируется (не создаём /app/logs)
    - TimedRotatingFileHandler заменяется mock
    Хэндлеры очищаем после тестов.
    """
    added_handlers: list[logging.Handler] = []
    original_add = logging.Logger.addHandler

    def _track_add(self, handler):
        added_handlers.append(handler)
        original_add(self, handler)

    spec = importlib.util.spec_from_file_location(
        f"_real_bot_logger_{fake.lexify('????')}", _LOGGER_FILE
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    mock_fh = mock.MagicMock(spec=logging.Handler)
    mock_fh.level = logging.DEBUG

    with mock.patch.object(Path, "mkdir"):
        with mock.patch("logging.handlers.TimedRotatingFileHandler", return_value=mock_fh):
            with mock.patch.object(logging.Logger, "addHandler", _track_add):
                spec.loader.exec_module(module)

    yield module

    root = logging.getLogger()
    for h in added_handlers:
        try:
            root.removeHandler(h)
        except Exception:
            pass

# _setup()

class TestBotSetup:

    def test_module_has_logger_attribute(self, bot_logger_module) -> None:
        assert hasattr(bot_logger_module, "logger")

    def test_logger_is_logging_logger(self, bot_logger_module) -> None:
        assert isinstance(bot_logger_module.logger, logging.Logger)

    def test_logger_named_bot(self, bot_logger_module) -> None:
        assert bot_logger_module.logger.name == "bot"

    def test_setup_returns_bot_logger(self, bot_logger_module) -> None:
        with mock.patch.object(Path, "mkdir"):
            with mock.patch("logging.handlers.TimedRotatingFileHandler",
                            return_value=mock.MagicMock(spec=logging.Handler)):
                result = bot_logger_module._setup()
        assert result.name == "bot"

    def test_noisy_loggers_silenced(self, bot_logger_module) -> None:
        for name in ("aiogram", "openai", "httpx", "asyncio"):
            assert logging.getLogger(name).level == logging.WARNING

    def test_excepthook_replaced(self, bot_logger_module) -> None:
        assert sys.excepthook is bot_logger_module._handle_unhandled

    def test_log_level_from_env(self, bot_logger_module) -> None:
        with mock.patch.dict("os.environ", {"LOG_LEVEL": "WARNING"}):
            with mock.patch.object(Path, "mkdir"):
                with mock.patch("logging.handlers.TimedRotatingFileHandler",
                                return_value=mock.MagicMock(spec=logging.Handler)):
                    bot_logger_module._setup()
        assert logging.getLogger().level == logging.WARNING

# _NoiseFilter

class TestNoiseFilter:

    def _record(self, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="uvicorn.access", level=logging.INFO,
            pathname="", lineno=0, msg=msg, args=(), exc_info=None,
        )

    def _get_filter(self, bot_logger_module):
        uvicorn_logger = logging.getLogger("uvicorn.access")
        filters = [f for f in uvicorn_logger.filters if hasattr(f, "filter")]
        if not filters:
            pytest.skip("_NoiseFilter не найден на uvicorn.access")
        return cast(logging.Filter, filters[-1])

    def test_webhook_path_filtered(self, bot_logger_module) -> None:
        f = self._get_filter(bot_logger_module)
        assert f.filter(self._record("POST /webhook HTTP/1.1 200")) is False

    def test_health_path_filtered(self, bot_logger_module) -> None:
        f = self._get_filter(bot_logger_module)
        assert f.filter(self._record("GET /health HTTP/1.1 200")) is False

    def test_normal_path_passes(self, bot_logger_module) -> None:
        f = self._get_filter(bot_logger_module)
        assert f.filter(self._record("GET /users/123 HTTP/1.1 200")) is True

    def test_faker_random_messages_pass(self, bot_logger_module) -> None:
        f = self._get_filter(bot_logger_module)
        for _ in range(5):
            msg = fake.sentence()
            assert f.filter(self._record(msg)) is True

    def test_message_with_both_keywords_filtered(self, bot_logger_module) -> None:
        f = self._get_filter(bot_logger_module)
        assert f.filter(self._record("POST /webhook/health 200")) is False

# _handle_unhandled

class TestBotHandleUnhandled:

    def test_keyboard_interrupt_calls_original_excepthook(self, bot_logger_module) -> None:
        with mock.patch.object(sys, "__excepthook__") as mock_hook:
            bot_logger_module._handle_unhandled(KeyboardInterrupt, KeyboardInterrupt(), None)
        mock_hook.assert_called_once()

    def test_value_error_logs_critical(self, bot_logger_module) -> None:
        with mock.patch.object(bot_logger_module.logger, "critical") as mock_crit:
            try:
                raise ValueError(fake.sentence())
            except ValueError:
                bot_logger_module._handle_unhandled(*sys.exc_info())
        mock_crit.assert_called_once()

    def test_runtime_error_message_contains_exception_info(self, bot_logger_module) -> None:
        msg = fake.sentence()
        with mock.patch.object(bot_logger_module.logger, "critical") as mock_crit:
            try:
                raise RuntimeError(msg)
            except RuntimeError:
                bot_logger_module._handle_unhandled(*sys.exc_info())
        call_msg = mock_crit.call_args[0][0]
        assert "Unhandled exception" in call_msg

# Async log functions

class TestAsyncLogFunctions:

    @pytest.mark.asyncio
    async def test_log_user_action_user(self, bot_logger_module) -> None:
        user_id = fake.random_int(min=100_000, max=999_999_999)
        action = fake.sentence()
        with mock.patch.object(bot_logger_module.logger, "info") as mock_info:
            await bot_logger_module.log_user_action(user_id, action, is_admin=False)
        call_msg = mock_info.call_args[0][0]
        assert "USER" in call_msg
        assert str(user_id) in call_msg

    @pytest.mark.asyncio
    async def test_log_user_action_admin(self, bot_logger_module) -> None:
        user_id = fake.random_int(min=100_000, max=999_999_999)
        action = fake.sentence()
        with mock.patch.object(bot_logger_module.logger, "info") as mock_info:
            await bot_logger_module.log_user_action(user_id, action, is_admin=True)
        call_msg = mock_info.call_args[0][0]
        assert "ADMIN" in call_msg

    @pytest.mark.asyncio
    async def test_log_api_call_without_duration(self, bot_logger_module) -> None:
        api_name = fake.word()
        status = fake.random_element(["ok", "error", "timeout"])
        with mock.patch.object(bot_logger_module.logger, "info") as mock_info:
            await bot_logger_module.log_api_call(api_name, status)
        call_msg = mock_info.call_args[0][0]
        assert api_name in call_msg
        assert status in call_msg

    @pytest.mark.asyncio
    async def test_log_api_call_with_duration(self, bot_logger_module) -> None:
        api_name = fake.word()
        duration = fake.pyfloat(min_value=0.01, max_value=10.0, right_digits=3)
        with mock.patch.object(bot_logger_module.logger, "info") as mock_info:
            await bot_logger_module.log_api_call(api_name, "ok", duration=duration)
        call_msg = mock_info.call_args[0][0]
        assert "s" in call_msg  # duration в секундах

    @pytest.mark.asyncio
    async def test_log_system_event_default_level(self, bot_logger_module) -> None:
        event = fake.sentence()
        with mock.patch.object(bot_logger_module.logger, "log") as mock_log:
            await bot_logger_module.log_system_event(event)
        mock_log.assert_called_once()
        assert mock_log.call_args[0][1] == event

    @pytest.mark.asyncio
    async def test_log_system_event_custom_level(self, bot_logger_module) -> None:
        event = fake.sentence()
        with mock.patch.object(bot_logger_module.logger, "log") as mock_log:
            await bot_logger_module.log_system_event(event, level=logging.WARNING)
        assert mock_log.call_args[0][0] == logging.WARNING

    @pytest.mark.asyncio
    async def test_log_exception_basic(self, bot_logger_module) -> None:
        exc = ValueError(fake.sentence())
        with mock.patch.object(bot_logger_module.logger, "error") as mock_error:
            await bot_logger_module.log_exception(exc)
        mock_error.assert_called_once()
        call_msg = mock_error.call_args[0][0]
        assert "ValueError" in call_msg

    @pytest.mark.asyncio
    async def test_log_exception_with_context(self, bot_logger_module) -> None:
        exc = RuntimeError(fake.sentence())
        context = fake.word()
        with mock.patch.object(bot_logger_module.logger, "error") as mock_error:
            await bot_logger_module.log_exception(exc, context=context)
        call_msg = mock_error.call_args[0][0]
        assert context in call_msg

    @pytest.mark.asyncio
    async def test_log_performance(self, bot_logger_module) -> None:
        operation = fake.word()
        duration = fake.pyfloat(min_value=0.001, max_value=5.0, right_digits=3)
        with mock.patch.object(bot_logger_module.logger, "info") as mock_info:
            await bot_logger_module.log_performance(operation, duration)
        call_msg = mock_info.call_args[0][0]
        assert "PERF" in call_msg
        assert operation in call_msg

    @pytest.mark.asyncio
    async def test_faker_batch_user_actions(self, bot_logger_module) -> None:
        """Несколько вызовов log_user_action с faker-данными не падают."""
        with mock.patch.object(bot_logger_module.logger, "info"):
            for _ in range(5):
                uid = fake.random_int(min=100_000, max=999_999_999)
                action = fake.sentence()
                await bot_logger_module.log_user_action(uid, action)
