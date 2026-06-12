import asyncio
from typing import Awaitable, Callable

from core.logger import logger

_TITLE_MODEL_FALLBACK = "gpt-5.4-nano"
_TITLE_TIMEOUT = 25.0
_TITLE_LIMIT = 40


def _title_model() -> str:
    from core.config import settings

    return settings.models.get("title_model") or _TITLE_MODEL_FALLBACK

# ссылки на фоновые задачи — иначе GC может убить их до завершения
_bg_tasks: set = set()
_TITLE_PROMPT = (
    "Сформулируй короткий заголовок диалога по первому сообщению пользователя "
    "и ответу ассистента (если он дан). "
    "2–4 слова, именная фраза на языке пользователя. "
    "Заголовок описывает тему, а не повторяет формулировку запроса: "
    "без глаголов в повелительном наклонении. "
    "Если сообщение короткое или неинформативное — определи тему по ответу ассистента. "
    "Без кавычек, точки в конце, markdown и эмодзи. "
    "Не выдумывай факты и не расшифровывай сокращения.\n"
    "Примеры:\n"
    "«напиши сказку про дракона» → Сказка про дракона\n"
    "«помоги составить резюме» → Помощь с резюме\n"
    "«what is the difference between tcp and udp» → TCP и UDP\n"
    "«привет» → Приветствие\n"
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


async def summarize_title(text: str, reply: str | None = None) -> tuple[str, int, int]:
    """Возвращает (title, input_tokens, output_tokens)."""
    content = (text or "")[:600]
    if reply:
        content = f"Сообщение пользователя: {content}\nОтвет ассистента: {reply[:800]}"
    client = _title_client()
    r = await client.chat.completions.create(
        model=_title_model(),
        messages=[
            {"role": "system", "content": _TITLE_PROMPT},
            {"role": "user", "content": content},
        ],
    )
    raw = (r.choices[0].message.content or "").strip().strip('"').strip()
    n_in = r.usage.prompt_tokens if r.usage else 0
    n_out = r.usage.completion_tokens if r.usage else 0
    return truncate_title(raw), n_in, n_out


async def _refine_title(
    dialog_id: str,
    user_id: int | None,
    text: str,
    reply: str | None,
    on_refined: Callable[[str], Awaitable[None]] | None,
) -> None:
    from db.db import Session
    from db.repositories.dialogs import update_dialog_title, update_n_used_tokens

    try:
        title, n_in, n_out = await summarize_title(text, reply)
        if not title:
            return
        async with Session() as session:
            await update_dialog_title(session, dialog_id, title)
            # токены заголовка — в общий бакет title-модели
            if user_id and (n_in or n_out):
                await update_n_used_tokens(session, user_id, _title_model(), n_in, n_out)
        if on_refined is not None:
            await on_refined(title)
    except Exception:
        logger.exception("Title refinement failed for dialog %s", dialog_id)


async def handle_first_message_title(
    session,
    dialog_id: str,
    text: str,
    reply: str | None = None,
    on_refined: Callable[[str], Awaitable[None]] | None = None,
    user_id: int | None = None,
) -> None:
    """Set instant title on first message, then schedule nano refinement in background."""
    from db.repositories.dialogs import set_initial_title

    initial = await set_initial_title(session, dialog_id, text)
    if initial is None:
        return
    task = asyncio.create_task(_refine_title(dialog_id, user_id, text, reply, on_refined))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
