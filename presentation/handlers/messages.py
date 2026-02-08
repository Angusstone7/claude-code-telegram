"""
Message Handlers for Claude Code Proxy (Refactored)

Handles user messages and forwards them to Claude Code.
This is a refactored version that delegates state management to specialized managers.

Follows Single Responsibility Principle by separating:
- UserStateManager: Core user state (sessions, working dirs)
- HITLManager: Human-in-the-Loop (permissions, questions)
- VariableInputManager: Variable input flow state machine
- PlanApprovalManager: Plan approval state (ExitPlanMode)
- FileContextManager: File upload context caching
"""

import asyncio
import html
import logging
import os
import re
import uuid
from typing import Optional, TYPE_CHECKING

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import StateFilter

from presentation.keyboards.keyboards import Keyboards
from presentation.handlers.streaming import StreamingHandler, HeartbeatTracker, StepStreamingHandler
from presentation.handlers.state import (
    UserStateManager,
    HITLManager,
    VariableInputManager,
    PlanApprovalManager,
    FileContextManager,
)
from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService, TaskResult
from domain.entities.claude_code_session import ClaudeCodeSession, SessionStatus

if TYPE_CHECKING:
    from infrastructure.claude_code.sdk_service import ClaudeAgentSDKService, SDKTaskResult
    from application.services.file_processor_service import FileProcessorService, ProcessedFile

# Try to import optional services
try:
    from application.services.file_processor_service import FileProcessorService, ProcessedFile, FileType
    FILE_PROCESSOR_AVAILABLE = True
except ImportError:
    FILE_PROCESSOR_AVAILABLE = False
    FileProcessorService = None

