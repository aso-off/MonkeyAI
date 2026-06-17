from __future__ import annotations

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.methods.base import TelegramMethod

from src.monitoring.prometheus import tg_api_request_duration_seconds, tg_api_requests_total


class MetricsAiohttpSession(AiohttpSession):
    async def __call__(self, bot, method: TelegramMethod, timeout=None):
        method_name = type(method).__name__
        with tg_api_request_duration_seconds.labels(method_name).time():
            try:
                result = await super().__call__(bot, method, timeout=timeout)
                tg_api_requests_total.labels(method_name, "true").inc()
                return result
            except Exception:
                tg_api_requests_total.labels(method_name, "false").inc()
                raise
