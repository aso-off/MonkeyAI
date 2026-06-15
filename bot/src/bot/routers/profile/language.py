import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.services import api_client as api
from src.utils.localization import resolve_lang, t

logger = logging.getLogger(__name__)
router = Router()

# Fixed language options shown in the picker
_FIXED_LANGUAGES: dict[str, str] = {
    "ru": "Русский",
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pl": "Polski",
    "pt": "Português",
    "tr": "Türkçe",
}

# Keyboard layout: pairs displayed side-by-side
_LANGUAGE_PAIRS: list[list[tuple[str, str]]] = [
    [("en", "English"),  ("ru", "Русский")],
    [("de", "Deutsch"),  ("fr", "Français")],
    [("es", "Español"),  ("pt", "Português")],
    [("tr", "Türkçe"),   ("pl", "Polski")],
]


def _language_keyboard(effective_lang: str, db_lang: str, tg_lang_code: str | None) -> InlineKeyboardMarkup:
    """Строим keyboard выбора языка.

    effective_lang — resolved interface language for button labels.
    db_lang        — what is stored in DB ("ru", "en", ... or "system").
    tg_lang_code   — raw Telegram language_code (e.g. "uk", "en", "sv").
    """
    resolved = resolve_lang(tg_lang_code)
    resolved_label = resolved.upper()
    system_check = " ✅" if db_lang == "system" else ""

    rows = [
        [InlineKeyboardButton(
            text=f"{t('language_system', effective_lang)} ({resolved_label}){system_check}",
            callback_data="set_lang|system",
            icon_custom_emoji_id="5769403725898584391",
        )],
    ]

    for pair in _LANGUAGE_PAIRS:
        row = []
        for code, name in pair:
            check = " ✅" if db_lang == code else ""
            row.append(InlineKeyboardButton(
                text=f"{name}{check}",
                callback_data=f"set_lang|{code}",
                icon_custom_emoji_id="5769403725898584391",
            ))
        rows.append(row)

    rows.append([InlineKeyboardButton(
        text=t("back_to_settings", effective_lang),
        callback_data="profile_settings",
        icon_custom_emoji_id="5960671702059848143",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("language"), StateFilter("*"))
async def cmd_language(message: Message, language: str, db_user=None) -> None:
    if message.from_user is None:
        return
    db_lang = db_user.language if db_user else "system"
    await message.answer(
        t("language_prompt", language),
        reply_markup=_language_keyboard(language, db_lang, message.from_user.language_code),
    )


@router.callback_query(F.data == "profile_language", StateFilter("*"))
async def cb_profile_language(query: CallbackQuery, language: str, db_user=None) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    db_lang = db_user.language if db_user else "system"
    await query.message.edit_text(
        t("language_prompt", language),
        reply_markup=_language_keyboard(language, db_lang, query.from_user.language_code),
    )


@router.callback_query(F.data.startswith("set_lang|"), StateFilter("*"))
async def cb_set_language(query: CallbackQuery, language: str) -> None:
    lang_code = (query.data or "").split("|", 1)[1]
    if lang_code not in _FIXED_LANGUAGES and lang_code != "system":
        await query.answer()
        return

    await api.update_user(query.from_user.id, language=lang_code)

    # Resolve effective interface language for the refreshed keyboard
    if lang_code == "system":
        effective = resolve_lang(query.from_user.language_code)
    else:
        effective = lang_code

    logger.info("User %s set language to %s (effective: %s) (client: %s)", query.from_user.id, lang_code, effective, query.from_user.language_code)
    await query.answer()
    if not isinstance(query.message, Message):
        return
    try:
        await query.message.edit_text(
            t("language_prompt", effective),
            reply_markup=_language_keyboard(effective, lang_code, query.from_user.language_code),
        )
    except TelegramBadRequest:
        pass