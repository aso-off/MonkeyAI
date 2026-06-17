"""Юнит-тесты для bot/src/utils/rich_builder.py."""

from src.utils.rich_builder import (
    build_draft,
    build_message,
    is_reasoning_model,
    normalize_latex,
    thinking_draft,
    to_rich_markdown,
)

_MODELS = {
    "info": {
        "gpt-5.4-mini": {"options": {"reasoning_effort": "medium"}},
        "gpt-4o": {"options": {"temperature": 0.3}},
    }
}


def test_normalize_latex_inline():
    assert normalize_latex(r"value \(x^2\) here") == "value $x^2$ here"


def test_normalize_latex_display_multiline():
    assert normalize_latex("a\n\\[E = mc^2\\]\nb") == "a\n$$E = mc^2$$\nb"


def test_normalize_latex_keeps_dollar_form():
    src = "inline $a$ and $$b$$"
    assert normalize_latex(src) == src


def test_normalize_latex_skips_fenced_code():
    src = "text \\(x\\)\n```python\nre.match(r\"\\(.+\\)\", s)\n```\nmore \\(y\\)"
    out = normalize_latex(src)
    assert 're.match(r"\\(.+\\)", s)' in out
    assert "text $x$" in out
    assert "more $y$" in out


def test_normalize_latex_skips_inline_code():
    src = "use `printf(\"\\(\")` and \\(z\\)"
    out = normalize_latex(src)
    assert '`printf("\\(")`' in out
    assert "and $z$" in out


def test_truncate_drops_unclosed_code_fence():
    text = ("a" * 40) + "\n\n```python\ncode here without close"
    out = to_rich_markdown(text, max_length=70)
    assert "```" not in out


def test_truncate_drops_unclosed_display_math():
    text = ("a" * 40) + "\n\n$$E = mc^2 incomplete"
    out = to_rich_markdown(text, max_length=60)
    assert out.count("$$") % 2 == 0


def test_to_rich_markdown_truncates_at_block_boundary():
    text = ("a" * 30) + "\n\n" + ("b" * 30)
    out = to_rich_markdown(text, max_length=40)
    assert out == "a" * 30


def test_to_rich_markdown_hard_cut_when_no_boundary():
    out = to_rich_markdown("y" * 100, max_length=10)
    assert out == "y" * 10


def test_build_message_returns_markdown_field():
    msg = build_message(r"sum \(a+b\)", max_length=32768)
    assert msg.markdown == "sum $a+b$"
    assert msg.html is None


def test_build_draft_returns_markdown_field():
    msg = build_draft("partial", max_length=32768)
    assert msg.markdown == "partial"


def test_thinking_draft_placeholder():
    msg = thinking_draft("Думаю…")
    assert msg.html.startswith("<tg-thinking>")
    assert msg.html.endswith("</tg-thinking>")
    assert 'tg-emoji emoji-id="5818740758257077530"' in msg.html
    assert "Думаю…" in msg.html
    assert msg.markdown is None


def test_thinking_draft_with_reasoning_escaped():
    msg = thinking_draft("Думаю…", reasoning="a < b & c")
    assert "a &lt; b &amp; c" in msg.html
    assert msg.html.endswith("</tg-thinking>")


def test_thinking_draft_strips_markdown_from_reasoning():
    msg = thinking_draft("Думаю…", reasoning="## Step one\n**Considering** the `factors`")
    assert "**" not in msg.html
    assert "`" not in msg.html
    assert "##" not in msg.html
    assert "Considering" in msg.html
    assert "Step one" in msg.html


def test_thinking_draft_empty_reasoning_falls_back_to_label():
    msg = thinking_draft("Thinking…", reasoning="   ")
    assert "Thinking…" in msg.html
    assert msg.html.startswith("<tg-thinking>")


def test_is_reasoning_model_true():
    assert is_reasoning_model("gpt-5.4-mini", _MODELS) is True


def test_is_reasoning_model_false():
    assert is_reasoning_model("gpt-4o", _MODELS) is False


def test_is_reasoning_model_unknown():
    assert is_reasoning_model("missing", _MODELS) is False
