"""Юнит-тесты для bot/src/utils/formatting.py — чистые функции, нет внешних зависимостей."""

from datetime import datetime

import pytest

from src.utils.formatting import (
    convert_to_markdownv2,
    escape_html,
    format_date,
    format_float,
    format_uptime,
    truncate,
)


class TestFormatUptime:
    @pytest.mark.unit
    @pytest.mark.parametrize("seconds,lang,expected", [
        (0,       "ru", "0д 0ч 0м"),
        (59,      "ru", "0д 0ч 0м"),
        (60,      "ru", "0д 0ч 1м"),
        (3600,    "ru", "0д 1ч 0м"),
        (3661,    "ru", "0д 1ч 1м"),
        (86400,   "ru", "1д 0ч 0м"),
        (90061,   "ru", "1д 1ч 1м"),
        (172861,  "ru", "2д 0ч 1м"),
        (0,       "en", "0d 0h 0m"),
        (3661,    "en", "0d 1h 1m"),
        (86400,   "en", "1d 0h 0m"),
        (604800,  "en", "7d 0h 0m"),
    ])
    def test_known_values(self, seconds: int, lang: str, expected: str) -> None:
        assert format_uptime(seconds, lang) == expected

    @pytest.mark.unit
    def test_fractional_seconds_truncated(self) -> None:
        assert format_uptime(3661.999, "ru") == format_uptime(3661, "ru")

    @pytest.mark.unit
    def test_default_lang_is_ru(self) -> None:
        result = format_uptime(3661)
        assert "д" in result and "ч" in result and "м" in result

    @pytest.mark.unit
    def test_faker_ru_contains_markers(self, fake) -> None:
        seconds = fake.random_int(min=0, max=9_999_999)
        assert "д" in format_uptime(seconds, "ru")

    @pytest.mark.unit
    def test_faker_en_contains_markers(self, fake) -> None:
        seconds = fake.random_int(min=0, max=9_999_999)
        assert "d" in format_uptime(seconds, "en")

    @pytest.mark.unit
    @pytest.mark.parametrize("seconds", [0, 1, 86399, 86400, 86401])
    def test_boundary_seconds(self, seconds: int) -> None:
        assert isinstance(format_uptime(seconds, "ru"), str)


class TestFormatDate:
    @pytest.mark.unit
    def test_none_returns_dash(self) -> None:
        assert format_date(None) == "—"

    @pytest.mark.unit
    def test_none_en_returns_dash(self) -> None:
        assert format_date(None, "en") == "—"

    @pytest.mark.unit
    def test_ru_format(self) -> None:
        assert format_date(datetime(2024, 3, 15), "ru") == "15.03.2024"

    @pytest.mark.unit
    def test_en_format(self) -> None:
        assert format_date(datetime(2024, 3, 15), "en") == "03/15/2024"

    @pytest.mark.unit
    def test_default_lang_is_ru(self) -> None:
        assert format_date(datetime(2024, 1, 1)) == "01.01.2024"

    @pytest.mark.unit
    def test_year_boundary(self) -> None:
        assert format_date(datetime(2000, 1, 1), "ru") == "01.01.2000"
        assert format_date(datetime(2099, 12, 31), "ru") == "31.12.2099"

    @pytest.mark.unit
    def test_faker_ru_has_dots(self, fake) -> None:
        result = format_date(fake.date_time(), "ru")
        assert result.count(".") == 2 and len(result) == 10

    @pytest.mark.unit
    def test_faker_en_has_slashes(self, fake) -> None:
        result = format_date(fake.date_time(), "en")
        assert result.count("/") == 2 and len(result) == 10


class TestEscapeHtml:
    @pytest.mark.unit
    @pytest.mark.parametrize("raw,expected", [
        ("<b>bold</b>",     "&lt;b&gt;bold&lt;/b&gt;"),
        ("a & b",           "a &amp; b"),
        ('"quoted"',        "&quot;quoted&quot;"),
        ("no special",      "no special"),
        ("",                ""),
        ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
        ("< > & \"",        "&lt; &gt; &amp; &quot;"),
    ])
    def test_known_values(self, raw: str, expected: str) -> None:
        assert escape_html(raw) == expected

    @pytest.mark.unit
    def test_no_special_chars_unchanged(self, fake) -> None:
        text = " ".join(fake.words(10)).replace("<","").replace(">","").replace("&","").replace('"',"")
        assert escape_html(text) == text

    @pytest.mark.unit
    def test_ampersand_not_double_escaped(self) -> None:
        result = escape_html("a & b")
        assert result == "a &amp; b"
        assert "amp;amp" not in result


