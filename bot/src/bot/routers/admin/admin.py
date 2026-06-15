import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.config import settings
from src.utils.admin import require_admin
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _admin_panel_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("status", lang), callback_data="admin_status", style="primary", icon_custom_emoji_id="6039630677182254664")],
        [
            InlineKeyboardButton(text=t("restart_button", lang), callback_data="admin_restart", style="primary", icon_custom_emoji_id="6030657343744644592"),
            InlineKeyboardButton(text=t("system", lang), callback_data="admin_system", style="primary", icon_custom_emoji_id="6044356915029348425"),
        ],
        [InlineKeyboardButton(text=t("moderation", lang), callback_data="admin_moderation", style="primary", icon_custom_emoji_id="6032850693348399258")],
        [InlineKeyboardButton(text=t("whitelist_management", lang), callback_data="admin_whitelist", style="primary", icon_custom_emoji_id="6032609071373226027")],
        [InlineKeyboardButton(text=t("back", lang), callback_data="back_to_start", icon_custom_emoji_id="5960671702059848143")],
    ])


@router.message(Command("admin"), StateFilter("*"))
async def cmd_admin(message: Message, language: str, db_user=None) -> None:
    if message.from_user is None:
        return
    is_admin = (db_user is not None and db_user.is_admin) or (message.from_user.id in settings.admin_ids)
    if not is_admin:
        return
    await message.answer(t("admin_welcome", language), reply_markup=_admin_panel_keyboard(language))


@router.callback_query(F.data == "admin_panel", StateFilter("*"))
async def cb_admin_panel(query: CallbackQuery, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text(t("admin_welcome", language), reply_markup=_admin_panel_keyboard(language))