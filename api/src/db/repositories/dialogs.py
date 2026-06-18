import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult, delete, func, select, true, update
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


async def append_messages(
    session: AsyncSession,
    user_id: int,
    dialog_id: str,
    new_messages: list[dict],
    max_messages: int = 400,
) -> bool:
    """Atomically append canonical messages (SELECT FOR UPDATE against races).

    Trims the history to the last max_messages entries so the JSON column stays bounded.
    """
    result = await session.execute(
        select(Dialog)
        .where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        .with_for_update()
    )
    dialog = result.scalar_one_or_none()
    if dialog is None:
        await session.commit()
        return False
    msgs = list(dialog.messages or []) + list(new_messages)
    dialog.messages = msgs[-max_messages:]
    dialog.last_activity = datetime.now(UTC)
    await session.commit()
    return True


async def get_context(
    session: AsyncSession,
    user_id: int,
    dialog_id: str,
    limit: int = 20,
) -> list:
    """Последние limit сообщений диалога — контекст строится на сервере."""
    result = await session.execute(
        select(Dialog.messages).where(Dialog.id == dialog_id, Dialog.user_id == user_id)
    )
    msgs = result.scalar_one_or_none() or []
    return list(msgs)[-limit:]


async def delete_last_exchange(
    session: AsyncSession,
    user_id: int,
    dialog_id: str,
) -> dict | None:
    """Удаляет последний обмен (хвост assistant-ответов + user-вопрос) — для /retry.

    Возвращает удалённое user-сообщение или None, если удалять нечего.
    """
    result = await session.execute(
        select(Dialog)
        .where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        .with_for_update()
    )
    dialog = result.scalar_one_or_none()
    if dialog is None:
        await session.commit()
        return None
    msgs = list(dialog.messages or [])
    while msgs and msgs[-1].get("role") == "assistant":
        msgs.pop()
    user_msg = msgs.pop() if msgs and msgs[-1].get("role") == "user" else None
    dialog.messages = msgs
    await session.commit()
    return user_msg


async def set_message_reaction(
    session: AsyncSession,
    user_id: int,
    dialog_id: str,
    message_id: str,
    reaction: str | None,
) -> bool:
    result = await session.execute(
        select(Dialog)
        .where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        .with_for_update()
    )
    dialog = result.scalar_one_or_none()
    if dialog is None:
        await session.commit()
        return False
    msgs = list(dialog.messages or [])
    found = False
    for m in msgs:
        if m.get("id") == message_id:
            m["reaction"] = reaction
            found = True
            break
    if found:
        dialog.messages = msgs
    await session.commit()
    return found


