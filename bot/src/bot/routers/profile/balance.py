import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from src.core.config import settings
from src.utils import rich_panel as rp
from src.utils.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _balance_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("back_to_profile", lang), callback_data="profile", icon_custom_emoji_id="5960671702059848143"
                )
            ]
        ]
    )


def _build_balance_md(user, lang: str) -> str:
    if user is None:
        return rp.bold(t("profile_error", lang))

    models_info: dict = settings.models.get("info", {})
    n_used_tokens: dict = user.n_used_tokens or {}
    n_generated_images: int = user.n_generated_images or 0
    n_transcribed_seconds: float = user.n_transcribed_seconds or 0.0

    total_dollars = 0.0
    total_tokens = 0
    rows: list[list] = []

    for model_key in sorted(n_used_tokens.keys()):
        entry = n_used_tokens[model_key]
        n_input = entry.get("n_input_tokens", 0)
        n_output = entry.get("n_output_tokens", 0)
        tokens = n_input + n_output
        total_tokens += tokens

        model_info = models_info.get(model_key, {})
        price_in = model_info.get("price_per_1000_input_tokens", settings.chatgpt_price_per_1000_tokens)
        price_out = model_info.get("price_per_1000_output_tokens", settings.chatgpt_price_per_1000_tokens)
        spent = price_in * (n_input / 1000) + price_out * (n_output / 1000)
        total_dollars += spent
        rows.append([model_key, f"${spent:.3f}", tokens])

    image_info = models_info.get("gpt-image-1.5", {})
    image_spent = image_info.get("price_per_1_image", 0.034) * n_generated_images
    total_dollars += image_spent
    if n_generated_images:
        rows.append(["GPT Image 1.5", f"${image_spent:.3f}", n_generated_images])

    whisper_info = models_info.get("whisper-1", {})
    voice_spent = whisper_info.get("price_per_1_min", settings.whisper_price_per_1_min) * (n_transcribed_seconds / 60)
    total_dollars += voice_spent
    if n_transcribed_seconds:
        rows.append(["Whisper", f"${voice_spent:.3f}", f"{n_transcribed_seconds:.0f}s"])

    summary = t("balance_summary", lang).format(total_dollars, total_tokens).strip()
    sections = [summary]
    if rows:
        sections.append(rp.heading(t("balance_details_header", lang).strip(), 3))
        sections.append(rp.table([], rows, align=[None, "right", "right"]))
    return rp.join(*sections)


@router.message(Command("balance"), StateFilter("*"))
async def cmd_balance(message: Message, language: str, db_user=None) -> None:
    await rp.answer_panel(message, _build_balance_md(db_user, language), reply_markup=_balance_keyboard(language))


@router.callback_query(F.data == "show_balance", StateFilter("*"))
async def cb_show_balance(query: CallbackQuery, language: str, db_user=None) -> None:
    await query.answer()
    if not isinstance(query.message, Message):
        return
    await rp.edit_panel(query.message, _build_balance_md(db_user, language), reply_markup=_balance_keyboard(language))
