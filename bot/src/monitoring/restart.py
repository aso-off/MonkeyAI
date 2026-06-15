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

        from src.utils.localization import t

        lang = lang_b.decode() if lang_b else "ru"
        source_b = await redis.get("restart:source")
        source = source_b.decode() if source_b else "cmd"

        keyboard = None
        if source == "panel":
            from src.bot.routers.admin.admin import _admin_panel_keyboard
            keyboard = _admin_panel_keyboard(lang)

        try:
            await bot.edit_message_text(
                chat_id=int(chat_id_b),
                message_id=int(message_id_b),
                text=t("restart_done", lang),
                reply_markup=keyboard,
            )
        except Exception as e:
            if "message is not modified" not in str(e):
                logger.warning(f"Could not edit restart message: {e}")
                try:
                    await bot.send_message(
                        chat_id=int(chat_id_b),
                        text=t("restart_done", lang),
                        reply_markup=keyboard,
                    )
                except Exception:
                    pass

        await redis.delete("restart:chat_id", "restart:message_id", "restart:lang", "restart:source")
        await redis.delete("restart_in_progress")
    except Exception as e:
        logger.error(f"check_restart_notification error: {e}")