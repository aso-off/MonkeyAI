import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, User

from src.core import auth_state
from src.core.config import settings
from src.services import api_client as api

logger = logging.getLogger(__name__)


def _chat_id_for_user(event: TelegramObject, user_id: int) -> int:
    """Prefer real chat_id from the update; private chats fall back to user_id."""
    if isinstance(event, Update):
        if event.message is not None:
            return event.message.chat.id
        if event.callback_query is not None and event.callback_query.message is not None:
            return event.callback_query.message.chat.id
    return user_id


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")

        if user is None:
            return await handler(event, data)

        # отказ чужим до похода в БД
        if settings.whitelist_mode:
            cached = await auth_state.is_allowed_cached(user.id)
            allowed = cached if cached is not None else auth_state.is_allowed(user.id)
            if not allowed:
                logger.debug("Access denied: user_id=%d username=@%s", user.id, user.username)
                return None

        try:
            db_user = await api.get_or_create_user(
                user_id=user.id,
                chat_id=_chat_id_for_user(event, user.id),
                username=user.username or "",
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                language="system",
            )
        except Exception:
            logger.warning("Auth: could not fetch/create user %d", user.id, exc_info=True)
            db_user = None

        data["db_user"] = db_user
        return await handler(event, data)
