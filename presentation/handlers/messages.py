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
import logging
import os
import re
import uuid
from typing import Optional, TYPE_CHECKING

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import StateFilter

from presentation.keyboards.keyboards import Keyboards
from presentation.handlers.streaming import StreamingHandler, HeartbeatTracker
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

        # Legacy compatibility aliases (to minimize changes in other files)
        self.default_working_dir = default_working_dir

    # === Public API (used by other handlers) ===

    def is_yolo_mode(self, user_id: int) -> bool:
        """Check if YOLO mode is enabled for user"""
        return self._state.is_yolo_mode(user_id)

    def set_yolo_mode(self, user_id: int, enabled: bool):
        """Set YOLO mode for user"""
        self._state.set_yolo_mode(user_id, enabled)

    def get_working_dir(self, user_id: int) -> str:
        """Get user's working directory"""
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

    async def handle_permission_response(self, user_id: int, approved: bool):
        """Handle permission response from callback"""
        if self.use_sdk and self.sdk_service:
            success = await self.sdk_service.respond_to_permission(user_id, approved)
            if success:
                return

        # Fall back to HITL manager handling
        await self._hitl.respond_to_permission(user_id, approved)

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

    async def handle_plan_response(self, user_id: int, response: str):
        """Handle plan approval response from callback"""
        if self.use_sdk and self.sdk_service:
            success = await self.sdk_service.respond_to_plan(user_id, response)
            if success:
                self._plans.cleanup(user_id)
                return
        logger.warning(f"[{user_id}] Failed to respond to plan: {response}")

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

    # === Message Handlers ===

    async def handle_document(self, message: Message) -> None:
        """Handle document (file) messages"""
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

        document = message.document
        if not document:
            return

        if not self.file_processor_service:
            await message.answer("Обработка файлов недоступна")
            return

        filename = document.file_name or "unknown"
        file_size = document.file_size or 0

        is_valid, error = self.file_processor_service.validate_file(filename, file_size)
        if not is_valid:
            await message.answer(f"{error}")
            return

        try:
            file = await bot.get_file(document.file_id)
            file_content = await bot.download_file(file.file_path)
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            await message.answer(f"Ошибка скачивания файла: {e}")
            return

        processed = await self.file_processor_service.process_file(
            file_content, filename, document.mime_type
        )

        if processed.error:
            await message.answer(f"Ошибка обработки: {processed.error}")
            return

        caption = message.caption or ""

        if caption:
            if caption.startswith("/"):
                self._files.cache_file(message.message_id, processed)
                parts = caption.split(maxsplit=1)
                command_name = parts[0][1:]
                command_args = parts[1] if len(parts) > 1 else ""
                skill_command = f"/{command_name}"
                if command_args:
                    skill_command += f" {command_args}"

                prompt = f"run {skill_command}"
                enriched_prompt = self.file_processor_service.format_for_prompt(processed, prompt)

                file_info = f"{processed.filename} ({processed.size_bytes // 1024} KB)"
                await message.answer(
                    f"<b>Команда плагина:</b> <code>{skill_command}</code>\n"
                    f"{file_info}\n\nПередаю в Claude Code...",
                    parse_mode="HTML"
                )
                await self.handle_text(message, prompt_override=enriched_prompt, force_new_session=True)
            else:
                enriched_prompt = self.file_processor_service.format_for_prompt(processed, caption)
                file_info = f"{processed.filename} ({processed.size_bytes // 1024} KB)"
                task_preview = caption[:50] + "..." if len(caption) > 50 else caption
                await message.answer(f"Получен файл: {file_info}\nЗадача: {task_preview}")
                await self._execute_task_with_prompt(message, enriched_prompt)
        else:
            self._files.cache_file(message.message_id, processed)
            await message.answer(
                f"<b>Файл получен:</b> {processed.filename}\n"
                f"<b>Размер:</b> {processed.size_bytes // 1024} KB\n"
                f"<b>Тип:</b> {processed.file_type.value}\n\n"
                f"Сделайте <b>reply</b> на это сообщение с текстом задачи\n"
                f"или командой плагина (например, <code>/ralph-loop</code>)",
                parse_mode="HTML"
            )

    async def handle_photo(self, message: Message) -> None:
        """Handle photo messages"""
        user_id = message.from_user.id
        bot = message.bot

        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await message.answer("Вы не авторизованы для использования этого бота.")
            return

        if self._is_task_running(user_id):
            await message.answer("Задача уже выполняется.", reply_markup=Keyboards.claude_cancel(user_id))
            return

        if not message.photo:
            return

        photo = message.photo[-1]
        max_image_size = 5 * 1024 * 1024

        if photo.file_size and photo.file_size > max_image_size:
            await message.answer("Изображение слишком большое (максимум 5 MB)")
            return

        if not self.file_processor_service:
            await message.answer("Обработка файлов недоступна")
            return

        try:
            file = await bot.get_file(photo.file_id)
            file_content = await bot.download_file(file.file_path)
        except Exception as e:
            logger.error(f"Error downloading photo: {e}")
            await message.answer(f"Ошибка скачивания: {e}")
            return

        filename = f"image_{photo.file_unique_id}.jpg"
        processed = await self.file_processor_service.process_file(
            file_content, filename, "image/jpeg"
        )

        if processed.error:
            await message.answer(f"Ошибка обработки: {processed.error}")
            return

        caption = message.caption or ""

        if caption:
            if caption.startswith("/"):
                self._files.cache_file(message.message_id, processed)
                parts = caption.split(maxsplit=1)
                command_name = parts[0][1:]
                command_args = parts[1] if len(parts) > 1 else ""
                skill_command = f"/{command_name}"
                if command_args:
                    skill_command += f" {command_args}"

                prompt = f"run {skill_command}"
                enriched_prompt = self.file_processor_service.format_for_prompt(processed, prompt)

                await message.answer(
                    f"<b>Команда плагина:</b> <code>{skill_command}</code>\n"
                    f"Изображение добавлено в контекст\n\nПередаю в Claude Code...",
                    parse_mode="HTML"
                )
                await self.handle_text(message, prompt_override=enriched_prompt, force_new_session=True)
            else:
                enriched_prompt = self.file_processor_service.format_for_prompt(processed, caption)
                task_preview = caption[:50] + "..." if len(caption) > 50 else caption
                await message.answer(f"Изображение получено. Задача: {task_preview}")
                await self._execute_task_with_prompt(message, enriched_prompt)
        else:
            self._files.cache_file(message.message_id, processed)
            await message.answer(
                "<b>Изображение получено</b>\n\n"
                "Сделайте <b>reply</b> на это сообщение с текстом задачи.",
                parse_mode="HTML"
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
        original_text = message.text
        message.text = prompt
        await self.handle_text(message)
        message.text = original_text

    async def handle_text(
        self,
        message: Message,
        prompt_override: str = None,
        force_new_session: bool = False
    ) -> None:
        """Handle text messages - main entry point"""
        user_id = message.from_user.id
        bot = message.bot

        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await message.answer("Вы не авторизованы для использования этого бота.")
            return

        # === FILE REPLY HANDLING ===
        reply = message.reply_to_message
        if reply and self._files.has_file(reply.message_id) and self.file_processor_service:
            processed_file = self._files.pop_file(reply.message_id)
            enriched_prompt = self.file_processor_service.format_for_prompt(
                processed_file, message.text
            )
            task_preview = message.text[:50] + "..." if len(message.text) > 50 else message.text
            await message.answer(f"Файл: {processed_file.filename}\nЗадача: {task_preview}")
            message.text = enriched_prompt

        elif reply and (reply.document or reply.photo) and self.file_processor_service:
            file_context = await self._extract_reply_file_context(reply, bot)
            if file_context:
                processed_file, _ = file_context
                enriched_prompt = self.file_processor_service.format_for_prompt(
                    processed_file, message.text
                )
                task_preview = message.text[:50] + "..." if len(message.text) > 50 else message.text
                await message.answer(f"Файл: {processed_file.filename}\nЗадача: {task_preview}")
                message.text = enriched_prompt

        # === SPECIAL INPUT MODES ===
        if self._hitl.is_expecting_answer(user_id):
            await self._handle_answer_input(message)
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
                        context_id, original_prompt
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

        yolo_indicator = " YOLO" if self.is_yolo_mode(user_id) else ""
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

        heartbeat = HeartbeatTracker(streaming, interval=5.0)
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
                        tokens, _, _ = streaming.get_context_usage()
                        tokens_k = tokens // 1000
                        cost_str = f"${result.total_cost_usd:.4f}"
                        await streaming.append(f"\n\n{cost_str} | ~{tokens_k}K токенов")

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

    # === Callback Handlers ===

    async def _on_text(self, user_id: int, text: str):
        """Handle streaming text output"""
        streaming = self._state.get_streaming_handler(user_id)
        if streaming:
            streaming.add_tokens(text)
            await streaming.append(text)

    async def _on_tool_use(self, user_id: int, tool_name: str, tool_input: dict, message: Message):
        """Handle tool use notification"""
        streaming = self._state.get_streaming_handler(user_id)

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
            elif tool_name.lower() in ["read", "write", "edit"]:
                details = tool_input.get("file_path", tool_input.get("path", ""))[:100]
            elif tool_name.lower() == "glob":
                details = tool_input.get("pattern", "")[:100]
            elif tool_name.lower() == "grep":
                details = tool_input.get("pattern", "")[:100]

            await streaming.show_tool_use(tool_name, details)

    async def _on_tool_result(self, user_id: int, tool_id: str, output: str):
        """Handle tool result"""
        streaming = self._state.get_streaming_handler(user_id)
        if streaming and output:
            streaming.add_tokens(output, multiplier=0.5)
            await streaming.show_tool_result(output, success=True)

    async def _on_permission(self, user_id: int, tool_name: str, details: str, message: Message) -> bool:
        """Handle permission request (CLI mode)"""
        if self.is_yolo_mode(user_id):
            streaming = self._state.get_streaming_handler(user_id)
            if streaming:
                truncated = details[:100] + "..." if len(details) > 100 else details
                await streaming.append(f"\n**Авто-одобрено:** `{tool_name}`\n`{truncated}`\n")
            return True

        session = self._state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        text = f"<b>Запрос разрешения</b>\n\n"
        text += f"<b>Инструмент:</b> <code>{tool_name}</code>\n"
        if details:
            display_details = details if len(details) < 500 else details[:500] + "..."
            text += f"<b>Детали:</b>\n<pre>{display_details}</pre>"

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

        text = f"<b>Вопрос</b>\n\n{question}"

        if options:
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
        else:
            self._hitl.set_expecting_answer(user_id, True)
            await message.answer(text + "\n\nВведите ваш ответ:", parse_mode=None)

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
        """Handle thinking output"""
        streaming = self._state.get_streaming_handler(user_id)
        if streaming and thinking:
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
        if self.is_yolo_mode(user_id):
            streaming = self._state.get_streaming_handler(user_id)
            if streaming:
                truncated = details[:100] + "..." if len(details) > 100 else details
                await streaming.append(f"\n**Авто-одобрено:** `{tool_name}`\n`{truncated}`\n")

            if self.sdk_service:
                await self.sdk_service.respond_to_permission(user_id, True)
            return

        session = self._state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        text = f"<b>Запрос разрешения</b>\n\n"
        text += f"<b>Инструмент:</b> <code>{tool_name}</code>\n"
        if details:
            display_details = details if len(details) < 500 else details[:500] + "..."
            text += f"<b>Детали:</b>\n<pre>{display_details}</pre>"

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

        text = f"<b>Вопрос</b>\n\n{question}"

        if options:
            q_msg = await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
            self._hitl.set_question_context(user_id, request_id, question, options, q_msg)
        else:
            self._hitl.set_expecting_answer(user_id, True)
            q_msg = await message.answer(text + "\n\nВведите ваш ответ:", parse_mode=None)
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
        request_id = str(uuid.uuid4())[:8]

        plan_content = ""
        if plan_file:
            try:
                working_dir = self.get_working_dir(user_id)
                plan_path = os.path.join(working_dir, plan_file)

                if os.path.exists(plan_path):
                    with open(plan_path, 'r', encoding='utf-8') as f:
                        plan_content = f.read()
            except Exception as e:
                logger.error(f"[{user_id}] Error reading plan file: {e}")

        if not plan_content:
            plan_content = tool_input.get("planContent", "")

        if plan_content:
            if len(plan_content) > 3500:
                plan_content = plan_content[:3500] + "\n\n... (план сокращён)"
            text = f"<b>План готов к выполнению</b>\n\n<pre>{plan_content}</pre>"
        else:
            text = "<b>План готов к выполнению</b>\n\n<i>Содержимое плана недоступно</i>"

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

        if perm_msg and streaming:
            status = "Одобрено" if approved else "Отклонено"
            try:
                await perm_msg.edit_text(f"{status}\n\nПродолжаю...", parse_mode=None)
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
            if session:
                session.cancel()
            return

        if result.success:
            if streaming:
                await streaming.send_completion(success=True)
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
            if session:
                session.fail(result.error or "Cancelled" if result.cancelled else "Unknown error")

            if result.error and not result.cancelled:
                await message.answer(
                    f"<b>Завершено с ошибкой:</b>\n<pre>{result.error[:1000]}</pre>",
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

    async def _handle_plan_clarification(self, message: Message):
        """Handle text input for plan clarification"""
        user_id = message.from_user.id
        self._plans.set_expecting_clarification(user_id, False)

        clarification = message.text.strip()
        preview = clarification[:50] + "..." if len(clarification) > 50 else clarification

        await message.answer(f"Уточнение отправлено: {preview}")

        await self.handle_plan_response(user_id, f"clarify:{clarification}")

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
