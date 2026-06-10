import asyncio
from typing import Awaitable, Callable

from core.logger import logger

_TITLE_MODEL = "gpt-5-nano"
_TITLE_TIMEOUT = 25.0
_TITLE_LIMIT = 40

# ссылки на фоновые задачи — иначе GC может убить их до завершения
_bg_tasks: set = set()
_TITLE_PROMPT = (
    "Сделай короткий заголовок чата по сообщению пользователя. "
    "Максимум 5 слов, на языке сообщения, без кавычек и финальной точки. "
    "Ответь только заголовком."
)


def truncate_title(text: str, limit: int = _TITLE_LIMIT) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    if " " in cut:
        cut = cut[: cut.rfind(" ")].rstrip()
    return cut + "…"


async def summarize_title(text: str) -> str:
    from services.openai import make_client

    client = make_client()
    r = await asyncio.wait_for(
        client.chat.completions.create(
            model=_TITLE_MODEL,
            messages=[
                {"role": "system", "content": _TITLE_PROMPT},
                {"role": "user", "content": (text or "")[:1000]},
            ],
        ),
        timeout=_TITLE_TIMEOUT,
    )
    raw = (r.choices[0].message.content or "").strip().strip('"').strip()
    return truncate_title(raw)


async def _refine_title(
    dialog_id: str,
    text: str,
    on_refined: Callable[[str], Awaitable[None]] | None,
) -> None:
    from db.db import Session
    from db.repositories.dialogs import update_dialog_title

    try:
        title = await summarize_title(text)
        if not title:
            return
        async with Session() as session:
            await update_dialog_title(session, dialog_id, title)
        if on_refined is not None:
            await on_refined(title)
    except Exception:
        logger.exception("Title refinement failed for dialog %s", dialog_id)


async def handle_first_message_title(
    session,
    dialog_id: str,
    text: str,
    on_refined: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    """Set instant title on first message, then schedule nano refinement in background."""
    from db.repositories.dialogs import set_initial_title

    initial = await set_initial_title(session, dialog_id, text)
    if initial is None:
        return
    task = asyncio.create_task(_refine_title(dialog_id, text, on_refined))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
