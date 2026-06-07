"""
Проверка полноты и корректности ключей для всех 8 языков Mini App.

Эталон: mini-app/src/locales/test.json — плоский JSON, все строковые значения
пустые, loading_tips — пустой массив. Определяет полный набор допустимых ключей.

Тест упадёт если:
  - у языка нет ключа из test.json               (missing)
  - у языка есть лишний ключ, которого нет в test.json  (extra)
  - строковое значение в языке — пустая строка
  - loading_tips — пустой массив или элементы не являются строками
  - в test.json появились непустые значения (нарушение назначения шаблона)
"""

import json
from pathlib import Path

import pytest
from faker import Faker

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MINIAPP_LOCALES_DIR = _PROJECT_ROOT / "mini-app" / "src" / "locales"
_TEST_LOCALE_FILE = _MINIAPP_LOCALES_DIR / "test.json"
_REAL_LANGS = ["ru", "en", "de", "es", "fr", "pl", "pt", "tr"]

_SKIP_ALL = not _MINIAPP_LOCALES_DIR.is_dir()

fake = Faker()
Faker.seed(42)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> dict:
    # utf-8-sig снимает BOM (присутствует в части файлов), для остальных — прозрачен
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _is_array_key(value) -> bool:
    return isinstance(value, list)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def reference_data() -> dict:
    """Полное содержимое test.json."""
    return _load_json(_TEST_LOCALE_FILE)


@pytest.fixture(scope="module")
def reference_string_keys(reference_data: dict) -> frozenset[str]:
    """Ключи, чьи значения в эталоне — строки."""
    return frozenset(k for k, v in reference_data.items() if isinstance(v, str))


@pytest.fixture(scope="module")
def reference_array_keys(reference_data: dict) -> frozenset[str]:
    """Ключи, чьи значения в эталоне — массивы."""
    return frozenset(k for k, v in reference_data.items() if isinstance(v, list))


@pytest.fixture(scope="module")
def reference_keys(reference_data: dict) -> frozenset[str]:
    """Все ключи из test.json."""
    return frozenset(reference_data.keys())


@pytest.fixture(scope="module")
def all_locale_data() -> dict[str, dict]:
    """Загружаем все 8 JSON-локалей один раз."""
    return {lang: _load_json(_MINIAPP_LOCALES_DIR / f"{lang}.json") for lang in _REAL_LANGS}


# ── Тесты самого test.json (эталон должен быть правильным) ────────────────────


@pytest.mark.skipif(_SKIP_ALL, reason="mini-app/src/locales не найден")
class TestReferenceFile:

    def test_reference_file_exists(self) -> None:
        assert _TEST_LOCALE_FILE.exists(), f"test.json не найден: {_TEST_LOCALE_FILE}"

    def test_reference_is_valid_json(self) -> None:
        data = _load_json(_TEST_LOCALE_FILE)
        assert isinstance(data, dict), "test.json должен быть объектом JSON"

    def test_reference_has_keys(self, reference_keys: frozenset[str]) -> None:
        assert len(reference_keys) >= 20, (
            f"test.json содержит слишком мало ключей: {len(reference_keys)}"
        )

    def test_reference_string_values_are_empty(
        self,
        reference_data: dict,
        reference_string_keys: frozenset[str],
    ) -> None:
        """Строковые значения в test.json — пустые строки (шаблон)."""
        non_empty = {
            k: reference_data[k]
            for k in reference_string_keys
            if reference_data[k] != ""
        }
        assert not non_empty, (
            f"test.json содержит непустые строки (должен быть шаблоном): "
            f"{list(non_empty.keys())[:5]}"
        )

    def test_reference_array_values_are_empty_lists(
        self,
        reference_data: dict,
        reference_array_keys: frozenset[str],
    ) -> None:
        """Массивы в test.json — пустые (шаблон)."""
        non_empty_arrays = {
            k: reference_data[k]
            for k in reference_array_keys
            if reference_data[k] != []
        }
        assert not non_empty_arrays, (
            f"test.json содержит непустые массивы: {list(non_empty_arrays.keys())}"
        )

    def test_faker_random_key_absent_from_reference(self, reference_keys: frozenset[str]) -> None:
        """Faker-ключи гарантированно отсутствуют в эталоне."""
        for _ in range(10):
            ghost_key = "faker_" + fake.lexify("?" * 24)
            assert ghost_key not in reference_keys


# ── Проверка всех языков против эталона ──────────────────────────────────────


