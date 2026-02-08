"""
Claude Callback Handlers

Handles HITL (Human-in-the-Loop) callbacks:
- Permission approval/rejection
- Question answering
- Plan approval
- Task cancellation
"""

import logging
from aiogram.types import CallbackQuery

from presentation.handlers.callbacks.base import BaseCallbackHandler
from presentation.keyboards.keyboards import CallbackData
from shared.constants import TEXT_TRUNCATE_LIMIT

logger = logging.getLogger(__name__)


class ClaudeCallbackHandler(BaseCallbackHandler):
    """Handles Claude Code HITL callbacks."""

    async def _get_user_id_from_callback(self, callback: CallbackQuery) -> int:
        """Extract user_id from callback data."""
        data = CallbackData.parse_claude_callback(callback.data)
        return int(data.get("user_id", 0))

    async def _validate_user(self, callback: CallbackQuery) -> int | None:
        """Validate user and return user_id if valid."""
        user_id = await self._get_user_id_from_callback(callback)
        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return None
        return user_id

    async def _truncate_and_append(self, text: str, suffix: str) -> str:
        """Truncate text if needed and append suffix."""
        if len(text) > TEXT_TRUNCATE_LIMIT:
            text = text[:TEXT_TRUNCATE_LIMIT] + "\n... (truncated)"
        return text + suffix

    # ============== Permission Callbacks ==============

    async def handle_claude_approve(self, callback: CallbackQuery) -> None:
        """Handle Claude Code permission approval"""
        user_id = await self._validate_user(callback)
        if not user_id:
            return

        try:
            original_text = callback.message.text or ""
            await callback.message.edit_text(
                original_text + "\n\n✅ Approved",
                parse_mode=None
            )

            if self.claude_proxy:
                await self.claude_proxy.respond_to_permission(user_id, True)

            if hasattr(self.message_handlers, 'handle_permission_response'):
                await self.message_handlers.handle_permission_response(user_id, True)

            await callback.answer("✅ Одобрено")

        except Exception as e:
            logger.error(f"Error handling claude approve: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_claude_reject(self, callback: CallbackQuery) -> None:
        """Handle Claude Code permission rejection"""
        user_id = await self._validate_user(callback)
        if not user_id:
            return

        try:
            original_text = callback.message.text or ""
            await callback.message.edit_text(
                original_text + "\n\n❌ Rejected",
                parse_mode=None
            )

            if self.claude_proxy:
                await self.claude_proxy.respond_to_permission(user_id, False)

            if hasattr(self.message_handlers, 'handle_permission_response'):
                await self.message_handlers.handle_permission_response(user_id, False)

            await callback.answer("❌ Отклонено")

        except Exception as e:
            logger.error(f"Error handling claude reject: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_claude_clarify(self, callback: CallbackQuery) -> None:
        """Handle Claude Code permission clarification request"""
        user_id = await self._validate_user(callback)
        if not user_id:
            return

        try:
            hitl = self.message_handlers._hitl if hasattr(self.message_handlers, '_hitl') else None
            if not hitl:
                await callback.answer("❌ HITL manager недоступен")
                return

            hitl.set_expecting_clarification(user_id, True)
            logger.info(f"[{user_id}] Set expecting_clarification=True for permission clarification")

            original_text = callback.message.text or ""
            await callback.message.edit_text(
                original_text + "\n\n💬 Введите уточнение:",
                parse_mode=None
            )

            await callback.answer("✏️ Введите текст уточнения")

        except Exception as e:
            logger.error(f"Error handling claude clarify: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Question Callbacks ==============

    async def handle_claude_answer(self, callback: CallbackQuery) -> None:
        """Handle Claude Code question answer (selected option)"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))
        option_index = int(data.get("option_index", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            answer = str(option_index)
            if hasattr(self.message_handlers, 'get_pending_question_option'):
                answer = self.message_handlers.get_pending_question_option(user_id, option_index)

            original_text = callback.message.text or ""
            await callback.message.edit_text(
                original_text + f"\n\n📝 Ответ: {answer}",
                parse_mode=None
            )

            if self.sdk_service:
                await self.sdk_service.respond_to_question(user_id, answer)
            elif self.claude_proxy:
                await self.claude_proxy.respond_to_question(user_id, answer)

            if hasattr(self.message_handlers, 'handle_question_response'):
                await self.message_handlers.handle_question_response(user_id, answer)

            await callback.answer(f"Ответ: {answer[:20]}...")

        except Exception as e:
            logger.error(f"Error handling claude answer: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_claude_other(self, callback: CallbackQuery) -> None:
        """Handle Claude Code question - user wants to type custom answer"""
        user_id = await self._validate_user(callback)
        if not user_id:
            return

        try:
            original_text = callback.message.text or ""
            await callback.message.edit_text(
                original_text + "\n\n✏️ Type your answer below:",
                parse_mode=None
            )

            if hasattr(self.message_handlers, 'set_expecting_answer'):
                self.message_handlers.set_expecting_answer(user_id, True)

            await callback.answer("Введите ответ в чат")

        except Exception as e:
            logger.error(f"Error handling claude other: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Task Control Callbacks ==============

    async def handle_claude_cancel(self, callback: CallbackQuery) -> None:
        """Handle Claude Code task cancellation"""
        user_id = await self._validate_user(callback)
        if not user_id:
            return

        try:
            cancelled = False

            if self.sdk_service:
                cancelled = await self.sdk_service.cancel_task(user_id)
                logger.info(f"SDK cancel_task for user {user_id}: {cancelled}")

            if not cancelled and self.claude_proxy:
                cancelled = await self.claude_proxy.cancel_task(user_id)
                logger.info(f"Proxy cancel_task for user {user_id}: {cancelled}")

            if cancelled:
                await callback.message.edit_text("🛑 Задача отменена", parse_mode=None)
                await callback.answer("Задача отменена")
            else:
                await callback.answer("Нет активной задачи для отмены")

        except Exception as e:
            logger.error(f"Error cancelling task: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_claude_continue(self, callback: CallbackQuery) -> None:
        """Handle continue Claude Code session"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))
        session_id = data.get("session_id")

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            await callback.message.edit_text(
                "▶️ Продолжение сессии...\n\nОтправьте следующее сообщение для продолжения.",
                parse_mode=None
            )

            if hasattr(self.message_handlers, 'set_continue_session'):
                self.message_handlers.set_continue_session(user_id, session_id)

            await callback.answer("Отправьте следующее сообщение")

        except Exception as e:
            logger.error(f"Error continuing session: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Plan Approval Callbacks (ExitPlanMode) ==============

    def _get_plan_user_id(self, callback: CallbackQuery) -> int:
        """Extract user_id from plan callback data.

        Callback data format: plan:{action}:{user_id}:{request_id}
        """
        parts = callback.data.split(":")
        return int(parts[2]) if len(parts) > 2 else 0

    async def handle_plan_approve(self, callback: CallbackQuery) -> None:
        """Handle plan approval - user approves the implementation plan"""
        user_id = self._get_plan_user_id(callback)

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            # CRITICAL: Deliver response to SDK FIRST, before editing message.
            # Editing the message takes time (network I/O to Telegram API),
            # during which the task status could change from WAITING_PERMISSION.
            success = False
            if hasattr(self.message_handlers, 'handle_plan_response'):
                success = await self.message_handlers.handle_plan_response(user_id, "approve")

            if success:
                original_text = callback.message.text or ""
                text = await self._truncate_and_append(
                    original_text,
                    "\n\n✅ **План одобрен** — начинаю выполнение!"
                )
                await callback.message.edit_text(text, parse_mode=None)
                await callback.answer("✅ План одобрен!")
            else:
                logger.warning(f"[{user_id}] Plan approve failed - response not accepted")
                await callback.answer("⚠️ Не удалось подтвердить. Задача могла завершиться.", show_alert=True)

        except Exception as e:
            logger.error(f"Error handling plan approve: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_plan_reject(self, callback: CallbackQuery) -> None:
        """Handle plan rejection - user rejects the plan"""
        user_id = self._get_plan_user_id(callback)

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            success = False
            if hasattr(self.message_handlers, 'handle_plan_response'):
                success = await self.message_handlers.handle_plan_response(user_id, "reject")

            original_text = callback.message.text or ""
            text = await self._truncate_and_append(original_text, "\n\n❌ **План отклонён**")
            await callback.message.edit_text(text, parse_mode=None)
            await callback.answer("❌ План отклонён")

        except Exception as e:
            logger.error(f"Error handling plan reject: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_plan_clarify(self, callback: CallbackQuery) -> None:
        """Handle plan clarification - user wants to provide feedback"""
        user_id = self._get_plan_user_id(callback)

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            original_text = callback.message.text or ""
            text = await self._truncate_and_append(
                original_text,
                "\n\n✏️ **Уточнение плана**\n\nВведите ваши комментарии в чат:"
            )
            await callback.message.edit_text(text, parse_mode=None)

            if hasattr(self.message_handlers, 'set_expecting_plan_clarification'):
                self.message_handlers.set_expecting_plan_clarification(user_id, True)

            await callback.answer("Введите уточнения в чат")

        except Exception as e:
            logger.error(f"Error handling plan clarify: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_plan_cancel(self, callback: CallbackQuery) -> None:
        """Handle plan cancellation - user wants to cancel the entire task"""
        user_id = self._get_plan_user_id(callback)

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            # Send plan cancel response FIRST
            if hasattr(self.message_handlers, 'handle_plan_response'):
                await self.message_handlers.handle_plan_response(user_id, "cancel")

            # Then cancel the task itself
            cancelled = False
            if self.sdk_service:
                cancelled = await self.sdk_service.cancel_task(user_id)

            if not cancelled and self.claude_proxy:
                cancelled = await self.claude_proxy.cancel_task(user_id)

            await callback.message.edit_text("🛑 **Задача отменена**", parse_mode=None)
            await callback.answer("🛑 Задача отменена")

        except Exception as e:
            logger.error(f"Error handling plan cancel: {e}")
            await callback.answer(f"❌ Ошибка: {e}")
