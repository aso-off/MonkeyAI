import logging
import os
import sys
import traceback
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def _setup() -> logging.Logger:
    log_dir = Path(os.environ.get("MONKEY_LOG_DIR", "/app/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M")

    file_handler = TimedRotatingFileHandler(
        log_dir / "api.log",
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    for name in ("openai", "httpx", "asyncio", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)

    class _NoHealthFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "/health" not in record.getMessage()

    # Применяем и к root, и к uvicorn.access — uvicorn может добавить хэндлеры позже
    root.addFilter(_NoHealthFilter())
    logging.getLogger("uvicorn.access").addFilter(_NoHealthFilter())

    return logging.getLogger("api")


def _handle_unhandled(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger.critical(
        "Unhandled exception:\n%s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )


logger = _setup()
sys.excepthook = _handle_unhandled
