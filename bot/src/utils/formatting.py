import html
import re
from datetime import datetime


def format_uptime(seconds: float, lang: str = "ru") -> str:
    total = int(seconds)
    days    = total // 86400
    hours   = (total % 86400) // 3600
    minutes = (total % 3600) // 60

    if lang == "ru":
        return f"{days}д {hours}ч {minutes}м"
    return f"{days}d {hours}h {minutes}m"


def format_date(dt: datetime | None, lang: str = "ru") -> str:
    if dt is None:
        return "—"
    if lang == "ru":
        return dt.strftime("%d.%m.%Y")
    return dt.strftime("%m/%d/%Y")


def escape_html(text: str) -> str:
    return html.escape(text)


def truncate(text: str, max_length: int = 4096, suffix: str = "…") -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def format_float(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


# MarkdownV2 special characters that must be escaped in plain text
_MDV2_SPECIAL_RE = re.compile(r'([_*\[\]()~`>#\+\-=|{}.!\\])')

# Combined pattern: finds formatting constructs in order of priority
_MD_PATTERN = re.compile(
    r'```(\w*)\n?(.*?)```'   # group 1=lang, group 2=code block
    r'|`([^`\n]+)`'           # group 3=inline code
    r'|\*\*([^\n]+?)\*\*'     # group 4=bold
    r'|\*([^\n*]+?)\*'        # group 5=italic star
    r'|_([^\n_]+?)_',         # group 6=italic underscore
    re.DOTALL,                # needed so code blocks span multiple lines
)


def _escape_mdv2(text: str) -> str:
    """Escape all MarkdownV2 special characters in plain text."""
    return _MDV2_SPECIAL_RE.sub(r'\\\1', text)


def _escape_mdv2_code(text: str) -> str:
    r"""Escape only ` and \ inside code/pre blocks (Telegram MarkdownV2 rule)."""
    return text.replace('\\', '\\\\').replace('`', '\\`')


def convert_to_markdownv2(text: str) -> str:
    """Convert standard markdown from the model to Telegram MarkdownV2."""
    result = []
    last = 0
    for m in _MD_PATTERN.finditer(text):
        # Escape plain text before this match
        if m.start() > last:
            result.append(_escape_mdv2(text[last:m.start()]))
        if m.group(2) is not None:          # code block
            lang = m.group(1) or ""
            code = _escape_mdv2_code(m.group(2).strip())  # only ` and \ inside pre
            result.append(f"```{lang}\n{code}\n```")
        elif m.group(3) is not None:        # inline code
            result.append(f"`{_escape_mdv2_code(m.group(3))}`")  # only ` and \
        elif m.group(4) is not None:        # bold
            result.append(f"*{_escape_mdv2(m.group(4))}*")
        elif m.group(5) is not None:        # italic *
            result.append(f"_{_escape_mdv2(m.group(5))}_")
        else:                               # italic _
            result.append(f"_{_escape_mdv2(m.group(6))}_")
        last = m.end()
    if last < len(text):
        result.append(_escape_mdv2(text[last:]))
    return "".join(result)
