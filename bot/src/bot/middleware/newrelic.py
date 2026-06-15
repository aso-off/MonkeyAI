import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from src.monitoring.newrelic_helpers import (
    nr_transaction_name,
    nr_add_custom_parameter,
    nr_notice_error,
)

logger = logging.getLogger(__name__)


class NewRelicMiddleware(BaseMiddleware):
    """Outer middleware for aiogram updates to automatically instrument transactions in New Relic.

    Categorizes incoming updates (commands, callback queries, texts, voice messages, etc.)
    and assigns descriptive transaction names so they don't all group under 'POST /webhook'.
    Also records custom attributes (e.g. user_id) and captures errors.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        # Determine the update type and a specific name for the transaction
        tx_name = "update/unknown"
        user_id = None
        username = None
        chat_id = None

        try:
            if event.message:
                msg = event.message
                if msg.from_user:
                    user_id = msg.from_user.id
                    username = msg.from_user.username
                if msg.chat:
                    chat_id = msg.chat.id

                if msg.text:
                    if msg.text.startswith("/"):
                        # Extract the command (e.g. /start)
                        cmd = msg.text.split()[0]
                        tx_name = f"command{cmd}"
                    else:
                        tx_name = "message/text"
                elif msg.voice:
                    tx_name = "message/voice"
                elif msg.photo:
                    tx_name = "message/photo"
                elif msg.document:
                    tx_name = "message/document"
                elif msg.sticker:
                    tx_name = "message/sticker"
                else:
                    tx_name = "message/other"

            elif event.callback_query:
                cb = event.callback_query
                if cb.from_user:
                    user_id = cb.from_user.id
                    username = cb.from_user.username
                if cb.message:
                    chat_id = cb.message.chat.id

                # Group callback queries by their prefix/action (e.g. select_model:gpt-4 -> callback/select_model)
                data_prefix = "unknown"
                if cb.data:
                    data_prefix = cb.data.split(":")[0]
                tx_name = f"callback/{data_prefix}"

            elif event.my_chat_member:
                member = event.my_chat_member
                if member.from_user:
                    user_id = member.from_user.id
                tx_name = "my_chat_member"

            else:
                # Fallback to update type (e.g., edited_message, inline_query)
                tx_name = f"update/{event.event_type}"

        except Exception as e:
            logger.warning("Error parsing update info in NewRelicMiddleware: %s", e)

        # Set transaction name and custom attributes
        nr_transaction_name(tx_name)
        if user_id is not None:
            nr_add_custom_parameter("telegram_user_id", user_id)
        if username is not None:
            nr_add_custom_parameter("telegram_username", username)
        if chat_id is not None:
            nr_add_custom_parameter("telegram_chat_id", chat_id)

        try:
            return await handler(event, data)
        except Exception:
            # Notice the exception in New Relic and re-raise it
            nr_notice_error()
            raise