try:
    from infrastructure.claude_code.sdk_service import (
        ClaudeAgentSDKService,
        SDKTaskResult,
        TaskStatus,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    ClaudeAgentSDKService = None

logger = logging.getLogger(__name__)
router = Router()


class MessageHandlers:
    """
    Bot message handlers for Claude Code proxy.

    Refactored to use specialized state managers instead of
    15+ separate dictionaries. This improves:
    - Testability (each manager can be tested in isolation)
    - Maintainability (clear separation of concerns)
    - Race condition safety (consolidated state per user)
    """

    def __init__(
        self,
        bot_service,
        claude_proxy: ClaudeCodeProxyService,
        sdk_service: Optional["ClaudeAgentSDKService"] = None,
        default_working_dir: str = "/root",
        project_service=None,
        context_service=None,
        file_processor_service: Optional["FileProcessorService"] = None
    ):
        self.bot_service = bot_service
        self.claude_proxy = claude_proxy
        self.sdk_service = sdk_service
        self.project_service = project_service
        self.context_service = context_service

        # File processor service
        if file_processor_service:
            self.file_processor_service = file_processor_service
        elif FILE_PROCESSOR_AVAILABLE:
            self.file_processor_service = FileProcessorService()
        else:
            self.file_processor_service = None

        # Determine which backend to use
        self.use_sdk = sdk_service is not None and SDK_AVAILABLE
        logger.info(f"MessageHandlers initialized with SDK backend: {self.use_sdk}")

        # === State Managers (replaces 15+ separate dicts) ===
        self._state = UserStateManager(default_working_dir)
        self._hitl = HITLManager()
        self._variables = VariableInputManager()
        self._plans = PlanApprovalManager()
        self._files = FileContextManager()

        # === Message Batcher (объединяет несколько сообщений за 0.5с в один запрос) ===
        from presentation.middleware.message_batcher import MessageBatcher
        self._batcher = MessageBatcher(batch_delay=0.5)

        # Reference to callback handlers (for global variable input)
        self.callback_handlers = None

        # Legacy compatibility aliases (to minimize changes in other files)
        self.default_working_dir = default_working_dir

    # === Public API (used by other handlers) ===

    def is_yolo_mode(self, user_id: int) -> bool:
        """Check if YOLO mode is enabled for user"""
        return self._state.is_yolo_mode(user_id)

    def set_yolo_mode(self, user_id: int, enabled: bool):
        """Set YOLO mode for user"""
        self._state.set_yolo_mode(user_id, enabled)

    def is_step_streaming_mode(self, user_id: int) -> bool:
        """Check if step streaming mode (brief output) is enabled for user"""
        return self._state.is_step_streaming_mode(user_id)

    def set_step_streaming_mode(self, user_id: int, enabled: bool):
        """Set step streaming mode for user"""
        self._state.set_step_streaming_mode(user_id, enabled)

    def _get_step_handler(self, user_id: int) -> Optional["StepStreamingHandler"]:
        """Get or create StepStreamingHandler for user in step streaming mode."""
        streaming = self._state.get_streaming_handler(user_id)
        if not streaming:
            return None
        if not hasattr(self, '_step_handlers'):
            self._step_handlers = {}
        if user_id not in self._step_handlers:
            from presentation.handlers.streaming import StepStreamingHandler
            self._step_handlers[user_id] = StepStreamingHandler(streaming)
        return self._step_handlers[user_id]

    def _cleanup_step_handler(self, user_id: int):
        """Clean up step handler for user."""
        if hasattr(self, '_step_handlers') and user_id in self._step_handlers:
            del self._step_handlers[user_id]

    def get_working_dir(self, user_id: int) -> str:
        """Get user's working directory"""
        return self._state.get_working_dir(user_id)

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
        return self._state.get_working_dir(user_id)

    def set_working_dir(self, user_id: int, path: str):
        """Set user's working directory"""
        self._state.set_working_dir(user_id, path)

    def clear_session_cache(self, user_id: int) -> None:
        """Clear in-memory session cache for user"""
        self._state.clear_session_cache(user_id)

    def set_continue_session(self, user_id: int, session_id: str):
        """Set session to continue on next message"""
        self._state.set_continue_session_id(user_id, session_id)

    # === HITL State (delegated to HITLManager) ===

    def set_expecting_answer(self, user_id: int, expecting: bool):
        """Set whether we're expecting a text answer from user"""
        self._hitl.set_expecting_answer(user_id, expecting)

    def set_expecting_path(self, user_id: int, expecting: bool):
        """Set whether we're expecting a path from user"""
        self._hitl.set_expecting_path(user_id, expecting)

    def get_pending_question_option(self, user_id: int, index: int) -> str:
        """Get option text by index from pending question"""
        return self._hitl.get_option_by_index(user_id, index)

    async def handle_permission_response(self, user_id: int, approved: bool, clarification_text: str = None) -> bool:
        """Handle permission response from callback. Returns True if response was accepted."""
        if self.use_sdk and self.sdk_service:
            success = await self.sdk_service.respond_to_permission(user_id, approved, clarification_text)
            if success:
                return True

        # Fall back to HITL manager handling
        result = await self._hitl.respond_to_permission(user_id, approved, clarification_text)
        return result if result is not None else False

    async def handle_question_response(self, user_id: int, answer: str):
        """Handle question response from callback"""
        if self.use_sdk and self.sdk_service:
            success = await self.sdk_service.respond_to_question(user_id, answer)
            if success:
                return

        await self._hitl.respond_to_question(user_id, answer)

    # === Variable Input State (delegated to VariableInputManager) ===

    def is_expecting_var_input(self, user_id: int) -> bool:
        """Check if we're expecting any variable input"""
        return self._variables.is_active(user_id)

    def set_expecting_var_name(self, user_id: int, expecting: bool, menu_msg: Message = None):
        """Set whether we're expecting a variable name"""
        if expecting:
            self._variables.start_add_flow(user_id, menu_msg)
        else:
            self._variables.cancel(user_id)

    def set_expecting_var_value(self, user_id: int, var_name: str, menu_msg: Message = None):
        """Set that we're expecting a value for the given variable name"""
        self._variables.move_to_value_step(user_id, var_name)

    def set_expecting_var_desc(self, user_id: int, var_name: str, var_value: str, menu_msg: Message = None):
        """Set that we're expecting a description for the variable"""
        self._variables.move_to_description_step(user_id, var_value)

    def clear_var_state(self, user_id: int):
        """Clear all variable input state"""
        self._variables.cancel(user_id)

    def get_pending_var_message(self, user_id: int) -> Optional[Message]:
        """Get the pending menu message to update"""
        return self._variables.get_menu_message(user_id)

    def start_var_input(self, user_id: int, menu_msg: Message = None):
        """Start variable input flow"""
        self._variables.start_add_flow(user_id, menu_msg)

    def start_var_edit(self, user_id: int, var_name: str, menu_msg: Message = None):
        """Start variable edit flow"""
        self._variables.start_edit_flow(user_id, var_name, menu_msg)

    def cancel_var_input(self, user_id: int):
        """Cancel variable input and clear state"""
        self._variables.cancel(user_id)

    # === Plan Approval State (delegated to PlanApprovalManager) ===

    async def handle_plan_response(self, user_id: int, response: str) -> bool:
        """Handle plan approval response from callback. Returns True if response was accepted."""
        if self.use_sdk and self.sdk_service:
            success = await self.sdk_service.respond_to_plan(user_id, response)
            if success:
                self._plans.cleanup(user_id)
                return True
        logger.warning(f"[{user_id}] Failed to respond to plan: {response}")
        return False

    def set_expecting_plan_clarification(self, user_id: int, expecting: bool):
        """Set whether we're expecting plan clarification text"""
        self._plans.set_expecting_clarification(user_id, expecting)

    # === Task State ===

    def _is_task_running(self, user_id: int) -> bool:
        """Check if a task is already running for user"""
        is_running = False
        if self.use_sdk and self.sdk_service:
            is_running = self.sdk_service.is_task_running(user_id)
        if not is_running:
            is_running = self.claude_proxy.is_task_running(user_id)
        return is_running

    # === CD Command Detection (utility) ===

    def _detect_cd_command(self, command: str, current_dir: str) -> Optional[str]:
        """
        Detect if a bash command changes directory and return the new path.

        Handles patterns like:
        - cd /path/to/dir
        - cd subdir
        - mkdir -p dir && cd dir
        - cd ~
        - cd ..
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

        if new_dir.startswith('/'):
            return new_dir
        elif new_dir == '~':
            return '/root'
        elif new_dir == '-':
            return None
        elif new_dir == '..':
            return os.path.dirname(current_dir)
        else:
            return os.path.join(current_dir, new_dir)

    # === File Handlers (Unified) ===

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
            self._files.cache_file(message.message_id, processed)
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
            await self.handle_text(message, prompt_override=enriched_prompt, force_new_session=True)
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

        self._files.cache_file(bot_msg.message_id, processed)
        logger.info(f"[{user_id}] {file_type_label} cached with bot message ID: {bot_msg.message_id}")

    # === Message Handlers ===

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
        # Use prompt_override instead of modifying frozen Message object
        await self.handle_text(message, prompt_override=prompt)

    async def handle_text(
        self,
        message: Message,
        prompt_override: str = None,
        force_new_session: bool = False,
        _from_batcher: bool = False
    ) -> None:
        """Handle text messages - main entry point"""
        user_id = message.from_user.id
        bot = message.bot

        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await message.answer("Вы не авторизованы для использования этого бота.")
            return

        # Load yolo_mode from DB if not already loaded
        session = self._state.get(user_id)
        if session is None:
            # First interaction - load persisted settings
            await self._state.load_yolo_mode(user_id)

        # === FILE REPLY HANDLING ===
        reply = message.reply_to_message
        if reply and self._files.has_file(reply.message_id) and self.file_processor_service:
            processed_file = self._files.pop_file(reply.message_id)
            # Get working directory for saving images (from project)
            working_dir = await self.get_project_working_dir(user_id)
            enriched_prompt = self.file_processor_service.format_for_prompt(
                processed_file, message.text, working_dir=working_dir
            )
            task_preview = message.text[:50] + "..." if len(message.text) > 50 else message.text
            await message.answer(f"📎 Файл: {processed_file.filename}\n📝 Задача: {task_preview}\n\n⏳ Запускаю Claude Code...")
            # Execute task with file context and return
            await self.handle_text(message, prompt_override=enriched_prompt)
            return

        elif reply and (reply.document or reply.photo) and self.file_processor_service:
            file_context = await self._extract_reply_file_context(reply, bot)
            if file_context:
                processed_file, _ = file_context
                # Get working directory for saving images (from project)
                working_dir = await self.get_project_working_dir(user_id)
                enriched_prompt = self.file_processor_service.format_for_prompt(
                    processed_file, message.text, working_dir=working_dir
                )
                task_preview = message.text[:50] + "..." if len(message.text) > 50 else message.text
                await message.answer(f"📎 Файл: {processed_file.filename}\n📝 Задача: {task_preview}\n\n⏳ Запускаю Claude Code...")
                # Execute task with file context and return
                await self.handle_text(message, prompt_override=enriched_prompt)
                return

        # === SPECIAL INPUT MODES (не батчатся - обрабатываются сразу) ===
        logger.debug(f"[{user_id}] Checking special input modes: "
                    f"expecting_answer={self._hitl.is_expecting_answer(user_id)}, "
                    f"expecting_clarification={self._hitl.is_expecting_clarification(user_id)}")

        if self._hitl.is_expecting_answer(user_id):
            logger.info(f"[{user_id}] Handling answer input")
            await self._handle_answer_input(message)
            return

        if self._hitl.is_expecting_clarification(user_id):
            logger.info(f"[{user_id}] Handling clarification input: {message.text[:50]}")
            await self._handle_clarification_input(message)
            return

        if self._hitl.is_expecting_path(user_id):
            await self._handle_path_input(message)
            return

        if self._variables.is_expecting_name(user_id):
            await self._handle_var_name_input(message)
            return

        if self._variables.is_expecting_value(user_id):
            await self._handle_var_value_input(message)
            return

        if self._variables.is_expecting_description(user_id):
            await self._handle_var_desc_input(message)
            return

        if self._plans.is_expecting_clarification(user_id):
            await self._handle_plan_clarification(message)
            return

        # Check for global variable input (handled by CallbackHandlers)
        if hasattr(self, 'callback_handlers') and self.callback_handlers:
            if self.callback_handlers.is_gvar_input_active(user_id):
                handled = await self.callback_handlers.process_gvar_input(
                    user_id, message.text, message
                )
                if handled:
                    return

            # Check for other callback handler states (e.g., folder creation)
            if self.callback_handlers.get_user_state(user_id):
                handled = await self.callback_handlers.process_user_input(message)
                if handled:
                    return

        # === MESSAGE BATCHING ===
        # Объединяем несколько сообщений за 0.5с в один запрос
        # НЕ батчим если: уже из батчера, есть prompt_override, или задача уже выполняется
        if not _from_batcher and not prompt_override and not self._is_task_running(user_id):
            # Добавляем сообщение в batch
            async def process_batched(first_msg: Message, combined_text: str):
                await self.handle_text(
                    first_msg,
                    prompt_override=combined_text,
                    force_new_session=force_new_session,
                    _from_batcher=True
                )

            await self._batcher.add_message(message, process_batched)
            return

        # === CHECK IF TASK RUNNING ===
        if self._is_task_running(user_id):
            await message.answer(
                "Задача уже выполняется.\n\n"
                "Используйте кнопку отмены или /cancel чтобы остановить.",
                reply_markup=Keyboards.claude_cancel(user_id)
            )
            return

        # === GET CONTEXT ===
        working_dir = self.get_working_dir(user_id)
        session_id = None if force_new_session else self._state.get_continue_session_id(user_id)
        context_id = None
        enriched_prompt = prompt_override if prompt_override else message.text

        if self.project_service and self.context_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)

                project = await self.project_service.get_current(uid)
                if project:
                    working_dir = project.working_dir
                    context = await self.context_service.get_current(project.id)
                    if not context:
                        context = await self.context_service.create_new(
                            project.id, uid, "main", set_as_current=True
                        )

                    context_id = context.id

                    if not force_new_session and not session_id and context.claude_session_id:
                        session_id = context.claude_session_id
                        logger.info(
                            f"[{user_id}] Auto-continue: loaded session {session_id[:16]}... "
                            f"from context '{context.name}' (messages: {context.message_count})"
                        )

                    original_prompt = prompt_override if prompt_override else message.text
                    new_prompt = await self.context_service.get_enriched_prompt(
                        context_id, original_prompt, user_id=uid  # Pass user_id for global variables
                    )
                    if new_prompt != original_prompt:
                        enriched_prompt = new_prompt

                    self._state.set_working_dir(user_id, working_dir)

            except Exception as e:
                logger.warning(f"Error getting project/context: {e}")

        # === CREATE SESSION ===
        session = ClaudeCodeSession(
            user_id=user_id,
            working_dir=working_dir,
            claude_session_id=session_id
        )
        session.start_task(enriched_prompt)
        self._state.set_claude_session(user_id, session)

        if context_id:
            session.context_id = context_id
        session._original_working_dir = working_dir

        # === START STREAMING ===
        cancel_keyboard = Keyboards.claude_cancel(user_id)
        streaming = StreamingHandler(bot, message.chat.id, reply_markup=cancel_keyboard)

        yolo_indicator = " ⚡" if self.is_yolo_mode(user_id) else ""
        header = ""
        if self.project_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                project = await self.project_service.get_current(uid)
                if project:
                    header = f"**{project.name}**{yolo_indicator}\n`{working_dir}`\n"
                else:
                    header = f"`{working_dir}`{yolo_indicator}\n"
            except Exception:
                header = f"`{working_dir}`{yolo_indicator}\n"
        else:
            header = f"`{working_dir}`{yolo_indicator}\n"

        await streaming.start(header)
        self._state.set_streaming_handler(user_id, streaming)

        # === SETUP HITL ===
        self._hitl.create_permission_event(user_id)
        self._hitl.create_question_event(user_id)

        heartbeat = HeartbeatTracker(streaming, interval=2.0)  # 2 seconds - координатор обеспечивает rate limiting
        self._state.set_heartbeat(user_id, heartbeat)
        await heartbeat.start()

        try:
            if self.use_sdk and self.sdk_service:
                result = await self.sdk_service.run_task(
                    user_id=user_id,
                    prompt=enriched_prompt,
                    working_dir=working_dir,
                    session_id=session_id,
                    on_text=lambda text: self._on_text(user_id, text),
                    on_tool_use=lambda tool, inp: self._on_tool_use(user_id, tool, inp, message),
                    on_tool_result=lambda tid, out: self._on_tool_result(user_id, tid, out),
                    on_permission_request=lambda tool, details, inp: self._on_permission_sdk(
                        user_id, tool, details, inp, message
                    ),
                    on_permission_completed=lambda approved: self._on_permission_completed(user_id, approved),
                    on_question=lambda q, opts: self._on_question_sdk(user_id, q, opts, message),
                    on_question_completed=lambda answer: self._on_question_completed(user_id, answer),
                    on_plan_request=lambda plan_file, inp: self._on_plan_request(user_id, plan_file, inp, message),
                    on_thinking=lambda think: self._on_thinking(user_id, think),
                    on_error=lambda err: self._on_error(user_id, err),
                )

                if result.total_cost_usd and not result.cancelled:
                    streaming = self._state.get_streaming_handler(user_id)
                    if streaming:
                        cost_str = f"${result.total_cost_usd:.4f}"
                        # Build completion info from real usage data
                        info_parts = [cost_str]

                        # Add real token usage if available
                        if result.usage:
                            # Full context = direct input + cached reads + cache creation
                            input_tokens = result.usage.get("input_tokens", 0)
                            cache_read = result.usage.get("cache_read_input_tokens", 0)
                            cache_create = result.usage.get("cache_creation_input_tokens", 0)
                            output_tokens = result.usage.get("output_tokens", 0)

                            # Total context used (input side)
                            total_input = input_tokens + cache_read + cache_create
                            total_all = total_input + output_tokens

                            if total_all > 0:
                                # Show as "199K ctx | 1.2K out" for clarity
                                ctx_k = total_input / 1000
                                out_k = output_tokens / 1000
                                if ctx_k >= 1:
                                    info_parts.append(f"{ctx_k:.0f}K ctx")
                                if out_k >= 1:
                                    info_parts.append(f"{out_k:.1f}K out")
                                elif output_tokens > 0:
                                    info_parts.append(f"{output_tokens} out")

                        # Add duration if available
                        if result.duration_ms:
                            secs = result.duration_ms / 1000
                            if secs >= 60:
                                mins = int(secs // 60)
                                secs_rem = int(secs % 60)
                                info_parts.append(f"{mins}m{secs_rem}s")
                            else:
                                info_parts.append(f"{secs:.1f}s")

                        # Add turns
                        if result.num_turns:
                            info_parts.append(f"{result.num_turns} turns")

                        streaming.set_completion_info(" | ".join(info_parts))

                cli_result = TaskResult(
                    success=result.success,
                    output=result.output,
                    session_id=result.session_id,
                    error=result.error,
                    cancelled=result.cancelled,
                )
                await self._handle_result(user_id, cli_result, message)
            else:
                result = await self.claude_proxy.run_task(
                    user_id=user_id,
                    prompt=enriched_prompt,
                    working_dir=working_dir,
                    session_id=session_id,
                    on_text=lambda text: self._on_text(user_id, text),
                    on_tool_use=lambda tool, inp: self._on_tool_use(user_id, tool, inp, message),
                    on_tool_result=lambda tid, out: self._on_tool_result(user_id, tid, out),
                    on_permission=lambda tool, details: self._on_permission(user_id, tool, details, message),
                    on_question=lambda q, opts: self._on_question(user_id, q, opts, message),
                    on_error=lambda err: self._on_error(user_id, err),
                )
                await self._handle_result(user_id, result, message)

        except Exception as e:
            logger.error(f"Error running Claude Code: {e}")
            await streaming.send_error(str(e))
            session.fail(str(e))

        finally:
            await heartbeat.stop()
            self._hitl.cleanup(user_id)
            self._state.remove_streaming_handler(user_id)
            self._state.remove_heartbeat(user_id)
            self._cleanup_step_handler(user_id)

    # === Callback Handlers ===

    async def _on_text(self, user_id: int, text: str):
        """Handle streaming text output.

        ВАЖНО: TextBlock от Claude — это ОСНОВНОЙ ответ (content), не thinking!
        ThinkingBlock — это отдельный тип, который приходит в on_thinking.

        Step streaming mode: текст идёт в buffer через append(),
        а UI state синхронизируется при добавлении tools через sync_from_buffer().
        """
        streaming = self._state.get_streaming_handler(user_id)

        if streaming:
            # Текст ВСЕГДА идёт в основной буфер — это ответ Claude!
            # Step streaming и обычный режим используют одинаковую логику
            await streaming.append(text)

        # Update heartbeat to show Claude is thinking/writing
        heartbeat = self._state.get_heartbeat(user_id)
        if heartbeat:
            heartbeat.set_action("thinking")

    async def _on_tool_use(self, user_id: int, tool_name: str, tool_input: dict, message: Message):
        """Handle tool use notification"""
        streaming = self._state.get_streaming_handler(user_id)
        heartbeat = self._state.get_heartbeat(user_id)

        # Update heartbeat with current action
        if heartbeat:
            tool_lower = tool_name.lower()
            action_map = {
                "read": "reading",
                "glob": "searching",
                "grep": "searching",
                "ls": "searching",
                "write": "writing",
                "edit": "editing",
                "notebookedit": "editing",
                "bash": "executing",
                "task": "thinking",
                "webfetch": "reading",
                "websearch": "searching",
                "todowrite": "planning",
                "enterplanmode": "planning",
                "exitplanmode": "planning",
                "askuserquestion": "waiting",
            }
            action = action_map.get(tool_lower, "thinking")

            # Get detail (filename, command, pattern)
            detail = ""
            if tool_lower in ("read", "write", "edit", "notebookedit"):
                detail = tool_input.get("file_path", "")
                if detail:
                    detail = detail.split("/")[-1]  # Just filename
            elif tool_lower == "bash":
                cmd = tool_input.get("command", "")
                detail = cmd[:30] if cmd else ""
            elif tool_lower in ("glob", "grep"):
                detail = tool_input.get("pattern", "")[:30]

            heartbeat.set_action(action, detail)

        if tool_name.lower() == "bash":
            command = tool_input.get("command", "")
            current_dir = self.get_working_dir(user_id)
            new_dir = self._detect_cd_command(command, current_dir)

            if new_dir:
                self._state.set_working_dir(user_id, new_dir)
                logger.info(f"[{user_id}] Working directory changed: {current_dir} -> {new_dir}")

                session = self._state.get_claude_session(user_id)
                if session:
                    session.working_dir = new_dir

        # Track file changes for end-of-session summary
        if streaming and tool_name.lower() in ("edit", "write", "bash"):
            streaming.track_file_change(tool_name, tool_input)

        # Step streaming mode: show brief tool notifications
        if self.is_step_streaming_mode(user_id):
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                await step_handler.on_tool_start(tool_name, tool_input)
            # Still show todo lists and plan mode in step streaming
            if streaming:
                if tool_name.lower() == "todowrite":
                    todos = tool_input.get("todos", [])
                    if todos:
                        await streaming.show_todo_list(todos)
                elif tool_name.lower() == "enterplanmode":
                    await streaming.show_plan_mode_enter()
                elif tool_name.lower() == "exitplanmode":
                    await streaming.show_plan_mode_exit()
            return

        if streaming:
            if tool_name.lower() == "todowrite":
                todos = tool_input.get("todos", [])
                if todos:
                    await streaming.show_todo_list(todos)
                return

            if tool_name.lower() == "enterplanmode":
                await streaming.show_plan_mode_enter()
                return

            if tool_name.lower() == "exitplanmode":
                await streaming.show_plan_mode_exit()
                return

            details = ""
            if tool_name.lower() == "bash":
                details = tool_input.get("command", "")[:100]
            elif tool_name.lower() in["read", "write", "edit"]:
                details = tool_input.get("file_path", tool_input.get("path", ""))[:100]
            elif tool_name.lower() == "glob":
                details = tool_input.get("pattern", "")[:100]
            elif tool_name.lower() == "grep":
                details = tool_input.get("pattern", "")[:100]

            await streaming.show_tool_use(tool_name, details)

    async def _on_tool_result(self, user_id: int, tool_id: str, output: str):
        """Handle tool result"""
        streaming = self._state.get_streaming_handler(user_id)

        # Step streaming mode: show brief completion status
        if self.is_step_streaming_mode(user_id):
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                # Get current tool name from step handler
                tool_name = step_handler.get_current_tool()
                await step_handler.on_tool_complete(tool_name, success=True)
            # Reset heartbeat
            heartbeat = self._state.get_heartbeat(user_id)
            if heartbeat:
                heartbeat.set_action("analyzing")
            return

        if streaming and output:
            await streaming.show_tool_result(output, success=True)

        # Reset heartbeat to "thinking" after tool completes
        heartbeat = self._state.get_heartbeat(user_id)
        if heartbeat:
            heartbeat.set_action("analyzing")

    async def _on_permission(self, user_id: int, tool_name: str, details: str, message: Message) -> bool:
        """Handle permission request (CLI mode)"""
        if self.is_yolo_mode(user_id):
            streaming = self._state.get_streaming_handler(user_id)
            # В step streaming mode не показываем "Авто-одобрено" - step handler уже показывает операции
            if streaming and not self.is_step_streaming_mode(user_id):
                truncated = details[:100] + "..." if len(details) > 100 else details
                await streaming.append(f"\n**Авто-одобрено:** `{tool_name}`\n```\n{truncated}\n```\n")
            return True

        session = self._state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        text = f"<b>Запрос разрешения</b>\n\n"
        text += f"<b>Инструмент:</b> <code>{html.escape(tool_name)}</code>\n"
        if details:
            display_details = details if len(details) < 500 else details[:500] + "..."
            # Escape HTML entities to prevent parse errors (e.g., <<'EOF' -> &lt;&lt;'EOF')
            text += f"<b>Детали:</b>\n<pre><code>{html.escape(display_details)}</code></pre>"

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.claude_permission(user_id, tool_name, request_id)
        )

        event = self._hitl.get_permission_event(user_id)
        if event:
            event.clear()
            try:
                from presentation.handlers.state.hitl_manager import PERMISSION_TIMEOUT_SECONDS
                await asyncio.wait_for(event.wait(), timeout=PERMISSION_TIMEOUT_SECONDS)
                approved = self._hitl.get_permission_response(user_id)
            except asyncio.TimeoutError:
                await message.answer("Время ожидания истекло. Отклоняю.")
                approved = False

            if session:
                session.resume_running()

            return approved

        return False

    async def _on_question(self, user_id: int, question: str, options: list[str], message: Message) -> str:
        """Handle question (CLI mode)"""
        session = self._state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_answer(request_id, question, options)

        self._hitl.set_question_context(user_id, request_id, question, options)

        text = f"<b>Вопрос</b>\n\n{html.escape(question)}"

        if options:
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
        else:
            self._hitl.set_expecting_answer(user_id, True)
            await message.answer(f"<b>Вопрос</b>\n\n{html.escape(question)}\n\nВведите ваш ответ:", parse_mode="HTML")

        event = self._hitl.get_question_event(user_id)
        if event:
            event.clear()
            try:
                from presentation.handlers.state.hitl_manager import QUESTION_TIMEOUT_SECONDS
                await asyncio.wait_for(event.wait(), timeout=QUESTION_TIMEOUT_SECONDS)
                answer = self._hitl.get_question_response(user_id)
            except asyncio.TimeoutError:
                await message.answer("Время ожидания ответа истекло.")
                answer = ""

            if session:
                session.resume_running()

            self._hitl.clear_question_state(user_id)
            return answer

        return ""

    async def _on_error(self, user_id: int, error: str):
        """Handle error from Claude Code"""
        streaming = self._state.get_streaming_handler(user_id)
        if streaming:
            await streaming.send_error(error)

        session = self._state.get_claude_session(user_id)
        if session:
            session.fail(error)

    async def _on_thinking(self, user_id: int, thinking: str):
        """Handle thinking output.

        ThinkingBlock — это внутренние рассуждения Claude (extended thinking).
        В step streaming mode показываем в сворачиваемом блоке.
        """
        streaming = self._state.get_streaming_handler(user_id)
        if not streaming or not thinking:
            return

        # Step streaming mode: показываем thinking в сворачиваемом блоке
        if self.is_step_streaming_mode(user_id):
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                await step_handler.on_thinking(thinking)
        else:
            # Обычный режим - показываем как курсив
            preview = thinking[:200] + "..." if len(thinking) > 200 else thinking
            await streaming.append(f"\n*{preview}*\n")

    async def _on_permission_sdk(
        self,
        user_id: int,
        tool_name: str,
        details: str,
        tool_input: dict,
        message: Message
    ):
        """Handle permission request from SDK"""
        # В step streaming mode показываем ожидание разрешения в основном сообщении
        if self.is_step_streaming_mode(user_id):
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                await step_handler.on_permission_request(tool_name, tool_input)

        if self.is_yolo_mode(user_id):
            streaming = self._state.get_streaming_handler(user_id)
            # В step streaming mode не показываем "Авто-одобрено" - step handler уже показывает операции
            if streaming and not self.is_step_streaming_mode(user_id):
                truncated = details[:100] + "..." if len(details) > 100 else details
                await streaming.append(f"\n**Авто-одобрено:** `{tool_name}`\n```\n{truncated}\n```\n")

            # В step streaming mode обновляем статус "Ожидаю" -> "Выполняю"
            if self.is_step_streaming_mode(user_id):
                step_handler = self._get_step_handler(user_id)
                if step_handler:
                    await step_handler.on_permission_granted(tool_name)

            if self.sdk_service:
                await self.sdk_service.respond_to_permission(user_id, True)
            return

        session = self._state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        text = f"<b>Запрос разрешения</b>\n\n"
        text += f"<b>Инструмент:</b> <code>{html.escape(tool_name)}</code>\n"
        if details:
            display_details = details if len(details) < 500 else details[:500] + "..."
            # Escape HTML entities to prevent parse errors (e.g., <<'EOF' -> &lt;&lt;'EOF')
            text += f"<b>Детали:</b>\n<pre><code>{html.escape(display_details)}</code></pre>"

        perm_msg = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.claude_permission(user_id, tool_name, request_id)
        )
        self._hitl.set_permission_context(user_id, request_id, tool_name, details, perm_msg)

    async def _on_question_sdk(
        self,
        user_id: int,
        question: str,
        options: list[str],
        message: Message
    ):
        """Handle question from SDK"""
        session = self._state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_answer(request_id, question, options)

        self._hitl.set_question_context(user_id, request_id, question, options)

        text = f"<b>Вопрос</b>\n\n{html.escape(question)}"

        if options:
            q_msg = await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
            self._hitl.set_question_context(user_id, request_id, question, options, q_msg)
        else:
            self._hitl.set_expecting_answer(user_id, True)
            q_msg = await message.answer(f"<b>Вопрос</b>\n\n{html.escape(question)}\n\nВведите ваш ответ:", parse_mode="HTML")
            self._hitl.set_question_context(user_id, request_id, question, options, q_msg)

    async def _on_plan_request(
        self,
        user_id: int,
        plan_file: str,
        tool_input: dict,
        message: Message
    ):
        """
        Handle plan approval request from SDK (ExitPlanMode).

        NOTE: Plan approval is ALWAYS shown with inline keyboard, even in YOLO mode.
        Plans should always be reviewed by user before execution - this is intentional.
        """
        logger.info(f"[{user_id}] _on_plan_request called: plan_file={plan_file}")
        request_id = str(uuid.uuid4())[:8]

        plan_content = ""

        # 1. Try planContent from tool_input (auto-detected plans pass it directly)
        if not plan_content:
            plan_content = tool_input.get("planContent", "")

        # 2. Try reading plan_file as-is (absolute path or relative to working dir)
        if not plan_content and plan_file:
            try:
                # Try absolute path first
                if os.path.isabs(plan_file) and os.path.exists(plan_file):
                    with open(plan_file, 'r', encoding='utf-8') as f:
                        plan_content = f.read()
                else:
                    # Try relative to working dir
                    working_dir = self.get_working_dir(user_id)
                    plan_path = os.path.join(working_dir, plan_file)
                    if os.path.exists(plan_path):
                        with open(plan_path, 'r', encoding='utf-8') as f:
                            plan_content = f.read()
            except Exception as e:
                logger.error(f"[{user_id}] Error reading plan file '{plan_file}': {e}")

        # 3. Fallback: try common plan file names in working dir (PLAN.md, plan.md)
        if not plan_content:
            try:
                import time
                working_dir = self.get_working_dir(user_id)
                common_plan_names = ["PLAN.md", "plan.md", "Plan.md"]
                for name in common_plan_names:
                    candidate = os.path.join(working_dir, name)
                    if os.path.exists(candidate):
                        mtime = os.path.getmtime(candidate)
                        # Only use if modified within last 5 minutes
                        if (time.time() - mtime) < 300:
                            logger.info(f"[{user_id}] Found plan in working dir: {candidate}")
                            with open(candidate, 'r', encoding='utf-8') as f:
                                plan_content = f.read()
                            break
            except Exception as e:
                logger.error(f"[{user_id}] Error checking common plan files: {e}")

        # 4. Fallback: find the most recent plan file in .claude/plans/
        if not plan_content:
            try:
                import time
                working_dir = self.get_working_dir(user_id)
                plans_dirs = [
                    os.path.join(working_dir, ".claude", "plans"),
                    os.path.expanduser("~/.claude/plans"),
                ]
                latest_plan = None
                latest_mtime = 0
                for plans_dir in plans_dirs:
                    if os.path.isdir(plans_dir):
                        for fname in os.listdir(plans_dir):
                            if fname.endswith(".md"):
                                fpath = os.path.join(plans_dir, fname)
                                mtime = os.path.getmtime(fpath)
                                if mtime > latest_mtime:
                                    latest_mtime = mtime
                                    latest_plan = fpath
                # Only use if modified within last 5 minutes (likely current plan)
                if latest_plan and (time.time() - latest_mtime) < 300:
                    logger.info(f"[{user_id}] Found recent plan file: {latest_plan}")
                    with open(latest_plan, 'r', encoding='utf-8') as f:
                        plan_content = f.read()
            except Exception as e:
                logger.error(f"[{user_id}] Error scanning for plan files: {e}")

        if plan_content:
            if len(plan_content) > 3500:
                plan_content = plan_content[:3500] + "\n\n... (план сокращён)"
            # Escape HTML entities in plan content to prevent parse errors
            escaped_content = html.escape(plan_content)
            text = f"<b>📋 План готов к выполнению</b>\n\n<pre><code>{escaped_content}</code></pre>"
        else:
            text = "<b>📋 План готов к выполнению</b>\n\n<i>Содержимое плана недоступно</i>"
            logger.warning(f"[{user_id}] Plan content is empty! plan_file={plan_file}, tool_input keys={list(tool_input.keys())}")

        plan_msg = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.plan_approval(user_id, request_id)
        )

        self._plans.set_context(user_id, request_id, plan_file, plan_content, plan_msg)
        logger.info(f"[{user_id}] Plan approval requested, file: {plan_file}")

    async def _on_permission_completed(self, user_id: int, approved: bool):
        """Handle permission completion - edit message and continue streaming"""
        perm_msg = self._hitl.get_permission_message(user_id)
        streaming = self._state.get_streaming_handler(user_id)

        # В step streaming mode обновляем строку ожидания
        if self.is_step_streaming_mode(user_id) and approved:
            step_handler = self._get_step_handler(user_id)
            if step_handler:
                # Получаем имя инструмента из HITL контекста
                tool_name = self._hitl.get_pending_tool_name(user_id) or "tool"
                await step_handler.on_permission_granted(tool_name)

        if perm_msg:
            # В step streaming mode удаляем сообщение о разрешении - информация уже в основном сообщении
            if self.is_step_streaming_mode(user_id):
                try:
                    await perm_msg.delete()
                except Exception as e:
                    logger.debug(f"Could not delete permission message: {e}")
            elif streaming:
                # В обычном режиме - редактируем сообщение
                status = "✅ Одобрено" if approved else "❌ Отклонено"
                try:
                    await perm_msg.edit_text(status, parse_mode=None)
                    streaming.current_message = perm_msg
                    streaming.buffer = f"{status}\n\nПродолжаю...\n"
                    streaming.is_finalized = False
                except Exception as e:
                    logger.debug(f"Could not edit permission message: {e}")

        self._hitl.clear_permission_state(user_id)

    async def _on_question_completed(self, user_id: int, answer: str):
        """Handle question completion"""
        q_msg = self._hitl.get_question_message(user_id)
        streaming = self._state.get_streaming_handler(user_id)

        if q_msg and streaming:
            short_answer = answer[:50] + "..." if len(answer) > 50 else answer
            try:
                await q_msg.edit_text(f"Ответ: {short_answer}\n\nПродолжаю...", parse_mode=None)
                streaming.current_message = q_msg
                streaming.buffer = f"Ответ: {short_answer}\n\nПродолжаю...\n"
                streaming.is_finalized = False
            except Exception as e:
                logger.debug(f"Could not edit question message: {e}")

        self._hitl.clear_question_state(user_id)

    async def _handle_result(self, user_id: int, result: TaskResult, message: Message):
        """Handle task completion"""
        session = self._state.get_claude_session(user_id)
        streaming = self._state.get_streaming_handler(user_id)

        if result.cancelled:
            if streaming:
                await streaming.finalize("**Задача отменена**")
                # Show file changes even on cancel (user might want to see what was done)
                await streaming.show_file_changes_summary()
            if session:
                session.cancel()
            return

        if result.success:
            if streaming:
                await streaming.send_completion(success=True)
                # Show summary of all file changes (Cursor-style)
                await streaming.show_file_changes_summary()
            if session:
                session.complete(result.session_id)

            context_id = getattr(session, 'context_id', None) if session else None
            if context_id and self.context_service and result.session_id:
                try:
                    await self.context_service.set_claude_session_id(context_id, result.session_id)
                    logger.info(
                        f"[{user_id}] Saved claude_session_id {result.session_id[:16]}... "
                        f"to context {context_id[:16]}..."
                    )

                    if session and session.current_prompt:
                        await self.context_service.save_message(context_id, "user", session.current_prompt)
                    if result.output:
                        await self.context_service.save_message(context_id, "assistant", result.output[:5000])

                except Exception as e:
                    logger.warning(f"Error saving to context: {e}")

            if result.session_id:
                self._state.set_continue_session_id(user_id, result.session_id)

            if session and self.project_service:
                new_working_dir = self._state.get_working_dir(user_id)
                original_dir = getattr(session, '_original_working_dir', session.working_dir)

                if new_working_dir and new_working_dir != original_dir:
                    try:
                        from domain.value_objects.user_id import UserId
                        uid = UserId.from_int(user_id)

                        project = await self.project_service.get_or_create(uid, new_working_dir)
                        await self.project_service.switch_project(uid, project.id)
                        logger.info(f"[{user_id}] Switched to project at {new_working_dir}")
                    except Exception as e:
                        logger.warning(f"Error updating project path: {e}")

        else:
            if streaming:
                await streaming.send_completion(success=False)
                # Show file changes even on error (user might want to see what was done)
                await streaming.show_file_changes_summary()
            if session:
                session.fail(result.error or "Cancelled" if result.cancelled else "Unknown error")

            if result.error and not result.cancelled:
                await message.answer(
                    f"<b>Завершено с ошибкой:</b>\n<pre><code>{html.escape(result.error[:1000])}</code></pre>",
                    parse_mode="HTML"
                )

    # === Input Handlers ===

    async def _handle_answer_input(self, message: Message):
        """Handle text input for question answer"""
        user_id = message.from_user.id
        self._hitl.set_expecting_answer(user_id, False)

        answer = message.text
        await message.answer(f"Ответ: {answer[:50]}...")

        await self.handle_question_response(user_id, answer)

    async def _handle_clarification_input(self, message: Message):
        """Handle text input for permission clarification"""
        user_id = message.from_user.id
        logger.info(f"[{user_id}] _handle_clarification_input called with: {message.text[:100]}")

        self._hitl.set_expecting_clarification(user_id, False)

        clarification = message.text.strip()
        preview = clarification[:50] + "..." if len(clarification) > 50 else clarification

        # Send clarification through permission response with approved=False
        logger.info(f"[{user_id}] Calling handle_permission_response with clarification")
        success = await self.handle_permission_response(user_id, False, clarification)
        logger.info(f"[{user_id}] handle_permission_response returned: {success}")

        if success:
            await message.answer(f"💬 Уточнение отправлено: {preview}")
        else:
            # No active permission request - clarification was ignored
            logger.warning(f"[{user_id}] Clarification was not accepted - no active permission request")
            await message.answer(
                f"⚠️ Нет активного запроса на подтверждение.\n\n"
                f"Ваше уточнение: {preview}\n\n"
                f"Отправьте это как новый запрос или дождитесь запроса от Claude.",
                parse_mode=None
            )

    async def _handle_plan_clarification(self, message: Message):
        """Handle text input for plan clarification"""
        user_id = message.from_user.id
        self._plans.set_expecting_clarification(user_id, False)

        clarification = message.text.strip()
        preview = clarification[:50] + "..." if len(clarification) > 50 else clarification

        success = await self.handle_plan_response(user_id, f"clarify:{clarification}")

        if success:
            await message.answer(f"💬 Уточнение плана отправлено: {preview}")
        else:
            await message.answer(
                f"⚠️ Нет активного запроса на утверждение плана.\n\n"
                f"Ваше уточнение: {preview}\n\n"
                f"Отправьте это как новый запрос.",
                parse_mode=None
            )

    async def _handle_path_input(self, message: Message):
        """Handle text input for path"""
        user_id = message.from_user.id
        self._hitl.set_expecting_path(user_id, False)

        path = message.text.strip()
        self.set_working_dir(user_id, path)

        await message.answer(f"Рабочая папка установлена:\n{path}", parse_mode=None)

    async def _handle_var_name_input(self, message: Message):
        """Handle variable name input during add flow"""
        user_id = message.from_user.id
        var_name = message.text.strip().upper()

        result = self._variables.validate_name(var_name)
        if not result.is_valid:
            await message.answer(
                f"Неверное имя переменной\n\n{result.error}",
                parse_mode=None,
                reply_markup=Keyboards.variable_cancel()
            )
            return

        menu_msg = self._variables.get_menu_message(user_id)
        self._variables.move_to_value_step(user_id, result.normalized_name)

        await message.answer(
            f"Введите значение для {result.normalized_name}:\n\n"
            f"Например: glpat-xxxx или Python/FastAPI",
            parse_mode=None,
            reply_markup=Keyboards.variable_cancel()
        )

    async def _handle_var_value_input(self, message: Message):
        """Handle variable value input during add/edit flow"""
        user_id = message.from_user.id
        var_name = self._variables.get_var_name(user_id)
        var_value = message.text.strip()

        if not var_name:
            self._variables.cancel(user_id)
            return

        result = self._variables.validate_value(var_value)
        if not result.is_valid:
            await message.answer(result.error, reply_markup=Keyboards.variable_cancel())
            return

        is_editing = self._variables.is_editing(user_id)

        if is_editing:
            old_desc = ""
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
            except Exception:
                pass

            await self._save_variable(message, var_name, var_value, old_desc)
            return

        menu_msg = self._variables.get_menu_message(user_id)
        self._variables.move_to_description_step(user_id, var_value)

        await message.answer(
            f"Введите описание для {var_name}:\n\n"
            f"Опишите, для чего эта переменная и как её использовать.\n"
            f"Например: Токен GitLab для git push/pull\n\n"
            f"Или нажмите кнопку, чтобы пропустить.",
            parse_mode=None,
            reply_markup=Keyboards.variable_skip_description()
        )

    async def _handle_var_desc_input(self, message: Message):
        """Handle variable description input and save the variable"""
        user_id = message.from_user.id
        var_name, var_value = self._variables.get_var_data(user_id)

        if not var_name or not var_value:
            self._variables.cancel(user_id)
            return

        var_desc = message.text.strip()
        await self._save_variable(message, var_name, var_value, var_desc)

    async def save_variable_skip_desc(self, user_id: int, message: Message):
        """Save variable without description (called from callback)"""
        var_name, var_value = self._variables.get_var_data(user_id)

        if not var_name or not var_value:
            self._variables.cancel(user_id)
            return

        await self._save_variable(message, var_name, var_value, "")

    async def _save_variable(self, message: Message, var_name: str, var_value: str, var_desc: str):
        """Save variable to context and show updated menu"""
        user_id = message.from_user.id

        if not self.project_service or not self.context_service:
            await message.answer("Сервисы не инициализированы")
            self._variables.cancel(user_id)
            return

        try:
            from domain.value_objects.user_id import UserId
            uid = UserId.from_int(user_id)

            project = await self.project_service.get_current(uid)
            if not project:
                await message.answer("Нет активного проекта. Используйте /change")
                self._variables.cancel(user_id)
                return

            context = await self.context_service.get_current(project.id)
            if not context:
                await message.answer("Нет активного контекста")
                self._variables.cancel(user_id)
                return

            await self.context_service.set_variable(context.id, var_name, var_value, var_desc)

            self._variables.complete(user_id)

            variables = await self.context_service.get_variables(context.id)

            display_val = var_value[:20] + "..." if len(var_value) > 20 else var_value
            desc_info = f"\n{var_desc}" if var_desc else ""

            await message.answer(
                f"Переменная создана\n\n"
                f"{var_name} = {display_val}"
                f"{desc_info}\n\n"
                f"Всего переменных: {len(variables)}",
                parse_mode=None,
                reply_markup=Keyboards.variables_menu(
                    variables, project.name, context.name,
                    show_back=True, back_to="menu:context"
                )
            )

        except Exception as e:
            logger.error(f"Error saving variable: {e}")
            await message.answer(f"Ошибка: {e}")
            self._variables.cancel(user_id)


def register_handlers(router: Router, handlers: MessageHandlers) -> None:
    """Register message handlers"""
    router.message.register(handlers.handle_document, F.document, StateFilter(None))
    router.message.register(handlers.handle_photo, F.photo, StateFilter(None))
    router.message.register(handlers.handle_text, F.text, StateFilter(None))


def get_message_handlers(bot_service, claude_proxy: ClaudeCodeProxyService) -> MessageHandlers:
    """Factory function to create message handlers"""
    return MessageHandlers(bot_service, claude_proxy)
