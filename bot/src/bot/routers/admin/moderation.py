import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.core.config import settings
from src.utils import rich_panel as rp
from src.utils.admin import require_admin
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _moderation_keyboard(lang: str) -> InlineKeyboardMarkup:
    enabled = settings.enable_content_moderation
    toggle_text = t("moderation_toggle", lang) if enabled else t("moderation_enable", lang)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data="toggle_moderation",
                    style="primary",
                    icon_custom_emoji_id="6030657343744644592",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("back_to_admin", lang),
                    callback_data="admin_panel",
                    icon_custom_emoji_id="5960671702059848143",
                )
            ],
        ]
    )


def _moderation_md(lang: str) -> str:
    enabled = settings.enable_content_moderation
    status = t("moderation_status_enabled" if enabled else "moderation_status_disabled", lang)
    return rp.join(
        rp.heading(t("moderation_settings_title", lang), 2),
        rp.kv(t("current_status", lang), rp.bold(status)),
        rp.quote(t("moderation_settings_help", lang)),
    )


@router.callback_query(F.data == "admin_moderation", StateFilter("*"))
async def cb_admin_moderation(query: CallbackQuery, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await rp.edit_panel(query.message, _moderation_md(language), reply_markup=_moderation_keyboard(language))


@router.callback_query(F.data == "toggle_moderation", StateFilter("*"))
async def cb_toggle_moderation(query: CallbackQuery, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return

    settings.enable_content_moderation = not settings.enable_content_moderation
    logger.info("Content moderation toggled: %s by user %s", settings.enable_content_moderation, query.from_user.id)

    status_key = "moderation_enabled" if settings.enable_content_moderation else "moderation_disabled"
    await query.answer(t("moderation_status_changed", language).format(t(status_key, language)))
    if not isinstance(query.message, Message):
        return
    await rp.edit_panel(query.message, _moderation_md(language), reply_markup=_moderation_keyboard(language))
