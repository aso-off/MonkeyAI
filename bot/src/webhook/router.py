import asyncio

from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request

from src.core.bot import bot, dp
from src.core.config import settings
from src.monitoring.prometheus import tg_updates_total, tg_webhook_requests_total

router = APIRouter()


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    secret = settings.webhook_secret.get_secret_value()
    if x_telegram_bot_api_secret_token != secret:
        tg_webhook_requests_total.labels("403").inc()
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    update = Update(**data)
    update_type = update.event_type or "unknown"
    tg_updates_total.labels(update_type).inc()
    tg_webhook_requests_total.labels("200").inc()
    asyncio.create_task(dp.feed_update(bot=bot, update=update))
    return {"ok": True}
