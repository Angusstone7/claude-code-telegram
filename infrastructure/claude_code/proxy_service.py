"""
Claude Code Proxy Service

Provides a proxy interface to Claude Code CLI, handling:
- Subprocess management for claude CLI
- Stream-JSON parsing for real-time output
- HITL (Human-in-the-Loop) event handling
- Session management for conversation continuity
"""

import asyncio
import json
import logging
import os
import signal
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events from Claude Code stream-json output"""
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

    Handles running Claude Code as a subprocess with stream-json output,
    parsing events, and forwarding them to registered callbacks for
    Telegram integration.
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

        # HITL waiting state
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
        on_text: Optional[Callable[[str], Awaitable[None]]] = None,
        on_tool_use: Optional[Callable[[str, dict], Awaitable[None]]] = None,
        on_tool_result: Optional[Callable[[str, str], Awaitable[None]]] = None,
        on_permission: Optional[Callable[[str, str], Awaitable[bool]]] = None,
        on_question: Optional[Callable[[str, list[str]], Awaitable[str]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> TaskResult:
        """
        Run a Claude Code task with the given prompt.

        Args:
            user_id: Telegram user ID (for tracking active processes)
            prompt: The task prompt to send to Claude Code
            working_dir: Working directory for the task
            session_id: Optional session ID to resume
            on_text: Callback for text output (streaming)
            on_tool_use: Callback when a tool is being used
            on_tool_result: Callback when tool execution completes
            on_permission: Callback for permission requests, return True to approve
            on_question: Callback for questions, return the answer string
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

        # Build command
        # Note: working directory is set via subprocess cwd parameter, not CLI flag
        # --dangerously-skip-permissions allows non-interactive operation
        cmd = [
            self.claude_path,
            "-p", prompt,
            "--output-format", "stream-json",
            "--max-turns", str(self.max_turns),
            "--dangerously-skip-permissions",
        ]

        if session_id:
            cmd.extend(["--resume", session_id])

        logger.info(f"[{user_id}] Full command: {' '.join(cmd)}")
        logger.info(f"[{user_id}] Working dir: {work_dir}")

        output_buffer = []
        result_session_id = session_id

        try:
            # Start process with inherited environment
            # ANTHROPIC_API_KEY should be set in container environment
            env = os.environ.copy()
            logger.info(f"Starting with API key present: {'ANTHROPIC_API_KEY' in env}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env=env,
            )
            self._processes[user_id] = process
            logger.info(f"[{user_id}] Process started with PID: {process.pid}")

            # Process output stream
            async def read_stdout():
                nonlocal result_session_id
                logger.info(f"[{user_id}] Starting stdout reader")

                while True:
                    # Check for cancellation
                    if self._cancel_events[user_id].is_set():
                        logger.info(f"[{user_id}] Stdout reader cancelled")
                        return

                    line = await process.stdout.readline()
                    if not line:
                        logger.info(f"[{user_id}] Stdout EOF")
                        break

                    try:
                        line_str = line.decode('utf-8').strip()
                        if not line_str:
                            continue

                        logger.info(f"[{user_id}] STDOUT: {line_str[:300]}")

                        event = self._parse_event(line_str)
                        logger.info(f"[{user_id}] Parsed: {event.type if event else 'None'}")
                        if event:
                            await self._handle_event(
                                user_id, event,
                                on_text, on_tool_use, on_tool_result,
                                on_permission, on_question, on_error,
                                output_buffer
                            )

                            # Extract session_id from result
                            if event.type == EventType.RESULT and event.session_id:
                                result_session_id = event.session_id

                    except json.JSONDecodeError:
                        # Non-JSON output, treat as text
                        logger.info(f"[{user_id}] Non-JSON: {line_str[:100]}")
                        if on_text and line_str:
                            output_buffer.append(line_str)
                            await on_text(line_str)
                    except Exception as e:
                        logger.error(f"[{user_id}] Error processing line: {e}")

            # Stderr reader - runs concurrently
            async def read_stderr():
                logger.info(f"[{user_id}] Starting stderr reader")
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        logger.info(f"[{user_id}] Stderr EOF")
                        break
                    line_str = line.decode('utf-8').strip()
                    if line_str:
                        logger.warning(f"[{user_id}] STDERR: {line_str}")

            # Run both readers concurrently with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(read_stdout(), read_stderr()),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(f"Task timeout for user {user_id}")
                if on_error:
                    await on_error("Task timed out")
                return TaskResult(
                    success=False,
                    output="\n".join(output_buffer),
                    session_id=result_session_id,
                    error="Task timed out"
                )

            # Wait for process to finish
            await process.wait()
            logger.info(f"Claude Code process finished with returncode {process.returncode}")

            # Check if cancelled
            if self._cancel_events[user_id].is_set():
                return TaskResult(
                    success=False,
                    output="\n".join(output_buffer),
                    session_id=result_session_id,
                    cancelled=True
                )

            # Read any stderr
            stderr = await process.stderr.read()
            error_msg = stderr.decode('utf-8') if stderr else ""
            if error_msg:
                logger.info(f"Claude Code stderr: {error_msg[:500]}")
            if error_msg and process.returncode != 0:
                logger.error(f"Claude Code error: {error_msg}")
                if on_error:
                    await on_error(error_msg)

            return TaskResult(
                success=process.returncode == 0,
                output="\n".join(output_buffer),
                session_id=result_session_id,
                error=error_msg if error_msg and process.returncode != 0 else None
            )

        except Exception as e:
            logger.error(f"Error running Claude Code: {e}")
            if on_error:
                await on_error(str(e))
            return TaskResult(
                success=False,
                output="\n".join(output_buffer),
                error=str(e)
            )
        finally:
            # Cleanup
            self._processes.pop(user_id, None)
            self._cancel_events.pop(user_id, None)
            self._permission_responses.pop(user_id, None)
            self._question_responses.pop(user_id, None)

    def _parse_event(self, line: str) -> Optional[ClaudeCodeEvent]:
        """Parse a JSON line from Claude Code stream output"""
        try:
            data = json.loads(line)

            # Determine event type
            event_type = data.get("type", "")

            if event_type == "assistant":
                # Assistant message with content blocks
                content = ""
                for block in data.get("message", {}).get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")
                return ClaudeCodeEvent(
                    type=EventType.ASSISTANT_MESSAGE,
                    content=content,
                    raw=data
                )

            elif event_type == "content_block_delta":
                # Streaming text delta
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

            elif event_type == "tool_result":
                return ClaudeCodeEvent(
                    type=EventType.TOOL_RESULT,
                    tool_id=data.get("tool_use_id"),
                    content=data.get("content", ""),
                    raw=data
                )

            elif event_type == "permission_request" or "permission" in str(data).lower():
                # Permission request for tool execution
                return ClaudeCodeEvent(
                    type=EventType.PERMISSION_REQUEST,
                    tool_name=data.get("tool") or data.get("name"),
                    content=data.get("command") or data.get("details") or json.dumps(data.get("input", {})),
                    raw=data
                )

            elif event_type == "ask_user" or event_type == "user_question":
                return ClaudeCodeEvent(
                    type=EventType.ASK_USER,
                    question=data.get("question") or data.get("message"),
                    options=data.get("options", []),
                    raw=data
                )

            elif event_type == "result" or event_type == "message_stop":
                return ClaudeCodeEvent(
                    type=EventType.RESULT,
                    content=data.get("content", ""),
                    session_id=data.get("session_id"),
                    raw=data
                )

            elif event_type == "error":
                return ClaudeCodeEvent(
                    type=EventType.ERROR,
                    error=data.get("error") or data.get("message"),
                    raw=data
                )

            elif "system" in event_type.lower():
                return ClaudeCodeEvent(
                    type=EventType.SYSTEM,
                    content=data.get("message") or data.get("content", ""),
                    raw=data
                )

            # Unknown event type - log and return as text if has content
            if data.get("text") or data.get("content"):
                return ClaudeCodeEvent(
                    type=EventType.TEXT,
                    content=data.get("text") or data.get("content", ""),
                    raw=data
                )

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
        """Handle a parsed event from Claude Code"""

        if event.type == EventType.TEXT:
            if event.content:
                output_buffer.append(event.content)
                if on_text:
                    await on_text(event.content)

        elif event.type == EventType.ASSISTANT_MESSAGE:
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
                # Request approval via callback
                approved = await on_permission(event.tool_name, event.content)

                # Send response back to Claude Code via stdin
                process = self._processes.get(user_id)
                if process and process.stdin:
                    response = "y\n" if approved else "n\n"
                    process.stdin.write(response.encode())
                    await process.stdin.drain()

        elif event.type == EventType.ASK_USER:
            if on_question:
                # Get answer via callback
                answer = await on_question(event.question, event.options or [])

                # Send response back to Claude Code via stdin
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
