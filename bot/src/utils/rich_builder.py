import html
import re
from typing import Any

from aiogram.types import InputRichMessage

_LATEX_DISPLAY_RE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_LATEX_INLINE_RE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)

# fenced + inline код — нормализацию не трогать
_CODE_SPAN_RE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)

# markdown-маркеры в reasoning — показываем как обычный текст
_RM_MARKDOWN_RE = re.compile(r"\*\*|__|~~|`|^\s{0,3}#{1,6}\s+", re.MULTILINE)


def _strip_markdown(text: str) -> str:
    return _RM_MARKDOWN_RE.sub("", text)


def _normalize_segment(text: str) -> str:
    text = _LATEX_DISPLAY_RE.sub(r"$$\1$$", text)
    text = _LATEX_INLINE_RE.sub(r"$\1$", text)
    return text


def normalize_latex(text: str) -> str:
    r"""Convert \(..\)/\[..\] LaTeX delimiters to $..$/$$..$$ outside code spans."""
    result = []
    last = 0
    for m in _CODE_SPAN_RE.finditer(text):
        result.append(_normalize_segment(text[last : m.start()]))
        result.append(m.group(0))
        last = m.end()
    result.append(_normalize_segment(text[last:]))
    return "".join(result)


def _truncate_blocks(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    cut = text[:max_length]
    boundary = cut.rfind("\n\n")
    if boundary > max_length // 2:
        cut = cut[:boundary]
    cut = cut.rstrip()
    # отрезать незакрытый код-фенс / display-math
    if cut.count("```") % 2:
        cut = cut[: cut.rfind("```")].rstrip()
    if cut.count("$$") % 2:
        cut = cut[: cut.rfind("$$")].rstrip()
    return cut


def to_rich_markdown(text: str, max_length: int) -> str:
    return _truncate_blocks(normalize_latex(text).strip(), max_length)


def build_message(text: str, max_length: int) -> InputRichMessage:
    return InputRichMessage(markdown=to_rich_markdown(text, max_length))


def build_draft(text: str, max_length: int) -> InputRichMessage:
    return InputRichMessage(markdown=to_rich_markdown(text, max_length))


def thinking_draft(label: str, reasoning: str | None = None) -> InputRichMessage:
    stripped = _strip_markdown(reasoning).strip() if reasoning else ""
    body = html.escape(stripped or label)
    return InputRichMessage(html=f"<tg-thinking>{body}</tg-thinking>")


def is_reasoning_model(model: str, models: dict[str, Any]) -> bool:
    info = models.get("info", {}).get(model, {})
    return "reasoning_effort" in (info.get("options") or {})
