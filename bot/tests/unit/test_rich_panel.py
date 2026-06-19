"""Юнит-тесты для bot/src/utils/rich_panel.py (HTML-билдеры + хелперы)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.utils import rich_panel as rp


def test_heading_levels():
    assert rp.heading("Profile") == "<h2>Profile</h2>"
    assert rp.heading("Top", 1) == "<h1>Top</h1>"
    assert rp.heading("Deep", 9) == "<h3>Deep</h3>"


def test_inline_styles():
    assert rp.bold("x") == "<b>x</b>"
    assert rp.italic("x") == "<i>x</i>"
    assert rp.strike("x") == "<s>x</s>"
    assert rp.code("123") == "<code>123</code>"
    assert rp.underline("x") == "<u>x</u>"
    assert rp.marked("x") == "<mark>x</mark>"


def test_kv_and_block():
    assert rp.kv("ID:", 42) == "<b>ID:</b> 42"
    assert rp.kv_block([("ID:", 1), ("Lang:", "ru")]) == "<b>ID:</b> 1\n<b>Lang:</b> ru"


def test_lists():
    assert rp.ul([1, 2]) == "<ul><li>1</li><li>2</li></ul>"
    assert rp.ol(["a", "b"]) == "<ol><li>a</li><li>b</li></ol>"


def test_checklist():
    assert rp.checklist([("API", True), ("DB", False)]) == "<ul><li>✅ API</li><li>⬜ DB</li></ul>"


def test_quote():
    assert rp.quote("hi", credit="Monkey") == "<blockquote>hi\n— Monkey</blockquote>"
    assert rp.quote("solo") == "<blockquote>solo</blockquote>"


def test_details():
    assert rp.details("More", "body", is_open=True) == "<details open><summary>More</summary>body</details>"


def test_divider_and_footer():
    assert rp.divider() == "<hr/>"
    assert rp.footer("Updated") == "<i>Updated</i>"


def test_table_basic():
    out = rp.table(["A", "B"], [[1, 2], [3, 4]])
    assert out == (
        "<table><thead><tr><th>A</th><th>B</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td></tr><tr><td>3</td><td>4</td></tr></tbody></table>"
    )


def test_table_align():
    out = rp.table(["A", "B"], [], align=["left", "right"])
    assert '<th align="left">A</th>' in out
    assert '<th align="right">B</th>' in out


def test_table_escapes_cells():
    assert "a&lt;b&gt;c" in rp.table(["X"], [["a<b>c"]])


def test_join_skips_empty():
    assert rp.join("a", "", "b") == "a\n\nb"


def test_to_legacy_html_degrades_rich_tags():
    legacy = rp.to_legacy_html(rp.join(rp.heading("Title"), rp.ul(["one", "two"])))
    assert "<h2>" not in legacy
    assert "<ul>" not in legacy
    assert "<b>Title</b>" in legacy
    assert "• one" in legacy


def test_to_legacy_html_table_to_lines():
    legacy = rp.to_legacy_html(rp.table(["A", "B"], [[1, 2]]))
    assert "<table>" not in legacy
    assert "A B" in legacy


@pytest.mark.asyncio
async def test_answer_panel_uses_rich_when_enabled(monkeypatch):
    monkeypatch.setattr(rp.settings, "enable_rich_messages", True, raising=False)
    monkeypatch.setattr(rp.settings, "rich_message_max_length", 32768, raising=False)
    msg = MagicMock()
    msg.answer_rich = AsyncMock()
    msg.answer = AsyncMock()
    await rp.answer_panel(msg, "<b>hi</b>")
    msg.answer_rich.assert_awaited_once()
    msg.answer.assert_not_awaited()
    assert msg.answer_rich.await_args.kwargs["rich_message"].html == "<b>hi</b>"


@pytest.mark.asyncio
async def test_answer_panel_fallback_when_disabled(monkeypatch):
    monkeypatch.setattr(rp.settings, "enable_rich_messages", False, raising=False)
    monkeypatch.setattr(rp.settings, "rich_message_max_length", 32768, raising=False)
    msg = MagicMock()
    msg.answer_rich = AsyncMock()
    msg.answer = AsyncMock()
    await rp.answer_panel(msg, rp.heading("Hi"))
    msg.answer.assert_awaited_once()
    msg.answer_rich.assert_not_awaited()
    assert msg.answer.await_args.kwargs["parse_mode"] == "HTML"
