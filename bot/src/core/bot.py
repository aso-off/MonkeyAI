import logging
from collections.abc import Awaitable, Mapping
from typing import Any, Protocol, cast

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ErrorEvent
from redis.asyncio import Redis

from src.core.config import settings
from src.monitoring.tg_session import MetricsAiohttpSession

logger = logging.getLogger(__name__)

_Encodable = str | int | float | bytes


class RedisAsync(Protocol):
    """Async-вид клиента: redis-py типизирует методы как sync|async в одном классе."""

    def get(self, name: str) -> Awaitable[Any]: ...
    def set(self, name: str, value: _Encodable, *, ex: int | None = ..., nx: bool = ...) -> Awaitable[Any]: ...
    def setex(self, name: str, time: int, value: _Encodable) -> Awaitable[Any]: ...
    def delete(self, *names: str) -> Awaitable[int]: ...
    def exists(self, *names: str) -> Awaitable[int]: ...
    def expire(self, name: str, time: int) -> Awaitable[bool]: ...
    def ttl(self, name: str) -> Awaitable[int]: ...
    def incr(self, name: str, amount: int = ...) -> Awaitable[int]: ...
    def ping(self) -> Awaitable[Any]: ...
    def sadd(self, name: str, *values: _Encodable) -> Awaitable[int]: ...
    def srem(self, name: str, *values: _Encodable) -> Awaitable[int]: ...
    def sismember(self, name: str, value: _Encodable) -> Awaitable[bool]: ...
    def hset(
        self,
        name: str,
        key: _Encodable | None = ...,
        value: _Encodable | None = ...,
        mapping: Mapping[str, _Encodable] | None = ...,
    ) -> Awaitable[int]: ...
    def hgetall(self, name: str) -> Awaitable[dict[Any, Any]]: ...
    def pipeline(self, transaction: bool = ...) -> Any: ...


def create_bot() -> Bot:
    return Bot(
        token=settings.telegram_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=MetricsAiohttpSession(),
    )


def create_dispatcher() -> Dispatcher:
    redis = Redis.from_url(settings.redis_url)
    storage = RedisStorage(redis=redis)
    return Dispatcher(storage=storage)


def fsm_redis() -> RedisAsync:
    """Redis-клиент из FSM-хранилища (storage всегда RedisStorage)."""
    storage = cast(RedisStorage, dp.storage)
    return cast(RedisAsync, storage.redis)


def setup_routers(dp: Dispatcher) -> None:
    from src.bot.routers.about.router import router as about_router
    from src.bot.routers.admin.admin import router as admin_panel_router
    from src.bot.routers.admin.moderation import router as admin_moderation_router
    from src.bot.routers.admin.restart import router as admin_restart_router
    from src.bot.routers.admin.status import router as admin_status_router
    from src.bot.routers.admin.system import router as admin_system_router
    from src.bot.routers.admin.whitelist import router as admin_whitelist_router
    from src.bot.routers.chat import router as chat_router
    from src.bot.routers.help import router as help_router
    from src.bot.routers.profile.assistant import router as profile_assistant_router
    from src.bot.routers.profile.balance import router as profile_balance_router
    from src.bot.routers.profile.language import router as profile_language_router
    from src.bot.routers.profile.model import router as profile_model_router
    from src.bot.routers.profile.ping import router as profile_ping_router
    from src.bot.routers.profile.profile import router as profile_router
    from src.bot.routers.profile.settings import router as profile_settings_router
    from src.bot.routers.profile.stats import router as profile_stats_router
    from src.bot.routers.start import router as start_router
    from src.bot.routers.webapp import router as webapp_router

    dp.include_routers(
        start_router,
        help_router,
        chat_router,
        webapp_router,
        about_router,
        profile_router,
        profile_assistant_router,
        profile_language_router,
        profile_model_router,
        profile_settings_router,
        profile_balance_router,
        profile_stats_router,
        profile_ping_router,
        admin_panel_router,
        admin_moderation_router,
        admin_whitelist_router,
        admin_status_router,
        admin_system_router,
        admin_restart_router,
    )


def setup_middleware(dp: Dispatcher) -> None:
    from src.bot.middleware.auth import AuthMiddleware
    from src.bot.middleware.i18n import I18nMiddleware
    from src.bot.middleware.newrelic import NewRelicMiddleware
    from src.bot.middleware.throttling import ThrottlingMiddleware

    # New Relic регистрируется самым первым как outer middleware для отслеживания всех транзакций и ошибок
    dp.update.outer_middleware(NewRelicMiddleware())

    # Auth регистрируется первым → выполняется первым (outermost):
    #   получает db_user из БД и кладёт в data["db_user"]
    # I18n регистрируется вторым → выполняется вторым:
    #   берёт db_user из data без повторного запроса в БД
    dp.update.middleware(AuthMiddleware())
    dp.update.middleware(I18nMiddleware())
    dp.message.middleware(ThrottlingMiddleware())


async def error_handler(event: ErrorEvent) -> None:
    from aiogram.exceptions import TelegramNetworkError

    exc = event.exception
    update = event.update

    if isinstance(exc, TelegramNetworkError):
        logger.warning("Network error: %s", exc)
        return

    logger.error("Unhandled exception for update %s: %s", update, exc, exc_info=exc)

    try:
        if update.message and update.message.from_user and update.message.chat.type == "private":
            from src.services import api_client as api
            from src.utils.localization import t
            from src.utils.stickers import monkey

            user = await api.get_user(update.message.from_user.id)
            lang = user.language if user else "ru"

            bot = event.update.bot if hasattr(event.update, "bot") else None
            if bot:
                await monkey.send(bot, update.message.chat.id, "error")
            await update.message.answer(t("system_error", lang), parse_mode="HTML")
    except Exception as inner:
        logger.error("Error in error_handler fallback: %s", inner)


bot = create_bot()
dp = create_dispatcher()
setup_routers(dp)
setup_middleware(dp)
dp.error.register(error_handler)
