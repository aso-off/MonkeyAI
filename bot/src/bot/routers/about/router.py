import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message

from src.core.config import settings
from src.utils.formatting import format_date
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _about_text(lang: str) -> str:
    try:
        creation_dt = datetime.strptime(settings.bot_creation_date, "%Y-%m-%d")
    except ValueError:
        creation_dt = None
    return (
        f"<b>{t('about_title', lang)}</b>\n\n"
        f"{t('about_description', lang)}\n\n"
        f"{t('about_capabilities', lang)}\n\n"
        f"<b>{t('version', lang)}</b> {settings.bot_version}\n"
        f"<b>{t('creation_date', lang)}</b> {format_date(creation_dt, lang)}"
    )


def _about_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("back", lang), callback_data="back_to_start", icon_custom_emoji_id="5960671702059848143")]
    ])


@router.message(Command("about"), StateFilter("*"))
async def cmd_about(message: Message, language: str) -> None:
    await message.answer(_about_text(language), reply_markup=_about_keyboard(language))


@router.callback_query(F.data == "about", StateFilter("*"))
async def cb_about(query: CallbackQuery, language: str) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text(_about_text(language), reply_markup=_about_keyboard(language))