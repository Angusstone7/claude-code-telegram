"""
File Message Handler

Handles document and photo messages sent by users.
Extracted from MessageHandlers God Object.
"""

import logging
from typing import TYPE_CHECKING, Optional
from aiogram.types import Message

from .base import BaseMessageHandler

if TYPE_CHECKING:
    from application.services.file_processor_service import ProcessedFile

logger = logging.getLogger(__name__)


class FileMessageHandler(BaseMessageHandler):
    """
    Handles file message processing (documents and photos).

    Responsibilities:
    - Validate and download files
    - Process files (text extraction, image analysis)
    - Cache files for reply workflow
    - Handle file + caption combinations
    """

    def __init__(self, *args, file_processor_service=None, **kwargs):
        """
        Initialize file handler.

        Args:
            file_processor_service: Service for file processing
            *args, **kwargs: Passed to BaseMessageHandler
        """
        super().__init__(*args, **kwargs)
        self.file_processor_service = file_processor_service

    async def handle_document(self, message: Message) -> None:
        """
        Handle document (file) messages.

        Args:
            message: Telegram message with document
        """
        document = message.document
        if not document:
            return

        await self._handle_file_message(
            message=message,
            file_id=document.file_id,
            filename=document.file_name or "unknown",
            file_size=document.file_size or 0,
            mime_type=document.mime_type or "application/octet-stream",
            file_type_label="Файл"
        )

    async def handle_photo(self, message: Message) -> None:
        """
        Handle photo messages.

        Args:
            message: Telegram message with photo
        """
        if not message.photo:
            return

        # Get largest photo
        photo = message.photo[-1]

        await self._handle_file_message(
            message=message,
            file_id=photo.file_id,
            filename=f"photo_{photo.file_unique_id}.jpg",
            file_size=photo.file_size or 0,
            mime_type="image/jpeg",
            file_type_label="Изображение"
        )

    async def _handle_file_message(
        self,
        message: Message,
        file_id: str,
        filename: str,
        file_size: int,
        mime_type: str,
        file_type_label: str = "Файл"
    ) -> None:
        """
        Unified handler for document and photo messages.

        Args:
            message: Telegram message
            file_id: Telegram file ID
            filename: File name
            file_size: File size in bytes
            mime_type: MIME type
            file_type_label: Display label (Файл/Изображение)
        """
        user_id = message.from_user.id
        bot = message.bot

        # Authorization check
        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await message.answer("Вы не авторизованы для использования этого бота.")
            return

        # Check if task is running
        if self._is_task_running(user_id):
            await message.answer(
                "Задача уже выполняется.\n\nДождитесь завершения или используйте /cancel"
            )
            return

        # Check if file processor is available
        if not self.file_processor_service:
            await message.answer("Обработка файлов недоступна")
            return

        # Validate file
        is_valid, error = self.file_processor_service.validate_file(filename, file_size)
        if not is_valid:
            await message.answer(f"{error}")
            return

        # Download file
        try:
            file = await bot.get_file(file_id)
            file_content = await bot.download_file(file.file_path)
            self.log_debug(user_id, f"Downloaded {file_type_label}: {filename}")
        except Exception as e:
            self.log_error(user_id, f"Error downloading {file_type_label.lower()}: {e}")
            await message.answer(f"Ошибка скачивания: {e}")
            return

        # Process file
        try:
            processed = await self.file_processor_service.process_file(
                file_content, filename, mime_type
            )

            if processed.error:
                await message.answer(f"Ошибка обработки: {processed.error}")
                return

            self.log_info(user_id, f"Processed {file_type_label}: {filename}")
        except Exception as e:
            self.log_error(user_id, f"Error processing file: {e}", exc_info=True)
            await message.answer(f"Ошибка обработки файла: {e}")
            return

        # Handle file based on caption
        caption = message.caption or ""
        if caption:
            await self._process_file_with_caption(
                message, processed, caption, file_type_label
            )
        else:
            await self._cache_file_for_reply(
                message, processed, file_type_label, user_id
            )

    async def _process_file_with_caption(
        self,
        message: Message,
        processed: "ProcessedFile",
        caption: str,
        file_type_label: str
    ) -> None:
        """
        Process file when caption is provided.

        Args:
            message: Telegram message
            processed: Processed file object
            caption: File caption (task description or command)
            file_type_label: Display label
        """
        user_id = message.from_user.id

        if caption.startswith("/"):
            # Plugin command with file
            await self._handle_file_with_command(
                message, processed, caption, file_type_label
            )
        else:
            # Regular task with file
            await self._handle_file_with_task(
                message, processed, caption, file_type_label
            )

    async def _handle_file_with_command(
        self,
        message: Message,
        processed: "ProcessedFile",
        caption: str,
        file_type_label: str
    ) -> None:
        """Handle file + plugin command"""
        # TODO: Implement plugin command handling
        # This requires integration with existing command system
        self.log_debug(message.from_user.id, "File with command - not yet implemented")
        await message.answer(
            f"{file_type_label} получен с командой: {caption}\n"
            "Обработка команд с файлами временно недоступна (рефакторинг)"
        )

    async def _handle_file_with_task(
        self,
        message: Message,
        processed: "ProcessedFile",
        caption: str,
        file_type_label: str
    ) -> None:
        """Handle file + task description"""
        # TODO: Implement task execution with file
        # This requires integration with existing task execution system
        user_id = message.from_user.id
        file_info = f"{processed.filename} ({processed.size_bytes // 1024} KB)"
        task_preview = caption[:50] + "..." if len(caption) > 50 else caption

        self.log_info(user_id, f"File task: {task_preview}")
        await message.answer(
            f"Получен {file_type_label.lower()}: {file_info}\n"
            f"Задача: {task_preview}\n\n"
            "Обработка задач с файлами временно недоступна (рефакторинг)"
        )

    async def _cache_file_for_reply(
        self,
        message: Message,
        processed: "ProcessedFile",
        file_type_label: str,
        user_id: int
    ) -> None:
        """
        Cache file and prompt user to reply with task.

        Args:
            message: Telegram message
            processed: Processed file object
            file_type_label: Display label
            user_id: User ID
        """
        if file_type_label == "Изображение":
            bot_msg = await message.answer(
                "<b>Изображение получено</b>\n\n"
                "Сделайте <b>reply</b> на это сообщение с текстом задачи.",
                parse_mode="HTML"
            )
        else:
            bot_msg = await message.answer(
                f"<b>Файл получен:</b> {processed.filename}\n"
                f"<b>Размер:</b> {processed.size_bytes // 1024} KB\n"
                f"<b>Тип:</b> {processed.file_type.value}\n\n"
                f"Сделайте <b>reply</b> на это сообщение с текстом задачи\n"
                f"или командой плагина (например, <code>/ralph-loop</code>)",
                parse_mode="HTML"
            )

        # TODO: Implement file caching
        # self._files.cache_file(bot_msg.message_id, processed)
        self.log_info(user_id, f"{file_type_label} готов к использованию (message_id: {bot_msg.message_id})")

    def _is_task_running(self, user_id: int) -> bool:
        """
        Check if task is currently running for user.

        TODO: Implement proper task status check
        """
        # Temporary implementation - always return False
        # Real implementation should check streaming handler or task status
        return False
