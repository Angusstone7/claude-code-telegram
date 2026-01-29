"""
Text Message Handler

Handles regular text messages sent by users.
Extracted from MessageHandlers God Object.
"""

import os
import re
import logging
from typing import Optional
from aiogram.types import Message

from .base import BaseMessageHandler

logger = logging.getLogger(__name__)


class TextMessageHandler(BaseMessageHandler):
    """
    Handles text message processing.

    Responsibilities:
    - Process user text input
    - Detect and handle cd commands
    - Route to appropriate handler based on context
    - Handle command messages
    """

    async def handle_text_message(self, message: Message) -> None:
        """
        Main entry point for text message handling.

        Args:
            message: Telegram message object
        """
        user_id = message.from_user.id
        text = message.text or ""

        self.log_debug(user_id, f"Processing text message: {text[:50]}...")

        # Check authorization
        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await message.answer("Вы не авторизованы для использования этого бота.")
            return

        # Check for special input states
        if await self._handle_special_input_states(message):
            return

        # Handle regular text as AI request
        await self._process_ai_request(message)

    async def _handle_special_input_states(self, message: Message) -> bool:
        """
        Check and handle special input states (HITL, variables, etc.)

        Returns:
            True if message was handled by special state, False otherwise
        """
        user_id = message.from_user.id

        # Check for HITL answer input
        if self.hitl_manager.is_expecting_answer(user_id):
            await self._handle_hitl_answer(message)
            return True

        # Check for path input
        if self.hitl_manager.is_expecting_path(user_id):
            await self._handle_path_input(message)
            return True

        # Check for clarification input
        if self.hitl_manager.is_expecting_clarification(user_id):
            await self._handle_clarification_input(message)
            return True

        # Check for variable input (3-step workflow)
        if self.variables.is_expecting_input(user_id):
            await self._handle_variable_input(message)
            return True

        # Check for plan clarification
        if self.plans.is_expecting_clarification(user_id):
            await self._handle_plan_clarification(message)
            return True

        return False

    async def _process_ai_request(self, message: Message) -> None:
        """
        Process message as AI request.

        Args:
            message: Telegram message
        """
        user_id = message.from_user.id
        text = message.text or ""

        # Detect cd command and update working directory
        current_dir = self.get_working_dir(user_id)
        new_dir = self.detect_cd_command(text, current_dir)
        if new_dir and new_dir != current_dir:
            self.user_state.set_working_dir(user_id, new_dir)
            self.log_info(user_id, f"Working directory changed to: {new_dir}")

        # Send to AI service for processing
        # This will be handled by the coordinator
        self.log_debug(user_id, "Delegating to AI service")

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

    # === Special Input Handlers ===

    async def _handle_hitl_answer(self, message: Message) -> None:
        """Handle HITL answer input - delegates to HITLHandler"""
        # Will be implemented by HITLHandler
        self.log_debug(message.from_user.id, "HITL answer - delegating")
        pass

    async def _handle_path_input(self, message: Message) -> None:
        """Handle path input - delegates to HITLHandler"""
        self.log_debug(message.from_user.id, "Path input - delegating")
        pass

    async def _handle_clarification_input(self, message: Message) -> None:
        """Handle clarification input - delegates to HITLHandler"""
        self.log_debug(message.from_user.id, "Clarification input - delegating")
        pass

    async def _handle_variable_input(self, message: Message) -> None:
        """Handle variable input - delegates to VariableInputHandler"""
        self.log_debug(message.from_user.id, "Variable input - delegating")
        pass

    async def _handle_plan_clarification(self, message: Message) -> None:
        """Handle plan clarification - delegates to PlanApprovalHandler"""
        self.log_debug(message.from_user.id, "Plan clarification - delegating")
        pass
