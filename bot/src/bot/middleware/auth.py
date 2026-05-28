import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, User

from src.core import auth_state
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

        is_admin = (db_user is not None and db_user.is_admin) or auth_state.is_admin(user.id)
        if is_admin:
            return await handler(event, data)

        from src.core.config import settings
        if not settings.whitelist_mode:
            return await handler(event, data)

        is_allowed = (db_user is not None and db_user.is_whitelisted) or auth_state.is_allowed(user.id)
        if is_allowed:
            return await handler(event, data)

        logger.debug("Access denied: user_id=%d username=@%s", user.id, user.username)
        return None