import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import Dialog, User, UserStatistics
from db.repositories.users import get_user


async def ensure_active_dialog(session: AsyncSession, user_id: int) -> str:
    """Return active dialog_id for user's current_chat_mode.

    Creates a new dialog if none exists for this mode yet.
    """
    user = await get_user(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    chat_mode = user.state.current_chat_mode
    ids = dict(user.state.current_dialog_ids or {})
    dialog_id = ids.get(chat_mode)

    if dialog_id:
        result = await session.execute(
            select(Dialog.id).where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        )
        if result.scalar_one_or_none() is not None:
            if user.state.current_dialog_id != dialog_id:
                user.state.current_dialog_id = dialog_id
                await session.commit()
            return dialog_id

    dialog = Dialog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        chat_mode=chat_mode,
        model=user.state.current_model,
        messages=[],
    )
    session.add(dialog)
    ids[chat_mode] = dialog.id
    user.state.current_dialog_ids = ids
    user.state.current_dialog_id = dialog.id
    await session.commit()
    return dialog.id


async def start_new_dialog(session: AsyncSession, user_id: int, commit: bool = True) -> str:
    user = await get_user(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    dialog = Dialog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        chat_mode=user.state.current_chat_mode,
        model=user.state.current_model,
        messages=[],
    )
    session.add(dialog)
    ids = dict(user.state.current_dialog_ids or {})
    ids[user.state.current_chat_mode] = dialog.id
    user.state.current_dialog_ids = ids
    user.state.current_dialog_id = dialog.id
    if commit:
        await session.commit()
    return dialog.id


