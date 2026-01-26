"""
Message Handlers for Claude Code Proxy

Handles user messages and forwards them to Claude Code,
managing streaming output, HITL interactions, and session state.

Supports two backends:
1. Claude Agent SDK (preferred) - proper HITL with can_use_tool callback
2. CLI subprocess (fallback) - stream-json parsing
"""

import asyncio
import logging
import os
import re
import uuid
from typing import Optional, Union
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter

from presentation.keyboards.keyboards import Keyboards
from presentation.handlers.streaming import StreamingHandler, HeartbeatTracker
from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService, TaskResult
from domain.entities.claude_code_session import ClaudeCodeSession, SessionStatus

# Try to import SDK service
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
    SDKTaskResult = None
    TaskStatus = None

logger = logging.getLogger(__name__)
router = Router()


class MessageHandlers:
    """Bot message handlers for Claude Code proxy"""

    def __init__(
        self,
        bot_service,
        claude_proxy: ClaudeCodeProxyService,
        sdk_service: Optional["ClaudeAgentSDKService"] = None,
        default_working_dir: str = "/root",
        project_service=None,
        context_service=None
    ):
        self.bot_service = bot_service
        self.claude_proxy = claude_proxy  # CLI fallback
        self.sdk_service = sdk_service    # Preferred SDK backend
        self.default_working_dir = default_working_dir
        self.project_service = project_service
        self.context_service = context_service

        # Determine which backend to use
        self.use_sdk = sdk_service is not None and SDK_AVAILABLE
        logger.info(f"MessageHandlers initialized with SDK backend: {self.use_sdk}")

        # User state tracking
        self._user_sessions: dict[int, ClaudeCodeSession] = {}
        self._user_working_dirs: dict[int, str] = {}
        self._continue_sessions: dict[int, str] = {}  # user_id -> claude_session_id

        # HITL state
        self._expecting_answer: dict[int, bool] = {}
        self._expecting_path: dict[int, bool] = {}
        self._pending_questions: dict[int, list[str]] = {}  # user_id -> options list
        self._pending_permission_messages: dict[int, Message] = {}  # user_id -> permission msg
        self._pending_question_messages: dict[int, Message] = {}  # user_id -> question msg

        # Permission/Question response events
        self._permission_events: dict[int, asyncio.Event] = {}
        self._permission_responses: dict[int, bool] = {}
        self._question_events: dict[int, asyncio.Event] = {}
        self._question_responses: dict[int, str] = {}

        # Active streaming handlers
        self._streaming_handlers: dict[int, StreamingHandler] = {}

        # YOLO mode (auto-approve all operations)
        self._yolo_mode: dict[int, bool] = {}

        # Variable input state (for interactive /vars menu)
        self._expecting_var_name: dict[int, bool] = {}      # user_id -> expecting name
        self._expecting_var_value: dict[int, str] = {}      # user_id -> var_name being set
        self._expecting_var_desc: dict[int, tuple] = {}     # user_id -> (var_name, var_value)
        self._pending_var_message: dict[int, Message] = {}  # user_id -> menu message to update
        self._editing_var_name: dict[int, str] = {}         # user_id -> var being edited

    def is_yolo_mode(self, user_id: int) -> bool:
        """Check if YOLO mode is enabled for user"""
        return self._yolo_mode.get(user_id, False)

    def set_yolo_mode(self, user_id: int, enabled: bool):
        """Set YOLO mode for user"""
        self._yolo_mode[user_id] = enabled

    def clear_session_cache(self, user_id: int) -> None:
        """Clear in-memory session cache for user.

        Call this when context is reset to ensure fresh start.
        Without this, the next message would use the cached session_id
        and Claude would continue the old context.
        """
        self._continue_sessions.pop(user_id, None)

    def get_working_dir(self, user_id: int) -> str:
        """Get user's working directory"""
        return self._user_working_dirs.get(user_id, self.default_working_dir)

    def set_working_dir(self, user_id: int, path: str):
        """Set user's working directory"""
        self._user_working_dirs[user_id] = path

    def set_expecting_answer(self, user_id: int, expecting: bool):
        """Set whether we're expecting a text answer from user"""
        self._expecting_answer[user_id] = expecting

    def set_expecting_path(self, user_id: int, expecting: bool):
        """Set whether we're expecting a path from user"""
        self._expecting_path[user_id] = expecting

    # ============== Variable Input State Management ==============

    def set_expecting_var_name(self, user_id: int, expecting: bool, menu_msg: Message = None):
        """Set whether we're expecting a variable name"""
        self._expecting_var_name[user_id] = expecting
        if menu_msg:
            self._pending_var_message[user_id] = menu_msg

    def set_expecting_var_value(self, user_id: int, var_name: str, menu_msg: Message = None):
        """Set that we're expecting a value for the given variable name"""
        self._expecting_var_name.pop(user_id, None)
        self._expecting_var_value[user_id] = var_name
        if menu_msg:
            self._pending_var_message[user_id] = menu_msg

    def set_expecting_var_desc(self, user_id: int, var_name: str, var_value: str, menu_msg: Message = None):
        """Set that we're expecting a description for the variable"""
        self._expecting_var_value.pop(user_id, None)
        self._expecting_var_desc[user_id] = (var_name, var_value)
        if menu_msg:
            self._pending_var_message[user_id] = menu_msg

    def clear_var_state(self, user_id: int):
        """Clear all variable input state"""
        self._expecting_var_name.pop(user_id, None)
        self._expecting_var_value.pop(user_id, None)
        self._expecting_var_desc.pop(user_id, None)
        self._pending_var_message.pop(user_id, None)

    def get_pending_var_message(self, user_id: int) -> Optional[Message]:
        """Get the pending menu message to update"""
        return self._pending_var_message.get(user_id)

    def is_expecting_var_input(self, user_id: int) -> bool:
        """Check if we're expecting any variable input"""
        return (
            self._expecting_var_name.get(user_id, False) or
            user_id in self._expecting_var_value or
            user_id in self._expecting_var_desc
        )

    def start_var_input(self, user_id: int, menu_msg: Message = None):
        """Start variable input flow - expect name first"""
        self.set_expecting_var_name(user_id, True, menu_msg)

    def start_var_edit(self, user_id: int, var_name: str, menu_msg: Message = None):
        """Start variable edit flow - expect new value"""
        self._editing_var_name[user_id] = var_name
        self._expecting_var_value[user_id] = var_name
        if menu_msg:
            self._pending_var_message[user_id] = menu_msg

    def cancel_var_input(self, user_id: int):
        """Cancel variable input and clear state"""
        self.clear_var_state(user_id)
        self._editing_var_name.pop(user_id, None)

    def set_continue_session(self, user_id: int, session_id: str):
        """Set session to continue on next message"""
        self._continue_sessions[user_id] = session_id

    def get_pending_question_option(self, user_id: int, index: int) -> str:
        """Get option text by index from pending question"""
        options = self._pending_questions.get(user_id, [])
        if 0 <= index < len(options):
            return options[index]
        return str(index)

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
        # Find cd commands in the command string
        # Match: cd followed by path (handles && chains, ; separators)
        cd_patterns = [
            r'(?:^|&&|;)\s*cd\s+([^\s;&|]+)',  # cd path
            r'(?:^|&&|;)\s*cd\s+"([^"]+)"',     # cd "path with spaces"
            r"(?:^|&&|;)\s*cd\s+'([^']+)'",     # cd 'path with spaces'
        ]

        new_dir = None
        for pattern in cd_patterns:
            matches = re.findall(pattern, command)
            if matches:
                # Take the last cd command in the chain
                new_dir = matches[-1]
                break

        if not new_dir:
            return None

        # Resolve the path
        if new_dir.startswith('/'):
            # Absolute path
            return new_dir
        elif new_dir == '~':
            return '/root'
        elif new_dir == '-':
            # cd - goes to previous dir, we can't track this
            return None
        elif new_dir == '..':
            # Go up one level
            return os.path.dirname(current_dir)
        else:
            # Relative path
            return os.path.join(current_dir, new_dir)

    async def handle_permission_response(self, user_id: int, approved: bool):
        """Handle permission response from callback"""
        # Try SDK first
        if self.use_sdk and self.sdk_service:
            success = await self.sdk_service.respond_to_permission(user_id, approved)
            if success:
                return

        # Fall back to CLI handling
        self._permission_responses[user_id] = approved
        event = self._permission_events.get(user_id)
        if event:
            event.set()

    async def handle_question_response(self, user_id: int, answer: str):
        """Handle question response from callback"""
        # Try SDK first
        if self.use_sdk and self.sdk_service:
            success = await self.sdk_service.respond_to_question(user_id, answer)
            if success:
                return

        # Fall back to CLI handling
        self._question_responses[user_id] = answer
        event = self._question_events.get(user_id)
        if event:
            event.set()

    async def handle_text(self, message: Message) -> None:
        """Handle text messages - main entry point"""
        user_id = message.from_user.id
        bot = message.bot

        # Check authorization
        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await message.answer("❌ Вы не авторизованы для использования этого бота.")
            return

        # Handle special input modes
        if self._expecting_answer.get(user_id):
            await self._handle_answer_input(message)
            return

        if self._expecting_path.get(user_id):
            await self._handle_path_input(message)
            return

        # Handle variable input modes (for /vars interactive menu)
        if self._expecting_var_name.get(user_id):
            await self._handle_var_name_input(message)
            return

        if user_id in self._expecting_var_value:
            await self._handle_var_value_input(message)
            return

        if user_id in self._expecting_var_desc:
            await self._handle_var_desc_input(message)
            return

        # Check if already running (check both backends)
        is_running = False
        if self.use_sdk and self.sdk_service:
            is_running = self.sdk_service.is_task_running(user_id)
        if not is_running:
            is_running = self.claude_proxy.is_task_running(user_id)

        if is_running:
            await message.answer(
                "⏳ Задача уже выполняется.\n\n"
                "Используйте кнопку отмены или /cancel чтобы остановить.",
                reply_markup=Keyboards.claude_cancel(user_id)
            )
            return

        # Get working directory and session from project/context (auto-continue)
        working_dir = self.get_working_dir(user_id)
        session_id = self._continue_sessions.get(user_id)  # Don't pop - keep for next message
        context_id = None
        enriched_prompt = message.text  # May be enriched with context variables

        # Use project/context services if available (for auto-continue)
        if self.project_service and self.context_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)

                # Get current project
                project = await self.project_service.get_current(uid)
                if project:
                    working_dir = project.working_dir

                    # Get or create context
                    context = await self.context_service.get_current(project.id)
                    if not context:
                        context = await self.context_service.create_new(
                            project.id, uid, "main", set_as_current=True
                        )

                    context_id = context.id

                    # Auto-continue: use context's claude_session_id
                    if not session_id and context.claude_session_id:
                        session_id = context.claude_session_id
                        logger.info(
                            f"[{user_id}] Auto-continue: loaded session {session_id[:16]}... "
                            f"from context '{context.name}' (messages: {context.message_count})"
                        )
                    elif session_id:
                        logger.info(f"[{user_id}] Using in-memory session {session_id[:16]}...")
                    else:
                        logger.info(f"[{user_id}] Starting new session (no previous session_id)")

                    # Enrich prompt with context variables
                    new_prompt = await self.context_service.get_enriched_prompt(
                        context_id, message.text
                    )
                    if new_prompt != message.text:
                        enriched_prompt = new_prompt
                        logger.info(f"Enriched prompt with {len(context.variables)} context variables")

                    # Update local working dir cache
                    self._user_working_dirs[user_id] = working_dir

            except Exception as e:
                logger.warning(f"Error getting project/context: {e}")

        # Create session state
        session = ClaudeCodeSession(
            user_id=user_id,
            working_dir=working_dir,
            claude_session_id=session_id
        )
        session.start_task(message.text)
        self._user_sessions[user_id] = session

        # Store context_id for saving messages later
        if context_id:
            session.context_id = context_id  # type: ignore

        # Store original working dir to detect changes
        session._original_working_dir = working_dir  # type: ignore

        # Start streaming handler with project info and cancel button
        cancel_keyboard = Keyboards.claude_cancel(user_id)
        streaming = StreamingHandler(bot, message.chat.id, reply_markup=cancel_keyboard)

        # Build header with project info (status will be at bottom via HeartbeatTracker)
        yolo_indicator = " ⚡YOLO" if self.is_yolo_mode(user_id) else ""
        header = ""
        if self.project_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                project = await self.project_service.get_current(uid)
                if project:
                    header = f"📂 **{project.name}**{yolo_indicator}\n"
                    header += f"📁 `{working_dir}`\n"
                else:
                    header = f"📁 `{working_dir}`{yolo_indicator}\n"
            except Exception:
                header = f"📁 `{working_dir}`{yolo_indicator}\n"
        else:
            header = f"📁 `{working_dir}`{yolo_indicator}\n"

        await streaming.start(header)
        self._streaming_handlers[user_id] = streaming

        # Setup HITL events
        self._permission_events[user_id] = asyncio.Event()
        self._question_events[user_id] = asyncio.Event()

        # Start heartbeat for progress indication
        heartbeat = HeartbeatTracker(streaming, interval=5.0)
        await heartbeat.start()

        try:
            # Choose backend: SDK (preferred) or CLI (fallback)
            if self.use_sdk and self.sdk_service:
                # Use SDK with proper HITL via can_use_tool callback
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
                    on_thinking=lambda think: self._on_thinking(user_id, think),
                    on_error=lambda err: self._on_error(user_id, err),
                )

                # Show cost summary if available
                if result.total_cost_usd and not result.cancelled:
                    streaming = self._streaming_handlers.get(user_id)
                    if streaming:
                        tokens, _, _ = streaming.get_context_usage()
                        tokens_k = tokens // 1000
                        cost_str = f"${result.total_cost_usd:.4f}"
                        await streaming.append(f"\n\n💰 {cost_str} | ~{tokens_k}K токенов")

                # Convert SDK result to common format
                cli_result = TaskResult(
                    success=result.success,
                    output=result.output,
                    session_id=result.session_id,
                    error=result.error,
                    cancelled=result.cancelled,
                )
                await self._handle_result(user_id, cli_result, message)
            else:
                # Use CLI subprocess with stream-json
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
            # Stop heartbeat
            await heartbeat.stop()
            # Cleanup
            self._permission_events.pop(user_id, None)
            self._question_events.pop(user_id, None)
            self._streaming_handlers.pop(user_id, None)

    async def _on_text(self, user_id: int, text: str):
        """Handle streaming text output"""
        streaming = self._streaming_handlers.get(user_id)
        if streaming:
            streaming.add_tokens(text)  # Count output tokens
            await streaming.append(text)

    async def _on_tool_use(self, user_id: int, tool_name: str, tool_input: dict, message: Message):
        """Handle tool use notification"""
        streaming = self._streaming_handlers.get(user_id)

        # Track directory changes from cd commands
        if tool_name.lower() == "bash":
            command = tool_input.get("command", "")
            current_dir = self.get_working_dir(user_id)
            new_dir = self._detect_cd_command(command, current_dir)

            if new_dir:
                # Update working directory for future operations
                self._user_working_dirs[user_id] = new_dir
                logger.info(f"[{user_id}] Working directory changed: {current_dir} -> {new_dir}")

                # Also update in current session
                session = self._user_sessions.get(user_id)
                if session:
                    session.working_dir = new_dir

        if streaming:
            # Special handling for TodoWrite - show todo list in separate message
            if tool_name.lower() == "todowrite":
                todos = tool_input.get("todos", [])
                if todos:
                    await streaming.show_todo_list(todos)
                return  # Don't show generic tool use message

            # Special handling for EnterPlanMode
            if tool_name.lower() == "enterplanmode":
                await streaming.show_plan_mode_enter()
                return

            # Special handling for ExitPlanMode
            if tool_name.lower() == "exitplanmode":
                await streaming.show_plan_mode_exit()
                return

            # Format tool details
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
        """Handle tool result - show output to user"""
        streaming = self._streaming_handlers.get(user_id)
        if streaming and output:
            streaming.add_tokens(output, multiplier=0.5)  # Tool results are compressed
            await streaming.show_tool_result(output, success=True)
        logger.debug(f"Tool result for user {user_id}: {output[:100]}...")

    async def _on_permission(self, user_id: int, tool_name: str, details: str, message: Message) -> bool:
        """Handle permission request - show approval buttons and wait"""
        # YOLO mode: auto-approve without waiting
        if self.is_yolo_mode(user_id):
            streaming = self._streaming_handlers.get(user_id)
            if streaming:
                truncated_details = details[:100] + "..." if len(details) > 100 else details
                await streaming.append(f"\n⚡ **Авто-одобрено:** `{tool_name}`\n`{truncated_details}`\n")
            return True

        # Normal mode: show buttons and wait for approval
        session = self._user_sessions.get(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        # Send permission request message
        text = f"🔐 <b>Запрос разрешения</b>\n\n"
        text += f"<b>Инструмент:</b> <code>{tool_name}</code>\n"
        if details:
            # Truncate long details
            display_details = details if len(details) < 500 else details[:500] + "..."
            text += f"<b>Детали:</b>\n<pre>{display_details}</pre>"

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.claude_permission(user_id, tool_name, request_id)
        )

        # Wait for response (with timeout)
        event = self._permission_events.get(user_id)
        if event:
            event.clear()
            try:
                await asyncio.wait_for(event.wait(), timeout=300)  # 5 min timeout
                approved = self._permission_responses.get(user_id, False)
            except asyncio.TimeoutError:
                await message.answer("⏱️ Время ожидания истекло. Отклоняю.")
                approved = False

            if session:
                session.resume_running()

            return approved

        return False

    async def _on_question(self, user_id: int, question: str, options: list[str], message: Message) -> str:
        """Handle question - show options and wait for answer"""
        session = self._user_sessions.get(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_answer(request_id, question, options)

        # Store options for later lookup
        self._pending_questions[user_id] = options

        # Send question message
        text = f"❓ <b>Вопрос</b>\n\n{question}"

        if options:
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
        else:
            # No options - expect text input
            self._expecting_answer[user_id] = True
            await message.answer(
                text + "\n\nВведите ваш ответ:",
                parse_mode=None
            )

        # Wait for response
        event = self._question_events.get(user_id)
        if event:
            event.clear()
            try:
                await asyncio.wait_for(event.wait(), timeout=300)
                answer = self._question_responses.get(user_id, "")
            except asyncio.TimeoutError:
                await message.answer("⏱️ Время ожидания ответа истекло.")
                answer = ""

            if session:
                session.resume_running()

            # Cleanup
            self._pending_questions.pop(user_id, None)
            self._expecting_answer.pop(user_id, None)

            return answer

        return ""

    async def _on_error(self, user_id: int, error: str):
        """Handle error from Claude Code"""
        streaming = self._streaming_handlers.get(user_id)
        if streaming:
            await streaming.send_error(error)

        session = self._user_sessions.get(user_id)
        if session:
            session.fail(error)

    async def _on_thinking(self, user_id: int, thinking: str):
        """Handle thinking output from Claude (extended thinking models)"""
        streaming = self._streaming_handlers.get(user_id)
        if streaming and thinking:
            # Show abbreviated thinking
            preview = thinking[:200] + "..." if len(thinking) > 200 else thinking
            await streaming.append(f"\n💭 *{preview}*\n")

    async def _on_permission_sdk(
        self,
        user_id: int,
        tool_name: str,
        details: str,
        tool_input: dict,
        message: Message
    ):
        """
        Handle permission request from SDK.

        Unlike CLI version, this just sends the UI - the SDK's can_use_tool
        callback handles waiting for the response.
        """
        # YOLO mode: auto-approve without showing buttons
        if self.is_yolo_mode(user_id):
            streaming = self._streaming_handlers.get(user_id)
            if streaming:
                truncated_details = details[:100] + "..." if len(details) > 100 else details
                await streaming.append(f"\n⚡ **Авто-одобрено:** `{tool_name}`\n`{truncated_details}`\n")

            # Auto-approve via SDK
            if self.sdk_service:
                await self.sdk_service.respond_to_permission(user_id, True)
            return

        # Normal mode: show permission request with buttons
        session = self._user_sessions.get(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        # Send permission request message with inline buttons
        text = f"🔐 <b>Запрос разрешения</b>\n\n"
        text += f"<b>Инструмент:</b> <code>{tool_name}</code>\n"
        if details:
            display_details = details if len(details) < 500 else details[:500] + "..."
            text += f"<b>Детали:</b>\n<pre>{display_details}</pre>"

        perm_msg = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.claude_permission(user_id, tool_name, request_id)
        )
        # Save the message so we can edit it after approval/rejection
        self._pending_permission_messages[user_id] = perm_msg

    async def _on_question_sdk(
        self,
        user_id: int,
        question: str,
        options: list[str],
        message: Message
    ):
        """
        Handle question from SDK (AskUserQuestion tool).

        Unlike CLI version, this just sends the UI - the SDK's can_use_tool
        callback handles waiting for the response.
        """
        session = self._user_sessions.get(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_answer(request_id, question, options)

        # Store options for callback lookup
        self._pending_questions[user_id] = options

        # Send question message with inline buttons
        text = f"❓ <b>Вопрос</b>\n\n{question}"

        if options:
            q_msg = await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
            # Save the message so we can edit it after answer
            self._pending_question_messages[user_id] = q_msg
        else:
            # No options - expect text input
            self._expecting_answer[user_id] = True
            q_msg = await message.answer(
                text + "\n\nВведите ваш ответ:",
                parse_mode=None
            )
            self._pending_question_messages[user_id] = q_msg

    async def _on_permission_completed(self, user_id: int, approved: bool):
        """
        Handle permission completion - edit the permission message to show result
        and use it for continued streaming.
        """
        perm_msg = self._pending_permission_messages.pop(user_id, None)
        streaming = self._streaming_handlers.get(user_id)

        if perm_msg and streaming:
            # Edit the permission message to show result and continue streaming there
            status = "✅ Одобрено" if approved else "❌ Отклонено"
            try:
                await perm_msg.edit_text(
                    f"{status}\n\n🤖 Продолжаю...",
                    parse_mode=None
                )
                # Use this message for continued streaming
                streaming.current_message = perm_msg
                streaming.buffer = f"{status}\n\n🤖 Продолжаю...\n"
                streaming.is_finalized = False
            except Exception as e:
                logger.debug(f"Could not edit permission message: {e}")

    async def _on_question_completed(self, user_id: int, answer: str):
        """
        Handle question completion - edit the question message to show answer
        and use it for continued streaming.
        """
        q_msg = self._pending_question_messages.pop(user_id, None)
        streaming = self._streaming_handlers.get(user_id)

        if q_msg and streaming:
            # Edit the question message to show answer and continue streaming there
            short_answer = answer[:50] + "..." if len(answer) > 50 else answer
            try:
                await q_msg.edit_text(
                    f"📝 Ответ: {short_answer}\n\n🤖 Продолжаю...",
                    parse_mode=None
                )
                # Use this message for continued streaming
                streaming.current_message = q_msg
                streaming.buffer = f"📝 Ответ: {short_answer}\n\n🤖 Продолжаю...\n"
                streaming.is_finalized = False
            except Exception as e:
                logger.debug(f"Could not edit question message: {e}")

    async def _handle_result(self, user_id: int, result: TaskResult, message: Message):
        """Handle task completion"""
        session = self._user_sessions.get(user_id)
        streaming = self._streaming_handlers.get(user_id)

        if result.cancelled:
            if streaming:
                await streaming.finalize("🛑 **Задача отменена**")
            if session:
                session.cancel()
            return

        if result.success:
            if streaming:
                await streaming.send_completion(success=True)
            if session:
                session.complete(result.session_id)

            # Save to context if available (for auto-continue)
            context_id = getattr(session, 'context_id', None) if session else None
            if context_id and self.context_service and result.session_id:
                try:
                    # Save claude_session_id for next auto-continue
                    await self.context_service.set_claude_session_id(context_id, result.session_id)
                    logger.info(
                        f"[{user_id}] Saved claude_session_id {result.session_id[:16]}... "
                        f"to context {context_id[:16]}..."
                    )

                    # Save messages to context
                    if session and session.current_prompt:
                        await self.context_service.save_message(context_id, "user", session.current_prompt)
                    if result.output:
                        await self.context_service.save_message(context_id, "assistant", result.output[:5000])

                    logger.info(f"[{user_id}] Saved messages to context")
                except Exception as e:
                    logger.warning(f"Error saving to context: {e}")

            # Fallback: save session_id for users without project (enables auto-continue)
            if result.session_id:
                self._continue_sessions[user_id] = result.session_id
                logger.debug(f"Saved session {result.session_id} for user {user_id} (fallback)")

            # Check if working directory changed and update project path
            if session and self.project_service:
                new_working_dir = self._user_working_dirs.get(user_id)
                original_dir = getattr(session, '_original_working_dir', session.working_dir)

                if new_working_dir and new_working_dir != original_dir:
                    try:
                        from domain.value_objects.user_id import UserId
                        uid = UserId.from_int(user_id)

                        # Get or create project at new path
                        project = await self.project_service.get_or_create(
                            uid, new_working_dir
                        )
                        # Switch to the new project
                        await self.project_service.switch_project(uid, project.id)
                        logger.info(f"[{user_id}] Switched to project at {new_working_dir}")
                    except Exception as e:
                        logger.warning(f"Error updating project path: {e}")

            # Auto-continue enabled: no need to show button, just confirm completion
            # User can simply send next message to continue
        else:
            if streaming:
                await streaming.send_completion(success=False)
            if session:
                session.fail(result.error or "Cancelled" if result.cancelled else "Unknown error")

            # Don't show error message if task was cancelled by user
            if result.error and not result.cancelled:
                await message.answer(f"⚠️ <b>Завершено с ошибкой:</b>\n<pre>{result.error[:1000]}</pre>", parse_mode="HTML")

    async def _handle_answer_input(self, message: Message):
        """Handle text input for question answer"""
        user_id = message.from_user.id
        self._expecting_answer[user_id] = False

        answer = message.text
        await message.answer(f"📝 Ответ: {answer[:50]}...")

        # Use the unified response handler (supports both SDK and CLI)
        await self.handle_question_response(user_id, answer)

    async def _handle_path_input(self, message: Message):
        """Handle text input for path"""
        user_id = message.from_user.id
        self._expecting_path[user_id] = False

        path = message.text.strip()
        self.set_working_dir(user_id, path)

        await message.answer(
            f"📁 Рабочая папка установлена:\n{path}",
            parse_mode=None
        )

    # ============== Variable Input Handlers ==============

    async def _handle_var_name_input(self, message: Message):
        """Handle variable name input during add flow"""
        user_id = message.from_user.id
        var_name = message.text.strip().upper()  # Uppercase convention

        # Validate name (alphanumeric + underscore, starts with letter)
        if not re.match(r'^[A-Z][A-Z0-9_]*$', var_name):
            await message.answer(
                "❌ Неверное имя переменной\n\n"
                "Имя должно:\n"
                "• Начинаться с буквы\n"
                "• Содержать только буквы, цифры и _\n\n"
                "Например: GITLAB_TOKEN, API_KEY, PROJECT_STACK",
                parse_mode=None,
                reply_markup=Keyboards.variable_cancel()
            )
            return

        # Move to value input state
        menu_msg = self._pending_var_message.get(user_id)
        self.set_expecting_var_value(user_id, var_name, menu_msg)

        await message.answer(
            f"✏️ Введите значение для {var_name}:\n\n"
            f"Например: glpat-xxxx или Python/FastAPI",
            parse_mode=None,
            reply_markup=Keyboards.variable_cancel()
        )

    async def _handle_var_value_input(self, message: Message):
        """Handle variable value input during add/edit flow"""
        user_id = message.from_user.id
        var_name = self._expecting_var_value.get(user_id)
        var_value = message.text.strip()

        if not var_name:
            self.clear_var_state(user_id)
            return

        if not var_value:
            await message.answer(
                "❌ Значение не может быть пустым",
                reply_markup=Keyboards.variable_cancel()
            )
            return

        # Check if editing an existing variable - keep old description
        is_editing = user_id in self._editing_var_name

        if is_editing:
            # Save directly with existing description
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
            self._editing_var_name.pop(user_id, None)
            return

        # Move to description input state (new variable)
        menu_msg = self._pending_var_message.get(user_id)
        self.set_expecting_var_desc(user_id, var_name, var_value, menu_msg)

        await message.answer(
            f"📝 Введите описание для {var_name}:\n\n"
            f"Опишите, для чего эта переменная и как её использовать.\n"
            f"Например: Токен GitLab для git push/pull\n\n"
            f"Или нажмите кнопку, чтобы пропустить.",
            parse_mode=None,
            reply_markup=Keyboards.variable_skip_description()
        )

    async def _handle_var_desc_input(self, message: Message):
        """Handle variable description input and save the variable"""
        user_id = message.from_user.id
        var_data = self._expecting_var_desc.get(user_id)

        if not var_data:
            self.clear_var_state(user_id)
            return

        var_name, var_value = var_data
        var_desc = message.text.strip()

        await self._save_variable(message, var_name, var_value, var_desc)

    async def save_variable_skip_desc(self, user_id: int, message: Message):
        """Save variable without description (called from callback)"""
        var_data = self._expecting_var_desc.get(user_id)

        if not var_data:
            self.clear_var_state(user_id)
            return

        var_name, var_value = var_data
        await self._save_variable(message, var_name, var_value, "")

    async def _save_variable(self, message: Message, var_name: str, var_value: str, var_desc: str):
        """Save variable to context and show updated menu"""
        user_id = message.from_user.id

        if not self.project_service or not self.context_service:
            await message.answer("⚠️ Сервисы не инициализированы")
            self.clear_var_state(user_id)
            return

        try:
            from domain.value_objects.user_id import UserId
            uid = UserId.from_int(user_id)

            project = await self.project_service.get_current(uid)
            if not project:
                await message.answer("❌ Нет активного проекта. Используйте /change")
                self.clear_var_state(user_id)
                return

            context = await self.context_service.get_current(project.id)
            if not context:
                await message.answer("❌ Нет активного контекста")
                self.clear_var_state(user_id)
                return

            # Save the variable
            await self.context_service.set_variable(context.id, var_name, var_value, var_desc)

            # Clear state
            self.clear_var_state(user_id)

            # Show success and updated list
            variables = await self.context_service.get_variables(context.id)

            # Truncate value for display
            display_val = var_value[:20] + "..." if len(var_value) > 20 else var_value
            desc_info = f"\n📝 {var_desc}" if var_desc else ""

            await message.answer(
                f"✅ Переменная создана\n\n"
                f"{var_name} = {display_val}"
                f"{desc_info}\n\n"
                f"📋 Всего переменных: {len(variables)}",
                parse_mode=None,
                reply_markup=Keyboards.variables_menu(variables, project.name, context.name, show_back=True, back_to="menu:context")
            )

        except Exception as e:
            logger.error(f"Error saving variable: {e}")
            await message.answer(f"❌ Ошибка: {e}")
            self.clear_var_state(user_id)


def register_handlers(router: Router, handlers: MessageHandlers) -> None:
    """Register message handlers"""
    # Only match text messages when NOT in any FSM state
    # This allows FSM handlers (account setup, etc.) to take priority
    router.message.register(handlers.handle_text, F.text, StateFilter(None))


def get_message_handlers(bot_service, claude_proxy: ClaudeCodeProxyService) -> MessageHandlers:
    """Factory function to create message handlers"""
    return MessageHandlers(bot_service, claude_proxy)
