from src.core.logger import logger


async def check_restart_notification(bot, redis) -> None:
    """On startup, check for a pending restart notification and edit the message."""
    try:
        chat_id_b = await redis.get("restart:chat_id")
        message_id_b = await redis.get("restart:message_id")
        lang_b = await redis.get("restart:lang")

        if not chat_id_b or not message_id_b:
            return

        # Atomically claim the notification (NX = only if key does not exist)
        claimed = await redis.set("restart_notified", "1", ex=60, nx=True)
        if not claimed:
            return

        from aiogram.types import InputRichMessage

        from src.core.config import settings
        from src.utils import rich_panel as rp
        from src.utils.localization import t

        lang = lang_b.decode() if lang_b else "ru"
        source_b = await redis.get("restart:source")
        source = source_b.decode() if source_b else "cmd"

        keyboard = None
        if source == "panel":
            from src.bot.routers.admin.admin import _admin_panel_keyboard

            keyboard = _admin_panel_keyboard(lang)

        md = rp.join(rp.bold(t("restart_done", lang)), rp.kv(t("version", lang), rp.code(settings.bot_version)))
        chat_id, message_id = int(chat_id_b), int(message_id_b)

        try:
            if settings.enable_rich_messages:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    rich_message=InputRichMessage(html=md),
                    reply_markup=keyboard,
                )
            else:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=rp.to_legacy_html(md),
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
        except Exception as e:
            if "not modified" not in str(e):
                logger.warning(f"Could not edit restart message: {e}")
                try:
                    await bot.send_message(
                        chat_id=chat_id, text=rp.to_legacy_html(md), parse_mode="HTML", reply_markup=keyboard
                    )
                except Exception:
                    pass

        await redis.delete("restart:chat_id", "restart:message_id", "restart:lang", "restart:source")
        await redis.delete("restart_in_progress")
    except Exception as e:
        logger.error(f"check_restart_notification error: {e}")
