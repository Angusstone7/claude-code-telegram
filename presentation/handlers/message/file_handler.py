"""File and photo message handler"""

import logging
from typing import TYPE_CHECKING, Optional

from aiogram.types import Message
from aiogram import Bot

from presentation.keyboards.keyboards import Keyboards
from .base import BaseMessageHandler

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from application.services.file_processor_service import FileProcessorService, ProcessedFile
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.variable_manager import VariableInputManager
    from presentation.handlers.state.plan_manager import PlanApprovalManager
    from presentation.handlers.state.file_context import FileContextManager

logger = logging.getLogger(__name__)


class FileMessageHandler(BaseMessageHandler):
    """Handles file and photo message processing"""

    def __init__(
        self,
        bot_service: "BotService",
        user_state: "UserStateManager",
        hitl_manager: "HITLManager",
        file_context_manager: "FileContextManager",
        variable_manager: "VariableInputManager",
        plan_manager: "PlanApprovalManager",
        file_processor_service: Optional["FileProcessorService"] = None,
        ai_request_handler=None,
    ):
        super().__init__(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )
        self.file_processor_service = file_processor_service
        self.ai_request_handler = ai_request_handler

    # TODO: Copy from legacy messages.py:331-393
    async def _handle_file_message(
        self,
        message: Message,
        file_id: str,
        filename: str,
        file_size: int,
        mime_type: str,
        file_type_label: str = "Файл"
    ) -> None:
        """Unified handler for document and photo messages"""
        pass

    # TODO: Copy from legacy messages.py:395-437
    async def _process_file_with_caption(
        self,
        message: Message,
        processed: "ProcessedFile",
        caption: str,
        file_type_label: str
    ) -> None:
        """Process file when caption is provided"""
        pass

    # TODO: Copy from legacy messages.py:439-464
    async def _cache_file_for_reply(
        self,
        message: Message,
        processed: "ProcessedFile",
        file_type_label: str,
        user_id: int
    ) -> None:
        """Cache file and prompt user to reply with task"""
        pass

    # TODO: Copy from legacy messages.py:504-550
    async def _extract_reply_file_context(
        self, reply_message: Message, bot: Bot
    ) -> Optional[tuple["ProcessedFile", str]]:
        """Extract file from reply message"""
        pass

    # TODO: Copy from legacy messages.py:552-555
    async def _execute_task_with_prompt(self, message: Message, prompt: str) -> None:
        """Execute Claude task with given prompt"""
        pass

    # Copied from legacy messages.py:468-481
    async def handle_document(self, message: Message) -> None:
        """Handle document (file) messages"""
        document = message.document
        if not document:
            return

        await self._handle_file_message(
            message=message,
            file_id=document.file_id,
            filename=document.file_name or "unknown",
            file_size=document.file_size or 0,
            mime_type=document.mime_type,
            file_type_label="Файл"
        )

    # Copied from legacy messages.py:483-502
    async def handle_photo(self, message: Message) -> None:
        """Handle photo messages"""
        if not message.photo:
            return

        photo = message.photo[-1]
        max_image_size = 5 * 1024 * 1024  # 5 MB

        if photo.file_size and photo.file_size > max_image_size:
            await message.answer("Изображение слишком большое (максимум 5 MB)")
            return

        await self._handle_file_message(
            message=message,
            file_id=photo.file_id,
            filename=f"image_{photo.file_unique_id}.jpg",
            file_size=photo.file_size or 0,
            mime_type="image/jpeg",
            file_type_label="Изображение"
        )
