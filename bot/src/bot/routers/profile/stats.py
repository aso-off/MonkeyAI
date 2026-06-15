import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.services import api_client as api
from src.utils.formatting import format_date
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _stats_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("back_to_profile", lang), callback_data="profile", icon_custom_emoji_id="5960671702059848143")]
    ])


@router.callback_query(F.data == "profile_stats", StateFilter("*"))
async def cb_profile_stats(query: CallbackQuery, language: str) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return

    profile = await api.get_user_full(query.from_user.id)

    if profile is None:
        await query.message.edit_text(t("profile_error", language), reply_markup=_stats_keyboard(language))
        return

    reg_date = format_date(profile.user.first_seen, language)
    text = (
        f"{t('profile_stats_title', language)}\n\n"
        f"{t('message_count', language)} {profile.message_count}\n"
        f"{t('registration_date', language)} {reg_date}"
    )
    await query.message.edit_text(text, reply_markup=_stats_keyboard(language))