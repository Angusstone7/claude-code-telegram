"""
Internationalization (i18n) module for Telegram bot.

Provides translation support for Russian, English, and Chinese.
"""

from .translator import Translator, get_translator

__all__ = ["Translator", "get_translator"]
