"""
Тесты для api/src/core/logger.py.

Стратегия: загружаем реальный модуль через importlib, патча Path.mkdir
(чтобы не создавать /app/logs на диске) и TimedRotatingFileHandler
(чтобы не открывать реальный файл). После загрузки тестируем всё напрямую.
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

_API_SRC = Path(__file__).resolve().parents[2] / "src"
_LOGGER_FILE = _API_SRC / "core" / "logger.py"

# Фикстура загрузки

@pytest.fixture(scope="module")
def logger_module():
    """
    Загружаем реальный logger.py, блокируя:
    - Path.mkdir            → не создаём /app/logs
    - TimedRotatingFileHandler → не открываем файл логов
    Собираем ссылки на добавленные хэндлеры, чтобы очистить их после.
    """
    added_handlers: list[logging.Handler] = []
    original_add = logging.Logger.addHandler

    def _tracking_add(self, handler):
        added_handlers.append(handler)
        original_add(self, handler)

    spec = importlib.util.spec_from_file_location(
        f"_real_api_logger_{fake.lexify('????')}", _LOGGER_FILE
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)

    mock_file_handler = mock.MagicMock(spec=logging.Handler)
    mock_file_handler.level = logging.DEBUG

    with mock.patch.object(Path, "mkdir"):
        with mock.patch(
            "logging.handlers.TimedRotatingFileHandler",
            return_value=mock_file_handler,
        ):
            with mock.patch.object(logging.Logger, "addHandler", _tracking_add):
                spec.loader.exec_module(module)

    yield module

    # Очистка: убираем хэндлеры, добавленные нашим тестом
    root = logging.getLogger()
    for h in added_handlers:
        try:
            root.removeHandler(h)
        except Exception:
            pass

# _setup()

class TestSetup:

    def test_module_has_logger_attribute(self, logger_module) -> None:
        assert hasattr(logger_module, "logger")

    def test_logger_is_logging_logger(self, logger_module) -> None:
        assert isinstance(logger_module.logger, logging.Logger)

    def test_logger_named_api(self, logger_module) -> None:
        assert logger_module.logger.name == "api"

    def test_setup_returns_logger(self, logger_module) -> None:
        """_setup() вызывается при загрузке и возвращает logger с именем 'api'."""
        with mock.patch.object(Path, "mkdir"):
            with mock.patch("logging.handlers.TimedRotatingFileHandler",
                            return_value=mock.MagicMock(spec=logging.Handler)):
                result = logger_module._setup()
        assert result.name == "api"

    def test_log_level_default_info(self, logger_module) -> None:
        with mock.patch.dict("os.environ", {"LOG_LEVEL": "INFO"}):
            with mock.patch.object(Path, "mkdir"):
                with mock.patch("logging.handlers.TimedRotatingFileHandler",
                                return_value=mock.MagicMock(spec=logging.Handler)):
                    logger_module._setup()
        assert logging.getLogger().level == logging.INFO

    def test_log_level_debug_from_env(self, logger_module) -> None:
        with mock.patch.dict("os.environ", {"LOG_LEVEL": "DEBUG"}):
            with mock.patch.object(Path, "mkdir"):
                with mock.patch("logging.handlers.TimedRotatingFileHandler",
                                return_value=mock.MagicMock(spec=logging.Handler)):
                    logger_module._setup()
        assert logging.getLogger().level == logging.DEBUG

    def test_noisy_loggers_silenced(self, logger_module) -> None:
        """openai, httpx, asyncio, sqlalchemy — должны быть WARNING или выше."""
        for name in ("openai", "httpx", "asyncio", "sqlalchemy.engine"):
            assert logging.getLogger(name).level == logging.WARNING

    def test_excepthook_replaced(self, logger_module) -> None:
        assert sys.excepthook is logger_module._handle_unhandled

# _NoHealthFilter

class TestNoHealthFilter:

    def _make_record(self, message: str) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        return record

    def test_health_path_filtered_out(self, logger_module) -> None:
        """Сообщения содержащие /health должны фильтроваться."""
        with mock.patch.object(Path, "mkdir"):
            with mock.patch("logging.handlers.TimedRotatingFileHandler",
                            return_value=mock.MagicMock(spec=logging.Handler)):
                logger_module._setup()

        # Получаем фильтр с root logger
        root = logging.getLogger()
        health_filters = [f for f in root.filters if hasattr(f, "filter")]
        if not health_filters:
            pytest.skip("Фильтр не найден на root-логгере")

        f = cast(logging.Filter, health_filters[-1])
        assert f.filter(self._make_record("GET /health HTTP/1.1 200")) is False

    def test_non_health_path_passes(self, logger_module) -> None:
        root = logging.getLogger()
        health_filters = [f for f in root.filters if hasattr(f, "filter")]
        if not health_filters:
            pytest.skip("Фильтр не найден на root-логгере")

        f = cast(logging.Filter, health_filters[-1])
        msg = f"POST /chat/complete {fake.random_int()} OK"
        assert f.filter(self._make_record(msg)) is True

    def test_faker_random_messages_pass(self, logger_module) -> None:
        root = logging.getLogger()
        health_filters = [f for f in root.filters if hasattr(f, "filter")]
        if not health_filters:
            pytest.skip("Фильтр не найден на root-логгере")

        f = cast(logging.Filter, health_filters[-1])
        for _ in range(5):
            msg = fake.sentence()
            assert f.filter(self._make_record(msg)) is True

# _handle_unhandled

class TestHandleUnhandled:

    def test_keyboard_interrupt_calls_original_excepthook(self, logger_module) -> None:
        """KeyboardInterrupt должен уходить в стандартный excepthook."""
        with mock.patch.object(sys, "__excepthook__") as mock_hook:
            logger_module._handle_unhandled(KeyboardInterrupt, KeyboardInterrupt(), None)
        mock_hook.assert_called_once()

    def test_regular_exception_logs_critical(self, logger_module) -> None:
        """Обычное исключение → logger.critical()."""
        with mock.patch.object(logger_module.logger, "critical") as mock_critical:
            try:
                raise ValueError(fake.sentence())
            except ValueError:
                import sys as _sys
                exc = _sys.exc_info()
                logger_module._handle_unhandled(*exc)
        mock_critical.assert_called_once()

    def test_runtime_error_logs_critical(self, logger_module) -> None:
        error_msg = fake.sentence()
        with mock.patch.object(logger_module.logger, "critical") as mock_critical:
            try:
                raise RuntimeError(error_msg)
            except RuntimeError:
                import sys as _sys
                logger_module._handle_unhandled(*_sys.exc_info())
        call_args = mock_critical.call_args[0]
        assert "Unhandled exception" in call_args[0]
