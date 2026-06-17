from core.security import verify_service_token
from db.db import get_session
from db.repositories import dialogs as dialog_repo
from db.repositories import users as user_repo
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from services.messages import assistant_message, user_message
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/dialogs", tags=["dialogs"])


@router.post("/{user_id}/new")
async def new_dialog(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    user = await user_repo.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    dialog_id = await dialog_repo.start_new_dialog(session, user_id)
    return {"dialog_id": dialog_id}


@router.post("/{user_id}/ensure")
async def ensure_dialog(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    user = await user_repo.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    dialog_id = await dialog_repo.ensure_active_dialog(session, user_id)
    messages = await dialog_repo.get_dialog_messages(session, user_id, dialog_id)
    return {"dialog_id": dialog_id, "messages": messages}


@router.get("/{user_id}/messages")
async def get_messages(
    user_id: int,
    dialog_id: str | None = None,
    chat_mode: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    # Behavior:
    # - if dialog_id is provided => return that dialog in {"messages": [...]}
    # - if chat_mode is provided => resolve dialog_id for that mode and return it in {"messages": [...]}
    # - if neither provided => return ALL modes in {"messages_by_mode": {...}}
    if not dialog_id and not chat_mode:
        try:
            data = await dialog_repo.get_dialog_messages_by_mode(session, user_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None
        return {"messages_by_mode": data}

    if chat_mode and not dialog_id:
        user = await user_repo.get_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        ids = dict(getattr(user, "current_dialog_ids", {}) or {})
        dialog_id = ids.get(chat_mode)

    messages = await dialog_repo.get_dialog_messages(session, user_id, dialog_id)
    return {"messages": messages}

@router.post("/{user_id}/pop-last")
async def pop_last_exchange(
    user_id: int,
    dialog_id: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    """Удаляет последний обмен (для /retry бота); возвращает удалённое user-сообщение."""
    if not dialog_id:
        user = await user_repo.get_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        dialog_id = user.state.current_dialog_id
    if not dialog_id:
        return {"message": None}
    message = await dialog_repo.delete_last_exchange(session, user_id, dialog_id)
    return {"message": message}


class _ExchangeBody(BaseModel):
    dialog_id: str | None = None
    user: str
    bot: str
    model: str | None = None


@router.post("/{user_id}/exchange")
async def append_exchange(
    user_id: int,
    body: _ExchangeBody,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    """Сохраняет готовый обмен user→bot (бот-художник: промпт + URL картинки)."""
    dialog_id = body.dialog_id
    if not dialog_id:
        dialog_id = await dialog_repo.ensure_active_dialog(session, user_id)
    u_msg = user_message(body.user)
    a_msg = assistant_message(body.bot, parent_id=u_msg["id"], model=body.model)
    ok = await dialog_repo.append_messages(session, user_id, dialog_id, [u_msg, a_msg])
    return {"ok": ok}


@router.get("/{user_id}/message-count")
async def get_message_count(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    count = await dialog_repo.get_user_message_count(session, user_id)
    return {"count": count}
