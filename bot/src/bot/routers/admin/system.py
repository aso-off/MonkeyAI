import json
import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.utils.admin import require_admin
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()

SYSTEM_INFO_KEY = "system_info"


def _back_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("back_to_admin", lang), callback_data="admin_panel", icon_custom_emoji_id="5960671702059848143")],
    ])


async def _get_cached_text(redis) -> str | None:
    cached = await redis.get(SYSTEM_INFO_KEY)
    if not cached:
        return None
    try:
        data = json.loads(cached)
        blocks = data.get("blocks", [])
        return "\n\n".join(blocks) if blocks else None
    except Exception:
        return None


@router.message(Command("system"), StateFilter("*"))
async def cmd_system(message: Message, language: str, db_user=None) -> None:
    if not await require_admin(message, language, db_user=db_user):
        return

    from src.core.bot import fsm_redis
    redis = fsm_redis()

    text = await _get_cached_text(redis)
    if not text:
        await message.answer(t("system_info_not_available", language))
        return

    await message.answer(text)


@router.callback_query(F.data == "admin_system", StateFilter("*"))
async def cb_admin_system(query: CallbackQuery, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return

    from src.core.bot import fsm_redis
    redis = fsm_redis()

    text = await _get_cached_text(redis)
    await query.answer()

    keyboard = _back_keyboard(language)
    if not text:
        text = t("system_info_not_available", language)

    if not isinstance(query.message, Message):
        return
    try:
        await query.message.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        if "message is not modified" not in str(e):
            logger.error(f"Error editing system info message: {e}")
            await query.message.answer(text, reply_markup=keyboard)