async def get_dialog_messages_page(
    session: AsyncSession,
    user_id: int,
    dialog_id: str,
    limit: int = 20,
    before_index: int | None = None,
) -> tuple[list, int, int]:
    """Return a page of messages using cursor-based pagination.

    before_index=None > last ``limit`` messages (newest, bootstrap behaviour).
    before_index=N    > ``limit`` messages whose array index is < N.

    Returns (messages_oldest_first, total, next_before_index).
    next_before_index == 0  >  no more older messages exist.
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
    # только сообщения пользователя — ответы модели не считаем
    elem = func.json_array_elements(Dialog.messages).table_valued("value").lateral()
    result = await session.execute(
        select(func.count())
        .select_from(Dialog)
        .join(elem, true())
        .where(Dialog.user_id == user_id, elem.c.value.op("->>")("role") == "user")
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


async def set_active_mini_app_dialog(session: AsyncSession, user_id: int, dialog_id: str) -> bool:
    """Сделать диалог активным для текущего mini-app режима — чтобы reload вернул именно его."""
    user = await get_user(session, user_id)
    if user is None:
        return False
    result = await session.execute(
        select(Dialog.id).where(Dialog.id == dialog_id, Dialog.user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        return False
    chat_mode = user.state.mini_app_chat_mode
    ids = dict(user.state.mini_app_dialog_ids or {})
    if ids.get(chat_mode) == dialog_id:
        return True
    ids[chat_mode] = dialog_id
    user.state.mini_app_dialog_ids = ids
    await session.commit()
    return True


async def set_initial_title(session: AsyncSession, dialog_id: str, text: str) -> str | None:
    """Set a word-boundary truncated title if the dialog has none yet.

    Returns the title it set (signal for nano refinement) or None if already titled.
    """
    from services.title import truncate_title

    result = await session.execute(select(Dialog).where(Dialog.id == dialog_id))
    dialog = result.scalar_one_or_none()
    if dialog is None or dialog.title:
        return None
    title = truncate_title(text)
    if not title:
        return None
    dialog.title = title
    await session.commit()
    return title


async def update_dialog_title(session: AsyncSession, dialog_id: str, title: str) -> None:
    await session.execute(update(Dialog).where(Dialog.id == dialog_id).values(title=title))
    await session.commit()


_MINI_APP_PREFIX = "mini_app_%"


async def list_dialogs(
    session: AsyncSession,
    user_id: int,
    before: datetime | None = None,
    limit: int = 20,
) -> list[Dialog]:
    """Незакреплённые mini-app диалоги, newest activity first. Cursor — last_activity < before."""
    q = select(Dialog).where(
        Dialog.user_id == user_id,
        Dialog.chat_mode.like(_MINI_APP_PREFIX),
        Dialog.pinned_at.is_(None),
    )
    if before is not None:
        q = q.where(Dialog.last_activity < before)
    q = q.order_by(Dialog.last_activity.desc()).limit(limit)
    return list((await session.execute(q)).scalars().all())


async def list_pinned_dialogs(session: AsyncSession, user_id: int) -> list[Dialog]:
    """Закреплённые mini-app диалоги, недавно закреплённые сверху."""
    q = (
        select(Dialog)
        .where(
            Dialog.user_id == user_id,
            Dialog.chat_mode.like(_MINI_APP_PREFIX),
            Dialog.pinned_at.is_not(None),
        )
        .order_by(Dialog.pinned_at.desc())
    )
    return list((await session.execute(q)).scalars().all())


async def set_pinned(session: AsyncSession, user_id: int, dialog_id: str, pinned: bool) -> bool:
    now = datetime.now(UTC)
    result = await session.execute(
        update(Dialog)
        .where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        # бамп last_activity — диалог встаёт наверх свежим (как у Grok)
        .values(pinned_at=now if pinned else None, last_activity=now)
    )
    await session.commit()
    return cast(CursorResult, result).rowcount > 0


async def search_dialogs(
    session: AsyncSession,
    user_id: int,
    query: str,
    limit: int = 50,
    include_untitled: bool = False,
):
    # ILIKE под C-локалью Postgres не сворачивает кириллицу — фильтруем в Python (Unicode).
    # Берём только лёгкие колонки (без messages), с разумным потолком.
    q = (
        select(
            Dialog.id,
            Dialog.title,
            Dialog.last_activity,
            Dialog.start_time,
            Dialog.pinned_at,
        )
        .where(Dialog.user_id == user_id, Dialog.chat_mode.like(_MINI_APP_PREFIX))
        .order_by(Dialog.last_activity.desc())
        .limit(500)
    )
    rows = (await session.execute(q)).all()
    ql = query.lower()
    out = []
    for r in rows:
        if ql in (r.title or "").lower() or (include_untitled and not r.title):
            out.append(r)
            if len(out) >= limit:
                break
    return out


async def rename_dialog(session: AsyncSession, user_id: int, dialog_id: str, title: str) -> bool:
    result = await session.execute(
        update(Dialog)
        .where(Dialog.id == dialog_id, Dialog.user_id == user_id)
        .values(title=title)
    )
    await session.commit()
    return cast(CursorResult, result).rowcount > 0


async def delete_dialog(session: AsyncSession, user_id: int, dialog_id: str) -> bool:
    result = await session.execute(
        delete(Dialog).where(Dialog.id == dialog_id, Dialog.user_id == user_id)
    )
    await session.commit()
    return cast(CursorResult, result).rowcount > 0


async def get_all_users_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar_one()


async def get_active_users_count(session: AsyncSession, days: int = 7) -> int:
    from datetime import timedelta
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await session.execute(
        select(func.count()).select_from(User).where(User.last_interaction >= cutoff)
    )
    return result.scalar_one()
