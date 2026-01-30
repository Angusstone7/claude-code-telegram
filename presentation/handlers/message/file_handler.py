"""File and photo message handler"""

import logging
from io import BytesIO
from typing import TYPE_CHECKING, Optional, List

from aiogram.types import Message
from aiogram import Bot

from presentation.keyboards.keyboards import Keyboards
from .base import BaseMessageHandler

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from application.services.file_processor_service import FileProcessorService, ProcessedFile
    from application.services.project_service import ProjectService
    from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService
    from infrastructure.claude_code.sdk_service import ClaudeAgentSDKService
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
        project_service: Optional["ProjectService"] = None,
        sdk_service: Optional["ClaudeAgentSDKService"] = None,
        claude_proxy: Optional["ClaudeCodeProxyService"] = None,
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
        self.project_service = project_service
        self.sdk_service = sdk_service
        self.claude_proxy = claude_proxy

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

        Eliminates code duplication between handle_document and handle_photo.
        """
        user_id = message.from_user.id
        bot = message.bot

        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await message.answer("Вы не авторизованы для использования этого бота.")
            return

        if self._is_task_running(user_id):
            await message.answer(
                "Задача уже выполняется.\n\nДождитесь завершения или используйте /cancel",
                reply_markup=Keyboards.claude_cancel(user_id)
            )
            return

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
        except Exception as e:
            logger.error(f"Error downloading {file_type_label.lower()}: {e}")
            await message.answer(f"Ошибка скачивания: {e}")
            return

        # Process file
        processed = await self.file_processor_service.process_file(
            file_content, filename, mime_type
        )

        if processed.error:
            await message.answer(f"Ошибка обработки: {processed.error}")
            return

        caption = message.caption or ""

        if caption:
            await self._process_file_with_caption(message, processed, caption, file_type_label)
        else:
            await self._cache_file_for_reply(message, processed, file_type_label, user_id)

    async def _process_file_with_caption(
        self,
        message: Message,
        processed: "ProcessedFile",
        caption: str,
        file_type_label: str
    ) -> None:
        """Process file when caption is provided."""
        user_id = message.from_user.id

        if caption.startswith("/"):
            # Plugin command with file
            self.file_context_manager.cache_file(message.message_id, processed)
            parts = caption.split(maxsplit=1)
            command_name = parts[0][1:]
            command_args = parts[1] if len(parts) > 1 else ""
            skill_command = f"/{command_name}"
            if command_args:
                skill_command += f" {command_args}"

            prompt = f"run {skill_command}"
            working_dir = await self.get_project_working_dir(user_id)
            enriched_prompt = self.file_processor_service.format_for_prompt(
                processed, prompt, working_dir=working_dir
            )

            file_info = f"{processed.filename} ({processed.size_bytes // 1024} KB)"
            await message.answer(
                f"<b>Команда плагина:</b> <code>{skill_command}</code>\n"
                f"{file_info}\n\nПередаю в Claude Code...",
                parse_mode="HTML"
            )
            if not self.ai_request_handler:
                await message.answer("⚠️ Обработчик запросов недоступен")
                return
            await self.ai_request_handler.handle_text(message, prompt_override=enriched_prompt, force_new_session=True)
        else:
            # Regular task with file
            working_dir = await self.get_project_working_dir(user_id)
            enriched_prompt = self.file_processor_service.format_for_prompt(
                processed, caption, working_dir=working_dir
            )
            file_info = f"{processed.filename} ({processed.size_bytes // 1024} KB)"
            task_preview = caption[:50] + "..." if len(caption) > 50 else caption
            await message.answer(f"Получен {file_type_label.lower()}: {file_info}\nЗадача: {task_preview}")
            await self._execute_task_with_prompt(message, enriched_prompt)

    async def _cache_file_for_reply(
        self,
        message: Message,
        processed: "ProcessedFile",
        file_type_label: str,
        user_id: int
    ) -> None:
        """Cache file and prompt user to reply with task."""
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

        self.file_context_manager.cache_file(bot_msg.message_id, processed)
        logger.info(f"[{user_id}] {file_type_label} cached with bot message ID: {bot_msg.message_id}")

    async def _extract_reply_file_context(
        self, reply_message: Message, bot: Bot
    ) -> Optional[tuple["ProcessedFile", str]]:
        """Extract file from reply message"""
        if not self.file_processor_service:
            return None

        if reply_message.document:
            doc = reply_message.document
            filename = doc.file_name or "unknown"
            file_size = doc.file_size or 0

            is_valid, _ = self.file_processor_service.validate_file(filename, file_size)
            if not is_valid:
                return None

            try:
                file = await bot.get_file(doc.file_id)
                file_content = await bot.download_file(file.file_path)
                processed = await self.file_processor_service.process_file(
                    file_content, filename, doc.mime_type
                )
                if processed.is_valid:
                    return (processed, reply_message.caption or "")
            except Exception as e:
                logger.error(f"Error extracting document from reply: {e}")
                return None

        if reply_message.photo:
            photo = reply_message.photo[-1]
            max_size = 5 * 1024 * 1024
            if photo.file_size and photo.file_size > max_size:
                return None

            try:
                file = await bot.get_file(photo.file_id)
                file_content = await bot.download_file(file.file_path)
                processed = await self.file_processor_service.process_file(
                    file_content, f"image_{photo.file_unique_id}.jpg", "image/jpeg"
                )
                if processed.is_valid:
                    return (processed, reply_message.caption or "")
            except Exception as e:
                logger.error(f"Error extracting photo from reply: {e}")
                return None

        return None

    async def _execute_task_with_prompt(self, message: Message, prompt: str) -> None:
        """Execute Claude task with given prompt"""
        if not self.ai_request_handler:
            await message.answer("⚠️ Обработчик запросов недоступен")
            return
        # Use prompt_override instead of modifying frozen Message object
        await self.ai_request_handler.handle_text(message, prompt_override=prompt)

    # Copied from legacy messages.py:468-481
    async def handle_document(self, message: Message, **kwargs) -> None:
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
    async def handle_photo(self, message: Message, **kwargs) -> None:
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

    def _is_task_running(self, user_id: int) -> bool:
        """Check if a task is already running for user"""
        is_running = False
        if self.sdk_service:
            is_running = self.sdk_service.is_task_running(user_id)
        if not is_running and self.claude_proxy:
            is_running = self.claude_proxy.is_task_running(user_id)
        return is_running

    async def get_project_working_dir(self, user_id: int) -> str:
        """Get working directory from current project (async, more accurate)"""
        if self.project_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                project = await self.project_service.get_current(uid)
                if project and project.working_dir:
                    return project.working_dir
            except Exception as e:
                logger.warning(f"Error getting project working_dir: {e}")
        # Fallback to state
        return self.user_state.get_working_dir(user_id)

    # === Media Group (Album) Support ===

    async def handle_media_group(self, messages: List[Message], **kwargs) -> None:
        """
        Handle media group (album) - multiple photos/documents sent together.

        This is called by MediaGroupBatcher after all messages in the group
        have been collected.

        Args:
            messages: List of Message objects from the same media group
        """
        if not messages:
            return

        # Use first message for user info and caption
        first_message = messages[0]
        user_id = first_message.from_user.id
        bot = first_message.bot
        caption = None

        # Find caption (usually on the first message)
        for msg in messages:
            if msg.caption:
                caption = msg.caption
                break

        # Authorize user
        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await first_message.answer("Вы не авторизованы для использования этого бота.")
            return

        # Check if task is already running
        if self._is_task_running(user_id):
            await first_message.answer(
                "⏳ Задача уже выполняется. Дождитесь её завершения или используйте /cancel."
            )
            return

        if not self.file_processor_service:
            await first_message.answer("⚠️ Обработка файлов недоступна")
            return

        # Process all files in the group
        processed_files: List["ProcessedFile"] = []

        for msg in messages:
            try:
                processed = await self._process_message_file(msg, bot)
                if processed and processed.is_valid:
                    processed_files.append(processed)
            except Exception as e:
                logger.error(f"Error processing file from media group: {e}")

        if not processed_files:
            await first_message.answer("❌ Не удалось обработать файлы из альбома")
            return

        logger.info(
            f"[{user_id}] Media group processed: {len(processed_files)} files, "
            f"caption: {bool(caption)}"
        )

        # Get working directory
        working_dir = await self.get_project_working_dir(user_id)

        if caption:
            # Album WITH caption - execute task immediately
            await self._process_media_group_with_caption(
                first_message, processed_files, caption, working_dir
            )
        else:
            # Album WITHOUT caption - cache for reply
            await self._cache_media_group_for_reply(
                first_message, processed_files, working_dir
            )

    async def _process_message_file(
        self, message: Message, bot: Bot
    ) -> Optional["ProcessedFile"]:
        """Extract and process file from a single message"""
        if message.document:
            doc = message.document
            file_id = doc.file_id
            filename = doc.file_name or "unknown"
            mime_type = doc.mime_type
        elif message.photo:
            photo = message.photo[-1]
            file_id = photo.file_id
            filename = f"image_{photo.file_unique_id}.jpg"
            mime_type = "image/jpeg"
        else:
            return None

        try:
            file = await bot.get_file(file_id)
            file_content = BytesIO()
            await bot.download_file(file.file_path, file_content)
            file_content.seek(0)

            processed = await self.file_processor_service.process_file(
                file_content, filename, mime_type
            )
            return processed

        except Exception as e:
            logger.error(f"Error downloading file {filename}: {e}")
            return None

    async def _process_media_group_with_caption(
        self,
        message: Message,
        files: List["ProcessedFile"],
        caption: str,
        working_dir: str
    ) -> None:
        """Process media group with caption - start task immediately"""
        user_id = message.from_user.id

        # Format prompt with all files
        enriched_prompt = self.file_processor_service.format_multiple_files_for_prompt(
            files, caption, working_dir=working_dir
        )

        # Show summary
        files_summary = self.file_processor_service.get_files_summary(files)
        task_preview = caption[:50] + "..." if len(caption) > 50 else caption

        await message.answer(
            f"📎 Файлы: {files_summary}\n"
            f"📝 Задача: {task_preview}\n\n"
            f"⏳ Запускаю Claude Code..."
        )

        # Execute task
        await self._execute_task_with_prompt(message, enriched_prompt)

    async def _cache_media_group_for_reply(
        self,
        message: Message,
        files: List["ProcessedFile"],
        working_dir: str
    ) -> None:
        """Cache media group for reply-based workflow"""
        user_id = message.from_user.id

        # Build file list for display
        file_list_lines = []
        total_size = 0

        for pf in files:
            size_kb = pf.size_bytes // 1024
            total_size += pf.size_bytes
            file_list_lines.append(f"  • {pf.filename} ({size_kb} KB)")

        file_list = "\n".join(file_list_lines)
        total_kb = total_size // 1024

        # Send response with file list
        bot_msg = await message.answer(
            f"📎 <b>Получено {len(files)} файлов</b> ({total_kb} KB):\n"
            f"{file_list}\n\n"
            f"💡 Сделайте <b>reply</b> на это сообщение с текстом задачи.",
            parse_mode="HTML"
        )

        # Cache files for reply
        self.file_context_manager.cache_files(bot_msg.message_id, files)
        logger.info(
            f"[{user_id}] Media group cached ({len(files)} files) "
            f"with bot message ID: {bot_msg.message_id}"
        )
