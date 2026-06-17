import asyncio
import logging
import time

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.bot.routers.profile.settings import _settings_keyboard
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()

_NUM_REQUESTS = 3
_REQUEST_INTERVAL = 0.2


async def _measure_ping_ms() -> float:
    from src.core.bot import bot  # ленивый импорт — избегает circular import с core.bot
    total = 0.0
    for i in range(_NUM_REQUESTS):
        start = time.perf_counter()
        await bot.get_me()
        total += max(0.0, (time.perf_counter() - start) * 1000)
        if i < _NUM_REQUESTS - 1:
            await asyncio.sleep(_REQUEST_INTERVAL)
    return max(0.01, total / _NUM_REQUESTS)


def _ping_result_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("back_to_settings", lang), callback_data="profile_settings", icon_custom_emoji_id="5960671702059848143")]
    ])


@router.message(Command("ping"), StateFilter("*"))
async def cmd_ping(message: Message, language: str) -> None:
    if message.from_user is None:
        return
    ms = await _measure_ping_ms()
    logger.debug("Ping for user %s: %.2f ms", message.from_user.id, ms)
    await message.answer(
        t("ping_response", language).format(ms),
        reply_markup=_ping_result_keyboard(language),
    )


@router.callback_query(F.data == "ping", StateFilter("*"))
async def cb_ping(query: CallbackQuery, language: str) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    ms = await _measure_ping_ms()
    logger.debug("Ping for user %s: %.2f ms", query.from_user.id, ms)

    await query.message.edit_text(
        f"{t('ping_response', language).format(ms)}\n\n{t('settings_prompt', language)}",
        reply_markup=_settings_keyboard(language),
    )
