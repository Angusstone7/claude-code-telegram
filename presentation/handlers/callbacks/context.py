"""
Context Callback Handlers

Handles context/session management callbacks:
- Context list and switching
- Context creation and clearing
- Context menu navigation
"""

import logging
from aiogram.types import CallbackQuery

from presentation.handlers.callbacks.base import BaseCallbackHandler
from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)


class ContextCallbackHandler(BaseCallbackHandler):
    """Handles context management callbacks."""

    async def _get_context_data(self, callback: CallbackQuery):
        """Helper to get project, context and user data for context operations."""
        user_id = callback.from_user.id

        if not self.project_service or not self.context_service:
            await callback.answer("⚠️ Сервисы недоступны")
            return None, None, None, None

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        project = await self.project_service.get_current(uid)
        if not project:
            await callback.answer("❌ Нет активного проекта")
            return None, None, None, None

        current_ctx = await self.context_service.get_current(project.id)
        return uid, project, current_ctx, self.context_service

    # ============== Context Menu ==============

    async def handle_context_menu(self, callback: CallbackQuery) -> None:
        """Show context main menu."""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            ctx_name = current_ctx.name if current_ctx else "не выбран"
            msg_count = current_ctx.message_count if current_ctx else 0
            has_session = current_ctx.has_session if current_ctx else False

            session_status = "📜 Есть сессия" if has_session else "✨ Чистый"
            text = (
                f"💬 Управление контекстами\n\n"
                f"📂 Проект: {project.name}\n"
                f"💬 Контекст: {ctx_name}\n"
                f"📝 Сообщений: {msg_count}\n"
                f"📌 Статус: {session_status}"
            )

            keyboard = Keyboards.context_menu(
                ctx_name, project.name, msg_count,
                show_back=True, back_to="menu:context"
            )
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing context menu: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Context List ==============

    async def handle_context_list(self, callback: CallbackQuery) -> None:
        """Show list of contexts."""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            contexts = await ctx_service.list_contexts(project.id)
            current_id = current_ctx.id if current_ctx else None

            if contexts:
                text = f"💬 Контексты проекта {project.name}\n\nВыберите контекст:"
                keyboard = Keyboards.context_list(contexts, current_id)
            else:
                # Create default context if none exist
                context = await ctx_service.create_new(project.id, uid, "main", set_as_current=True)
                text = f"✨ Создан контекст: {context.name}"
                keyboard = Keyboards.context_menu(
                    context.name, project.name, 0,
                    show_back=True, back_to="menu:context"
                )

            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error listing contexts: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Context Switch ==============

    async def handle_context_switch(self, callback: CallbackQuery) -> None:
        """Handle context switch."""
        context_id = callback.data.split(":")[-1]

        try:
            uid, project, _, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            context = await ctx_service.switch_context(project.id, context_id)

            if context:
                session_status = "📜 Есть сессия" if context.has_session else "✨ Чистый"
                text = (
                    f"💬 Переключено на контекст:\n\n"
                    f"📝 {context.name}\n"
                    f"📊 Сообщений: {context.message_count}\n"
                    f"📂 Проект: {project.name}\n"
                    f"📌 Статус: {session_status}"
                )
                keyboard = Keyboards.context_menu(
                    context.name, project.name, context.message_count,
                    show_back=True, back_to="menu:context"
                )
                await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
                await callback.answer(f"Контекст: {context.name}")
            else:
                await callback.answer("❌ Контекст не найден")

        except Exception as e:
            logger.error(f"Error switching context: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Context Creation ==============

    async def handle_context_new(self, callback: CallbackQuery) -> None:
        """Handle new context creation."""
        try:
            uid, project, _, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            context = await ctx_service.create_new(project.id, uid, set_as_current=True)

            text = (
                f"✨ Новый контекст создан\n\n"
                f"📝 {context.name}\n"
                f"📂 Проект: {project.name}\n\n"
                f"Чистый старт — без истории!\n"
                f"Отправьте первое сообщение."
            )
            keyboard = Keyboards.context_menu(
                context.name, project.name, 0,
                show_back=True, back_to="menu:context"
            )
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer(f"Создан {context.name}")

        except Exception as e:
            logger.error(f"Error creating context: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Context Clearing ==============

    async def handle_context_clear(self, callback: CallbackQuery) -> None:
        """Show clear confirmation."""
        try:
            uid, project, current_ctx, _ = await self._get_context_data(callback)
            if not project:
                return

            if not current_ctx:
                await callback.answer("❌ Нет активного контекста")
                return

            text = (
                f"🗑️ Очистить контекст?\n\n"
                f"📝 {current_ctx.name}\n"
                f"📊 Сообщений: {current_ctx.message_count}\n\n"
                f"⚠️ Вся история будет удалена!"
            )
            keyboard = Keyboards.context_clear_confirm()
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing clear confirm: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_context_clear_confirm(self, callback: CallbackQuery) -> None:
        """Confirm and clear context - creates NEW context for fresh start."""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            if not current_ctx:
                await callback.answer("❌ Нет активного контекста")
                return

            # 1. Create new context (auto-generated name, set as current)
            new_context = await ctx_service.create_new(
                project_id=project.id,
                user_id=uid,
                name=None,  # Auto-generate name
                set_as_current=True
            )

            # 2. Clear in-memory session cache to ensure fresh start
            user_id = callback.from_user.id
            if self.message_handlers:
                self.message_handlers.clear_session_cache(user_id)

            text = (
                f"✅ Новый контекст создан\n\n"
                f"📝 {new_context.name}\n"
                f"📂 Проект: {project.name}\n\n"
                f"Начните новый диалог."
            )
            keyboard = Keyboards.context_menu(
                new_context.name, project.name, 0,
                show_back=True, back_to="menu:context"
            )
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer("Новый контекст создан")

        except Exception as e:
            logger.error(f"Error clearing context: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Navigation ==============

    async def handle_context_close(self, callback: CallbackQuery) -> None:
        """Close context menu."""
        try:
            await callback.message.delete()
            await callback.answer()
        except Exception as e:
            logger.debug(f"Error closing context menu: {e}")
            await callback.answer()