@pytest.mark.skipif(_SKIP_ALL, reason="mini-app/src/locales не найден")
class TestLocaleKeyCompleteness:

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_no_missing_keys(
        self,
        lang: str,
        reference_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """Все ключи из test.json присутствуют в языке."""
        lang_keys = frozenset(all_locale_data[lang].keys())
        missing = reference_keys - lang_keys
        assert not missing, (
            f"Язык '{lang}' не хватает {len(missing)} ключей из test.json:\n"
            + "\n".join(f"  - {k}" for k in sorted(missing))
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_no_extra_keys(
        self,
        lang: str,
        reference_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """В языке нет ключей сверх тех, что заявлены в test.json.

        Если тест падает — добавьте новый ключ в test.json.
        """
        lang_keys = frozenset(all_locale_data[lang].keys())
        extra = lang_keys - reference_keys
        assert not extra, (
            f"Язык '{lang}' содержит {len(extra)} ключей, которых нет в test.json:\n"
            + "\n".join(f"  - {k}" for k in sorted(extra))
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_key_count_matches_reference(
        self,
        lang: str,
        reference_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """Количество ключей точно совпадает с эталоном."""
        lang_key_count = len(all_locale_data[lang])
        ref_count = len(reference_keys)
        assert lang_key_count == ref_count, (
            f"Язык '{lang}': {lang_key_count} ключей, эталон: {ref_count}"
        )


# ── Проверка строковых значений ───────────────────────────────────────────────


@pytest.mark.skipif(_SKIP_ALL, reason="mini-app/src/locales не найден")
class TestLocaleStringValues:

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_string_keys_have_non_empty_values(
        self,
        lang: str,
        reference_string_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """Все строковые значения в языке непустые."""
        lang_data = all_locale_data[lang]
        empty_keys = [
            k for k in reference_string_keys
            if k in lang_data and isinstance(lang_data[k], str) and not lang_data[k].strip()
        ]
        assert not empty_keys, (
            f"Язык '{lang}' содержит пустые строки:\n"
            + "\n".join(f"  - {k}" for k in empty_keys)
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_string_keys_remain_strings(
        self,
        lang: str,
        reference_string_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """Ключи, которые являются строками в эталоне, остаются строками."""
        lang_data = all_locale_data[lang]
        type_mismatch = {
            k: type(lang_data[k]).__name__
            for k in reference_string_keys
            if k in lang_data and not isinstance(lang_data[k], str)
        }
        assert not type_mismatch, (
            f"Язык '{lang}': ожидались строки, получены другие типы: {type_mismatch}"
        )


# ── Проверка массивов (loading_tips и подобные) ───────────────────────────────


@pytest.mark.skipif(_SKIP_ALL, reason="mini-app/src/locales не найден")
class TestLocaleArrayValues:

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_array_keys_remain_lists(
        self,
        lang: str,
        reference_array_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """Ключи, являющиеся массивами в эталоне, остаются списками."""
        lang_data = all_locale_data[lang]
        type_mismatch = {
            k: type(lang_data[k]).__name__
            for k in reference_array_keys
            if k in lang_data and not isinstance(lang_data[k], list)
        }
        assert not type_mismatch, (
            f"Язык '{lang}': ожидались массивы, получены другие типы: {type_mismatch}"
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_array_keys_are_non_empty(
        self,
        lang: str,
        reference_array_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """Массивы в языковом файле не должны быть пустыми."""
        lang_data = all_locale_data[lang]
        empty_arrays = [
            k for k in reference_array_keys
            if k in lang_data and isinstance(lang_data[k], list) and len(lang_data[k]) == 0
        ]
        assert not empty_arrays, (
            f"Язык '{lang}' содержит пустые массивы: {empty_arrays}"
        )

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_array_elements_are_non_empty_strings(
        self,
        lang: str,
        reference_array_keys: frozenset[str],
        all_locale_data: dict,
    ) -> None:
        """Каждый элемент массива — непустая строка."""
        lang_data = all_locale_data[lang]
        for key in reference_array_keys:
            if key not in lang_data or not isinstance(lang_data[key], list):
                continue
            for i, item in enumerate(lang_data[key]):
                assert isinstance(item, str) and item.strip(), (
                    f"Язык '{lang}', ключ '{key}', элемент [{i}]: "
                    f"ожидалась непустая строка, получено {item!r}"
                )


# ── Структурные тесты файлов ──────────────────────────────────────────────────


@pytest.mark.skipif(_SKIP_ALL, reason="mini-app/src/locales не найден")
class TestLocaleFileStructure:

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_json_file_exists(self, lang: str) -> None:
        json_file = _MINIAPP_LOCALES_DIR / f"{lang}.json"
        assert json_file.exists(), f"Файл локализации не найден: {json_file}"

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_json_is_valid(self, lang: str) -> None:
        json_file = _MINIAPP_LOCALES_DIR / f"{lang}.json"
        data = _load_json(json_file)
        assert isinstance(data, dict), f"{lang}.json не является объектом"

    @pytest.mark.parametrize("lang", _REAL_LANGS)
    def test_json_not_empty(self, lang: str, all_locale_data: dict) -> None:
        assert all_locale_data[lang], f"{lang}.json пустой"

    def test_all_8_languages_present(self) -> None:
        """Убеждаемся, что все 8 языков действительно существуют."""
        missing_files = [
            lang for lang in _REAL_LANGS
            if not (_MINIAPP_LOCALES_DIR / f"{lang}.json").exists()
        ]
        assert not missing_files, f"Отсутствуют файлы для языков: {missing_files}"

    def test_faker_generated_values_not_in_test_json(self, reference_data: dict) -> None:
        """Faker-значения не проникают в эталонный файл."""
        for _ in range(5):
            random_val = fake.sentence()
            for v in reference_data.values():
                if isinstance(v, str):
                    assert v != random_val
