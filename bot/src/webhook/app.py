import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from fastapi.responses import JSONResponse
from fastapi.responses import Response

from src.core.bot import bot, dp
from src.core.config import settings
from src.core.logger import logger
from src.webhook.router import router as webhook_router
from src.monitoring.heartbeat import _heartbeat, REDIS_KEY_START_TIME, REDIS_KEY_ALIVE, ALIVE_TTL
from src.monitoring.system_info import _system_info_loop
from src.monitoring.restart import check_restart_notification
from src.bot.commands import _set_commands


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting...")

    await _set_commands()

    await bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.webhook_secret.get_secret_value(),
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "my_chat_member"],
    )
    logger.info(f"Webhook set: {settings.webhook_url}")

    me = await bot.get_me()
    from src.bot.routers.chat import set_bot_meta

    set_bot_meta(me.username, me.id)

    redis = dp.storage.redis
    await redis.set(REDIS_KEY_START_TIME, str(time.time()))
    await redis.set(REDIS_KEY_ALIVE, "1", ex=ALIVE_TTL)
    await redis.delete("restart_in_progress")
    logger.info("Redis start_time and alive keys set")

    from src.core import auth_state
    auth_state.reload_sync()
    logger.info(f"Auth state loaded: admins={auth_state._admin_ids}, whitelist={settings.whitelist_mode}")

    heartbeat_task = asyncio.create_task(_heartbeat(redis))
    system_info_task = asyncio.create_task(_system_info_loop(redis))

    await check_restart_notification(bot, redis)

    yield

    heartbeat_task.cancel()
    system_info_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    try:
        await system_info_task
    except asyncio.CancelledError:
        pass

    await bot.delete_webhook()
    logger.info("Webhook deleted")

    from src.services.api_client import close_client
    await close_client()
    logger.info("Bot stopped")


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
    app.include_router(webhook_router)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/webhook_info")
    async def webhook_info() -> dict:
        info = await bot.get_webhook_info()
        return info.model_dump()

    return app