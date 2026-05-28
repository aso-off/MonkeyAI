import logging
import os
import sys
import traceback
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def _setup() -> logging.Logger:
    log_dir = Path("/app/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M")

    file_handler = TimedRotatingFileHandler(
        log_dir / "bot.log",
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

    for name in ("aiogram", "openai", "httpx", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)

    class _NoiseFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            return "/webhook" not in msg and "/health" not in msg

    logging.getLogger("uvicorn.access").addFilter(_NoiseFilter())

    return logging.getLogger("bot")


def _handle_unhandled(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger.critical("Unhandled exception:\n" + "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))


logger = _setup()
sys.excepthook = _handle_unhandled


async def log_user_action(user_id: int, action: str, is_admin: bool = False) -> None:
    prefix = "ADMIN" if is_admin else "USER"
    logger.info(f"{prefix} {user_id}: {action}")


async def log_api_call(api: str, status: str, duration: float | None = None) -> None:
    msg = f"API:{api} | {status}"
    if duration is not None:
        msg += f" | {duration:.2f}s"
    logger.info(msg)


async def log_system_event(event: str, level: int = logging.INFO) -> None:
    logger.log(level, event)


async def log_exception(e: Exception, context: str | None = None) -> None:
    msg = f"{type(e).__name__}: {e}"
    if context:
        msg = f"{context} | {msg}"
    logger.error(f"{msg}\n{traceback.format_exc()}")


async def log_performance(operation: str, duration: float) -> None:
    logger.info(f"PERF:{operation} | {duration:.2f}s")