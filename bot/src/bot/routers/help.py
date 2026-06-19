import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, FSInputFile, Message
from src.core.config import settings
from src.utils import rich_panel as rp
from src.utils.localization import t

_VIDEO_PATH = Path("/app/static/help_group_chat.mp4")

logger = logging.getLogger(__name__)
router = Router()

_USER_CMD_KEYS = (
    "help_start",
    "help_new",
    "help_mode",
    "help_model",
    "help_retry",
    "help_balance",
    "help_settings",
    "help_language",
    "help_profile",
    "help_ping",
    "help_about",
    "help_cancel",
)
_ADMIN_CMD_KEYS = ("help_admin", "help_status", "help_restart", "help_system")


def _cmd_line(raw: str) -> str:
    cmd, sep, desc = raw.partition(" - ")
    return f"{rp.bold(cmd)} — {desc}" if sep else raw


def _help_md(is_admin: bool, lang: str) -> str:
    md = rp.join(
        rp.heading(t("help_title", lang), 2),
        rp.ul(_cmd_line(t(k, lang)) for k in _USER_CMD_KEYS),
    )
    if is_admin:
        admin_body = rp.ul(_cmd_line(t(k, lang)) for k in _ADMIN_CMD_KEYS)
        md = rp.join(md, rp.details(t("help_admin_title", lang), admin_body))
    return md


@router.message(Command("help"), StateFilter("*"))
async def cmd_help(message: Message, language: str, db_user=None) -> None:
    if message.from_user is None:
        return
    is_admin = (db_user is not None and db_user.is_admin) or (message.from_user.id in settings.admin_ids)
    await rp.answer_panel(message, _help_md(is_admin, language))


@router.callback_query(F.data == "help", StateFilter("*"))
async def cb_help(query: CallbackQuery, language: str, db_user=None) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    is_admin = (db_user is not None and db_user.is_admin) or (query.from_user.id in settings.admin_ids)
    await rp.edit_panel(query.message, _help_md(is_admin, language))


@router.message(Command("help_group_chat"), StateFilter("*"))
async def cmd_help_group_chat(message: Message, language: str, bot: Bot) -> None:
    if message.chat.type != ChatType.PRIVATE:
        return
    bot_info = await bot.get_me()
    text = t("help_group_chat_message", language).format("@" + (bot_info.username or ""))
    await message.answer(text, parse_mode="HTML")
    if _VIDEO_PATH.exists():
        await message.answer_video(
            FSInputFile(_VIDEO_PATH),
            caption=t("group_chat_help_caption", language),
        )
    else:
        logger.warning("help_group_chat video not found at %s", _VIDEO_PATH)
        await message.answer(t("group_chat_missing_video", language))
