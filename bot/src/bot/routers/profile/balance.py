import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.config import settings
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _balance_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("back_to_profile", lang), callback_data="profile", icon_custom_emoji_id="5960671702059848143")]
    ])


def _build_balance_text(user, lang: str) -> str:
    if user is None:
        return t("profile_error", lang)

    models_info: dict = settings.models.get("info", {})
    n_used_tokens: dict = user.n_used_tokens or {}
    n_generated_images: int = user.n_generated_images or 0
    n_transcribed_seconds: float = user.n_transcribed_seconds or 0.0

    total_dollars = 0.0
    total_tokens = 0
    details = t("balance_details_header", lang)

    for model_key in sorted(n_used_tokens.keys()):
        entry = n_used_tokens[model_key]
        n_input = entry.get("n_input_tokens", 0)
        n_output = entry.get("n_output_tokens", 0)
        total_tokens += n_input + n_output

        model_info = models_info.get(model_key, {})
        price_in = model_info.get("price_per_1000_input_tokens", settings.chatgpt_price_per_1000_tokens)
        price_out = model_info.get("price_per_1000_output_tokens", settings.chatgpt_price_per_1000_tokens)
        spent = price_in * (n_input / 1000) + price_out * (n_output / 1000)
        total_dollars += spent
        details += t("balance_tokens_detail", lang).format(model_key, spent, n_input + n_output)

    image_info = models_info.get("gpt-image-1.5", {})
    image_price = image_info.get("price_per_1_image", 0.034)
    image_spent = image_price * n_generated_images
    total_dollars += image_spent
    if n_generated_images:
        details += t("balance_images_detail", lang).format(image_spent, n_generated_images)

    whisper_info = models_info.get("whisper-1", {})
    whisper_price = whisper_info.get("price_per_1_min", settings.whisper_price_per_1_min)
    voice_spent = whisper_price * (n_transcribed_seconds / 60)
    total_dollars += voice_spent
    if n_transcribed_seconds:
        details += t("balance_voice_detail", lang).format(voice_spent, n_transcribed_seconds)

    return t("balance_summary", lang).format(total_dollars, total_tokens) + details


@router.message(Command("balance"), StateFilter("*"))
async def cmd_balance(message: Message, language: str, db_user=None) -> None:
    text = _build_balance_text(db_user, language)
    await message.answer(text, reply_markup=_balance_keyboard(language), parse_mode="HTML")


@router.callback_query(F.data == "show_balance", StateFilter("*"))
async def cb_show_balance(query: CallbackQuery, language: str, db_user=None) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    text = _build_balance_text(db_user, language)
    await query.message.edit_text(text, reply_markup=_balance_keyboard(language), parse_mode="HTML")