import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.core.config import settings
from src.services import api_client as api
from src.utils import rich_panel as rp
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _assistant_keyboard(lang: str, current_mode: str) -> InlineKeyboardMarkup:
    chat_modes: dict = settings.chat_modes
    skip_keys = {"default_modes", "premium_modes", "system_prompt", "mini_app_assistant", "mini_app_artist"}
    rows = []
    for mode_key, mode_info in chat_modes.items():
        if mode_key in skip_keys:
            continue
        name_template = mode_info.get("name", "")
        if name_template.startswith("{") and name_template.endswith("}"):
            name = t(name_template.strip("{}"), lang)
        else:
            name = name_template or mode_key
        label = name + (" ✅" if mode_key == current_mode else "")
        rows.append([InlineKeyboardButton(text=label, callback_data=f"set_chat_mode|{mode_key}")])
    rows.append(
        [
            InlineKeyboardButton(
                text=t("back_to_settings", lang),
                callback_data="profile_settings",
                icon_custom_emoji_id="5960671702059848143",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _assistant_md(lang: str, current_mode: str) -> str:
    mode_info = settings.chat_modes.get(current_mode, {})
    welcome_template = mode_info.get("welcome_message", "")
    if welcome_template.startswith("{") and welcome_template.endswith("}"):
        welcome = t(welcome_template.strip("{}"), lang)
    else:
        welcome = welcome_template
    sections = [rp.quote(welcome)] if welcome else []
    sections.append(f"{t('assistant_selection', lang)}:")
    return rp.join(*sections)


@router.message(Command("mode"), StateFilter("*"))
async def cmd_mode(message: Message, language: str, db_user=None) -> None:
    if db_user is None:
        await rp.answer_panel(message, rp.bold(t("profile_error", language)))
        return
    await rp.answer_panel(
        message,
        _assistant_md(language, db_user.current_chat_mode),
        reply_markup=_assistant_keyboard(language, db_user.current_chat_mode),
    )


@router.callback_query(F.data == "profile_assistant", StateFilter("*"))
async def cb_profile_assistant(query: CallbackQuery, language: str, db_user=None) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if db_user is None:
        await rp.edit_panel(query.message, rp.bold(t("profile_error", language)))
        return
    try:
        await rp.edit_panel(
            query.message,
            _assistant_md(language, db_user.current_chat_mode),
            reply_markup=_assistant_keyboard(language, db_user.current_chat_mode),
        )
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("set_chat_mode|"), StateFilter("*"))
async def cb_set_chat_mode(query: CallbackQuery, language: str, db_user=None) -> None:
    mode_key = (query.data or "").split("|", 1)[1]
    if mode_key not in settings.chat_modes:
        await query.answer()
        return

    if db_user is None or db_user.current_chat_mode == mode_key:
        await query.answer()
        return
    await api.update_user(query.from_user.id, current_chat_mode=mode_key)
    # Switch mode without resetting its memory; create dialog only if missing.
    await api.ensure_dialog(query.from_user.id)

    logger.info("User %s changed chat mode to %s", query.from_user.id, mode_key)
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await rp.edit_panel(
        query.message,
        _assistant_md(language, mode_key),
        reply_markup=_assistant_keyboard(language, mode_key),
    )
