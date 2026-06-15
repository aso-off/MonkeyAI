import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, StateFilter
from aiogram.types import FSInputFile, Message, CallbackQuery

from src.core.config import settings
from src.utils.localization import t

_VIDEO_PATH = Path("/app/static/help_group_chat.mp4")

logger = logging.getLogger(__name__)
router = Router()


def _help_text(is_admin: bool, lang: str) -> str:
    text = (
        f"{t('help_title', lang)}\n\n"
        f"{t('help_start', lang)}\n"
        f"{t('help_new', lang)}\n"
        f"{t('help_mode', lang)}\n"
        f"{t('help_model', lang)}\n"
        f"{t('help_retry', lang)}\n"
        f"{t('help_balance', lang)}\n"
        f"{t('help_settings', lang)}\n"
        f"{t('help_language', lang)}\n"
        f"{t('help_profile', lang)}\n"
        f"{t('help_ping', lang)}\n"
        f"{t('help_about', lang)}\n"
        f"{t('help_cancel', lang)}"
    )
    if is_admin:
        text += (
            f"\n\n{t('help_admin_title', lang)}\n\n"
            f"{t('help_admin', lang)}\n"
            f"{t('help_status', lang)}\n"
            f"{t('help_restart', lang)}\n"
            f"{t('help_system', lang)}"
        )
    return text


@router.message(Command("help"), StateFilter("*"))
async def cmd_help(message: Message, language: str, db_user=None) -> None:
    if message.from_user is None:
        return
    is_admin = (db_user is not None and db_user.is_admin) or (message.from_user.id in settings.admin_ids)
    await message.answer(_help_text(is_admin, language))


@router.callback_query(F.data == "help", StateFilter("*"))
async def cb_help(query: CallbackQuery, language: str, db_user=None) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    is_admin = (db_user is not None and db_user.is_admin) or (query.from_user.id in settings.admin_ids)
    await query.message.edit_text(_help_text(is_admin, language))


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