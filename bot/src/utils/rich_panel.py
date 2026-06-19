import html as _html
import logging
import re
from collections.abc import Iterable, Sequence

from aiogram.types import InlineKeyboardMarkup, InputRichMessage, Message

from src.core.config import settings

logger = logging.getLogger(__name__)

_NOT_MODIFIED = "not modified"


def esc(value: object) -> str:
    return _html.escape(str(value), quote=False)


def heading(text: str, level: int = 2) -> str:
    level = max(1, min(level, 3))
    return f"<h{level}>{text}</h{level}>"


def bold(text: str) -> str:
    return f"<b>{text}</b>"


def italic(text: str) -> str:
    return f"<i>{text}</i>"


def underline(text: str) -> str:
    return f"<u>{text}</u>"


def strike(text: str) -> str:
    return f"<s>{text}</s>"


def code(text: str) -> str:
    return f"<code>{text}</code>"


def marked(text: str) -> str:
    return f"<mark>{text}</mark>"


def quote(text: str, credit: str | None = None) -> str:
    body = f"{text}\n— {credit}" if credit else text
    return f"<blockquote>{body}</blockquote>"


def divider() -> str:
    return "<hr/>"


def footer(text: str) -> str:
    return italic(text)


def kv(label: str, value: object) -> str:
    return f"{bold(label)} {value}"


def kv_block(pairs: Iterable[tuple[str, object]]) -> str:
    return "\n".join(kv(label, value) for label, value in pairs)


def ul(items: Iterable[object]) -> str:
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def ol(items: Iterable[object]) -> str:
    return "<ol>" + "".join(f"<li>{item}</li>" for item in items) + "</ol>"


def checklist(items: Iterable[tuple[object, bool]]) -> str:
    return "<ul>" + "".join(f"<li>{'✅' if done else '⬜'} {label}</li>" for label, done in items) + "</ul>"


def details(summary: str, body: str, *, is_open: bool = False) -> str:
    open_attr = " open" if is_open else ""
    return f"<details{open_attr}><summary>{summary}</summary>{body}</details>"


_ALIGN = {"left", "center", "right"}


def _row(cells: Iterable[object], tag: str, aligns: Sequence[str | None]) -> str:
    out = []
    for i, cell in enumerate(cells):
        a = aligns[i] if i < len(aligns) else None
        attr = f' align="{a}"' if a in _ALIGN else ""
        out.append(f"<{tag}{attr}>{esc(cell)}</{tag}>")
    return "<tr>" + "".join(out) + "</tr>"


def table(
    headers: Sequence[object],
    rows: Iterable[Sequence[object]],
    *,
    align: Sequence[str | None] | None = None,
) -> str:
    aligns = list(align) if align else []
    body = "<tbody>" + "".join(_row(r, "td", aligns) for r in rows) + "</tbody>"
    if not headers:
        return f"<table>{body}</table>"
    head = "<thead>" + _row(headers, "th", aligns) + "</thead>"
    return f"<table>{head}{body}</table>"


def join(*sections: str) -> str:
    return "\n\n".join(s for s in sections if s)


# rich-only теги > legacy-safe HTML для fallback на старых клиентах
_LEGACY_SUBS = (
    (re.compile(r"<h[1-6]>"), "<b>"),
    (re.compile(r"</h[1-6]>"), "</b>\n"),
    (re.compile(r"<summary>"), "<b>"),
    (re.compile(r"</summary>"), "</b>\n"),
    (re.compile(r"</?details[^>]*>"), ""),
    (re.compile(r"</?mark>"), ""),
    (re.compile(r"<hr\s*/?>"), "\n"),
    (re.compile(r"</?(?:ul|ol|thead|tbody|table)>"), ""),
    (re.compile(r"<li>"), "• "),
    (re.compile(r"</li>"), "\n"),
    (re.compile(r"<tr>"), ""),
    (re.compile(r"</tr>"), "\n"),
    (re.compile(r"<t[hd][^>]*>"), ""),
    (re.compile(r"</t[hd]>"), " "),
)


def to_legacy_html(html_str: str) -> str:
    for pattern, repl in _LEGACY_SUBS:
        html_str = pattern.sub(repl, html_str)
    return html_str


def _cap(html_str: str) -> str:
    limit = settings.rich_message_max_length
    return html_str if len(html_str) <= limit else html_str[:limit]


async def edit_panel(
    message: Message,
    html_str: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    html_str = _cap(html_str)
    if settings.enable_rich_messages and message.bot is not None:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                rich_message=InputRichMessage(html=html_str),
                reply_markup=reply_markup,
            )
            return
        except Exception as exc:
            if _NOT_MODIFIED in str(exc):
                return
            logger.warning("edit_panel rich failed (chat %s): %s", message.chat.id, exc)
    try:
        await message.edit_text(to_legacy_html(html_str), reply_markup=reply_markup, parse_mode="HTML")
    except Exception as exc:
        if _NOT_MODIFIED not in str(exc):
            logger.warning("edit_panel fallback failed (chat %s): %s", message.chat.id, exc)


async def answer_panel(
    message: Message,
    html_str: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    html_str = _cap(html_str)
    if settings.enable_rich_messages:
        try:
            return await message.answer_rich(rich_message=InputRichMessage(html=html_str), reply_markup=reply_markup)
        except Exception as exc:
            logger.warning("answer_panel rich failed (chat %s): %s", message.chat.id, exc)
    return await message.answer(to_legacy_html(html_str), reply_markup=reply_markup, parse_mode="HTML")
