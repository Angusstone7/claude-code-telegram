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

    def is_task_running(self, user_id: int) -> bool:
        """Check if a task is currently running for this user"""
        is_running = False
        if self.use_sdk and self.sdk_service:
            is_running = self.sdk_service.is_task_running(user_id)
        if not is_running and self.claude_proxy:
            is_running = self.claude_proxy.is_task_running(user_id)
        return is_running

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
        bot = message.bot  # Get bot from message

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
        # CRITICAL FIX: Explicitly get and pass coordinator
        from presentation.handlers.state.update_coordinator import get_coordinator

        coordinator = get_coordinator()
        if coordinator is None:
            logger.error(f"[{user_id}] CRITICAL: MessageUpdateCoordinator not initialized!")
        else:
            logger.info(f"[{user_id}] StreamingHandler using coordinator: {id(coordinator)}")

        cancel_keyboard = Keyboards.claude_cancel(user_id)
        streaming = StreamingHandler(
            bot,
            message.chat.id,
            reply_markup=cancel_keyboard,
            coordinator=coordinator  # Pass explicitly
        )

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

    # === SDK Callbacks (copied from legacy messages.py) ===

    async def _on_text(self, user_id: int, text: str):
        """Handle streaming text output"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            await streaming.append(text)

        # Update heartbeat
        heartbeat = self.user_state.get_heartbeat(user_id)
        if heartbeat:
            heartbeat.set_action("thinking")

    async def _on_tool_use(self, user_id: int, tool: str, input_data: dict, message: Message):
        """Handle tool use notification"""
        streaming = self.user_state.get_streaming_handler(user_id)
        heartbeat = self.user_state.get_heartbeat(user_id)

        # Update heartbeat with current action
        if heartbeat:
            tool_lower = tool.lower()
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
                detail = input_data.get("file_path", "")
                if detail:
                    detail = detail.split("/")[-1]  # Just filename
            elif tool_lower == "bash":
                cmd = input_data.get("command", "")
                detail = cmd[:30] if cmd else ""
            elif tool_lower in ("glob", "grep"):
                detail = input_data.get("pattern", "")[:30]

            heartbeat.set_action(action, detail)

        # Track file changes
        if streaming and tool.lower() in ("edit", "write", "bash"):
            streaming.track_file_change(tool, input_data)

    async def _on_tool_result(self, user_id: int, tool_id: str, output: str):
        """Handle tool result"""
        streaming = self.user_state.get_streaming_handler(user_id)

        if streaming and output:
            await streaming.show_tool_result(output, success=True)

        # Reset heartbeat
        heartbeat = self.user_state.get_heartbeat(user_id)
        if heartbeat:
            heartbeat.set_action("analyzing")

    async def _on_permission_sdk(self, user_id: int, tool: str, details: str, input_data: dict, message: Message):
        """Handle permission request from SDK"""
        import html
        import uuid
        from presentation.keyboards.keyboards import Keyboards

        # YOLO mode - auto-approve
        if self.user_state.is_yolo_mode(user_id):
            streaming = self.user_state.get_streaming_handler(user_id)
            if streaming:
                truncated = details[:100] + "..." if len(details) > 100 else details
                await streaming.append(f"\n**Авто-одобрено:** `{tool}`\n```\n{truncated}\n```\n")

            if self.sdk_service:
                await self.sdk_service.respond_to_permission(user_id, True)
            return

        # Normal mode - ask for permission
        session = self.user_state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_approval(request_id, tool, details)

        text = f"<b>Запрос разрешения</b>\n\n"
        text += f"<b>Инструмент:</b> <code>{html.escape(tool)}</code>\n"
        if details:
            display_details = details if len(details) < 500 else details[:500] + "..."
            text += f"<b>Детали:</b>\n<pre>{html.escape(display_details)}</pre>"

        perm_msg = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.claude_permission(user_id, tool, request_id)
        )
        self.hitl_manager.set_permission_context(user_id, request_id, tool, details, perm_msg)
        self.log_info(user_id, f"Permission request sent: {tool}")

    async def _on_permission_completed(self, user_id: int, approved: bool):
        """Handle permission completion"""
        # SDK handles this internally
        pass

    async def _on_question_sdk(self, user_id: int, question: str, options: list, message: Message):
        """Handle question from SDK"""
        import html
        import uuid
        from presentation.keyboards.keyboards import Keyboards

        session = self.user_state.get_claude_session(user_id)
        request_id = str(uuid.uuid4())[:8]

        if session:
            session.set_waiting_answer(request_id, question, options)

        self.hitl_manager.set_question_context(user_id, request_id, question, options)

        text = f"<b>Вопрос</b>\n\n{html.escape(question)}"

        if options:
            q_msg = await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=Keyboards.claude_question(user_id, options, request_id)
            )
            self.hitl_manager.set_question_context(user_id, request_id, question, options, q_msg)
        else:
            self.hitl_manager.set_expecting_answer(user_id, True)
            q_msg = await message.answer(f"<b>Вопрос</b>\n\n{html.escape(question)}\n\nВведите ваш ответ:", parse_mode="HTML")
            self.hitl_manager.set_question_context(user_id, request_id, question, options, q_msg)

        self.log_info(user_id, f"Question sent: {question[:50]}...")

    async def _on_question_completed(self, user_id: int, answer: str):
        """Handle question completion"""
        # SDK handles this internally
        pass

    async def _on_plan_request(self, user_id: int, plan_file: str, input_data: dict, message: Message):
        """Handle plan approval request from SDK (ExitPlanMode)"""
        import html
        import uuid
        import os
        from presentation.keyboards.keyboards import Keyboards

        self.log_info(user_id, f"Plan request: plan_file={plan_file}")
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
                self.log_error(user_id, f"Error reading plan file: {e}")

        if not plan_content:
            plan_content = input_data.get("planContent", "")

        if plan_content:
            if len(plan_content) > 3500:
                plan_content = plan_content[:3500] + "\n\n... (план сокращён)"
            escaped_content = html.escape(plan_content)
            text = f"<b>📋 План готов к выполнению</b>\n\n<pre>{escaped_content}</pre>"
        else:
            text = "<b>📋 План готов к выполнению</b>\n\n<i>Содержимое плана недоступно</i>"

        plan_msg = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.plan_approval(user_id, request_id)
        )

        self.plan_manager.set_context(user_id, request_id, plan_file, plan_content, plan_msg)
        self.log_info(user_id, f"Plan approval requested, file: {plan_file}")

    async def _on_thinking(self, user_id: int, thinking: str):
        """Handle thinking output (extended thinking)"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming and thinking:
            # Show thinking in italic
            await streaming.append(f"\n*{thinking[:200]}...*\n" if len(thinking) > 200 else f"\n*{thinking}*\n")

    async def _on_error(self, user_id: int, error: str):
        """Handle error"""
        streaming = self.user_state.get_streaming_handler(user_id)
        if streaming:
            await streaming.send_error(error)

        session = self.user_state.get_claude_session(user_id)
        if session:
            session.fail(error)

    async def _handle_result(self, user_id: int, result: TaskResult, message: Message):
        """Handle task completion result"""
        streaming = self.user_state.get_streaming_handler(user_id)
        session = self.user_state.get_claude_session(user_id)

        # Handle cancellation
        if result.cancelled:
            if streaming:
                await streaming.finalize("**Задача отменена**")
                # Show file changes even on cancel (user might want to see what was done)
                await streaming.show_file_changes_summary()
            if session:
                session.cancel()
            return

        # Handle success
        if result.success:
            if streaming:
                # Show completion status (✅)
                await streaming.send_completion(success=True)
                # Show file changes summary (Cursor-style)
                await streaming.show_file_changes_summary()
                # Finalize the stream
                await streaming.finalize()

            # Mark session as complete
            if session:
                session.complete(result.session_id)

            # Save session ID to context
            if session and session.context_id and result.session_id:
                try:
                    await self.context_service.set_claude_session_id(
                        session.context_id,
                        result.session_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to save session ID: {e}")

            # Set continue session if successful
            if result.session_id:
                self.user_state.set_continue_session_id(user_id, result.session_id)

        # Handle failure
        else:
            if streaming:
                # Show completion status (⚠️)
                await streaming.send_completion(success=False)
                # Show file changes even on error (user might want to see what was done)
                await streaming.show_file_changes_summary()
                # Finalize the stream
                await streaming.finalize()

            # Mark session as failed
            if session:
                session.fail(result.error or "Unknown error")

    async def _cleanup_after_task(self, user_id: int):
        """Cleanup after task completes"""
        # Stop heartbeat
        heartbeat = self.user_state.get_heartbeat(user_id)
        if heartbeat:
            await heartbeat.stop()
            self.user_state.remove_heartbeat(user_id)

        # Clear HITL events
        self.hitl_manager.cleanup(user_id)

        # Remove streaming handler
        self.user_state.remove_streaming_handler(user_id)

        # NOTE: Session is NOT cleared here - it stays for potential continuation
        # Only cleared when force_new_session=True or user explicitly resets
