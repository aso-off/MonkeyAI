import ast
from pathlib import Path

import pytest
import yaml


# parents[2] resolves to the app root in both layouts:
#   Docker: /app/tests/unit/test_localization_keys.py  → /app
#   Local:  bot/tests/unit/test_localization_keys.py   → bot/
BOT_SRC_DIR = Path(__file__).resolve().parents[2] / "src"
LOCALES_DIR = BOT_SRC_DIR / "locales"


def _load_locale_keys(lang: str) -> set[str]:
    locale_file = LOCALES_DIR / f"{lang}.yml"
    data = yaml.safe_load(locale_file.read_text(encoding="utf-8")) or {}
    lang_block = data.get(lang, {})
    if not isinstance(lang_block, dict):
        return set()
    return set(lang_block.keys())


def _extract_used_localization_keys() -> set[str]:
    """Extract static keys from calls like t("some_key", ...)."""
    keys: set[str] = set()

    for py_file in BOT_SRC_DIR.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "t":
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                keys.add(first_arg.value)

    return keys


@pytest.mark.unit
def test_used_localization_keys_exist_in_ru_and_en() -> None:
    used = _extract_used_localization_keys()
    ru_keys = _load_locale_keys("ru")
    en_keys = _load_locale_keys("en")

    missing_ru = sorted(used - ru_keys)
    missing_en = sorted(used - en_keys)

    assert not missing_ru, f"Missing keys in ru.yml: {missing_ru}"
    assert not missing_en, f"Missing keys in en.yml: {missing_en}"


@pytest.mark.unit
def test_ru_and_en_have_same_keyset() -> None:
    ru_keys = _load_locale_keys("ru")
    en_keys = _load_locale_keys("en")

    ru_only = sorted(ru_keys - en_keys)
    en_only = sorted(en_keys - ru_keys)

    assert not ru_only, f"Keys present only in ru.yml: {ru_only}"
    assert not en_only, f"Keys present only in en.yml: {en_only}"


@pytest.mark.unit
def test_report_unused_localization_keys() -> None:
    used = _extract_used_localization_keys()
    ru_keys = _load_locale_keys("ru")
    en_keys = _load_locale_keys("en")
    all_locale_keys = ru_keys | en_keys

    unused = sorted(all_locale_keys - used)
    if unused:
        # Informational test: does not fail build, only reports candidates for cleanup.
        print(f"\nUnused localization keys candidates ({len(unused)}): {unused}")

    assert True
