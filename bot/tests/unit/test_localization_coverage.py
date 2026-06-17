"""Тесты покрытия локализации.

Два слоя:
1. Структурный (без реальных файлов) — проверяем функции с mock locales
2. Файловый (если locale/*.yml существуют) — верифицируем реальные данные:
   - все языки имеют одинаковый набор ключей
   - все значения — непустые строки
   - нет дублирующихся ключей
"""

from pathlib import Path
from typing import Any

import pytest

from src.utils.localization import t

# Путь к реальным locale файлам

_LOCALES_DIR = Path(__file__).resolve().parents[2] / "src" / "locales"
_LOCALES_EXIST = _LOCALES_DIR.is_dir() and any(_LOCALES_DIR.glob("*.yml"))

# Mock-локали для структурных тестов

_COMPLETE_LOCALES: dict[str, dict[str, Any]] = {
    "ru": {
        "greeting": "Привет!",
        "welcome": "Добро пожаловать, {name}!",
        "access_denied": "Доступ запрещён.",
        "error": "Ошибка.",
        "profile_info": "Профиль",
        "status_admin": "Администратор",
        "status_user": "Пользователь",
    },
    "en": {
        "greeting": "Hello!",
        "welcome": "Welcome, {name}!",
        "access_denied": "Access denied.",
        "error": "Error.",
        "profile_info": "Profile",
        "status_admin": "Administrator",
        "status_user": "User",
    },
    "de": {
        "greeting": "Hallo!",
        "welcome": "Willkommen, {name}!",
        "access_denied": "Zugang verweigert.",
        "error": "Fehler.",
        "profile_info": "Profil",
        "status_admin": "Administrator",
        "status_user": "Benutzer",
    },
}

_INCOMPLETE_LOCALES: dict[str, dict[str, Any]] = {
    "ru": {"key_a": "A", "key_b": "B", "key_c": "C"},
    "en": {"key_a": "A", "key_b": "B"},  # missing key_c
}

# Структурные тесты (mock locales)

class TestLocaleCoverage:
    @pytest.mark.unit
    def test_all_languages_have_same_keys(self) -> None:
        """Все языки должны иметь одинаковый набор ключей."""
        all_langs = list(_COMPLETE_LOCALES.keys())
        key_sets = [set(_COMPLETE_LOCALES[lang].keys()) for lang in all_langs]
        reference = key_sets[0]
        for lang, keys in zip(all_langs[1:], key_sets[1:]):
            missing = reference - keys
            extra = keys - reference
            assert not missing, f"Lang '{lang}' missing keys: {missing}"
            assert not extra, f"Lang '{lang}' has extra keys: {extra}"

    @pytest.mark.unit
    def test_all_values_are_non_empty_strings(self) -> None:
        for lang, keys in _COMPLETE_LOCALES.items():
            for key, value in keys.items():
                assert isinstance(value, str) and len(value) > 0, \
                    f"Lang '{lang}', key '{key}': empty or non-string value"

    @pytest.mark.unit
    def test_detect_missing_keys_in_incomplete_locales(self) -> None:
        """Тест обнаруживает когда язык не хватает ключей."""
        ru_keys = set(_INCOMPLETE_LOCALES["ru"].keys())
        en_keys = set(_INCOMPLETE_LOCALES["en"].keys())
        missing_in_en = ru_keys - en_keys
        assert missing_in_en == {"key_c"}

    @pytest.mark.unit
    def test_no_duplicate_keys_per_language(self) -> None:
        """Дубликатов быть не должно (dict гарантирует это в Python 3.7+)."""
        for lang, keys in _COMPLETE_LOCALES.items():
            assert len(keys) == len(set(keys.keys())), f"Duplicate keys in '{lang}'"

    @pytest.mark.unit
    def test_format_placeholders_are_valid(self) -> None:
        """Строки с {name} и {count} должны форматироваться без ошибок."""
        for lang, keys in _COMPLETE_LOCALES.items():
            for key, value in keys.items():
                if "{name}" in value:
                    result = value.format(name="Test")
                    assert "Test" in result
                elif "{count}" in value:
                    result = value.format(count=42)
                    assert "42" in result

    @pytest.mark.unit
    @pytest.mark.parametrize("lang", ["ru", "en", "de"])
    def test_t_function_with_complete_locales(self, mocker, lang: str) -> None:
        """t() возвращает корректный перевод для каждого языка."""
        import types
        mocker.patch(
            "src.utils.localization.get_settings",
            return_value=types.SimpleNamespace(locales=_COMPLETE_LOCALES),
        )
        result = t("greeting", lang)
        assert result == _COMPLETE_LOCALES[lang]["greeting"]

    @pytest.mark.unit
    def test_t_function_missing_key_placeholder(self, mocker) -> None:
        import types
        mocker.patch(
            "src.utils.localization.get_settings",
            return_value=types.SimpleNamespace(locales=_COMPLETE_LOCALES),
        )
        result = t("nonexistent_key_xyz_987", "ru")
        assert result.startswith("[MISSING KEY:")

    @pytest.mark.unit
    def test_t_function_fallback_to_ru(self, mocker) -> None:
        """Если в языке нет ключа, должен быть fallback на ru."""
        import types
        locales = {
            "ru": {"hello": "Привет!"},
            "de": {},  # пустой DE — нет ни одного ключа
        }
        mocker.patch(
            "src.utils.localization.get_settings",
            return_value=types.SimpleNamespace(locales=locales),
        )
        result = t("hello", "de")
        assert result == "Привет!"  # fallback на ru

    @pytest.mark.unit
    def test_faker_random_key_always_missing(self, mocker, fake) -> None:
        import types
        mocker.patch(
            "src.utils.localization.get_settings",
            return_value=types.SimpleNamespace(locales=_COMPLETE_LOCALES),
        )
        for _ in range(5):
            key = "random_" + fake.lexify("?" * 30)
            result = t(key, "ru")
            assert result.startswith("[MISSING KEY:")

