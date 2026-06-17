import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("model_selection", lang), callback_data="profile_model", style="primary", icon_custom_emoji_id="6030400221232501136"),
            InlineKeyboardButton(text=t("assistant_selection", lang), callback_data="profile_assistant", style="primary", icon_custom_emoji_id="6032625495328165724"),
        ],
        [
            InlineKeyboardButton(text=t("change_language", lang), callback_data="profile_language", style="primary", icon_custom_emoji_id="5776233299424843260"),
            InlineKeyboardButton(text=t("ping", lang), callback_data="ping", style="primary", icon_custom_emoji_id="6030537810509828330"),
        ],
        [InlineKeyboardButton(text=t("back_to_profile", lang), callback_data="profile", icon_custom_emoji_id="5960671702059848143")],
    ])


@router.message(Command("settings"), StateFilter("*"))
async def cmd_settings(message: Message, language: str) -> None:
    await message.answer(t("settings_prompt", language), reply_markup=_settings_keyboard(language))


@router.callback_query(F.data == "profile_settings", StateFilter("*"))
async def cb_profile_settings(query: CallbackQuery, language: str) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text(t("settings_prompt", language), reply_markup=_settings_keyboard(language))