async def get_dialog_messages(
    session: AsyncSession,
    user_id: int,
    dialog_id: str | None = None,
) -> list:
    if dialog_id is None:
        user = await get_user(session, user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        dialog_id = user.state.current_dialog_id

    result = await session.execute(
        select(Dialog).where(Dialog.id == dialog_id, Dialog.user_id == user_id)
    )
    dialog = result.scalar_one_or_none()
    return dialog.messages if dialog else []


async def get_dialog_messages_by_mode(session: AsyncSession, user_id: int) -> dict[str, list]:
    """Return messages for all active dialogs keyed by chat_mode."""
    user = await get_user(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    ids = dict(user.state.current_dialog_ids or {})
    if not ids:
        return {}

    out: dict[str, list] = {}
    for mode, dialog_id in ids.items():
        if not dialog_id:
            continue
        result = await session.execute(
            select(Dialog.messages).where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        )
        msgs = result.scalar_one_or_none()
        out[str(mode)] = list(msgs or [])
    return out


async def set_dialog_messages(
    session: AsyncSession,
    user_id: int,
    messages: list,
    dialog_id: str | None = None,
    commit: bool = True,
) -> None:
    if dialog_id is None:
        user = await get_user(session, user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        dialog_id = user.state.current_dialog_id

    await session.execute(
        update(Dialog)
        .where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        .values(messages=messages)
    )
    if commit:
        await session.commit()


async def update_n_used_tokens(
    session: AsyncSession,
    user_id: int,
    model: str,
    n_input_tokens: int,
    n_output_tokens: int,
) -> None:
    # SELECT FOR UPDATE to prevent lost-update race when two requests finish simultaneously.
    result = await session.execute(
        select(UserStatistics).where(UserStatistics.user_id == user_id).with_for_update()
    )
    stats = result.scalar_one_or_none()
    if stats is None:
        return

    tokens = dict(stats.n_used_tokens or {})
    entry = tokens.get(model, {"n_input_tokens": 0, "n_output_tokens": 0})
    tokens[model] = {
        "n_input_tokens": entry["n_input_tokens"] + n_input_tokens,
        "n_output_tokens": entry["n_output_tokens"] + n_output_tokens,
    }
    await session.execute(
        update(UserStatistics).where(UserStatistics.user_id == user_id).values(n_used_tokens=tokens)
    )
    await session.commit()


async def append_dialog_message(
    session: AsyncSession,
    user_id: int,
    new_message: dict,
    dialog_id: str,
    max_messages: int = 200,
) -> str | None:
    """Atomically append a message using SELECT FOR UPDATE to prevent race conditions.
    Trims the history to the last max_messages entries so the JSON column stays bounded.
    Assigns a stable ``mid`` to the message and returns it (for client-side reactions).
    """
    mid = new_message.get("mid") or uuid.uuid4().hex
    new_message["mid"] = mid
    result = await session.execute(
        select(Dialog)
        .where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        .with_for_update()
    )
    dialog = result.scalar_one_or_none()
    if dialog is None:
        await session.commit()
        return None
    msgs = list(dialog.messages or []) + [new_message]
    dialog.messages = msgs[-max_messages:]
    dialog.last_activity = datetime.now(timezone.utc)
    await session.commit()
    return mid


async def get_dialog_messages_page(
    session: AsyncSession,
    user_id: int,
    dialog_id: str,
    limit: int = 20,
    before_index: int | None = None,
) -> tuple[list, int, int]:
    """Return a page of messages using cursor-based pagination.

    before_index=None → last ``limit`` messages (newest, bootstrap behaviour).
    before_index=N    → ``limit`` messages whose array index is < N.

    Returns (messages_oldest_first, total, next_before_index).
    next_before_index == 0  →  no more older messages exist.
    """
    result = await session.execute(
        select(Dialog).where(Dialog.id == dialog_id, Dialog.user_id == user_id)
    )
    dialog = result.scalar_one_or_none()
    if not dialog or not dialog.messages:
        return [], 0, 0
    msgs = list(dialog.messages)
    total = len(msgs)
    end = total if before_index is None else min(before_index, total)
    start = max(0, end - limit)
    return msgs[start:end], total, start  # start IS next_before_index


async def get_user_message_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.coalesce(
            func.sum(func.json_array_length(Dialog.messages)),
            0,
        )).where(Dialog.user_id == user_id)
    )
    return result.scalar_one()


async def ensure_active_mini_app_dialog(session: AsyncSession, user_id: int) -> str:
    """Return active dialog_id for the user's mini_app_chat_mode (separate from bot)."""
    user = await get_user(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    chat_mode = user.state.mini_app_chat_mode
    ids = dict(user.state.mini_app_dialog_ids or {})
    dialog_id = ids.get(chat_mode)

    if dialog_id:
        result = await session.execute(
            select(Dialog.id).where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        )
        if result.scalar_one_or_none() is not None:
            return dialog_id

    dialog = Dialog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        chat_mode=chat_mode,
        model=user.state.current_model,
        messages=[],
    )
    session.add(dialog)
    ids[chat_mode] = dialog.id
    user.state.mini_app_dialog_ids = ids
    await session.commit()
    return dialog.id


async def start_new_mini_app_dialog(session: AsyncSession, user_id: int, commit: bool = True) -> str:
    user = await get_user(session, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    chat_mode = user.state.mini_app_chat_mode
    dialog = Dialog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        chat_mode=chat_mode,
        model=user.state.current_model,
        messages=[],
    )
    session.add(dialog)
    ids = dict(user.state.mini_app_dialog_ids or {})
    ids[chat_mode] = dialog.id
    user.state.mini_app_dialog_ids = ids
    if commit:
        await session.commit()
    return dialog.id


async def get_mini_app_dialog_id(
    session: AsyncSession,
    user_id: int,
    chat_mode: str | None = None,
) -> str | None:
    user = await get_user(session, user_id)
    if user is None:
        return None
    mode = chat_mode or user.state.mini_app_chat_mode
    ids = dict(user.state.mini_app_dialog_ids or {})
    return ids.get(mode)


async def get_all_users_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar_one()


async def get_active_users_count(session: AsyncSession, days: int = 7) -> int:
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(func.count()).select_from(User).where(User.last_interaction >= cutoff)
    )
    return result.scalar_one()
