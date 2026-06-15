import logging

import asyncssh
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, Message

from src.core.config import settings
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


async def _do_restart(redis) -> None:
    """SSH into the host and run docker compose restart."""
    ssh = settings.ssh_connection
    project_path = ssh.get("project_path", "/root/bot")
    try:
        async with asyncssh.connect(
            ssh["hostname"],
            username=ssh.get("username"),
            password=ssh.get("password"),
            known_hosts=None,
            connect_timeout=ssh.get("timeout", 30),
        ) as conn:
            result = await conn.run(f'cd "{project_path}" && docker compose restart')
            if result.returncode == 0:
                logger.info("Containers restarted successfully")
                # restart_in_progress будет удалён в check_restart_notification после старта
            else:
                logger.error(f"Restart error: {result.stderr}")
                await redis.delete("restart_in_progress")
    except Exception as e:
        logger.error(f"SSH restart error: {e}")
        await redis.delete("restart_in_progress")


@router.message(Command("restart"), StateFilter("*"))
async def cmd_restart(message: Message, language: str) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        return

    from src.core.bot import fsm_redis
    redis = fsm_redis()

    ssh = settings.ssh_connection
    if not ssh.get("hostname"):
        await message.answer(t("ssh_not_configured", language))
        return

    lock = await redis.get("restart_in_progress")
    if lock:
        await message.answer(t("restart_already_in_progress", language))
        return

    await redis.setex("restart_in_progress", 300, "1")

    reply = await message.answer(
        t("restart_in_progress_msg", language),
    )

    try:
        await redis.setex("restart:chat_id", 3600, str(message.from_user.id))
        await redis.setex("restart:message_id", 3600, str(reply.message_id))
        await redis.setex("restart:lang", 3600, language)
        await redis.setex("restart:source", 3600, "cmd")
        await redis.delete("restart_notified")
    except Exception as e:
        logger.error(f"Error saving restart data: {e}")
        await redis.delete("restart_in_progress")
        return

    await _do_restart(redis)


@router.callback_query(F.data == "admin_restart", StateFilter("*"))
async def cb_admin_restart(query: CallbackQuery, language: str) -> None:
    if query.from_user.id not in settings.admin_ids:
        await query.answer(t("access_denied", language), show_alert=True)
        return

    from src.core.bot import fsm_redis
    redis = fsm_redis()

    ssh = settings.ssh_connection
    if not ssh.get("hostname"):
        await query.answer(t("ssh_not_configured", language), show_alert=True)
        return

    lock = await redis.get("restart_in_progress")
    if lock:
        await query.answer(t("restart_already_in_progress", language), show_alert=True)
        return

    await redis.setex("restart_in_progress", 300, "1")
    await query.answer()
    if not isinstance(query.message, Message):
        return

    # Сохраняем данные в Redis ДО редактирования сообщения (как в Oblivion)
    try:
        await redis.setex("restart:chat_id", 3600, str(query.from_user.id))
        await redis.setex("restart:message_id", 3600, str(query.message.message_id))
        await redis.setex("restart:lang", 3600, language)
        await redis.setex("restart:source", 3600, "panel")
        await redis.delete("restart_notified")
    except Exception as e:
        logger.error(f"Error saving restart data: {e}")
        await redis.delete("restart_in_progress")
        return

    try:
        # Сохраняем существующую клавиатуру — текст меняется, кнопки остаются
        await query.message.edit_text(
            t("restart_in_progress_msg", language),
            reply_markup=query.message.reply_markup,
        )
    except Exception as e:
        logger.error(f"Error editing restart message: {e}")

    await _do_restart(redis)