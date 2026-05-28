import logging
from typing import Any

from src.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_LANG = "ru"

# Telegram language_codes mapped to Russian interface
_CIS_LANGS = frozenset({"ru", "be", "uk", "kk", "ky", "uz", "tg", "tk", "hy", "az", "mo"})

# All supported interface languages
_SUPPORTED_LANGS = frozenset({"ru", "en", "de", "es", "fr", "pl", "pt", "tr"})


def resolve_lang(tg_lang: str | None) -> str:
    """Map a Telegram language_code to one of the 8 supported interface languages.

    Strategy:
      1. Strip region suffix: "es-MX" → "es", "pt-BR" → "pt"
      2. CIS languages (ru/uk/be/kk/uz/ky/tg/tk/hy/az/mo) → "ru"
      3. Directly supported (en/de/es/fr/pl/pt/tr) → themselves
      4. Anything else → "en"
    """
    if tg_lang:
        base = tg_lang.split("-")[0].lower()
        if base in _CIS_LANGS:
            return "ru"
        if base in _SUPPORTED_LANGS:
            return base
    return "en"


def t(key: str, lang: str = DEFAULT_LANG, *args: Any, **kwargs: Any) -> str:
    locales = get_settings().locales

    # Пробуем запрошенный язык, потом ru как fallback
    result: str | None = locales.get(lang, {}).get(key)
    if result is None and lang != DEFAULT_LANG:
        result = locales.get(DEFAULT_LANG, {}).get(key)
    if result is None:
        logger.warning("Missing locale key: %r (lang=%s)", key, lang)
        return f"[MISSING KEY: {key}]"

    if args or kwargs:
        try:
            return result.format(*args, **kwargs)
        except (IndexError, KeyError) as e:
            logger.warning("Locale format error for key=%r: %s", key, e)
            return result

    return result


def get_supported_languages() -> list[str]:
    return list(get_settings().locales.keys())
