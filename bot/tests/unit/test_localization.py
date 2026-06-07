"""Юнит-тесты для bot/src/utils/localization.py."""

import types

import pytest

from src.utils.localization import get_supported_languages, resolve_lang, t

_TEST_LOCALES = {
    "ru": {
        "greeting":      "Привет!",
        "access_denied": "Доступ запрещён.",
        "hello":         "Привет, {name}!",
        "count":         "Всего: {count} штук.",
    },
    "en": {
        "greeting":      "Hello!",
        "access_denied": "Access denied.",
        "hello":         "Hello, {name}!",
        "count":         "Total: {count} items.",
    },
    "de": {
        "greeting": "Hallo!",
        # 'hello' намеренно отсутствует → тест fallback на ru
    },
}


@pytest.fixture
def mock_locales(mocker):
    return mocker.patch(
        "src.utils.localization.get_settings",
        return_value=types.SimpleNamespace(locales=_TEST_LOCALES),
    )


class TestResolveLang:
    @pytest.mark.unit
    @pytest.mark.parametrize("input_lang,expected", [
        # CIS → ru
        ("ru", "ru"), ("uk", "ru"), ("be", "ru"), ("kk", "ru"), ("ky", "ru"),
        ("uz", "ru"), ("tg", "ru"), ("tk", "ru"), ("hy", "ru"), ("az", "ru"), ("mo", "ru"),
        # Поддерживаемые
        ("en", "en"), ("de", "de"), ("es", "es"), ("fr", "fr"),
        ("pl", "pl"), ("pt", "pt"), ("tr", "tr"),
        # Региональный суффикс отбрасывается
        ("es-MX", "es"), ("pt-BR", "pt"), ("en-US", "en"),
        ("ru-RU", "ru"), ("fr-CA", "fr"), ("de-AT", "de"),
        # Unsupported → en
        ("zh", "en"), ("ja", "en"), ("ar", "en"), ("ko", "en"), ("hi", "en"),
        # Edge cases
        (None, "en"), ("", "en"),
        # Case insensitive
        ("RU", "ru"), ("EN", "en"), ("ES-MX", "es"), ("PT-BR", "pt"),
    ])
    def test_resolve_lang(self, input_lang, expected: str) -> None:
        assert resolve_lang(input_lang) == expected

    @pytest.mark.unit
    def test_cis_with_region_suffix(self) -> None:
        assert resolve_lang("uk-UA") == "ru"
        assert resolve_lang("kk-KZ") == "ru"

    @pytest.mark.unit
    def test_unknown_code_returns_en(self) -> None:
        assert resolve_lang("xx") == "en"


class TestT:
    @pytest.mark.unit
    def test_found_key_ru(self, mock_locales) -> None:
        assert t("greeting", "ru") == "Привет!"

    @pytest.mark.unit
    def test_found_key_en(self, mock_locales) -> None:
        assert t("greeting", "en") == "Hello!"

    @pytest.mark.unit
    def test_found_key_de(self, mock_locales) -> None:
        assert t("greeting", "de") == "Hallo!"

    @pytest.mark.unit
    def test_missing_key_returns_placeholder(self, mock_locales) -> None:
        result = t("nonexistent_key_xyz", "ru")
        assert result == "[MISSING KEY: nonexistent_key_xyz]"

    @pytest.mark.unit
    def test_missing_key_in_lang_falls_back_to_ru(self, mock_locales) -> None:
        # "de" не имеет ключа "hello" → fallback на ru
        result = t("hello", "de")
        assert "Привет" in result

    @pytest.mark.unit
    def test_missing_key_in_both(self, mock_locales) -> None:
        assert t("totally_missing", "de").startswith("[MISSING KEY:")

    @pytest.mark.unit
    def test_format_kwargs(self, mock_locales) -> None:
        assert t("hello", "ru", name="Вася") == "Привет, Вася!"

    @pytest.mark.unit
    def test_format_kwargs_en(self, mock_locales) -> None:
        assert t("hello", "en", name="World") == "Hello, World!"

    @pytest.mark.unit
    def test_format_kwargs_count(self, mock_locales) -> None:
        assert t("count", "ru", count=42) == "Всего: 42 штук."

    @pytest.mark.unit
    def test_format_wrong_key_returns_template(self, mock_locales) -> None:
        result = t("hello", "ru", wrong_key="value")
        assert "Привет" in result

    @pytest.mark.unit
    def test_no_format_args_returns_plain(self, mock_locales) -> None:
        result = t("greeting", "ru")
        assert result == "Привет!" and "{" not in result

    @pytest.mark.unit
    def test_faker_key_always_placeholder(self, mock_locales, fake) -> None:
        key = "fake_" + fake.lexify("?" * 20)
        assert t(key, "ru") == f"[MISSING KEY: {key}]"

    @pytest.mark.unit
    @pytest.mark.parametrize("lang", ["ru", "en", "de"])
    def test_all_langs_return_string(self, mock_locales, lang: str) -> None:
        result = t("greeting", lang)
        assert isinstance(result, str) and len(result) > 0


class TestGetSupportedLanguages:
    @pytest.mark.unit
    def test_returns_list(self, mock_locales) -> None:
        assert isinstance(get_supported_languages(), list)

    @pytest.mark.unit
    def test_contains_mocked_langs(self, mock_locales) -> None:
        langs = get_supported_languages()
        assert "ru" in langs and "en" in langs and "de" in langs

    @pytest.mark.unit
    def test_length_matches_locales(self, mock_locales) -> None:
        assert len(get_supported_languages()) == len(_TEST_LOCALES)

    @pytest.mark.unit
    def test_no_duplicates(self, mock_locales) -> None:
        langs = get_supported_languages()
        assert len(langs) == len(set(langs))
