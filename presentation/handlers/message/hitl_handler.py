"""
HITL (Human-in-the-Loop) Handler

Handles permission requests, questions, and user responses.
Extracted from MessageHandlers God Object.
"""

import logging
from typing import Optional
from aiogram.types import Message

from .base import BaseMessageHandler

logger = logging.getLogger(__name__)


class HITLHandler(BaseMessageHandler):
    """
    Handles Human-in-the-Loop interactions.

    Responsibilities:
    - Handle permission requests from Claude
    - Handle question/answer interactions
    - Process user responses (approve/reject/clarify)
    - Manage waiting states for async coordination
    """

    async def handle_permission_request(
        self,
        user_id: int,
        tool_name: str,
        details: str,
        request_id: str
    ) -> bool:
        """
        Handle permission request from Claude.

        Args:
            user_id: User ID
            tool_name: Name of tool requiring permission
            details: Details about the operation
            request_id: Unique request ID

        Returns:
            True if permission granted, False otherwise
        """
        self.log_info(user_id, f"Permission request: {tool_name}")

        # Check YOLO mode (auto-approve)
        if self.is_yolo_mode(user_id):
            self.log_debug(user_id, "Auto-approved (YOLO mode)")
            return True

        # Create permission event and wait for user response
        event = self.hitl_manager.create_permission_event(user_id)
        self.hitl_manager.set_permission_context(
            user_id=user_id,
            request_id=request_id,
            tool_name=tool_name,
            details=details
        )

        # Wait for user response (with timeout)
        try:
            await event.wait()
            approved = self.hitl_manager.get_permission_response(user_id)
            self.log_info(user_id, f"Permission response: {'approved' if approved else 'rejected'}")
            return approved
        except Exception as e:
            self.log_error(user_id, f"Error waiting for permission: {e}")
            return False
        finally:
            self.hitl_manager.clear_permission_state(user_id)

    async def handle_question_request(
        self,
        user_id: int,
        question: str,
        options: list[str],
        request_id: str
    ) -> str:
        """
        Handle question request from Claude.

        Args:
            user_id: User ID
            question: Question text
            options: List of answer options
            request_id: Unique request ID

        Returns:
            User's answer
        """
        self.log_info(user_id, f"Question request: {question[:50]}...")

        # Create question event and wait for user response
        event = self.hitl_manager.create_question_event(user_id)
        self.hitl_manager.set_question_context(
            user_id=user_id,
            request_id=request_id,
            question=question,
            options=options
        )

        # Wait for user response (with timeout)
        try:
            await event.wait()
            answer = self.hitl_manager.get_question_response(user_id)
            self.log_info(user_id, f"Question response: {answer[:50]}...")
            return answer
        except Exception as e:
            self.log_error(user_id, f"Error waiting for answer: {e}")
            return ""
        finally:
            self.hitl_manager.clear_question_state(user_id)

    async def handle_text_answer(self, message: Message) -> None:
        """
        Handle text answer from user.

        Called when user is expected to provide text input.

        Args:
            message: Telegram message with answer
        """
        user_id = message.from_user.id
        text = message.text or ""

        self.log_debug(user_id, f"Text answer received: {text[:50]}...")

        # Respond to pending question
        success = await self.hitl_manager.respond_to_question(user_id, text)
        if success:
            await message.answer("✓ Ответ получен")
            self.hitl_manager.set_expecting_answer(user_id, False)
        else:
            self.log_warning(user_id, "No pending question for text answer")
            await message.answer("⚠️ Нет ожидающего вопроса")

    async def handle_path_input(self, message: Message) -> None:
        """
        Handle path input from user.

        Called when user is expected to provide file/directory path.

        Args:
            message: Telegram message with path
        """
        user_id = message.from_user.id
        path = message.text or ""

        self.log_debug(user_id, f"Path input received: {path}")

        # Validate path (basic check)
        if not path or path.strip() == "":
            await message.answer("⚠️ Путь не может быть пустым")
            return

        # Respond with path
        success = await self.hitl_manager.respond_to_question(user_id, path)
        if success:
            await message.answer(f"✓ Путь получен: {path}")
            self.hitl_manager.set_expecting_path(user_id, False)
        else:
            self.log_warning(user_id, "No pending path request")
            await message.answer("⚠️ Нет ожидающего запроса пути")

    async def handle_clarification_input(self, message: Message) -> None:
        """
        Handle clarification text from user.

        Called when user provides clarification for rejected permission.

        Args:
            message: Telegram message with clarification
        """
        user_id = message.from_user.id
        clarification = message.text or ""

        self.log_debug(user_id, f"Clarification received: {clarification[:50]}...")

        # Respond to permission with clarification
        success = await self.hitl_manager.respond_to_permission(
            user_id,
            approved=False,
            clarification_text=clarification
        )

        if success:
            await message.answer("✓ Пояснение получено")
            self.hitl_manager.set_expecting_clarification(user_id, False)
        else:
            self.log_warning(user_id, "No pending permission for clarification")
            await message.answer("⚠️ Нет ожидающего запроса разрешения")

    def is_expecting_input(self, user_id: int) -> bool:
        """
        Check if user is expected to provide any input.

        Args:
            user_id: User ID

        Returns:
            True if expecting input, False otherwise
        """
        return (
            self.hitl_manager.is_expecting_answer(user_id) or
            self.hitl_manager.is_expecting_path(user_id) or
            self.hitl_manager.is_expecting_clarification(user_id)
        )

    def get_expected_input_type(self, user_id: int) -> Optional[str]:
        """
        Get type of expected input.

        Args:
            user_id: User ID

        Returns:
            Input type: 'answer', 'path', 'clarification', or None
        """
        if self.hitl_manager.is_expecting_answer(user_id):
            return 'answer'
        elif self.hitl_manager.is_expecting_path(user_id):
            return 'path'
        elif self.hitl_manager.is_expecting_clarification(user_id):
            return 'clarification'
        return None

    async def cancel_waiting(self, user_id: int) -> None:
        """
        Cancel all waiting HITL interactions.

        Args:
            user_id: User ID
        """
        self.log_info(user_id, "Cancelling HITL waiting")
        self.hitl_manager.cancel_all_waits(user_id)
        self.hitl_manager.cleanup(user_id)
