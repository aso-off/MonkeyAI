import json
import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.utils import rich_panel as rp
from src.utils.admin import require_admin
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()

SYSTEM_INFO_KEY = "system_info"


def _back_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("back_to_admin", lang),
                    callback_data="admin_panel",
                    icon_custom_emoji_id="5960671702059848143",
                )
            ],
        ]
    )


async def _get_data(redis) -> dict | None:
    cached = await redis.get(SYSTEM_INFO_KEY)
    if not cached:
        return None
    try:
        return json.loads(cached)
    except Exception:
        return None


def _render_md(data: dict, lang: str) -> str | None:
    containers = data.get("containers") or []
    host = data.get("host")
    sections: list[str] = []

    if containers:
        ordered = sorted(containers, key=lambda c: c.get("cpu_percent", 0.0), reverse=True)
        rows = [
            [
                str(c.get("name", "")).removeprefix("monkey_"),
                f"{c.get('cpu_percent', 0.0):.1f}%",
                f"{c.get('ram_usage', 0.0):.2f}/{c.get('ram_limit', 0.0):.2f}",
                f"{c.get('net_rx', '')}/{c.get('net_tx', '')}",
            ]
            for c in ordered
        ]
        sections.append(rp.heading(t("docker_title", lang), 2))
        sections.append(rp.table(["Container", "CPU", "RAM", "NET I/O"], rows))

    if host:
        host_row = [
            [
                host.get("hostname", ""),
                f"{host.get('cpu_percent', 0.0):.1f}%",
                f"{host.get('ram_usage', 0.0):.2f}/{host.get('ram_total', 0.0):.2f}",
                f"{host.get('disk_usage', 0.0):.2f}/{host.get('disk_total', 0.0):.2f}",
            ]
        ]
        sections.append(rp.heading(t("host_title", lang), 2))
        sections.append(rp.table(["Host", "CPU", "RAM", "DISK"], host_row))

    return rp.join(*sections) if sections else None


@router.message(Command("system"), StateFilter("*"))
async def cmd_system(message: Message, language: str, db_user=None) -> None:
    if not await require_admin(message, language, db_user=db_user):
        return

    from src.core.bot import fsm_redis

    redis = fsm_redis()

    data = await _get_data(redis)
    md = _render_md(data, language) if data else None
    if not md:
        await rp.answer_panel(message, rp.bold(t("system_info_not_available", language)))
        return

    await rp.answer_panel(message, md)


@router.callback_query(F.data == "admin_system", StateFilter("*"))
async def cb_admin_system(query: CallbackQuery, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return

    from src.core.bot import fsm_redis

    redis = fsm_redis()

    data = await _get_data(redis)
    await query.answer()

    md = (_render_md(data, language) if data else None) or rp.bold(t("system_info_not_available", language))

    if not isinstance(query.message, Message):
        return
    await rp.edit_panel(query.message, md, reply_markup=_back_keyboard(language))
