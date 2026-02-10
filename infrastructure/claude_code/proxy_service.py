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

        Args:
            user_id: Telegram user ID (for tracking active processes)
            prompt: The task prompt to send to Claude Code
            working_dir: Working directory for the task
            session_id: Optional session ID to resume
            yolo_mode: If True, pass --dangerously-skip-permissions to auto-approve all tools
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

        # Build command with stream-json for real-time events
        cmd = [
            self.claude_path,
            "-p", prompt,
            "--output-format", "stream-json",  # JSON events for streaming
            "--verbose",  # More detailed output
            "--max-turns", str(self.max_turns),
        ]

        # YOLO mode → skip all permission prompts (auto-approve everything)
        if yolo_mode:
            cmd.append("--dangerously-skip-permissions")

        if session_id:
            cmd.extend(["--resume", session_id])

        logger.info(f"[{user_id}] Full command: {' '.join(cmd)}")
        logger.info(f"[{user_id}] Working dir: {work_dir}")

        output_buffer = []
        result_session_id = session_id

        try:
            env = os.environ.copy()
            # Don't set CI=true - we want HITL permissions!
            # env["CI"] = "true"  # This would auto-approve everything
            env["TERM"] = "dumb"  # Simple terminal
            env["NO_COLOR"] = "1"  # Disable colors
            logger.info(f"[{user_id}] Starting with API key present: {'ANTHROPIC_API_KEY' in env}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,  # For HITL responses
                cwd=work_dir,
                env=env,
            )
            self._processes[user_id] = process
            logger.info(f"[{user_id}] Process started with PID: {process.pid}")

            # Read stream-json output line by line (each event is a JSON line)
            async def read_stream():
                nonlocal result_session_id
                text_buffer = ""  # Accumulate text for streaming

                while True:
                    if self._cancel_events[user_id].is_set():
                        logger.info(f"[{user_id}] Stream cancelled")
                        return

                    try:
                        line = await asyncio.wait_for(
                            process.stdout.readline(),
                            timeout=60  # 60 sec timeout per line
                        )
                    except asyncio.TimeoutError:
                        # No output for 60 seconds - check if process still running
                        if process.returncode is not None:
                            break
                        continue

                    if not line:
                        logger.info(f"[{user_id}] Stream EOF")
                        break

                    line_str = line.decode('utf-8').strip()
                    if not line_str:
                        continue

                    logger.debug(f"[{user_id}] RAW: {line_str[:200]}")

                    # Try to parse as JSON event
                    event = self._parse_event(line_str)
                    if event:
                        # Log event details for debugging
                        extra = ""
                        if event.type == EventType.TOOL_USE:
                            extra = f" tool={event.tool_name}"
                        elif event.type == EventType.ASSISTANT_MESSAGE:
                            extra = f" len={len(event.content)}"
                        elif event.type == EventType.RESULT:
                            extra = f" len={len(event.content)} sid={event.session_id}"
                        logger.info(f"[{user_id}] Event: {event.type.value}{extra}")

                        # Handle the event
                        try:
                            await self._handle_event(
                                user_id, event,
                                on_text, on_tool_use, on_tool_result,
                                on_permission, on_question, on_error,
                                output_buffer
                            )
                        except Exception as e:
                            logger.error(f"[{user_id}] Error handling event {event.type.value}: {e}", exc_info=True)

                        # Extract session_id from result or assistant events
                        if event.session_id:
                            result_session_id = event.session_id
                    else:
                        # Non-JSON line - might be plain text output
                        logger.info(f"[{user_id}] Non-JSON: {line_str[:100]}")
                        if on_text and line_str:
                            output_buffer.append(line_str)
                            try:
                                await on_text(line_str + "\n")
                            except Exception as e:
                                logger.error(f"[{user_id}] Error in on_text callback: {e}")

            # Read stderr in background
            async def read_stderr():
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    line_str = line.decode('utf-8').strip()
                    if line_str:
                        logger.warning(f"[{user_id}] STDERR: {line_str}")

            # Run both readers with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(read_stream(), read_stderr()),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(f"[{user_id}] Task timeout after {self.timeout_seconds}s")
                process.kill()
                await process.wait()
                if on_error:
                    await on_error("Task timed out")
                return TaskResult(
                    success=False,
                    output="\n".join(output_buffer),
                    session_id=result_session_id,
                    error="Task timed out"
                )

            await process.wait()
            logger.info(
                f"[{user_id}] Process finished, returncode={process.returncode}, "
                f"output_lines={len(output_buffer)}, session_id={result_session_id}"
            )

            # Check if cancelled
            if self._cancel_events[user_id].is_set():
                return TaskResult(
                    success=False,
                    output="\n".join(output_buffer),
                    session_id=result_session_id,
                    cancelled=True
                )

            # Determine error message for non-zero return codes
            error_msg = None
            if process.returncode != 0:
                if process.returncode == 143:  # SIGTERM
                    error_msg = "Process was terminated (SIGTERM)"
                elif process.returncode == 137:  # SIGKILL
                    error_msg = "Process was killed (SIGKILL - possibly OOM)"
                elif process.returncode < 0:
                    error_msg = f"Process killed by signal {-process.returncode}"
                else:
                    error_msg = f"Process exited with code {process.returncode}"

            return TaskResult(
                success=process.returncode == 0,
                output="\n".join(output_buffer),
                session_id=result_session_id,
                error=error_msg
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
        """Parse a JSON line from Claude Code stream output.

        Returns a single event. For assistant messages with multiple blocks,
        tool_use takes priority (text is usually in a separate assistant event).
        """
        try:
            data = json.loads(line)

            # Determine event type
            event_type = data.get("type", "")
            logger.debug(f"Parsing event type: {event_type}, data keys: {list(data.keys())}")

            # Assistant message - can contain text and/or tool_use blocks
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

                # If there's a tool_use block, return it (text will come in result event)
                if first_tool_use:
                    return ClaudeCodeEvent(
                        type=EventType.TOOL_USE,
                        tool_name=first_tool_use.get("name"),
                        tool_input=first_tool_use.get("input", {}),
                        tool_id=first_tool_use.get("id"),
                        raw=data
                    )

                # Text-only assistant message
                if text_content:
                    return ClaudeCodeEvent(
                        type=EventType.ASSISTANT_MESSAGE,
                        content=text_content,
                        session_id=data.get("session_id"),
                        raw=data
                    )

            # Content block start - tool use
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

            # Streaming text delta
            elif event_type == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    return ClaudeCodeEvent(
                        type=EventType.TEXT,
                        content=delta.get("text", ""),
                        raw=data
                    )
                elif delta.get("type") == "input_json_delta":
                    # Tool input streaming - skip for now
                    pass

            # Tool use event
            elif event_type == "tool_use":
                return ClaudeCodeEvent(
                    type=EventType.TOOL_USE,
                    tool_name=data.get("name") or data.get("tool"),
                    tool_input=data.get("input", {}),
                    tool_id=data.get("id"),
                    raw=data
                )

            # Tool result — can come as "tool_result" or "user" type
            elif event_type == "tool_result" or event_type == "user":
                # Format from CLI stream-json:
                # {"type":"user","message":{"role":"user","content":[{"tool_use_id":"...","type":"tool_result","content":"...","is_error":false}]}}
                msg = data.get("message", {})
                content_blocks = msg.get("content", data.get("content", ""))
                tool_id = data.get("tool_use_id") or data.get("id")
                result_content = ""

                if isinstance(content_blocks, list):
                    text_parts = []
                    for block in content_blocks:
                        if isinstance(block, dict):
                            if block.get("type") == "tool_result":
                                block_content = block.get("content", "")
                                text_parts.append(str(block_content))
                                if not tool_id:
                                    tool_id = block.get("tool_use_id")
                            elif block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                    result_content = "\n".join(text_parts)
                elif isinstance(content_blocks, str):
                    result_content = content_blocks

                # Also check top-level tool_use_result shorthand
                if not result_content:
                    result_content = str(data.get("tool_use_result", ""))

                return ClaudeCodeEvent(
                    type=EventType.TOOL_RESULT,
                    tool_id=tool_id,
                    content=str(result_content)[:500],  # Truncate long results
                    raw=data
                )

            # Result/completion
            elif event_type == "result" or event_type == "message_stop":
                # 'result' field contains the final text output
                result_text = data.get("result", "") or data.get("content", "")
                return ClaudeCodeEvent(
                    type=EventType.RESULT,
                    content=result_text,
                    session_id=data.get("session_id"),
                    raw=data
                )

            # Error
            elif event_type == "error":
                return ClaudeCodeEvent(
                    type=EventType.ERROR,
                    error=data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else data.get("error") or data.get("message"),
                    raw=data
                )

            # System message
            elif event_type == "system" or "system" in event_type.lower():
                return ClaudeCodeEvent(
                    type=EventType.SYSTEM,
                    content=data.get("message") or data.get("content", ""),
                    raw=data
                )

            # Input request (permission or question)
            elif event_type == "input_request" or event_type == "input":
                # This is the HITL event - permission or question
                input_type = data.get("input_type", "")

                if input_type == "permission" or "permission" in str(data).lower():
                    return ClaudeCodeEvent(
                        type=EventType.PERMISSION_REQUEST,
                        tool_name=data.get("tool") or data.get("tool_name", ""),
                        content=data.get("description") or data.get("command") or json.dumps(data),
                        raw=data
                    )
                else:
                    # Question
                    return ClaudeCodeEvent(
                        type=EventType.ASK_USER,
                        question=data.get("question") or data.get("message") or data.get("prompt", ""),
                        options=data.get("options", []),
                        raw=data
                    )

            # Skip these event types silently
            elif event_type in ["message_start", "content_block_stop", "message_delta", "ping"]:
                return None

            # Unknown event type - log it and try to extract content
            logger.info(f"Unknown event type: {event_type}, keys: {list(data.keys())}")

            # Check for permission-like events
            if "permission" in str(data).lower() or "approve" in str(data).lower():
                return ClaudeCodeEvent(
                    type=EventType.PERMISSION_REQUEST,
                    tool_name=data.get("tool") or data.get("name", "unknown"),
                    content=json.dumps(data, ensure_ascii=False)[:500],
                    raw=data
                )

            # Try to extract any text content
            if data.get("text") or data.get("content"):
                content = data.get("text") or data.get("content", "")
                if isinstance(content, str) and content:
                    return ClaudeCodeEvent(
                        type=EventType.TEXT,
                        content=content,
                        raw=data
                    )

            return None

        except json.JSONDecodeError:
            # Not JSON - could be plain text
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
