"""
Internationalization (i18n) module for Telegram bot.

Provides translation support for Russian, English, and Chinese.
"""

from .translator import (
    Translator,
    get_translator,
    get_supported_languages,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
)

__all__ = [
    "Translator",
    "get_translator",
    "get_supported_languages",
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
]
