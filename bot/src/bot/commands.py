from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from src.core.bot import bot
from src.core.config import settings
from src.core.logger import logger


def _make_user_commands(lang: str) -> list[BotCommand]:
    from src.utils.localization import t
    return [
        BotCommand(command="start",           description=t("cmd_start",           lang)),
        BotCommand(command="new",             description=t("cmd_new",             lang)),
        BotCommand(command="mode",            description=t("cmd_mode",            lang)),
        BotCommand(command="model",           description=t("cmd_model",           lang)),
        BotCommand(command="retry",           description=t("cmd_retry",           lang)),
        BotCommand(command="balance",         description=t("cmd_balance",         lang)),
        BotCommand(command="settings",        description=t("cmd_settings",        lang)),
        BotCommand(command="profile",         description=t("cmd_profile",         lang)),
        BotCommand(command="language",        description=t("cmd_language",        lang)),
        BotCommand(command="ping",            description=t("cmd_ping",            lang)),
        BotCommand(command="about",           description=t("cmd_about",           lang)),
        BotCommand(command="help",            description=t("cmd_help",            lang)),
        BotCommand(command="help_group_chat", description=t("cmd_help_group_chat", lang)),
        BotCommand(command="cancel",          description=t("cmd_cancel",          lang)),
    ]


def _make_admin_commands(lang: str) -> list[BotCommand]:
    from src.utils.localization import t
    return _make_user_commands(lang) + [
        BotCommand(command="admin",   description=t("cmd_admin",   lang)),
        BotCommand(command="status",  description=t("cmd_status",  lang)),
        BotCommand(command="system",  description=t("cmd_system",  lang)),
        BotCommand(command="restart", description=t("cmd_restart", lang)),
    ]


_ALL_LANGS = ("ru", "en", "de", "es", "fr", "pl", "pt", "tr")


async def _set_commands() -> None:
    # Устанавливаем команды для личных чатов на всех 8 языках
    for lang in _ALL_LANGS:
        await bot.set_my_commands(
            _make_user_commands(lang),
            scope=BotCommandScopeAllPrivateChats(),
            language_code=lang,
        )
    logger.info("User commands set (%s)", " + ".join(_ALL_LANGS))

    # Групповые чаты — без help_group_chat и прочего личного
    for lang in _ALL_LANGS:
        await bot.set_my_commands(
            _make_user_commands(lang)[:6],  # start, new, mode, retry, balance, settings
            scope=BotCommandScopeAllGroupChats(),
            language_code=lang,
        )
    logger.info("Group commands set")

    # Команды администраторов (перекрывают общие для их chat_id)
    for admin_id in settings.admin_ids:
        for lang in _ALL_LANGS:
            try:
                await bot.set_my_commands(
                    _make_admin_commands(lang),
                    scope=BotCommandScopeChat(chat_id=admin_id),
                    language_code=lang,
                )
            except Exception:
                pass
    logger.info("Admin commands set")