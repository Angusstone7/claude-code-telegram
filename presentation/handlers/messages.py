"""
Message Handlers for Claude Code Proxy

Handles user messages and forwards them to Claude Code CLI,
managing streaming output, HITL interactions, and session state.
"""

import asyncio
import logging
import uuid
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.enums import ParseMode

from presentation.keyboards.keyboards import Keyboards
from presentation.handlers.streaming import StreamingHandler
from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService, TaskResult
from domain.entities.claude_code_session import ClaudeCodeSession, SessionStatus

logger = logging.getLogger(__name__)
router = Router()


class MessageHandlers:
    """Bot message handlers for Claude Code proxy"""

    def __init__(
        self,
        bot_service,
        claude_proxy: ClaudeCodeProxyService,
        default_working_dir: str = "/root"
    ):
        self.bot_service = bot_service
        self.claude_proxy = claude_proxy
        self.default_working_dir = default_working_dir

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

    async def handle_permission_response(self, user_id: int, approved: bool):
        """Handle permission response from callback"""
        self._permission_responses[user_id] = approved
        event = self._permission_events.get(user_id)
        if event:
            event.set()

    async def handle_question_response(self, user_id: int, answer: str):
        """Handle question response from callback"""
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

        # Check if already running
        if self.claude_proxy.is_task_running(user_id):
            await message.answer(
                "⏳ A task is already running.\n\n"
                "Use the cancel button or /cancel to stop it.",
                reply_markup=Keyboards.claude_cancel(user_id)
            )
            return

        # Get working directory and session
        working_dir = self.get_working_dir(user_id)
        session_id = self._continue_sessions.pop(user_id, None)

        # Create session state
        session = ClaudeCodeSession(
            user_id=user_id,
            working_dir=working_dir,
            claude_session_id=session_id
        )
        session.start_task(message.text)
        self._user_sessions[user_id] = session

        # Start streaming handler
        streaming = StreamingHandler(bot, message.chat.id)
        await streaming.start(f"🤖 **Working...**\n📁 `{working_dir}`\n\n")
        self._streaming_handlers[user_id] = streaming

        # Setup HITL events
        self._permission_events[user_id] = asyncio.Event()
        self._question_events[user_id] = asyncio.Event()

        try:
            # Run Claude Code task
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

            # Handle result
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

            # Offer to continue if we have a session
            if result.session_id:
                await message.answer(
                    "✅ **Task completed**\n\nYou can continue this conversation or start fresh.",
                    reply_markup=Keyboards.claude_continue(user_id, result.session_id)
                )
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
