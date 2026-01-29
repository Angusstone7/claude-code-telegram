"""
AI Request Handler

Handles the full AI request flow including:
- Context enrichment (project/session/variables)
- Streaming handler setup
- SDK service integration with all callbacks
- Result processing and cleanup

This encapsulates the ~300 lines of SDK integration logic
from the original MessageHandlers.handle_text method.
"""

import logging
from typing import Optional, TYPE_CHECKING
from aiogram.types import Message

from .base import BaseMessageHandler
from presentation.keyboards.keyboards import Keyboards
from presentation.handlers.streaming.handler import StreamingHandler
from presentation.handlers.streaming.trackers import HeartbeatTracker

if TYPE_CHECKING:
    from infrastructure.claude_code.sdk_service import ClaudeAgentSDKService
    from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService

logger = logging.getLogger(__name__)


class ClaudeCodeSession:
    """Represents a Claude Code session"""
    def __init__(self, user_id: int, working_dir: str, claude_session_id: Optional[str] = None):
        self.user_id = user_id
        self.working_dir = working_dir
        self.claude_session_id = claude_session_id
        self.context_id: Optional[str] = None
        self._original_working_dir: Optional[str] = None
        self._task_prompt: Optional[str] = None

    def start_task(self, prompt: str):
        """Mark task as started with the given prompt"""
        self._task_prompt = prompt


class TaskResult:
    """Result from Claude Code execution"""
    def __init__(self, success: bool, output: str, session_id: Optional[str] = None,
                 error: Optional[str] = None, cancelled: bool = False):
        self.success = success
        self.output = output
        self.session_id = session_id
        self.error = error
        self.cancelled = cancelled


