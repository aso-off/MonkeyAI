from aiogram.types import CallbackQuery, Message

from src.services import api_client as api
from src.utils.localization import t


async def require_admin(event: CallbackQuery | Message, language: str, db_user=None) -> bool:
    """Check if user is admin. Pass db_user from middleware to skip the API call."""
    from src.core.config import settings
    if event.from_user is None:
        return False
    if db_user is not None:
        is_admin = db_user.is_admin or (event.from_user.id in settings.admin_ids)
    else:
        is_admin = await api.is_user_admin(event.from_user.id)
    if is_admin:
        return True
    if isinstance(event, CallbackQuery):
        await event.answer(t("access_denied", language), show_alert=True)
    return False
