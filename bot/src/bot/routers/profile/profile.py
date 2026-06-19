import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.core.config import settings
from src.utils import rich_panel as rp
from src.utils.formatting import format_date
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()

_CODE_SPAN = re.compile(r"`([^`]+)`")


def _profile_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("settings", lang),
                    callback_data="profile_settings",
                    style="primary",
                    icon_custom_emoji_id="6032742198179532882",
                ),
                InlineKeyboardButton(
                    text=t("stats", lang),
                    callback_data="profile_stats",
                    style="primary",
                    icon_custom_emoji_id="5936143551854285132",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("balance", lang),
                    callback_data="show_balance",
                    style="primary",
                    icon_custom_emoji_id="5904462880941545555",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("back", lang), callback_data="back_to_start", icon_custom_emoji_id="5960671702059848143"
                )
            ],
        ]
    )


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


def _kv_line(line: str) -> str:
    line = _CODE_SPAN.sub(r"<code>\1</code>", line)
    label, sep, value = line.partition(": ")
    return f"{rp.bold(label + ':')} {value}" if sep else line


def _build_profile_md(user, lang: str) -> str:
    if user is None:
        return rp.bold(t("profile_error", lang))

    status = t("status_admin", lang) if user.id in settings.admin_ids else t("status_user", lang)
    reg_date = format_date(user.first_seen, lang)
    formatted = t("profile_info", lang).format(user.id, _lang_label(user.language, lang), reg_date, status)
    head, _, body = formatted.partition("\n")
    return rp.join(rp.heading(head, 2), "\n".join(_kv_line(ln) for ln in body.splitlines()))


@router.message(Command("profile"), StateFilter("*"))
async def cmd_profile(message: Message, language: str, db_user=None) -> None:
    await rp.answer_panel(message, _build_profile_md(db_user, language), reply_markup=_profile_keyboard(language))


@router.callback_query(F.data == "profile", StateFilter("*"))
async def cb_profile(query: CallbackQuery, language: str, db_user=None) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await rp.edit_panel(query.message, _build_profile_md(db_user, language), reply_markup=_profile_keyboard(language))
