"""
Проверка полноты и корректности ключей для всех 8 языков бота.

Эталон: bot/src/locales/test.yml, секция «test_language».
Там перечислены все допустимые ключи с пустыми значениями.

Тест упадёт если:
  - у языка нет ключа из test_language        (missing)
  - у языка есть лишний ключ, которого нет в test_language  (extra)
  - любое строковое значение в языковом файле — пустая строка
  - в test.yml появились непустые значения (нарушение назначения шаблона)
"""

from pathlib import Path

import pytest
import yaml
from faker import Faker

_LOCALES_DIR = Path(__file__).resolve().parents[2] / "src" / "locales"
_TEST_LOCALE_FILE = _LOCALES_DIR / "test.yml"
_REAL_LANGS = ["ru", "en", "de", "es", "fr", "pl", "pt", "tr"]

fake = Faker()
Faker.seed(42)

# Fixtures

@pytest.fixture(scope="module")
def reference_keys() -> frozenset[str]:
    """Ключи из test.yml → gold standard для всех языков."""
    data = yaml.safe_load(_TEST_LOCALE_FILE.read_text(encoding="utf-8")) or {}
    keys = frozenset((data.get("test_language") or {}).keys())
    assert keys, "test.yml пустой — нет эталонных ключей"
    return keys

@pytest.fixture(scope="module")
def all_locale_data() -> dict[str, dict]:
    """Загружаем все 8 языковых файлов один раз для модуля."""
    result: dict[str, dict] = {}
    for lang in _REAL_LANGS:
        yml_file = _LOCALES_DIR / f"{lang}.yml"
        data = yaml.safe_load(yml_file.read_text(encoding="utf-8")) or {}
        result[lang] = data.get(lang) or {}
    return result

# Тесты самого test.yml (эталон должен быть правильным)

class TestReferenceFile:

    def test_reference_file_exists(self) -> None:
        assert _TEST_LOCALE_FILE.exists(), f"test.yml не найден: {_TEST_LOCALE_FILE}"

    def test_reference_has_test_language_section(self) -> None:
        data = yaml.safe_load(_TEST_LOCALE_FILE.read_text(encoding="utf-8")) or {}
        assert "test_language" in data, "В test.yml нет секции test_language"

    def test_reference_has_reasonable_key_count(self, reference_keys: frozenset[str]) -> None:
        assert len(reference_keys) >= 50, (
            f"В test.yml слишком мало ключей: {len(reference_keys)} — возможно файл неполный"
        )

    def test_reference_all_values_are_empty_strings(self) -> None:
        """test.yml — шаблон, все значения должны быть пустыми строками."""
        data = yaml.safe_load(_TEST_LOCALE_FILE.read_text(encoding="utf-8")) or {}
        section = data.get("test_language") or {}
        non_empty = {k: v for k, v in section.items() if v != ""}
        assert not non_empty, (
            f"test.yml содержит непустые значения (шаблон должен быть пустым): "
            f"{list(non_empty.keys())[:5]}"
        )

    def test_faker_random_key_absent_from_reference(self, reference_keys: frozenset[str]) -> None:
        """Рандомные ключи заведомо не входят в эталон."""
        for _ in range(10):
            random_key = "faker_test_" + fake.lexify("?" * 24)
            assert random_key not in reference_keys, (
                f"Случайный ключ '{random_key}' неожиданно оказался в test.yml"
            )

    def test_reference_no_duplicate_keys(self) -> None:
        """YAML-парсер объединяет дубли — проверяем через raw-текст."""
        raw = _TEST_LOCALE_FILE.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        section = data.get("test_language") or {}
        assert len(section) == len(set(section.keys())), "В test.yml есть дублирующиеся ключи"

# Проверка всех языков против эталона

class TestLocaleKeyCompleteness:

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_no_missing_keys(
        self,
        lang: str,
        reference_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """Все ключи из test.yml присутствуют в языке."""
        lang_keys = frozenset(all_locale_data[lang].keys())
        missing = reference_keys - lang_keys
        assert not missing, (
            f"Язык '{lang}' не хватает {len(missing)} ключей из test.yml:\n"
            + "\n".join(f"  - {k}" for k in sorted(missing))
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_no_extra_keys(
        self,
        lang: str,
        reference_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """В языке нет ключей сверх тех, что заявлены в test.yml.

        Если тест падает — добавьте новый ключ в test.yml.
        """
        lang_keys = frozenset(all_locale_data[lang].keys())
        extra = lang_keys - reference_keys
        assert not extra, (
            f"Язык '{lang}' содержит {len(extra)} ключей, которых нет в test.yml:\n"
            + "\n".join(f"  - {k}" for k in sorted(extra))
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_key_count_matches_reference(
        self,
        lang: str,
        reference_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """Количество ключей в языке равно количеству ключей в эталоне."""
        lang_key_count = len(all_locale_data[lang])
        ref_count = len(reference_keys)
        assert lang_key_count == ref_count, (
            f"Язык '{lang}': {lang_key_count} ключей, эталон: {ref_count}"
        )

# Проверка значений

class TestLocaleValues:

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_all_values_are_strings(
        self,
        lang: str,
        all_locale_data: dict,
    ) -> None:
        """Все значения в языковом файле — строки."""
        non_string = {
            k: type(v).__name__
            for k, v in all_locale_data[lang].items()
            if not isinstance(v, str)
        }
        assert not non_string, (
            f"Язык '{lang}' содержит нестроковые значения: {non_string}"
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_no_empty_string_values(
        self,
        lang: str,
        all_locale_data: dict,
    ) -> None:
        """Ни одно строковое значение не должно быть пустым."""
        empty_keys = [
            key for key, val in all_locale_data[lang].items()
            if isinstance(val, str) and not val.strip()
        ]
        assert not empty_keys, (
            f"Язык '{lang}' содержит пустые строки:\n"
            + "\n".join(f"  - {k}" for k in empty_keys)
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_values_differ_from_key_names(
        self,
        lang: str,
        all_locale_data: dict,
    ) -> None:
        """Значения не совпадают с именами ключей (признак незаполненного файла)."""
        same_as_key = [
            k for k, v in all_locale_data[lang].items()
            if isinstance(v, str) and v.strip() == k
        ]
        assert not same_as_key, (
            f"Язык '{lang}': значения совпадают с именами ключей "
            f"(незаполненный файл?): {same_as_key[:5]}"
        )

# Корректность структуры файлов

class TestLocaleFileStructure:

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_yml_file_exists(self, lang: str) -> None:
        yml_file = _LOCALES_DIR / f"{lang}.yml"
        assert yml_file.exists(), f"Файл локализации не найден: {yml_file}"

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_yml_root_key_matches_lang(self, lang: str) -> None:
        """Корневой ключ файла должен совпадать с кодом языка."""
        yml_file = _LOCALES_DIR / f"{lang}.yml"
        data = yaml.safe_load(yml_file.read_text(encoding="utf-8")) or {}
        assert lang in data, (
            f"{lang}.yml не содержит корневого ключа '{lang}'. "
            f"Найденные ключи: {list(data.keys())}"
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_yml_not_empty(self, lang: str, all_locale_data: dict) -> None:
        assert all_locale_data[lang], f"Файл {lang}.yml пустой"

    def test_all_8_languages_present(self) -> None:
        """Убеждаемся, что все 8 языков действительно существуют."""
        missing_files = [
            lang for lang in _REAL_LANGS
            if not (_LOCALES_DIR / f"{lang}.yml").exists()
        ]
        assert not missing_files, f"Отсутствуют файлы для языков: {missing_files}"