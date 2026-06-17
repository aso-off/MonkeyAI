import asyncio
import logging
from pathlib import Path

import httpx
import yaml
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.bot.states.admin import WhitelistStates
from src.core import auth_state
from src.core.config import settings
from src.services import api_client as api
from src.utils.admin import require_admin
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()

USER_IDS_PATH = Path("/app/configs/user-ids.yml")
_SUPERADMIN_ID = settings.admin_ids[0] if settings.admin_ids else None

# Async file helpers (run in thread to avoid blocking the event loop)

def _read_user_ids() -> dict:
    if USER_IDS_PATH.exists():
        return yaml.safe_load(USER_IDS_PATH.read_text(encoding="utf-8")) or {}
    return {"admin_user_ids": [], "allowed_user_ids": []}


def _write_user_ids(data: dict) -> None:
    USER_IDS_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


async def _load_user_ids() -> dict:
    return await asyncio.to_thread(_read_user_ids)


async def _save_user_ids(data: dict) -> None:
    await asyncio.to_thread(_write_user_ids, data)

# Keyboard / text builders

def _whitelist_keyboard(lang: str, wl: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("whitelist_mode", lang) + (" ✅" if wl else ""),
            callback_data="set_access_mode|whitelist",
            icon_custom_emoji_id="5778570255555105942",
        )],
        [InlineKeyboardButton(
            text=t("open_mode", lang) + (" ✅" if not wl else ""),
            callback_data="set_access_mode|open",
            icon_custom_emoji_id="6037496202990194718",
        )],
        [InlineKeyboardButton(text=t("manage_users", lang), callback_data="manage_users", style="primary", icon_custom_emoji_id="6032609071373226027")],
        [InlineKeyboardButton(text=t("back_to_admin", lang), callback_data="admin_panel", icon_custom_emoji_id="5960671702059848143")],
    ])


async def _whitelist_text(lang: str) -> str:
    data = await _load_user_ids()
    admin_count = len(data.get("admin_user_ids", []))
    allowed_count = len(data.get("allowed_user_ids", []))
    wl = settings.whitelist_mode
    current_mode = t("mode_whitelist", lang) if wl else t("mode_open", lang)
    description = t("whitelist_mode_description" if wl else "open_mode_description", lang)
    return (
        f"{t('whitelist_management_title', lang)}\n\n"
        f"{t('current_access_mode', lang)} {current_mode}\n\n"
        f"{t('whitelist_stats', lang).format(admin_count, allowed_count)}\n\n"
        f"{description}"
    )


def _manage_users_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("add_allowed_user", lang), callback_data="user_action|add_user", style="primary", icon_custom_emoji_id="5774022692642492953"),
            InlineKeyboardButton(text=t("remove_allowed_user", lang), callback_data="user_action|remove_user", style="primary", icon_custom_emoji_id="5774077015388852135"),
        ],
        [
            InlineKeyboardButton(text=t("add_admin", lang), callback_data="user_action|add_admin", style="primary", icon_custom_emoji_id="6033108709213736873"),
            InlineKeyboardButton(text=t("remove_admin", lang), callback_data="user_action|remove_admin", style="primary", icon_custom_emoji_id="6039522349517115015"),
        ],
        [InlineKeyboardButton(text=t("view_users_list", lang), callback_data="user_action|view_list", style="primary", icon_custom_emoji_id="6034969813032374911")],
        [InlineKeyboardButton(text=t("back_to_whitelist", lang), callback_data="admin_whitelist", icon_custom_emoji_id="5960671702059848143")],
    ])


def _cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("cancel_operation", lang), callback_data="cancel_user_operation", style="danger", icon_custom_emoji_id="5774077015388852135")]
    ])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_whitelist", StateFilter("*"))
