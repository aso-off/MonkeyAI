import asyncio
from typing import Awaitable, Callable

from core.logger import logger

_TITLE_MODEL = "gpt-5-nano"
_TITLE_TIMEOUT = 25.0
_TITLE_LIMIT = 40

# ссылки на фоновые задачи — иначе GC может убить их до завершения
_bg_tasks: set = set()
_TITLE_PROMPT = (
    "Придумай короткий заголовок чата по первому сообщению пользователя. "
    "2–5 слов, на языке сообщения, отражает основную тему или намерение запроса. "
    "Без кавычек, без точки в конце, без markdown и эмодзи. "
    "Не выдумывай факты и не расшифровывай сокращения. "
    "В ответе только заголовок."
)


def truncate_title(text: str, limit: int = _TITLE_LIMIT) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    if " " in cut:
        cut = cut[: cut.rfind(" ")].rstrip()
    return cut + "…"


# Отдельный клиент для заголовков — НЕ общий с генерацией бота.
# wait_for-отмена общего клиента портила пул httpx → бот ловил incomplete chunked read.
_title_openai_client = None


def _title_client():
    global _title_openai_client
    if _title_openai_client is None:
        from openai import AsyncOpenAI

        from core.config import settings

        client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=_TITLE_TIMEOUT,  # SDK-таймаут, без отмены корутины
            max_retries=0,
        )
        if settings.openai_api_base:
            client.base_url = settings.openai_api_base
        _title_openai_client = client
    return _title_openai_client


async def summarize_title(text: str) -> str:
    client = _title_client()
    r = await client.chat.completions.create(
        model=_TITLE_MODEL,
        messages=[
            {"role": "system", "content": _TITLE_PROMPT},
            {"role": "user", "content": (text or "")[:1000]},
        ],
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
    # слишком короткое сообщение — nano выдумывает; оставляем как есть
    if len((text or "").strip()) < 5:
        return
    task = asyncio.create_task(_refine_title(dialog_id, text, on_refined))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
