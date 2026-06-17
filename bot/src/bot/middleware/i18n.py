import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from src.services import api_client as api
from src.utils.localization import _SUPPORTED_LANGS, resolve_lang

logger = logging.getLogger(__name__)


class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        tg_lang = user.language_code if user else None

        language = resolve_lang(tg_lang)  # default: auto-detect

        if user is not None:
            try:
                # Reuse db_user from AuthMiddleware if available (avoids extra API call)
                db_user = data.get("db_user")
                if db_user is None:
                    db_user = await api.get_user(user.id)
                if db_user is not None:
                    lang = db_user.language
                    if lang in _SUPPORTED_LANGS:
                        language = lang
                    else:
                        language = resolve_lang(tg_lang)
            except Exception:
                logger.warning("Failed to fetch language for user %d", user.id, exc_info=True)

        data["language"] = language
        return await handler(event, data)
