"""
Text Message Handler

Handles regular text messages sent by users.
Includes message batching, task running checks, and AI request processing.
"""

import os
import re
import logging
from typing import Optional
from aiogram.types import Message

from .base import BaseMessageHandler
from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)


class TextMessageHandler(BaseMessageHandler):
    """
    Handles text message processing.

    Responsibilities:
    - Process user text input
    - Detect and handle cd commands
    - Message batching
    - Task running checks
    - Route to appropriate handler based on context
    """

    def __init__(
        self,
        bot_service,
        user_state,
        hitl_manager,
        file_context_manager,
        variable_manager,
        plan_manager,
        ai_request_handler=None,
        message_batcher=None,
        callback_handlers=None,
    ):
        super().__init__(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )
        self.ai_request_handler = ai_request_handler
        self.message_batcher = message_batcher
        self.callback_handlers = callback_handlers

    async def handle_text_message(
        self,
        message: Message,
        prompt_override: Optional[str] = None,
        force_new_session: bool = False,
        _from_batcher: bool = False,
    ) -> None:
        """
        Main entry point for text message handling.

        Args:
            message: Telegram message object
            prompt_override: Override prompt (for batching or file context)
            force_new_session: Force new session instead of continuing
            _from_batcher: Internal flag indicating message is from batcher
        """
        user_id = message.from_user.id
        text = message.text or ""

        self.log_debug(user_id, f"Processing text message: {text[:50]}...")

        # Check authorization
        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await message.answer("Вы не авторизованы для использования этого бота.")
            return

        # Check for special input states (не батчатся - обрабатываются сразу)
        if await self._handle_special_input_states(message):
            return

        # === MESSAGE BATCHING ===
        # Объединяем несколько сообщений за 0.5с в один запрос
        # НЕ батчим если: уже из батчера, есть prompt_override, или задача уже выполняется
        if (
            not _from_batcher
            and not prompt_override
            and self.message_batcher
            and not self._is_task_running(user_id)
        ):
            # Добавляем сообщение в batch
            async def process_batched(first_msg: Message, combined_text: str):
                await self.handle_text_message(
                    first_msg,
                    prompt_override=combined_text,
                    force_new_session=force_new_session,
                    _from_batcher=True,
                )

            await self.message_batcher.add_message(message, process_batched)
            return

        # === CHECK IF TASK RUNNING ===
        if self._is_task_running(user_id):
            await message.answer(
                "Задача уже выполняется.\n\n"
                "Используйте кнопку отмены или /cancel чтобы остановить.",
                reply_markup=Keyboards.claude_cancel(user_id),
            )
            return

        # Detect cd command and update working directory
        current_dir = self.get_working_dir(user_id)
        new_dir = self.detect_cd_command(text, current_dir)
        if new_dir and new_dir != current_dir:
            self.user_state.set_working_dir(user_id, new_dir)
            self.log_info(user_id, f"Working directory changed to: {new_dir}")

        # === PROCESS AI REQUEST ===
        if self.ai_request_handler:
            await self.ai_request_handler.process_ai_request(
                message,
                prompt_override=prompt_override,
                force_new_session=force_new_session,
            )
        else:
            self.log_error(user_id, "AIRequestHandler not available!")
            await message.answer("Ошибка: обработчик AI запросов не настроен.")

    async def _handle_special_input_states(self, message: Message) -> bool:
        """
        Check and handle special input states (HITL, variables, etc.)

        Returns:
            True if message was handled by special state, False otherwise
        """
        user_id = message.from_user.id

        # Check for HITL answer input
        if self.hitl_manager.is_expecting_answer(user_id):
            self.log_info(user_id, "Handling HITL answer input")
            # Delegate to HITL handler (implemented in original messages.py)
            # For now, just log - will be implemented properly when migrating HITL handlers
            return True

        # Check for path input
        if self.hitl_manager.is_expecting_path(user_id):
            self.log_info(user_id, "Handling path input")
            return True

        # Check for clarification input
        if self.hitl_manager.is_expecting_clarification(user_id):
            self.log_info(user_id, "Handling clarification input")
            return True

        # Check for variable input (3-step workflow)
        if self.variables.is_expecting_input(user_id):
            self.log_info(user_id, "Handling variable input")
            # Delegate to variable handler
            return True

        # Check for plan clarification
        if self.plans.is_expecting_clarification(user_id):
            self.log_info(user_id, "Handling plan clarification")
            return True

        # Check for callback handler states (e.g., folder creation, global variable input)
        if self.callback_handlers:
            if hasattr(self.callback_handlers, "is_gvar_input_active"):
                if self.callback_handlers.is_gvar_input_active(user_id):
                    handled = await self.callback_handlers.process_gvar_input(
                        user_id, message.text, message
                    )
                    if handled:
                        return True

            # Check for other callback handler states
            if hasattr(self.callback_handlers, "get_user_state"):
                if self.callback_handlers.get_user_state(user_id):
                    handled = await self.callback_handlers.process_user_input(message)
                    if handled:
                        return True

        return False

    def _is_task_running(self, user_id: int) -> bool:
        """Check if a Claude Code task is currently running for this user"""
        # CRITICAL FIX: Check via SDK/proxy service, not session existence
        # Session persists for continuation, so checking it would always block
        if self.ai_request_handler:
            return self.ai_request_handler.is_task_running(user_id)
        return False

    def detect_cd_command(self, command: str, current_dir: str) -> Optional[str]:
        """
        Detect if a bash command changes directory and return the new path.

        Handles patterns like:
        - cd /path/to/dir
        - cd subdir
        - mkdir -p dir && cd dir
        - cd ~
        - cd ..

        Args:
            command: Bash command string
            current_dir: Current working directory

        Returns:
            New directory path if cd detected, None otherwise
        """
        cd_patterns = [
            r'(?:^|&&|;)\s*cd\s+([^\s;&|]+)',
            r'(?:^|&&|;)\s*cd\s+"([^"]+)"',
            r"(?:^|&&|;)\s*cd\s+'([^']+)'",
        ]

        new_dir = None
        for pattern in cd_patterns:
            matches = re.findall(pattern, command)
            if matches:
                new_dir = matches[-1]
                break

        if not new_dir:
            return None

        # Handle absolute path
        if new_dir.startswith('/'):
            return new_dir

        # Handle home directory
        if new_dir == '~':
            return '/root'

        # Handle previous directory (skip)
        if new_dir == '-':
            return None

        # Handle parent directory
        if new_dir == '..':
            return os.path.dirname(current_dir)

        # Handle relative path
        return os.path.join(current_dir, new_dir)
