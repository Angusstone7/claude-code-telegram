"""
Translation manager for multi-language support.

Supports: Russian (ru), English (en), Chinese (zh)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = ["ru", "en", "zh"]
DEFAULT_LANGUAGE = "ru"

# Cache for loaded translations
_translations_cache: Dict[str, Dict[str, str]] = {}

# Cache for Translator instances
_translator_cache: Dict[str, "Translator"] = {}


def _load_translations(lang: str) -> Dict[str, str]:
    """Load translations from JSON file."""
    if lang in _translations_cache:
        return _translations_cache[lang]

    # Get path to translation file
    i18n_dir = Path(__file__).parent
    file_path = i18n_dir / f"{lang}.json"

    if not file_path.exists():
        logger.warning(f"Translation file not found: {file_path}, falling back to {DEFAULT_LANGUAGE}")
        if lang != DEFAULT_LANGUAGE:
            return _load_translations(DEFAULT_LANGUAGE)
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            translations = json.load(f)
            _translations_cache[lang] = translations
            logger.info(f"Loaded {len(translations)} translations for '{lang}'")
            return translations
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load translations for '{lang}': {e}")
        if lang != DEFAULT_LANGUAGE:
            return _load_translations(DEFAULT_LANGUAGE)
        return {}


class Translator:
    """
    Translation helper class.

    Usage:
        t = Translator("en")
        text = t.get("menu.projects")  # Returns "Projects"
        text = t.get("greeting", name="John")  # Returns "Hello, John!"
    """

    def __init__(self, lang: str = DEFAULT_LANGUAGE):
        """Initialize translator with specified language."""
        if lang not in SUPPORTED_LANGUAGES:
            logger.warning(f"Unsupported language '{lang}', using {DEFAULT_LANGUAGE}")
            lang = DEFAULT_LANGUAGE

        self.lang = lang
        self._translations = _load_translations(lang)
        self._fallback = None

        # Load fallback translations (Russian) if not already Russian
        if lang != DEFAULT_LANGUAGE:
            self._fallback = _load_translations(DEFAULT_LANGUAGE)

    def get(self, key: str, **kwargs) -> str:
        """
        Get translated string by key.

        Args:
            key: Translation key (e.g., "menu.projects", "error.not_found")
            **kwargs: Format arguments for string interpolation

        Returns:
            Translated string, or key if translation not found
        """
        # Try current language
        text = self._translations.get(key)

        # Fallback to default language
        if text is None and self._fallback:
            text = self._fallback.get(key)

        # If still not found, return key
        if text is None:
            logger.debug(f"Missing translation for key '{key}' in '{self.lang}'")
            return key

        # Apply format arguments if provided
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing format argument {e} for key '{key}'")
                return text

        return text

    def __call__(self, key: str, **kwargs) -> str:
        """Shorthand for get() - allows t("key") syntax."""
        return self.get(key, **kwargs)

    @property
    def language(self) -> str:
        """Get current language code."""
        return self.lang

    @property
    def language_name(self) -> str:
        """Get human-readable language name."""
        names = {
            "ru": "Русский",
            "en": "English",
            "zh": "中文",
        }
        return names.get(self.lang, self.lang)

    @property
    def language_flag(self) -> str:
        """Get language flag emoji."""
        flags = {
            "ru": "🇷🇺",
            "en": "🇬🇧",
            "zh": "🇨🇳",
        }
        return flags.get(self.lang, "🌐")


def get_translator(lang: str = DEFAULT_LANGUAGE) -> Translator:
    """
    Get or create a cached Translator instance.

    This is the recommended way to get a translator to avoid
    creating multiple instances for the same language.
    """
    if lang not in _translator_cache:
        _translator_cache[lang] = Translator(lang)
    return _translator_cache[lang]


def clear_cache():
    """Clear all translation caches. Useful for reloading translations."""
    _translations_cache.clear()
    _translator_cache.clear()


# Convenience function for getting supported languages
def get_supported_languages() -> list:
    """Return list of supported language codes."""
    return SUPPORTED_LANGUAGES.copy()