class AIRequestHandler(BaseMessageHandler):
    """
    Handles AI request processing with full SDK integration.

    Responsibilities:
    - Get project/context enrichment
    - Create Claude Code session
    - Setup streaming handler
    - Setup HITL events and heartbeat
    - Call SDK service with all callbacks
    - Process results and cleanup
    """

    def __init__(
        self,
        bot_service,
        user_state,
        hitl_manager,
        file_context_manager,
        variable_manager,
        plan_manager,
        sdk_service: Optional["ClaudeAgentSDKService"] = None,
        claude_proxy: Optional["ClaudeCodeProxyService"] = None,
        project_service=None,
        context_service=None,
    ):
        super().__init__(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )
        self.sdk_service = sdk_service
        self.claude_proxy = claude_proxy
        self.project_service = project_service
        self.context_service = context_service

        # Determine which backend to use
        self.use_sdk = sdk_service is not None
        self.log_info(0, f"AIRequestHandler initialized with SDK: {self.use_sdk}")

    async def process_ai_request(
        self,
        message: Message,
        prompt_override: Optional[str] = None,
        force_new_session: bool = False,
    ) -> None:
        """
        Process AI request through full SDK flow.

        Args:
            message: Telegram message
            prompt_override: Override prompt (e.g., from file context or batching)
            force_new_session: Force new session instead of continuing
        """
        user_id = message.from_user.id

        # Import bot here to avoid circular dependency
        from main import bot

        # === GET CONTEXT ===
        working_dir = self.get_working_dir(user_id)
        session_id = None if force_new_session else self.user_state.get_continue_session_id(user_id)
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
                        self.log_info(
                            user_id,
                            f"Auto-continue: loaded session {session_id[:16]}... "
                            f"from context '{context.name}' (messages: {context.message_count})"
                        )

                    original_prompt = prompt_override if prompt_override else message.text
                    new_prompt = await self.context_service.get_enriched_prompt(
                        context_id, original_prompt, user_id=uid
                    )
                    if new_prompt != original_prompt:
                        enriched_prompt = new_prompt

                    self.user_state.set_working_dir(user_id, working_dir)

            except Exception as e:
                logger.warning(f"Error getting project/context: {e}")

        # === CREATE SESSION ===
        session = ClaudeCodeSession(
            user_id=user_id,
            working_dir=working_dir,
            claude_session_id=session_id
        )
        session.start_task(enriched_prompt)
        self.user_state.set_claude_session(user_id, session)

        if context_id:
            session.context_id = context_id
        session._original_working_dir = working_dir

        # === START STREAMING ===
        cancel_keyboard = Keyboards.claude_cancel(user_id)
        streaming = StreamingHandler(bot, message.chat.id, reply_markup=cancel_keyboard)

        yolo_indicator = " ⚡" if self.user_state.is_yolo_mode(user_id) else ""
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
        self.user_state.set_streaming_handler(user_id, streaming)

        # === SETUP HITL ===
        self.hitl_manager.create_permission_event(user_id)
        self.hitl_manager.create_question_event(user_id)

        heartbeat = HeartbeatTracker(streaming, interval=2.0)
        self.user_state.set_heartbeat(user_id, heartbeat)
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
                    streaming_instance = self.user_state.get_streaming_handler(user_id)
                    if streaming_instance:
                        cost_str = f"${result.total_cost_usd:.4f}"
                        info_parts = [cost_str]

                        # Add real token usage if available
                        if result.usage:
                            input_tokens = result.usage.get("input_tokens", 0)
                            cache_read = result.usage.get("cache_read_input_tokens", 0)
                            cache_create = result.usage.get("cache_creation_input_tokens", 0)
                            output_tokens = result.usage.get("output_tokens", 0)

                            total_input = input_tokens + cache_read + cache_create
                            total_all = total_input + output_tokens

                            if total_all > 0:
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

                        streaming_instance.set_completion_info(" | ".join(info_parts))

                cli_result = TaskResult(
                    success=result.success,
                    output=result.output,
                    session_id=result.session_id,
                    error=result.error,
                    cancelled=result.cancelled,
                )
                await self._handle_result(user_id, cli_result, message)
            else:
                # CLI fallback
                result = await self.claude_proxy.run_task(
                    user_id=user_id,
                    prompt=enriched_prompt,
                    working_dir=working_dir,
                    session_id=session_id,
                )
                await self._handle_result(user_id, result, message)

        finally:
            # Cleanup
            await self._cleanup_after_task(user_id)

    # === SDK Callbacks ===

    def _on_text(self, user_id: int, text: str):
        """Handle text output from SDK"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.append_text(text)

    def _on_tool_use(self, user_id: int, tool: str, input_data: dict, message: Message):
        """Handle tool use notification"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.add_tool_use(tool, input_data)

    def _on_tool_result(self, user_id: int, tool_id: str, output: str):
        """Handle tool result"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.add_tool_result(tool_id, output)

    def _on_permission_sdk(self, user_id: int, tool: str, details: str, input_data: dict, message: Message):
        """Handle permission request from SDK"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.pause()

        self.hitl_manager.request_permission(user_id, tool, details, input_data, message)

    def _on_permission_completed(self, user_id: int, approved: bool):
        """Handle permission completion"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.resume()

    def _on_question_sdk(self, user_id: int, question: str, options: list, message: Message):
        """Handle question from SDK"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.pause()

        self.hitl_manager.request_question(user_id, question, options, message)

    def _on_question_completed(self, user_id: int, answer: str):
        """Handle question completion"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.resume()

    def _on_plan_request(self, user_id: int, plan_file: str, input_data: dict, message: Message):
        """Handle plan approval request"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.pause()

        self.plans.request_approval(user_id, plan_file, input_data, message)

    def _on_thinking(self, user_id: int, thinking: str):
        """Handle thinking output"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.set_thinking(thinking)

    def _on_error(self, user_id: int, error: str):
        """Handle error"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            streaming.set_error(error)

    async def _handle_result(self, user_id: int, result: TaskResult, message: Message):
        """Handle task completion result"""
        streaming = self.user_state.get_streaming_handler(user_id)
        session = self.user_state.get_claude_session(user_id)

        if streaming:
            await streaming.finalize()

        # Save session ID to context
        if session and session.context_id and result.session_id:
            try:
                await self.context_service.update_claude_session_id(
                    session.context_id,
                    result.session_id
                )
            except Exception as e:
                logger.warning(f"Failed to save session ID: {e}")

        # Set continue session if successful
        if result.success and result.session_id:
            self.user_state.set_continue_session_id(user_id, result.session_id)

    async def _cleanup_after_task(self, user_id: int):
        """Cleanup after task completes"""
        # Stop heartbeat
        heartbeat = self.user_state.get_heartbeat(user_id)
        if heartbeat:
            await heartbeat.stop()
            self.user_state.clear_heartbeat(user_id)

        # Clear HITL events
        self.hitl_manager.cleanup(user_id)

        # Clear session (but keep continue_session_id)
        self.user_state.clear_claude_session(user_id)
