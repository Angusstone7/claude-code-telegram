"""
Claude Code Proxy Service

Provides a proxy interface to Claude Code CLI, handling:
- Subprocess management for claude CLI
- JSON result parsing
- Session management for conversation continuity

NOTE: Uses --output-format json (NOT stream-json) because stream-json
is broken in Node.js CLI v2.1.38 — hangs indefinitely with zero output.
JSON mode returns a single result after CLI completion.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events from Claude Code output"""
    TEXT = "text"
    ASSISTANT_MESSAGE = "assistant"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    PERMISSION_REQUEST = "permission_request"
    ASK_USER = "ask_user"
    RESULT = "result"
    ERROR = "error"
    SYSTEM = "system"


@dataclass
class ClaudeCodeEvent:
    """Parsed event from Claude Code stream"""
    type: EventType
    content: str = ""
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_id: Optional[str] = None
    question: Optional[str] = None
    options: Optional[list[str]] = None
    session_id: Optional[str] = None
    error: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of a Claude Code task"""
    success: bool
    output: str
    session_id: Optional[str] = None
    error: Optional[str] = None
    cancelled: bool = False


class ClaudeCodeProxyService:
    """
    Proxy service for Claude Code CLI.

    Runs Claude Code as a subprocess with --output-format json,
    parses the JSON result, and returns it to the caller.
    """

    def __init__(
        self,
        claude_path: str = "claude",
        default_working_dir: str = "/root",
        max_turns: int = 50,
        timeout_seconds: int = 600,
    ):
        self.claude_path = claude_path
        self.default_working_dir = default_working_dir
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds

        # Active processes by user_id
        self._processes: dict[int, asyncio.subprocess.Process] = {}
        self._cancel_events: dict[int, asyncio.Event] = {}

        # HITL waiting state (kept for interface compat)
        self._permission_responses: dict[int, asyncio.Queue] = {}
        self._question_responses: dict[int, asyncio.Queue] = {}

    async def check_claude_installed(self) -> tuple[bool, str]:
        """Check if Claude Code CLI is installed and accessible"""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.claude_path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                version = stdout.decode().strip()
                return True, f"Claude Code: {version}"
            else:
                return False, f"Claude Code error: {stderr.decode()}"
        except FileNotFoundError:
            return False, "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
        except Exception as e:
            return False, f"Error checking Claude Code: {e}"

    async def run_task(
        self,
        user_id: int,
        prompt: str,
        working_dir: Optional[str] = None,
        session_id: Optional[str] = None,
        yolo_mode: bool = False,
        on_text: Optional[Callable[[str], Awaitable[None]]] = None,
        on_tool_use: Optional[Callable[[str, dict], Awaitable[None]]] = None,
        on_tool_result: Optional[Callable[[str, str], Awaitable[None]]] = None,
        on_permission: Optional[Callable[[str, str], Awaitable[bool]]] = None,
        on_question: Optional[Callable[[str, list[str]], Awaitable[str]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> TaskResult:
        """
        Run a Claude Code task with the given prompt.

        Uses --output-format json which returns a single JSON object
        after CLI completes. No streaming — result appears all at once.

        Args:
            user_id: Telegram user ID (for tracking active processes)
            prompt: The task prompt to send to Claude Code
            working_dir: Working directory for the task
            session_id: Optional session ID to resume
            yolo_mode: If True, pass --dangerously-skip-permissions
            on_text: Callback for text output
            on_tool_use: Callback when a tool is being used
            on_tool_result: Callback when tool execution completes
            on_permission: Callback for permission requests
            on_question: Callback for questions
            on_error: Callback for errors

        Returns:
            TaskResult with success status and output
        """
        # Cancel any existing task for this user
        await self.cancel_task(user_id)

        # Setup state
        self._cancel_events[user_id] = asyncio.Event()
        self._permission_responses[user_id] = asyncio.Queue()
        self._question_responses[user_id] = asyncio.Queue()

        work_dir = working_dir or self.default_working_dir
        result_session_id = session_id

        # Build command — use json format (stream-json is broken in Node CLI)
        cmd = [
            self.claude_path,
            "-p", prompt,
            "--output-format", "json",
            "--max-turns", str(self.max_turns),
        ]

        if yolo_mode:
            cmd.append("--dangerously-skip-permissions")

        if session_id:
            cmd.extend(["--resume", session_id])

        logger.info(
            f"[{user_id}] CLI cmd: claude -p '<{len(prompt)}ch>' --output-format json "
            f"--max-turns {self.max_turns}"
            f"{' --dangerously-skip-permissions' if yolo_mode else ''}"
            f"{f' --resume {session_id[:16]}...' if session_id else ''}"
        )
        logger.info(f"[{user_id}] Working dir: {work_dir}")

        try:
            env = os.environ.copy()
            env["TERM"] = "dumb"
            env["NO_COLOR"] = "1"

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env=env,
            )
            self._processes[user_id] = process
            logger.info(f"[{user_id}] CLI process started, PID={process.pid}")

            # Wait for process to complete with timeout
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(f"[{user_id}] CLI timeout after {self.timeout_seconds}s")
                process.kill()
                await process.wait()
                if on_error:
                    await on_error(f"CLI task timed out after {self.timeout_seconds}s")
                return TaskResult(
                    success=False,
                    output="",
                    session_id=result_session_id,
                    error=f"CLI timed out after {self.timeout_seconds}s"
                )

            logger.info(
                f"[{user_id}] CLI finished: rc={process.returncode}, "
                f"stdout={len(stdout_data)}b, stderr={len(stderr_data)}b"
            )

            if stderr_data:
                stderr_text = stderr_data.decode('utf-8', errors='replace').strip()
                if stderr_text:
                    logger.warning(f"[{user_id}] CLI STDERR: {stderr_text[:500]}")

            # Check if cancelled while running
            if self._cancel_events[user_id].is_set():
                return TaskResult(
                    success=False,
                    output="",
                    session_id=result_session_id,
                    cancelled=True
                )

            # Parse output
            stdout_text = stdout_data.decode('utf-8', errors='replace').strip()

            if not stdout_text:
                error_msg = f"CLI returned empty output (rc={process.returncode})"
                logger.error(f"[{user_id}] {error_msg}")
                if on_error:
                    await on_error(error_msg)
                return TaskResult(
                    success=False,
                    output="",
                    session_id=result_session_id,
                    error=error_msg
                )

            # Try to parse as JSON result
            try:
                data = json.loads(stdout_text)
            except json.JSONDecodeError:
                # Plain text output (text format fallback)
                logger.info(f"[{user_id}] CLI output is plain text ({len(stdout_text)}ch)")
                if on_text:
                    await on_text(stdout_text)
                return TaskResult(
                    success=process.returncode == 0,
                    output=stdout_text,
                    session_id=result_session_id,
                    error=None if process.returncode == 0 else f"Exit code {process.returncode}"
                )

            # Extract from JSON result
            result_text = data.get("result", "") or ""
            result_session_id = data.get("session_id") or result_session_id
            is_error = data.get("is_error", False)
            cost_usd = data.get("total_cost_usd", 0)
            num_turns = data.get("num_turns", 0)
            duration_ms = data.get("duration_ms", 0)

            logger.info(
                f"[{user_id}] CLI result: error={is_error}, "
                f"text={len(result_text)}ch, sid={result_session_id}, "
                f"turns={num_turns}, cost=${cost_usd:.4f}, {duration_ms}ms"
            )

            # Send result text to callback
            if result_text and on_text:
                try:
                    await on_text(result_text)
                except Exception as e:
                    logger.error(f"[{user_id}] on_text callback error: {e}")

            # Determine error
            error_msg = None
            if is_error:
                error_msg = result_text or "CLI returned an error"
                if on_error:
                    await on_error(error_msg)
            elif process.returncode != 0:
                if process.returncode == 143:
                    error_msg = "Process was terminated (SIGTERM)"
                elif process.returncode == 137:
                    error_msg = "Process was killed (SIGKILL)"
                else:
                    error_msg = f"Exit code {process.returncode}"

            return TaskResult(
                success=process.returncode == 0 and not is_error,
                output=result_text,
                session_id=result_session_id,
                error=error_msg
            )

        except Exception as e:
            logger.error(f"[{user_id}] CLI error: {e}", exc_info=True)
            if on_error:
                await on_error(str(e))
            return TaskResult(
                success=False,
                output="",
                session_id=result_session_id,
                error=str(e)
            )
        finally:
            self._processes.pop(user_id, None)
            self._cancel_events.pop(user_id, None)
            self._permission_responses.pop(user_id, None)
            self._question_responses.pop(user_id, None)

    def _parse_event(self, line: str) -> Optional[ClaudeCodeEvent]:
        """Parse a JSON line from Claude Code stream output.

        Kept for backward compatibility with tests and potential future
        stream-json support. Currently unused by run_task which uses json mode.
        """
        try:
            data = json.loads(line)
            event_type = data.get("type", "")

            if event_type == "assistant":
                message = data.get("message", {})
                content_blocks = message.get("content", [])

                text_content = ""
                first_tool_use = None
                for block in content_blocks:
                    block_type = block.get("type", "")
                    if block_type == "text":
                        text_content += block.get("text", "")
                    elif block_type == "tool_use" and first_tool_use is None:
                        first_tool_use = block

                if first_tool_use:
                    return ClaudeCodeEvent(
                        type=EventType.TOOL_USE,
                        tool_name=first_tool_use.get("name"),
                        tool_input=first_tool_use.get("input", {}),
                        tool_id=first_tool_use.get("id"),
                        raw=data
                    )

                if text_content:
                    return ClaudeCodeEvent(
                        type=EventType.ASSISTANT_MESSAGE,
                        content=text_content,
                        session_id=data.get("session_id"),
                        raw=data
                    )

            elif event_type == "content_block_start":
                content_block = data.get("content_block", {})
                if content_block.get("type") == "tool_use":
                    return ClaudeCodeEvent(
                        type=EventType.TOOL_USE,
                        tool_name=content_block.get("name"),
                        tool_input=content_block.get("input", {}),
                        tool_id=content_block.get("id"),
                        raw=data
                    )

            elif event_type == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    return ClaudeCodeEvent(
                        type=EventType.TEXT,
                        content=delta.get("text", ""),
                        raw=data
                    )

            elif event_type == "tool_use":
                return ClaudeCodeEvent(
                    type=EventType.TOOL_USE,
                    tool_name=data.get("name") or data.get("tool"),
                    tool_input=data.get("input", {}),
                    tool_id=data.get("id"),
                    raw=data
                )

            elif event_type in ("tool_result", "user"):
                msg = data.get("message", {})
                content_blocks = msg.get("content", data.get("content", ""))
                tool_id = data.get("tool_use_id") or data.get("id")
                result_content = ""

                if isinstance(content_blocks, list):
                    text_parts = []
                    for block in content_blocks:
                        if isinstance(block, dict):
                            if block.get("type") == "tool_result":
                                text_parts.append(str(block.get("content", "")))
                                if not tool_id:
                                    tool_id = block.get("tool_use_id")
                            elif block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                    result_content = "\n".join(text_parts)
                elif isinstance(content_blocks, str):
                    result_content = content_blocks

                if not result_content:
                    result_content = str(data.get("tool_use_result", ""))

                return ClaudeCodeEvent(
                    type=EventType.TOOL_RESULT,
                    tool_id=tool_id,
                    content=str(result_content)[:500],
                    raw=data
                )

            elif event_type in ("result", "message_stop"):
                result_text = data.get("result", "") or data.get("content", "")
                return ClaudeCodeEvent(
                    type=EventType.RESULT,
                    content=result_text,
                    session_id=data.get("session_id"),
                    raw=data
                )

            elif event_type == "error":
                return ClaudeCodeEvent(
                    type=EventType.ERROR,
                    error=(
                        data.get("error", {}).get("message")
                        if isinstance(data.get("error"), dict)
                        else data.get("error") or data.get("message")
                    ),
                    raw=data
                )

            elif event_type == "system" or (event_type and "system" in event_type.lower()):
                return ClaudeCodeEvent(
                    type=EventType.SYSTEM,
                    content=data.get("message") or data.get("content", ""),
                    raw=data
                )

            elif event_type in ("input_request", "input"):
                input_type = data.get("input_type", "")
                if input_type == "permission" or "permission" in str(data).lower():
                    return ClaudeCodeEvent(
                        type=EventType.PERMISSION_REQUEST,
                        tool_name=data.get("tool") or data.get("tool_name", ""),
                        content=data.get("description") or data.get("command") or json.dumps(data),
                        raw=data
                    )
                else:
                    return ClaudeCodeEvent(
                        type=EventType.ASK_USER,
                        question=data.get("question") or data.get("message") or data.get("prompt", ""),
                        options=data.get("options", []),
                        raw=data
                    )

            elif event_type in ("message_start", "content_block_stop", "message_delta", "ping"):
                return None

            return None

        except json.JSONDecodeError:
            return None

    async def _handle_event(
        self,
        user_id: int,
        event: ClaudeCodeEvent,
        on_text: Optional[Callable],
        on_tool_use: Optional[Callable],
        on_tool_result: Optional[Callable],
        on_permission: Optional[Callable],
        on_question: Optional[Callable],
        on_error: Optional[Callable],
        output_buffer: list[str],
    ):
        """Handle a parsed event from Claude Code (kept for tests/compat)"""

        if event.type in (EventType.TEXT, EventType.ASSISTANT_MESSAGE):
            if event.content:
                output_buffer.append(event.content)
                if on_text:
                    await on_text(event.content)

        elif event.type == EventType.TOOL_USE:
            if on_tool_use:
                await on_tool_use(event.tool_name, event.tool_input or {})

        elif event.type == EventType.TOOL_RESULT:
            if on_tool_result:
                await on_tool_result(event.tool_id, event.content)

        elif event.type == EventType.PERMISSION_REQUEST:
            if on_permission:
                approved = await on_permission(event.tool_name, event.content)
                process = self._processes.get(user_id)
                if process and process.stdin:
                    response = "y\n" if approved else "n\n"
                    process.stdin.write(response.encode())
                    await process.stdin.drain()

        elif event.type == EventType.ASK_USER:
            if on_question:
                answer = await on_question(event.question, event.options or [])
                process = self._processes.get(user_id)
                if process and process.stdin:
                    process.stdin.write(f"{answer}\n".encode())
                    await process.stdin.drain()

        elif event.type == EventType.ERROR:
            logger.error(f"Claude Code error: {event.error}")
            if on_error:
                await on_error(event.error)

        elif event.type == EventType.RESULT:
            if event.content:
                output_buffer.append(event.content)

    async def cancel_task(self, user_id: int) -> bool:
        """Cancel the active task for a user"""
        cancel_event = self._cancel_events.get(user_id)
        if cancel_event:
            cancel_event.set()

        process = self._processes.get(user_id)
        if process:
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
                return True
            except Exception as e:
                logger.error(f"Error cancelling task: {e}")
        return False

    def is_task_running(self, user_id: int) -> bool:
        """Check if a task is currently running for a user"""
        process = self._processes.get(user_id)
        return process is not None and process.returncode is None

    async def respond_to_permission(self, user_id: int, approved: bool):
        """Respond to a pending permission request"""
        queue = self._permission_responses.get(user_id)
        if queue:
            await queue.put(approved)

    async def respond_to_question(self, user_id: int, answer: str):
        """Respond to a pending question"""
        queue = self._question_responses.get(user_id)
        if queue:
            await queue.put(answer)
