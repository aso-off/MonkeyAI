import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.config import settings
from src.utils.formatting import format_date
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _profile_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("settings", lang), callback_data="profile_settings", style="primary", icon_custom_emoji_id="6032742198179532882"),
            InlineKeyboardButton(text=t("stats", lang), callback_data="profile_stats", style="primary", icon_custom_emoji_id="5936143551854285132"),
        ],
        [InlineKeyboardButton(text=t("balance", lang), callback_data="show_balance", style="primary", icon_custom_emoji_id="5904462880941545555")],
        [InlineKeyboardButton(text=t("back", lang), callback_data="back_to_start", icon_custom_emoji_id="5960671702059848143")],
    ])


_LANG_DISPLAY: dict[str, str] = {
    "ru": "Русский",
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pl": "Polski",
    "pt": "Português",
    "tr": "Türkçe",
}


def _lang_label(code: str, lang: str) -> str:
    if code == "system":
        return t("language_system", lang)
    return _LANG_DISPLAY.get(code, code)


def _build_profile_text(user, lang: str) -> str:
    if user is None:
        return t("profile_error", lang)

    status = t("status_admin", lang) if user.id in settings.admin_ids else t("status_user", lang)
    reg_date = format_date(user.first_seen, lang)
    return t("profile_info", lang).format(user.id, _lang_label(user.language, lang), reg_date, status)


@router.message(Command("profile"), StateFilter("*"))
async def cmd_profile(message: Message, language: str, db_user=None) -> None:
    text = _build_profile_text(db_user, language)
    await message.answer(text, reply_markup=_profile_keyboard(language), parse_mode="Markdown")


@router.callback_query(F.data == "profile", StateFilter("*"))
async def cb_profile(query: CallbackQuery, language: str, db_user=None) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    text = _build_profile_text(db_user, language)
    await query.message.edit_text(text, reply_markup=_profile_keyboard(language), parse_mode="Markdown")