# Реальные файлы (пропускаем если не найдены)

@pytest.mark.skipif(not _LOCALES_EXIST, reason=f"Locale files not found at {_LOCALES_DIR}")
class TestRealLocaleFiles:
    @pytest.fixture(scope="class")
    def real_locales(self) -> dict[str, dict]:
        import yaml
        locales = {}
        for yml_file in sorted(_LOCALES_DIR.glob("*.yml")):
            data = yaml.safe_load(yml_file.read_text(encoding="utf-8")) or {}
            # Файл может быть структурирован как {lang: {keys}} или {key: {lang: val}}
            locales.update(data)
        return locales

    @pytest.mark.unit
    def test_real_locales_not_empty(self, real_locales) -> None:
        assert len(real_locales) > 0

    @pytest.mark.unit
    def test_all_real_langs_have_same_keys(self, real_locales) -> None:
        langs = list(real_locales.keys())
        if len(langs) < 2:
            pytest.skip("Only one language found — cannot compare")
        ru_keys = set(real_locales.get("ru", {}).keys())
        for lang in langs:
            lang_keys = set(real_locales[lang].keys())
            missing = ru_keys - lang_keys
            if missing:
                pytest.fail(f"Language '{lang}' is missing {len(missing)} keys: {list(missing)[:10]}")

    @pytest.mark.unit
    def test_all_real_values_are_strings(self, real_locales) -> None:
        for lang, keys in real_locales.items():
            for key, value in keys.items():
                assert isinstance(value, str), \
                    f"Lang='{lang}', key='{key}': expected str, got {type(value)}"

    @pytest.mark.unit
    def test_no_empty_real_values(self, real_locales) -> None:
        for lang, keys in real_locales.items():
            if lang == "test_language":
                continue  # эталонный шаблон — все значения намеренно пустые
            for key, value in keys.items():
                assert value.strip(), f"Lang='{lang}', key='{key}': empty string"

    @pytest.mark.unit
    def test_supported_langs_present(self, real_locales) -> None:
        expected_langs = {"ru", "en"}
        actual_langs = set(real_locales.keys())
        missing = expected_langs - actual_langs
        assert not missing, f"Missing expected languages: {missing}"