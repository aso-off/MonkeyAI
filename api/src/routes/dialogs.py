from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import verify_service_token
from db.db import get_session
from db.repositories import dialogs as dialog_repo
from db.repositories import users as user_repo
from schemas.dialog import DialogMessagesSet

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {"messages_by_mode": data}

    if chat_mode and not dialog_id:
        user = await user_repo.get_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        ids = dict(getattr(user, "current_dialog_ids", {}) or {})
        dialog_id = ids.get(chat_mode)

    messages = await dialog_repo.get_dialog_messages(session, user_id, dialog_id)
    return {"messages": messages}

@router.put("/{user_id}/messages")
async def set_messages(
    user_id: int,
    body: DialogMessagesSet,
    dialog_id: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    await dialog_repo.set_dialog_messages(session, user_id, body.messages, dialog_id)
    return {"ok": True}


@router.post("/{user_id}/tokens")
async def update_tokens(
    user_id: int,
    model: str,
    n_input_tokens: int,
    n_output_tokens: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    await dialog_repo.update_n_used_tokens(session, user_id, model, n_input_tokens, n_output_tokens)
    return {"ok": True}


@router.get("/{user_id}/message-count")
async def get_message_count(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> dict:
    count = await dialog_repo.get_user_message_count(session, user_id)
    return {"count": count}
