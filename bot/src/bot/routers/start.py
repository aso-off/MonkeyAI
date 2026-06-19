import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from src.core.config import settings
from src.services import api_client as api
from src.utils import rich_panel as rp
from src.utils.localization import t
from src.utils.stickers import monkey

logger = logging.getLogger(__name__)
router = Router()


def _menu_md(head: str, *paragraphs: str) -> str:
    title, _, rest = head.partition("\n")
    return rp.join(rp.heading(title, 2), rest, *paragraphs)


def _private_keyboard(is_admin: bool, lang: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=t("profile", lang),
                callback_data="profile",
                style="primary",
                icon_custom_emoji_id="6035084557378654059",
            ),
            InlineKeyboardButton(
                text=t("about", lang),
                callback_data="about",
                style="primary",
                icon_custom_emoji_id="6030848053177486888",
            ),
        ],
    ]
    if is_admin:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=t("admin_panel", lang),
                    callback_data="admin_panel",
                    style="primary",
                    icon_custom_emoji_id="5778570255555105942",
                )
            ]
        )
    if settings.webapp_url:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=t("open_mini_app", lang),
                    web_app=WebAppInfo(url=settings.webapp_url),
                    style="success",
                    icon_custom_emoji_id="5940660740758184142",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _group_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile", lang), callback_data="profile", icon_custom_emoji_id="6035084557378654059"
                )
            ],
            [
                InlineKeyboardButton(text=t("help", lang), callback_data="help"),
                InlineKeyboardButton(
                    text=t("about", lang), callback_data="about", icon_custom_emoji_id="6030848053177486888"
                ),
            ],
        ]
    )


@router.message(Command("start"), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext, language: str, bot: Bot, db_user=None) -> None:
    await state.clear()
    if message.from_user is None:
        return
    if db_user is None:
        db_user = await api.get_or_create_user(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
            last_name=message.from_user.last_name or "",
            language="system",
        )
    is_admin = db_user.is_admin or (message.from_user.id in settings.admin_ids)

    if message.chat.type == ChatType.PRIVATE:
        await monkey.send(bot, message.chat.id, "hello")
        md = _menu_md(
            t("welcome", language, message.from_user.first_name),
            t("welcome_description", language),
            t("welcome_instruction", language),
        )
        await rp.answer_panel(message, md, reply_markup=_private_keyboard(is_admin, language))
    else:
        md = rp.heading(f"\U0001f44b {t('welcome_group_minimal', language)}", 2)
        await rp.answer_panel(message, md, reply_markup=_group_keyboard(language))


@router.message(Command("menu"), StateFilter("*"))
async def cmd_menu(message: Message, state: FSMContext, language: str, db_user=None) -> None:
    await state.clear()
    if message.from_user is None:
        return
    if message.chat.type == ChatType.PRIVATE:
        md = _menu_md(t("back_to_menu", language), t("welcome_instruction", language))
        is_admin = (db_user is not None and db_user.is_admin) or (message.from_user.id in settings.admin_ids)
        markup = _private_keyboard(is_admin, language)
    else:
        md = rp.heading(f"\U0001f44b {t('welcome_group_minimal', language)}", 2)
        markup = _group_keyboard(language)
    await rp.answer_panel(message, md, reply_markup=markup)


@router.callback_query(F.data == "back_to_start", StateFilter("*"))
async def cb_back_to_start(query: CallbackQuery, state: FSMContext, language: str, db_user=None) -> None:
    await state.clear()
    await query.answer()
    if not isinstance(query.message, Message):
        return

    if query.message.chat.type == ChatType.PRIVATE:
        md = _menu_md(t("back_to_menu", language), t("welcome_instruction", language))
        is_admin = (db_user is not None and db_user.is_admin) or (query.from_user.id in settings.admin_ids)
        markup = _private_keyboard(is_admin, language)
    else:
        md = rp.heading(f"\U0001f44b {t('welcome_group_minimal', language)}", 2)
        markup = _group_keyboard(language)

    await rp.edit_panel(query.message, md, reply_markup=markup)
