import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.core.config import settings
from src.utils import rich_panel as rp
from src.utils.formatting import format_date
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _about_md(lang: str) -> str:
    try:
        creation_dt = datetime.strptime(settings.bot_creation_date, "%Y-%m-%d")
    except ValueError:
        creation_dt = None

    cap_lines = t("about_capabilities", lang).splitlines()
    cap_head = cap_lines[0] if cap_lines else ""
    cap_items = [ln.lstrip("•").strip() for ln in cap_lines[1:] if ln.strip()]

    return rp.join(
        rp.heading(t("about_title", lang), 2),
        t("about_description", lang),
        cap_head,
        rp.ul(cap_items),
        rp.divider(),
        rp.kv_block(
            [
                (t("version", lang), rp.code(settings.bot_version)),
                (t("creation_date", lang), format_date(creation_dt, lang)),
            ]
        ),
    )


def _about_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("back", lang), callback_data="back_to_start", icon_custom_emoji_id="5960671702059848143"
                )
            ]
        ]
    )


@router.message(Command("about"), StateFilter("*"))
async def cmd_about(message: Message, language: str) -> None:
    await rp.answer_panel(message, _about_md(language), reply_markup=_about_keyboard(language))


@router.callback_query(F.data == "about", StateFilter("*"))
async def cb_about(query: CallbackQuery, language: str) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await rp.edit_panel(query.message, _about_md(language), reply_markup=_about_keyboard(language))
