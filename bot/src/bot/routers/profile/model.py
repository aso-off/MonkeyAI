import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.core.config import settings
from src.services import api_client as api
from src.utils import rich_panel as rp
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _model_keyboard(lang: str, current_model: str) -> InlineKeyboardMarkup:
    available = settings.models.get("available_text_models", [])
    models_info = settings.models.get("info", {})
    rows = []
    for key in available:
        if key not in models_info:
            continue
        name = models_info[key].get("name", key)
        label = name + (" ✅" if key == current_model else "")
        rows.append([InlineKeyboardButton(text=label, callback_data=f"set_model|{key}")])
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


def _model_md(lang: str, current_model: str) -> str:
    models_info = settings.models.get("info", {})
    desc_key = "model_description_" + current_model.replace("-", "_").replace(".", "_")

    scores: dict = models_info.get(current_model, {}).get("scores", {})
    rows = [
        [t(score_key.strip("{}"), lang), "🟢" * score_value + "⚪️" * (5 - score_value)]
        for score_key, score_value in scores.items()
    ]

    sections = [t(desc_key, lang)]
    if rows:
        sections.append(rp.table([], rows))
    sections.append(f"{t('model_selection', lang)}:")
    return rp.join(*sections)


@router.message(Command("model"), StateFilter("*"))
async def cmd_model(message: Message, language: str, db_user=None) -> None:
    if message.from_user is None:
        return
    if db_user is None:
        await rp.answer_panel(message, rp.bold(t("profile_error", language)))
        return
    current = db_user.current_model
    available = settings.models.get("available_text_models", [])
    if current not in available and available:
        current = available[0]
        await api.update_user(message.from_user.id, current_model=current)
    await rp.answer_panel(
        message,
        _model_md(language, current),
        reply_markup=_model_keyboard(language, current),
    )


@router.callback_query(F.data == "profile_model", StateFilter("*"))
async def cb_profile_model(query: CallbackQuery, language: str, db_user=None) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if db_user is None:
        await rp.edit_panel(query.message, rp.bold(t("profile_error", language)))
        return
    current = db_user.current_model
    available = settings.models.get("available_text_models", [])
    if current not in available and available:
        current = available[0]
        await api.update_user(query.from_user.id, current_model=current)
    await rp.edit_panel(
        query.message,
        _model_md(language, current),
        reply_markup=_model_keyboard(language, current),
    )


@router.callback_query(F.data.startswith("set_model|"), StateFilter("*"))
async def cb_set_model(query: CallbackQuery, language: str, db_user=None) -> None:
    model_key = (query.data or "").split("|", 1)[1]
    available = settings.models.get("available_text_models", [])
    if model_key not in available:
        await query.answer()
        return

    if db_user is None or db_user.current_model == model_key:
        await query.answer()
        return
    await api.update_user(query.from_user.id, current_model=model_key)
    await api.start_new_dialog(query.from_user.id)

    logger.info("User %s changed model to %s", query.from_user.id, model_key)
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await rp.edit_panel(
        query.message,
        _model_md(language, model_key),
        reply_markup=_model_keyboard(language, model_key),
    )