async def cb_admin_whitelist(query: CallbackQuery, state: FSMContext, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return
    await state.clear()
    await query.answer()
    if not isinstance(query.message, Message):
        return
    text = await _whitelist_text(language)
    await query.message.edit_text(text, reply_markup=_whitelist_keyboard(language, settings.whitelist_mode))


@router.callback_query(F.data.startswith("set_access_mode|"), StateFilter("*"))
async def cb_set_access_mode(query: CallbackQuery, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return

    if not isinstance(query.message, Message):
        return
    mode = (query.data or "").split("|")[1]
    is_whitelist = mode == "whitelist"
    settings.whitelist_mode = is_whitelist
    logger.info("Access mode changed to '%s' by user %s", mode, query.from_user.id)

    mode_text = t("mode_whitelist" if is_whitelist else "mode_open", language)
    await query.answer(t("access_mode_changed", language).format(mode_text), show_alert=True)
    text = await _whitelist_text(language)
    await query.message.edit_text(text, reply_markup=_whitelist_keyboard(language, is_whitelist))


@router.callback_query(F.data == "manage_users", StateFilter("*"))
async def cb_manage_users(query: CallbackQuery, state: FSMContext, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return
    await state.clear()
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text(t("user_management_title", language), reply_markup=_manage_users_keyboard(language))


@router.callback_query(F.data.startswith("user_action|"), StateFilter("*"))
async def cb_user_action(query: CallbackQuery, state: FSMContext, language: str, db_user=None) -> None:
    if not await require_admin(query, language, db_user=db_user):
        return

    if not isinstance(query.message, Message):
        return
    action = (query.data or "").split("|")[1]

    if action in ("add_admin", "remove_admin") and query.from_user.id != _SUPERADMIN_ID:
        await query.answer(t("superadmin_only", language), show_alert=True)
        return

    if action == "view_list":
        data = await _load_user_ids()
        admins = data.get("admin_user_ids", [])
        allowed = data.get("allowed_user_ids", [])
        admin_list = "\n".join(f"• {i}" for i in admins) or t("no_admins", language)
        allowed_list = "\n".join(f"• {i}" for i in allowed) or t("no_allowed_users", language)
        text = (
            f"{t('users_list_title', language)}\n\n"
            f"🔐 {t('admins_list', language)}\n{admin_list}\n\n"
            f"✅ {t('allowed_users_list', language)}\n{allowed_list}"
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("back_to_user_management", language), callback_data="manage_users", icon_custom_emoji_id="5960671702059848143")]
        ])
        await query.answer()
        await query.message.edit_text(text, reply_markup=back_kb)
        return

    prompts = {
        "add_user": "enter_user_id_to_add",
        "remove_user": "enter_user_id_to_remove",
        "add_admin": "enter_user_id_to_add_admin",
        "remove_admin": "enter_user_id_to_remove_admin",
    }
    await state.set_state(WhitelistStates.waiting_for_user_id)
    await state.update_data(action=action)
    await query.answer()
    await query.message.edit_text(t(prompts[action], language), reply_markup=_cancel_keyboard(language))


@router.callback_query(F.data == "cancel_user_operation", StateFilter("*"))
async def cb_cancel_user_operation(query: CallbackQuery, state: FSMContext, language: str) -> None:
    await state.clear()
    await query.answer(t("operation_cancelled", language))
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text(t("user_management_title", language), reply_markup=_manage_users_keyboard(language))


@router.message(WhitelistStates.waiting_for_user_id)
async def msg_user_id_input(message: Message, state: FSMContext, language: str) -> None:
    if message.from_user is None:
        return
    raw = (message.text or "").strip()

    if not raw.isdigit() or not (8 <= len(raw) <= 13):
        await message.answer(t("invalid_user_id", language))
        return

    target_id = int(raw)
    fsm_data = await state.get_data()
    action: str = fsm_data.get("action", "")
    await state.clear()

    cfg = await _load_user_ids()
    admins: list = cfg.get("admin_user_ids", [])
    allowed: list = cfg.get("allowed_user_ids", [])

    if action == "add_user":
        if target_id in allowed:
            await message.answer(t("user_already_in_list", language))
        else:
            allowed.append(target_id)
            if target_id not in settings.allowed_user_ids:
                settings.allowed_user_ids.append(target_id)
            await _save_user_ids({"admin_user_ids": admins, "allowed_user_ids": allowed})
            await auth_state.reload()
            await api.set_user_whitelisted(target_id, True)
            logger.info("User %s added to whitelist by %s", target_id, message.from_user.id)
            await message.answer(t("user_added_successfully", language))

    elif action == "remove_user":
        if target_id in admins:
            await message.answer(t("cannot_remove_admin", language))
        elif target_id not in allowed:
            await message.answer(t("user_not_in_list", language))
        else:
            allowed.remove(target_id)
            if target_id in settings.allowed_user_ids:
                settings.allowed_user_ids.remove(target_id)
            await _save_user_ids({"admin_user_ids": admins, "allowed_user_ids": allowed})
            await auth_state.reload()
            try:
                await api.set_user_whitelisted(target_id, False)
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise
                logger.debug("User %s not in DB, skipping DB update", target_id)
            logger.info("User %s removed from whitelist by %s", target_id, message.from_user.id)
            await message.answer(t("user_removed_successfully", language))

    elif action == "add_admin":
        if target_id not in allowed:
            await message.answer(t("admin_not_in_whitelist", language))
        elif target_id in admins:
            await message.answer(t("admin_already_in_list", language))
        else:
            admins.append(target_id)
            if target_id not in settings.admin_ids:
                settings.admin_ids.append(target_id)
            await _save_user_ids({"admin_user_ids": admins, "allowed_user_ids": allowed})
            await auth_state.reload()
            await api.set_user_admin(target_id, True)
            logger.info("User %s promoted to admin by %s", target_id, message.from_user.id)
            await message.answer(t("admin_added_successfully", language))

    elif action == "remove_admin":
        if target_id not in admins:
            await message.answer(t("admin_not_in_list", language))
        else:
            admins.remove(target_id)
            if target_id in settings.admin_ids:
                settings.admin_ids.remove(target_id)
            await _save_user_ids({"admin_user_ids": admins, "allowed_user_ids": allowed})
            await auth_state.reload()
            try:
                await api.set_user_admin(target_id, False)
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise
                logger.debug("User %s not in DB, skipping DB update", target_id)
            logger.info("Admin %s removed by %s", target_id, message.from_user.id)
            await message.answer(t("admin_removed_successfully", language))