class TestTruncate:
    @pytest.mark.unit
    def test_short_text_unchanged(self) -> None:
        assert truncate("hello", 100) == "hello"

    @pytest.mark.unit
    def test_exactly_max_length_unchanged(self) -> None:
        text = "a" * 4096
        assert truncate(text, 4096) == text

    @pytest.mark.unit
    def test_longer_text_truncated_with_ellipsis(self) -> None:
        result = truncate("a" * 5000, 4096)
        assert len(result) == 4096 and result.endswith("…")

    @pytest.mark.unit
    def test_custom_suffix(self) -> None:
        result = truncate("a" * 200, 100, suffix="...")
        assert len(result) == 100 and result.endswith("...")

    @pytest.mark.unit
    def test_default_max_length_4096(self) -> None:
        assert len(truncate("x" * 5000)) == 4096

    @pytest.mark.unit
    def test_empty_string(self) -> None:
        assert truncate("", 100) == ""

    @pytest.mark.unit
    def test_faker_long_text_bounded(self, fake) -> None:
        assert len(truncate(fake.text(max_nb_chars=10_000), 4096)) <= 4096

    @pytest.mark.unit
    @pytest.mark.parametrize("max_len", [10, 100, 500, 1000, 4096])
    def test_result_never_exceeds_max_length(self, max_len: int) -> None:
        assert len(truncate("x" * (max_len * 2), max_len)) == max_len


class TestFormatFloat:
    @pytest.mark.unit
    @pytest.mark.parametrize("value,decimals,expected", [
        (3.14159,  2,  "3.14"),
        (0.0,      2,  "0.00"),
        (1.0,      0,  "1"),
        (3.14159,  4,  "3.1416"),
        (100.0,    2,  "100.00"),
        (-1.5,     1,  "-1.5"),
        (0.005,    2,  "0.01"),
        (0.004,    2,  "0.00"),
    ])
    def test_known_values(self, value: float, decimals: int, expected: str) -> None:
        assert format_float(value, decimals) == expected

    @pytest.mark.unit
    def test_default_decimals_is_2(self) -> None:
        assert format_float(3.14159) == "3.14"

    @pytest.mark.unit
    def test_faker_correct_decimal_places(self, fake) -> None:
        result = format_float(fake.pyfloat(min_value=0, max_value=9999), 3)
        assert len(result.split(".")[1]) == 3


class TestConvertToMarkdownV2:
    @pytest.mark.unit
    def test_plain_text_escapes_special_chars(self) -> None:
        assert convert_to_markdownv2("Hello. World!") == r"Hello\. World\!"

    @pytest.mark.unit
    def test_empty_string(self) -> None:
        assert convert_to_markdownv2("") == ""

    @pytest.mark.unit
    def test_no_markdown_plain_words(self) -> None:
        assert convert_to_markdownv2("simple text") == "simple text"

    @pytest.mark.unit
    def test_code_block_language_tag(self) -> None:
        result = convert_to_markdownv2("```python\nprint('hello')\n```")
        assert result.startswith("```python") and "print" in result

    @pytest.mark.unit
    def test_code_block_no_language(self) -> None:
        result = convert_to_markdownv2("```\nsome code\n```")
        assert "some code" in result and result.count("```") == 2

    @pytest.mark.unit
    def test_inline_code_preserved(self) -> None:
        assert "`print()`" in convert_to_markdownv2("Use `print()` here")

    @pytest.mark.unit
    def test_bold_converted(self) -> None:
        assert "*bold*" in convert_to_markdownv2("This is **bold** text")

    @pytest.mark.unit
    def test_italic_star_converted(self) -> None:
        assert "_italic_" in convert_to_markdownv2("This is *italic* text")

    @pytest.mark.unit
    def test_italic_underscore_converted(self) -> None:
        assert "_italic_" in convert_to_markdownv2("This is _italic_ text")

    @pytest.mark.unit
    def test_mixed_bold_and_code(self) -> None:
        result = convert_to_markdownv2("Use **bold** and `code` together")
        assert "*bold*" in result and "`code`" in result

    @pytest.mark.unit
    @pytest.mark.parametrize("char", [".", "!", "-", "#", "+", "=", "|", "{", "}", "~"])
    def test_special_chars_escaped(self, char: str) -> None:
        assert convert_to_markdownv2(char) == f"\\{char}"

    @pytest.mark.unit
    def test_code_block_backtick_escaped_inside(self) -> None:
        assert r"\`" in convert_to_markdownv2("```\ncode with ` backtick\n```")

    @pytest.mark.unit
    def test_result_is_string(self, fake) -> None:
        assert isinstance(convert_to_markdownv2(fake.paragraph()), str)

    @pytest.mark.unit
    @pytest.mark.parametrize("text,fragment", [
        ("**hello world**",   "*hello world*"),
        ("*hello world*",     "_hello world_"),
        ("_hello world_",     "_hello world_"),
        ("`hello world`",     "`hello world`"),
    ])
    def test_formatting_constructs(self, text: str, fragment: str) -> None:
        assert fragment in convert_to_markdownv2(text)
