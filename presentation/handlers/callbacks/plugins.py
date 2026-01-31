"""
Plugin management callback handlers.

Handles plugin listing, marketplace, enable/disable operations.
"""

import logging
from typing import Optional

from aiogram.types import CallbackQuery

from presentation.handlers.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)


class PluginCallbackHandler(BaseCallbackHandler):
    """Handler for plugin management callbacks."""

    async def handle_plugin_list(self, callback: CallbackQuery) -> None:
        """Show list of enabled plugins"""
        from presentation.keyboards.keyboards import Keyboards

        if not self.sdk_service:
            await callback.answer("⚠️ SDK не доступен")
            return

        plugins = self.sdk_service.get_enabled_plugins_info()

        if not plugins:
            text = (
                "🔌 <b>Плагины Claude Code</b>\n\n"
                "Нет активных плагинов.\n\n"
                "Нажмите 🛒 <b>Магазин</b> чтобы добавить плагины."
            )
        else:
            text = "🔌 <b>Плагины Claude Code</b>\n\n"
            for p in plugins:
                name = p.get("name", "unknown")
                desc = p.get("description", "")
                source = p.get("source", "official")
                available = p.get("available", True)

                status = "✅" if available else "⚠️"
                source_icon = "🌐" if source == "official" else "📁"
                text += f"{status} {source_icon} <b>{name}</b>\n"
                if desc:
                    text += f"   <i>{desc}</i>\n"

            text += f"\n<i>Всего: {len(plugins)} плагинов</i>"

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.plugins_menu(plugins)
        )
        await callback.answer()

    async def handle_plugin_refresh(self, callback: CallbackQuery) -> None:
        """Refresh plugins list"""
        await callback.answer("🔄 Обновлено")
        await self.handle_plugin_list(callback)

    async def handle_plugin_marketplace(self, callback: CallbackQuery) -> None:
        """Show marketplace with available plugins"""
        from presentation.keyboards.keyboards import Keyboards

        if not self.sdk_service:
            await callback.answer("⚠️ SDK не доступен")
            return

        # All available plugins from official marketplace
        marketplace_plugins = [
            {"name": "commit-commands", "desc": "Git workflow: commit, push, PR"},
            {"name": "code-review", "desc": "Ревью кода и PR"},
            {"name": "feature-dev", "desc": "Разработка фичи с архитектурой"},
            {"name": "frontend-design", "desc": "Создание UI интерфейсов"},
            {"name": "ralph-loop", "desc": "RAFL: итеративное решение задач"},
            {"name": "security-guidance", "desc": "Проверка безопасности кода"},
            {"name": "pr-review-toolkit", "desc": "Инструменты ревью PR"},
            {"name": "claude-code-setup", "desc": "Настройка Claude Code"},
            {"name": "hookify", "desc": "Управление хуками"},
            {"name": "explanatory-output-style", "desc": "Объяснительный стиль вывода"},
            {"name": "learning-output-style", "desc": "Обучающий стиль вывода"},
        ]

        # Get currently enabled plugins
        enabled = self.sdk_service.get_enabled_plugins_info()
        enabled_names = [p.get("name") for p in enabled]

        text = (
            "🛒 <b>Магазин плагинов</b>\n\n"
            "Выберите плагин для включения:\n"
            "✅ - уже включен\n"
            "➕ - нажмите чтобы включить\n\n"
            "<i>Изменения вступят в силу после перезапуска бота</i>"
        )

        await callback.message.edit_text(
text,
            parse_mode="HTML",
            reply_markup=Keyboards.plugins_marketplace(marketplace_plugins, enabled_names)
        )
        await callback.answer()

    async def handle_plugin_info(self, callback: CallbackQuery) -> None:
        """Show plugin info"""
        parts = callback.data.split(":")
        plugin_name = parts[2] if len(parts) > 2 else "unknown"

        # Plugin descriptions
        descriptions = {
            "commit-commands": "Автоматизация Git workflow: создание коммитов, пуш, создание PR с правильным форматированием.",
            "code-review": "Профессиональный ревью кода: находит баги, проблемы безопасности, предлагает улучшения.",
            "feature-dev": "Пошаговая разработка фичи: анализ архитектуры, планирование, реализация.",
            "frontend-design": "Создание красивых UI компонентов и страниц с современным дизайном.",
            "ralph-loop": "RAFL (Reflect-Act-Fix-Loop): итеративное решение сложных задач с самопроверкой.",
            "security-guidance": "Анализ безопасности кода: уязвимости, best practices, рекомендации.",
            "pr-review-toolkit": "Инструменты для ревью Pull Request'ов на GitHub.",
            "claude-code-setup": "Настройка и конфигурирование Claude Code.",
            "hookify": "Создание и управление git хуками.",
        }

        desc = descriptions.get(plugin_name, "Официальный плагин Claude Code")

        await callback.answer(f"ℹ️ {plugin_name}: {desc[:150]}", show_alert=True)

    async def handle_plugin_enable(self, callback: CallbackQuery) -> None:
        """Enable a plugin"""
        parts = callback.data.split(":")
        plugin_name = parts[2] if len(parts) > 2 else "unknown"

        if not self.sdk_service:
            await callback.answer("⚠️ SDK не доступен")
            return

        # Add plugin to enabled list
        if hasattr(self.sdk_service, 'add_plugin'):
            self.sdk_service.add_plugin(plugin_name)
            await callback.answer(f"✅ Плагин {plugin_name} включен!")
            await self.handle_plugin_marketplace(callback)
        else:
            await callback.answer(
                f"ℹ️ Добавьте {plugin_name} в CLAUDE_PLUGINS и перезапустите бота",
                show_alert=True
            )

    async def handle_plugin_disable(self, callback: CallbackQuery) -> None:
        """Disable a plugin"""
        parts = callback.data.split(":")
        plugin_name = parts[2] if len(parts) > 2 else "unknown"

        if not self.sdk_service:
            await callback.answer("⚠️ SDK не доступен")
            return

        # Remove plugin from enabled list
        if hasattr(self.sdk_service, 'remove_plugin'):
            self.sdk_service.remove_plugin(plugin_name)
            await callback.answer(f"❌ Плагин {plugin_name} отключен!")
            await self.handle_plugin_list(callback)
        else:
            await callback.answer(
                f"ℹ️ Удалите {plugin_name} из CLAUDE_PLUGINS и перезапустите бота",
                show_alert=True
            )

    async def handle_plugin_close(self, callback: CallbackQuery) -> None:
        """Close plugins menu"""
        await callback.message.delete()
        await callback.answer()
