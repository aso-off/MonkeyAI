import logging
import time
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.core.config import settings
from src.services import api_client as api
from src.utils import rich_panel as rp
from src.utils.admin import require_admin
from src.utils.formatting import format_date, format_uptime
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()

REDIS_KEY_START_TIME = "bot_start_time"
REDIS_KEY_ALIVE = "bot_alive"


def _status_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("back_to_admin", lang),
                    callback_data="admin_panel",
                    icon_custom_emoji_id="5960671702059848143",
                )
            ]
        ]
    )


async def _build_status_md(lang: str) -> str:
    from src.core.bot import fsm_redis  # ленивый импорт - избегает circular import с core.bot

    redis = fsm_redis()

    # Uptime из Redis
    raw_start = await redis.get(REDIS_KEY_START_TIME)
    if raw_start:
        elapsed = time.time() - float(raw_start)
        uptime_str = format_uptime(elapsed, lang)
    else:
        uptime_str = "—"

    # Telegram API - сам факт что мы отвечаем означает что всё ок
    telegram_ok = True

    # API сервис
    api_ping = await api.api_health_check()
    api_ok = api_ping is not None

    # БД + статистика пользователей
    db_ok = True
    user_count = "—"
    active_user_count = "—"
    try:
        stats = await api.get_users_stats()
        user_count = stats.all_users_count
        active_user_count = stats.active_users_count
    except Exception:
        logger.exception("DB/API check failed")
        db_ok = False

    # OpenAI - проверяем что ключ задан
    openai_ok = bool(settings.openai_api_key)

    all_ok = telegram_ok and api_ok and db_ok and openai_ok
    summary = t("status_summary_ok", lang) if all_ok else t("status_summary_issues", lang)

    try:
        creation_dt = datetime.strptime(settings.bot_creation_date, "%Y-%m-%d")
    except ValueError:
        creation_dt = None

    api_label = t("status_api", lang)
    if api_ok:
        api_label = f"{api_label} {rp.code(f'{api_ping} ms')}"

    return rp.join(
        rp.heading(f"📊 {summary}", 2),
        rp.checklist(
            [
                (t("status_telegram", lang), telegram_ok),
                (api_label, api_ok),
                (t("status_database", lang), db_ok),
                (t("status_openai", lang), openai_ok),
            ]
        ),
        rp.divider(),
        rp.heading(f"📈 {t('status_process', lang)}", 3),
        rp.kv_block(
            [
                (t("users", lang), user_count),
                (t("status_active_users", lang), active_user_count),
                (t("uptime", lang), uptime_str),
                (t("version", lang), settings.bot_version),
                (t("creation_date", lang), format_date(creation_dt, lang)),
            ]
        ),
    )


@router.message(Command("status"), StateFilter("*"))
async def cmd_status(message: Message, language: str, db_user=None) -> None:
    if not await require_admin(message, language, db_user=db_user):
        return
    msg = await message.answer(f"⏳ {t('status_checking', language)}")
    md = await _build_status_md(language)
    await rp.edit_panel(msg, md, reply_markup=_status_keyboard(language))


@router.callback_query(F.data == "admin_status", StateFilter("*"))
async def cb_admin_status(query: CallbackQuery, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text(f"⏳ {t('status_checking', language)}", reply_markup=query.message.reply_markup)
    md = await _build_status_md(language)
    await rp.edit_panel(query.message, md, reply_markup=_status_keyboard(language))
