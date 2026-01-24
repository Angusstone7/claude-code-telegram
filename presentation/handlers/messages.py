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

from presentation.keyboards.keyboards import Keyboards
from presentation.handlers.streaming import StreamingHandler
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

        # Permission/Question response events
        self._permission_events: dict[int, asyncio.Event] = {}
        self._permission_responses: dict[int, bool] = {}
        self._question_events: dict[int, asyncio.Event] = {}
        self._question_responses: dict[int, str] = {}

        # Active streaming handlers
        self._streaming_handlers: dict[int, StreamingHandler] = {}

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
            await message.answer("❌ You are not authorized to use this bot.")
            return

        # Handle special input modes
        if self._expecting_answer.get(user_id):
            await self._handle_answer_input(message)
            return

        if self._expecting_path.get(user_id):
            await self._handle_path_input(message)
            return

        # Check if already running (check both backends)
        is_running = False
        if self.use_sdk and self.sdk_service:
            is_running = self.sdk_service.is_task_running(user_id)
        if not is_running:
            is_running = self.claude_proxy.is_task_running(user_id)

        if is_running:
            await message.answer(
                "⏳ A task is already running.\n\n"
                "Use the cancel button or /cancel to stop it.",
                reply_markup=Keyboards.claude_cancel(user_id)
            )
            return

        # Get working directory and session from project/context (auto-continue)
        working_dir = self.get_working_dir(user_id)
        session_id = self._continue_sessions.pop(user_id, None)
        context_id = None

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
                        logger.info(f"Auto-continuing session {session_id} for context {context.name}")

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

        # Start streaming handler
        streaming = StreamingHandler(bot, message.chat.id)
        await streaming.start(f"🤖 **Working...**\n📁 `{working_dir}`\n\n")
        self._streaming_handlers[user_id] = streaming

        # Setup HITL events
        self._permission_events[user_id] = asyncio.Event()
        self._question_events[user_id] = asyncio.Event()

        try:
            # Choose backend: SDK (preferred) or CLI (fallback)
            if self.use_sdk and self.sdk_service:
                # Use SDK with proper HITL via can_use_tool callback
                result = await self.sdk_service.run_task(
                    user_id=user_id,
                    prompt=message.text,
                    working_dir=working_dir,
                    session_id=session_id,
                    on_text=lambda text: self._on_text(user_id, text),
                    on_tool_use=lambda tool, inp: self._on_tool_use(user_id, tool, inp, message),
                    on_tool_result=lambda tid, out: self._on_tool_result(user_id, tid, out),
                    on_permission_request=lambda tool, details, inp: self._on_permission_sdk(
                        user_id, tool, details, inp, message
                    ),
                    on_question=lambda q, opts: self._on_question_sdk(user_id, q, opts, message),
                    on_thinking=lambda think: self._on_thinking(user_id, think),
                    on_error=lambda err: self._on_error(user_id, err),
                )

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
                    prompt=message.text,
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
            # Cleanup
            self._permission_events.pop(user_id, None)
            self._question_events.pop(user_id, None)
            self._streaming_handlers.pop(user_id, None)

    async def _on_text(self, user_id: int, text: str):
        """Handle streaming text output"""
        streaming = self._streaming_handlers.get(user_id)
        if streaming:
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
        """Handle tool result"""
        # Just log for now - output is streamed
        logger.debug(f"Tool result for user {user_id}: {output[:100]}...")

    async def _on_permission(self, user_id: int, tool_name: str, details: str, message: Message) -> bool:
        """Handle permission request - show approval buttons and wait"""
        session = self._user_sessions.get(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        # Send permission request message
        text = f"🔐 **Permission Request**\n\n"
        text += f"**Tool:** `{tool_name}`\n"
        if details:
            # Truncate long details
            display_details = details if len(details) < 500 else details[:500] + "..."
            text += f"**Details:**\n```\n{display_details}\n```"

        await message.answer(
            text,
            parse_mode=ParseMode.MARKDOWN,
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
                await message.answer("⏱️ Permission request timed out. Rejecting.")
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
        text = f"❓ **Question**\n\n{question}"

        if options:
            await message.answer(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
        else:
            # No options - expect text input
            self._expecting_answer[user_id] = True
            await message.answer(
                text + "\n\n✏️ **Type your answer:**",
                parse_mode=ParseMode.MARKDOWN
            )

        # Wait for response
        event = self._question_events.get(user_id)
        if event:
            event.clear()
            try:
                await asyncio.wait_for(event.wait(), timeout=300)
                answer = self._question_responses.get(user_id, "")
            except asyncio.TimeoutError:
                await message.answer("⏱️ Question timed out.")
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
        session = self._user_sessions.get(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool_name, details)

        # Send permission request message with inline buttons
        text = f"🔐 **Permission Request**\n\n"
        text += f"**Tool:** `{tool_name}`\n"
        if details:
            display_details = details if len(details) < 500 else details[:500] + "..."
            text += f"**Details:**\n```\n{display_details}\n```"

        await message.answer(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=Keyboards.claude_permission(user_id, tool_name, request_id)
        )

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
        text = f"❓ **Question**\n\n{question}"

        if options:
            await message.answer(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
        else:
            # No options - expect text input
            self._expecting_answer[user_id] = True
            await message.answer(
                text + "\n\n✏️ **Type your answer:**",
                parse_mode=ParseMode.MARKDOWN
            )

    async def _handle_result(self, user_id: int, result: TaskResult, message: Message):
        """Handle task completion"""
        session = self._user_sessions.get(user_id)
        streaming = self._streaming_handlers.get(user_id)

        if result.cancelled:
            if streaming:
                await streaming.finalize("🛑 **Task cancelled**")
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

                    # Save messages to context
                    if session and session.current_prompt:
                        await self.context_service.save_message(context_id, "user", session.current_prompt)
                    if result.output:
                        await self.context_service.save_message(context_id, "assistant", result.output[:5000])

                    logger.info(f"Saved session to context {context_id}")
                except Exception as e:
                    logger.warning(f"Error saving to context: {e}")

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
                session.fail(result.error or "Unknown error")

            if result.error:
                await message.answer(f"⚠️ **Completed with error:**\n```\n{result.error[:1000]}\n```")

    async def _handle_answer_input(self, message: Message):
        """Handle text input for question answer"""
        user_id = message.from_user.id
        self._expecting_answer[user_id] = False

        # Send answer to waiting handler
        self._question_responses[user_id] = message.text
        event = self._question_events.get(user_id)
        if event:
            event.set()

        await message.answer(f"📝 Answer: {message.text[:50]}...")

    async def _handle_path_input(self, message: Message):
        """Handle text input for path"""
        user_id = message.from_user.id
        self._expecting_path[user_id] = False

        path = message.text.strip()
        self.set_working_dir(user_id, path)

        await message.answer(
            f"📁 **Working directory set:**\n`{path}`",
            parse_mode=ParseMode.MARKDOWN
        )


def register_handlers(router: Router, handlers: MessageHandlers) -> None:
    """Register message handlers"""
    router.message.register(handlers.handle_text, F.text)


def get_message_handlers(bot_service, claude_proxy: ClaudeCodeProxyService) -> MessageHandlers:
    """Factory function to create message handlers"""
    return MessageHandlers(bot_service, claude_proxy)
