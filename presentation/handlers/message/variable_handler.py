"""
Variable Input Handler

Handles 3-step variable input workflow: name → value → description
Extracted from MessageHandlers God Object.
"""

import logging
from typing import Optional
from aiogram.types import Message

from .base import BaseMessageHandler

logger = logging.getLogger(__name__)


class VariableInputHandler(BaseMessageHandler):
    """
    Handles variable input workflow.

    Responsibilities:
    - 3-step workflow: name → value → description
    - Validate variable names and values
    - Save variables to context
    - Handle edit mode
    - Cancel workflow

    Workflow:
    1. User clicks "Add Variable" → start_var_input()
    2. User enters name → handle_var_name_input()
    3. User enters value → handle_var_value_input()
    4. User enters description (or skips) → handle_var_desc_input()
    5. Variable saved → show_updated_menu()
    """

    def __init__(self, *args, context_service=None, project_service=None, **kwargs):
        """
        Initialize variable handler.

        Args:
            context_service: Context service for variable storage
            project_service: Project service for current project
            *args, **kwargs: Passed to BaseMessageHandler
        """
        super().__init__(*args, **kwargs)
        self.context_service = context_service
        self.project_service = project_service

    def is_expecting_input(self, user_id: int) -> bool:
        """
        Check if user is in variable input workflow.

        Args:
            user_id: User ID

        Returns:
            True if expecting variable input
        """
        return self.variables.is_expecting_input(user_id)

    def start_var_input(self, user_id: int, menu_msg: Optional[Message] = None) -> None:
        """
        Start variable input workflow.

        Args:
            user_id: User ID
            menu_msg: Menu message to edit after completion
        """
        self.variables.start_input(user_id, menu_msg)
        self.log_info(user_id, "Started variable input workflow")

    def start_var_edit(self, user_id: int, var_name: str, menu_msg: Optional[Message] = None) -> None:
        """
        Start variable edit workflow.

        Args:
            user_id: User ID
            var_name: Variable name to edit
            menu_msg: Menu message to edit after completion
        """
        self.variables.start_edit(user_id, var_name, menu_msg)
        self.log_info(user_id, f"Started variable edit: {var_name}")

    def cancel_var_input(self, user_id: int) -> None:
        """
        Cancel variable input workflow.

        Args:
            user_id: User ID
        """
        self.variables.cancel(user_id)
        self.log_info(user_id, "Cancelled variable input workflow")

    async def handle_var_name_input(self, message: Message) -> None:
        """
        Handle variable name input (step 1).

        Args:
            message: Telegram message with variable name
        """
        user_id = message.from_user.id
        var_name = message.text.strip().upper()

        self.log_debug(user_id, f"Variable name input: {var_name}")

        # Validate name
        result = self.variables.validate_name(var_name)
        if not result.is_valid:
            self.log_warning(user_id, f"Invalid variable name: {result.error}")
            await message.answer(
                f"❌ Неверное имя переменной\n\n{result.error}",
                parse_mode=None
            )
            return

        # Move to value step
        self.variables.move_to_value_step(user_id, result.normalized_name)

        await message.answer(
            f"✓ Имя принято: {result.normalized_name}\n\n"
            f"Теперь введите значение для {result.normalized_name}:\n\n"
            f"Например: glpat-xxxx или Python/FastAPI",
            parse_mode=None
        )

    async def handle_var_value_input(self, message: Message) -> None:
        """
        Handle variable value input (step 2).

        Args:
            message: Telegram message with variable value
        """
        user_id = message.from_user.id
        var_name = self.variables.get_var_name(user_id)
        var_value = message.text.strip()

        if not var_name:
            self.log_error(user_id, "No variable name found in state")
            self.variables.cancel(user_id)
            await message.answer("❌ Ошибка: имя переменной не найдено")
            return

        self.log_debug(user_id, f"Variable value input for {var_name}: {len(var_value)} chars")

        # Validate value
        result = self.variables.validate_value(var_value)
        if not result.is_valid:
            self.log_warning(user_id, f"Invalid variable value: {result.error}")
            await message.answer(f"❌ {result.error}", parse_mode=None)
            return

        # Check if editing (skip description step for edits)
        is_editing = self.variables.is_editing(user_id)
        if is_editing:
            await self._handle_edit_save(message, var_name, var_value)
            return

        # Move to description step
        self.variables.move_to_description_step(user_id, var_value)

        await message.answer(
            f"✓ Значение принято\n\n"
            f"Теперь введите описание для {var_name}:\n\n"
            f"Опишите, для чего эта переменная и как её использовать.\n"
            f"Например: Токен GitLab для git push/pull\n\n"
            f"Или отправьте /skip чтобы пропустить.",
            parse_mode=None
        )

    async def handle_var_desc_input(self, message: Message) -> None:
        """
        Handle variable description input (step 3).

        Args:
            message: Telegram message with variable description
        """
        user_id = message.from_user.id
        var_name, var_value = self.variables.get_var_data(user_id)

        if not var_name or not var_value:
            self.log_error(user_id, "Missing variable data in state")
            self.variables.cancel(user_id)
            await message.answer("❌ Ошибка: данные переменной не найдены")
            return

        var_desc = message.text.strip()
        self.log_debug(user_id, f"Variable description for {var_name}: {len(var_desc)} chars")

        await self._save_variable(message, var_name, var_value, var_desc)

    async def save_variable_skip_desc(self, user_id: int, message: Message) -> None:
        """
        Save variable without description.

        Called when user clicks "Skip description" button.

        Args:
            user_id: User ID
            message: Telegram message
        """
        var_name, var_value = self.variables.get_var_data(user_id)

        if not var_name or not var_value:
            self.log_error(user_id, "Missing variable data for skip")
            self.variables.cancel(user_id)
            return

        self.log_info(user_id, f"Skipping description for {var_name}")
        await self._save_variable(message, var_name, var_value, "")

    async def _handle_edit_save(self, message: Message, var_name: str, var_value: str) -> None:
        """
        Handle saving edited variable (preserves old description).

        Args:
            message: Telegram message
            var_name: Variable name
            var_value: New variable value
        """
        user_id = message.from_user.id
        old_desc = ""

        # Try to get old description
        try:
            if self.context_service and self.project_service:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                project = await self.project_service.get_current(uid)
                if project:
                    context = await self.context_service.get_current(project.id)
                    if context:
                        old_var = await self.context_service.get_variable(context.id, var_name)
                        if old_var:
                            old_desc = old_var.description
        except Exception as e:
            self.log_error(user_id, f"Error getting old description: {e}")

        await self._save_variable(message, var_name, var_value, old_desc)

    async def _save_variable(self, message: Message, var_name: str, var_value: str, var_desc: str) -> None:
        """
        Save variable to context.

        Args:
            message: Telegram message
            var_name: Variable name
            var_value: Variable value
            var_desc: Variable description
        """
        user_id = message.from_user.id

        # Check services availability
        if not self.project_service or not self.context_service:
            self.log_error(user_id, "Services not initialized")
            await message.answer("❌ Сервисы не инициализированы")
            self.variables.cancel(user_id)
            return

        try:
            from domain.value_objects.user_id import UserId
            uid = UserId.from_int(user_id)

            # Get current project
            project = await self.project_service.get_current(uid)
            if not project:
                await message.answer("❌ Нет активного проекта")
                self.variables.cancel(user_id)
                return

            # Get or create context
            context = await self.context_service.get_current(project.id)
            if not context:
                await message.answer("❌ Нет активного контекста")
                self.variables.cancel(user_id)
                return

            # Save variable
            await self.context_service.set_variable(
                context.id,
                var_name,
                var_value,
                var_desc
            )

            self.log_info(user_id, f"Variable saved: {var_name}")
            await message.answer(
                f"✅ Переменная {var_name} сохранена\n\n"
                f"Значение: {var_value[:50]}{'...' if len(var_value) > 50 else ''}\n"
                f"Описание: {var_desc[:100] if var_desc else '(нет)'}"
            )

            # Clear state
            self.variables.cancel(user_id)

        except Exception as e:
            self.log_error(user_id, f"Error saving variable: {e}", exc_info=True)
            await message.answer(f"❌ Ошибка сохранения: {e}")
            self.variables.cancel(user_id)
