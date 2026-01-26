"""
Claude Agent SDK Service

Provides a proper programmatic interface to Claude Code using the official
Agent SDK instead of CLI subprocess. This enables true HITL (Human-in-the-Loop)
support with proper async waiting for user approval/answers.

Key features:
- can_use_tool callback for permission handling (pauses until user responds)
- Hooks for tool use notifications
- Streaming message support
- Session continuity
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import SDK - may not be installed yet
try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        HookMatcher,
        HookContext,
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,
        ThinkingBlock,
    )
    from claude_agent_sdk.types import (
        PermissionResultAllow,
        PermissionResultDeny,
        ToolPermissionContext,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning("claude-agent-sdk not installed. Install with: pip install claude-agent-sdk")


def _format_tool_response(tool_name: str, response: Any, max_length: int = 500) -> str:
    """Format tool response for display in Telegram.

    Parses different response types and formats them nicely instead of raw dict.
    """
    import json

    if not response:
        return ""

    # Parse JSON string if needed (SDK may return serialized JSON)
    if isinstance(response, str):
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                response = parsed
        except (json.JSONDecodeError, TypeError):
            pass  # Keep as string

    tool_lower = tool_name.lower()

    # Handle dict responses
    if isinstance(response, dict):
        # Glob results
        if tool_lower == "glob" and "filenames" in response:
            files = response.get("filenames", [])
            if not files:
                return "Файлов не найдено"
            # Show file list
            file_list = "\n".join(f"  {f}" for f in files[:20])
            if len(files) > 20:
                file_list += f"\n  ... и ещё {len(files) - 20} файлов"
            return f"Найдено {len(files)} файлов:\n{file_list}"

        # Read results
        if tool_lower == "read" and "file" in response:
            file_info = response.get("file", {})
            content = file_info.get("content", "")
            path = file_info.get("filePath", "")
            if content:
                truncated = content[:max_length]
                if len(content) > max_length:
                    truncated += "\n... (обрезано)"
                return truncated
            return f"Файл прочитан: {path}"

        # Grep results
        if tool_lower == "grep" and "matches" in response:
            matches = response.get("matches", [])
            if not matches:
                return "Совпадений не найдено"
            return f"Найдено {len(matches)} совпадений"

        # Generic dict - try to extract useful info
        if "content" in response:
            return str(response["content"])[:max_length]
        if "output" in response:
            return str(response["output"])[:max_length]
        if "result" in response:
            return str(response["result"])[:max_length]

        # Skip technical dicts with only metadata
        if set(response.keys()) <= {"durationMs", "numFiles", "truncated", "type"}:
            return ""

        # Fallback: simple representation
        return str(response)[:max_length]

    # String response
    response_str = str(response)
    if len(response_str) > max_length:
        return response_str[:max_length] + "..."
    return response_str


class TaskStatus(str, Enum):
    """Task execution status"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING_PERMISSION = "waiting_permission"
    WAITING_ANSWER = "waiting_answer"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PermissionRequest:
    """Pending permission request"""
    request_id: str
    tool_name: str
    tool_input: dict
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class QuestionRequest:
    """Pending question request"""
    request_id: str
    question: str
    options: list[str]
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SDKTaskResult:
    """Result of a Claude Agent SDK task"""
    success: bool
    output: str
    session_id: Optional[str] = None
    error: Optional[str] = None
    cancelled: bool = False
    total_cost_usd: Optional[float] = None
    num_turns: Optional[int] = None
    duration_ms: Optional[int] = None


class ClaudeAgentSDKService:
    """
    Service for interacting with Claude Code via the official Agent SDK.

    Uses ClaudeSDKClient with can_use_tool callback for proper HITL support.
    When a tool requires permission, execution pauses until the callback returns.
    """

    def __init__(
        self,
        default_working_dir: str = "/root",
        max_turns: int = 50,
        permission_mode: str = "default",  # "default", "acceptEdits", "bypassPermissions"
        plugins_dir: str = "/plugins",  # For custom plugins only
        enabled_plugins: list[str] = None,  # For custom plugins only
        telegram_mcp_path: str = "/app/telegram-mcp/build/index.js",  # Path to telegram MCP server
        account_service: "AccountService" = None,  # For auth mode switching
    ):
        if not SDK_AVAILABLE:
            raise RuntimeError(
                "claude-agent-sdk is not installed. "
                "Install with: pip install claude-agent-sdk"
            )

        self.default_working_dir = default_working_dir
        self.max_turns = max_turns
        self.permission_mode = permission_mode
        self.plugins_dir = plugins_dir
        self.enabled_plugins = enabled_plugins or []
        self.telegram_mcp_path = telegram_mcp_path
        self.account_service = account_service  # Optional - for auth mode switching

        # Active clients by user_id
        self._clients: dict[int, ClaudeSDKClient] = {}
        self._tasks: dict[int, asyncio.Task] = {}
        self._cancel_events: dict[int, asyncio.Event] = {}

        # HITL state - events for waiting on user response
        self._permission_events: dict[int, asyncio.Event] = {}
        self._permission_requests: dict[int, PermissionRequest] = {}
        self._permission_responses: dict[int, bool] = {}

        self._question_events: dict[int, asyncio.Event] = {}
        self._question_requests: dict[int, QuestionRequest] = {}
        self._question_responses: dict[int, str] = {}

        # Task status
        self._task_status: dict[int, TaskStatus] = {}

    async def check_sdk_available(self) -> tuple[bool, str]:
        """Check if Claude Agent SDK is available"""
        if not SDK_AVAILABLE:
            return False, "claude-agent-sdk not installed. Install with: pip install claude-agent-sdk"
        return True, "Claude Agent SDK is available"

    async def get_env_for_user(self, user_id: int) -> dict[str, str]:
        """
        Get environment variables for the user based on their auth mode.

        If AccountService is configured, returns env vars based on user's
        selected auth mode (z.ai API or Claude Account with proxy).
        Otherwise, returns current environment.
        """
        if not self.account_service:
            return dict(os.environ)

        try:
            mode = await self.account_service.get_auth_mode(user_id)
            env = self.account_service.apply_env_for_mode(mode)
            logger.debug(f"[{user_id}] Using auth mode: {mode.value}")
            return env
        except Exception as e:
            logger.warning(f"[{user_id}] Error getting auth mode, using default env: {e}")
            return dict(os.environ)

    def _get_mcp_servers_config(self, user_id: int) -> dict:
        """
        Build MCP servers configuration for ClaudeAgentOptions.

        Includes telegram MCP server with dynamic chat_id for the current user.

        Args:
            user_id: Telegram user ID to send files/messages to

        Returns:
            Dict of MCP server configurations
        """
        mcp_servers = {}

        # Check if telegram MCP server exists
        if os.path.isfile(self.telegram_mcp_path):
            telegram_token = os.environ.get("TELEGRAM_TOKEN", "")
            if telegram_token:
                mcp_servers["telegram"] = {
                    "command": "node",
                    "args": [self.telegram_mcp_path],
                    "env": {
                        "TELEGRAM_TOKEN": telegram_token,
                        "TELEGRAM_CHAT_ID": str(user_id),
                    }
                }
                logger.debug(f"[{user_id}] Telegram MCP server configured")
            else:
                logger.warning("TELEGRAM_TOKEN not set, telegram MCP server disabled")
        else:
            logger.debug(f"Telegram MCP server not found at {self.telegram_mcp_path}")

        return mcp_servers

    def _get_plugin_configs(self) -> list[dict]:
        """
        Build plugin configuration list for ClaudeAgentOptions.

        Supports two types of plugins:
        1. Local plugins: from /plugins directory (custom plugins)
        2. Official plugins: from Claude plugins marketplace (auto-downloaded)

        Format: "plugin-name" tries local first, falls back to official.
        Format: "official:plugin-name" forces official marketplace.
        Format: "local:plugin-name" forces local only.
        """
        plugins = []
        for plugin_name in self.enabled_plugins:
            if not plugin_name:  # Skip empty strings
                continue

            # Check for explicit type prefix
            if plugin_name.startswith("official:"):
                # Force official marketplace
                name = plugin_name.replace("official:", "")
                plugins.append({"type": "official", "name": name})
                logger.info(f"Plugin enabled (official): {name}")
            elif plugin_name.startswith("local:"):
                # Force local only
                name = plugin_name.replace("local:", "")
                plugin_path = os.path.join(self.plugins_dir, name)
                if os.path.isdir(plugin_path):
                    plugins.append({"type": "local", "path": plugin_path})
                    logger.info(f"Plugin enabled (local): {name} at {plugin_path}")
                else:
                    logger.warning(f"Local plugin not found: {name} at {plugin_path}")
            else:
                # Try local first, fall back to official
                plugin_path = os.path.join(self.plugins_dir, plugin_name)
                if os.path.isdir(plugin_path):
                    plugins.append({"type": "local", "path": plugin_path})
                    logger.info(f"Plugin enabled (local): {plugin_name} at {plugin_path}")
                else:
                    # Use official marketplace
                    plugins.append({"type": "official", "name": plugin_name})
                    logger.info(f"Plugin enabled (official): {plugin_name}")
        return plugins

    def get_enabled_plugins_info(self) -> list[dict]:
        """
        Get info about enabled plugins for display.

        Returns info about plugins - supports both local and official marketplace plugins.
        """
        plugins_info = []

        # Plugin descriptions (from official repo)
        plugin_descriptions = {
            "commit-commands": "Git workflow: commit, push, PR",
            "code-review": "Ревью кода и PR",
            "feature-dev": "Разработка фичи с архитектурой",
            "frontend-design": "Создание UI интерфейсов",
            "claude-code-setup": "Настройка Claude Code",
            "security-guidance": "Проверка безопасности кода",
            "pr-review-toolkit": "Инструменты ревью PR",
            "ralph-loop": "RAFL: итеративное решение задач",
        }

        for plugin_name in self.enabled_plugins:
            if not plugin_name:
                continue

            # Parse plugin name (may have prefix)
            if plugin_name.startswith("official:"):
                name = plugin_name.replace("official:", "")
                source = "official"
                is_available = True  # Official plugins always available
                path = None
            elif plugin_name.startswith("local:"):
                name = plugin_name.replace("local:", "")
                source = "local"
                plugin_path = os.path.join(self.plugins_dir, name)
                is_available = os.path.isdir(plugin_path)
                path = plugin_path if is_available else None
            else:
                name = plugin_name
                plugin_path = os.path.join(self.plugins_dir, name)
                if os.path.isdir(plugin_path):
                    source = "local"
                    is_available = True
                    path = plugin_path
                else:
                    source = "official"
                    is_available = True  # Will be downloaded from marketplace
                    path = None

            plugins_info.append({
                "name": name,
                "description": plugin_descriptions.get(name, "Plugin"),
                "available": is_available,
                "source": source,
                "path": path,
            })

        return plugins_info

    def add_plugin(self, plugin_name: str) -> bool:
        """
        Dynamically add a plugin to enabled list.

        Args:
            plugin_name: Name of the plugin to enable

        Returns:
            True if added, False if already enabled
        """
        # Normalize name (remove prefix if any)
        if plugin_name.startswith("official:") or plugin_name.startswith("local:"):
            plugin_name = plugin_name.split(":", 1)[1]

        if plugin_name in self.enabled_plugins:
            return False

        self.enabled_plugins.append(plugin_name)
        logger.info(f"Plugin enabled: {plugin_name}")
        return True

    def remove_plugin(self, plugin_name: str) -> bool:
        """
        Dynamically remove a plugin from enabled list.

        Args:
            plugin_name: Name of the plugin to disable

        Returns:
            True if removed, False if not found
        """
        # Normalize name (remove prefix if any)
        if plugin_name.startswith("official:") or plugin_name.startswith("local:"):
            plugin_name = plugin_name.split(":", 1)[1]

        if plugin_name not in self.enabled_plugins:
            return False

        self.enabled_plugins.remove(plugin_name)
        logger.info(f"Plugin disabled: {plugin_name}")
        return True

    def is_task_running(self, user_id: int) -> bool:
        """Check if a task is currently running for a user"""
        status = self._task_status.get(user_id, TaskStatus.IDLE)
        return status in (TaskStatus.RUNNING, TaskStatus.WAITING_PERMISSION, TaskStatus.WAITING_ANSWER)

    def get_task_status(self, user_id: int) -> TaskStatus:
        """Get current task status for a user"""
        return self._task_status.get(user_id, TaskStatus.IDLE)

    def get_pending_permission(self, user_id: int) -> Optional[PermissionRequest]:
        """Get pending permission request for a user"""
        return self._permission_requests.get(user_id)

    def get_pending_question(self, user_id: int) -> Optional[QuestionRequest]:
        """Get pending question for a user"""
        return self._question_requests.get(user_id)

    async def respond_to_permission(self, user_id: int, approved: bool) -> bool:
        """Respond to a pending permission request"""
        event = self._permission_events.get(user_id)
        if event and self._task_status.get(user_id) == TaskStatus.WAITING_PERMISSION:
            self._permission_responses[user_id] = approved
            event.set()
            return True
        return False

    async def respond_to_question(self, user_id: int, answer: str) -> bool:
        """Respond to a pending question"""
        event = self._question_events.get(user_id)
        if event and self._task_status.get(user_id) == TaskStatus.WAITING_ANSWER:
            self._question_responses[user_id] = answer
            event.set()
            return True
        return False

    async def cancel_task(self, user_id: int) -> bool:
        """Cancel the active task for a user"""
        cancelled = False

        # Set all events to signal the running task (it may be waiting on any of these)
        # This ensures the task wakes up from any wait_for() call
        cancel_event = self._cancel_events.get(user_id)
        if cancel_event:
            cancel_event.set()
            cancelled = True

        permission_event = self._permission_events.get(user_id)
        if permission_event:
            permission_event.set()

        question_event = self._question_events.get(user_id)
        if question_event:
            question_event.set()

        # Try to interrupt the SDK client
        client = self._clients.get(user_id)
        if client:
            try:
                await client.interrupt()
                cancelled = True
                logger.info(f"[{user_id}] Client interrupted")
            except Exception as e:
                logger.error(f"[{user_id}] Error interrupting client: {e}")

        # Try to cancel the asyncio task
        task = self._tasks.get(user_id)
        if task and not task.done():
            task.cancel()
            cancelled = True
            logger.info(f"[{user_id}] Asyncio task cancelled")

        # Always reset status and clean up when cancel is requested
        current_status = self._task_status.get(user_id, TaskStatus.IDLE)
        if current_status != TaskStatus.IDLE:
            logger.info(f"[{user_id}] Resetting task status from {current_status} to IDLE")
            self._task_status[user_id] = TaskStatus.IDLE
            cancelled = True

        # Clean up any leftover state
        self._clients.pop(user_id, None)
        self._tasks.pop(user_id, None)
        self._cancel_events.pop(user_id, None)
        self._permission_events.pop(user_id, None)
        self._question_events.pop(user_id, None)
        self._permission_requests.pop(user_id, None)
        self._question_requests.pop(user_id, None)
        self._permission_responses.pop(user_id, None)
        self._question_responses.pop(user_id, None)

        return cancelled

    async def run_task(
        self,
        user_id: int,
        prompt: str,
        working_dir: Optional[str] = None,
        session_id: Optional[str] = None,
        on_text: Optional[Callable[[str], Awaitable[None]]] = None,
        on_tool_use: Optional[Callable[[str, dict], Awaitable[None]]] = None,
        on_tool_result: Optional[Callable[[str, str], Awaitable[None]]] = None,
        on_permission_request: Optional[Callable[[str, str, dict], Awaitable[None]]] = None,
        on_permission_completed: Optional[Callable[[bool], Awaitable[None]]] = None,
        on_question: Optional[Callable[[str, list[str]], Awaitable[None]]] = None,
        on_question_completed: Optional[Callable[[str], Awaitable[None]]] = None,
        on_thinking: Optional[Callable[[str], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
        _retry_without_resume: bool = False,  # Internal: retry flag for 0-turns issue
    ) -> SDKTaskResult:
        """
        Run a Claude Code task using the Agent SDK.

        Unlike the CLI approach, this uses the SDK's can_use_tool callback
        which properly pauses execution until we respond, enabling true HITL.

        Args:
            user_id: User ID for tracking
            prompt: The task prompt
            working_dir: Working directory
            session_id: Optional session ID to resume
            on_text: Callback for text output
            on_tool_use: Callback when a tool is being used (for UI updates)
            on_tool_result: Callback when tool completes
            on_permission_request: Callback to notify UI about permission request
            on_question: Callback to notify UI about question (via AskUserQuestion tool)
            on_thinking: Callback for thinking output
            on_error: Callback for errors

        Returns:
            SDKTaskResult with success status and output
        """
        # Cancel any existing task
        await self.cancel_task(user_id)

        # Initialize state - store local references to avoid race conditions
        # when another message arrives and creates new events
        cancel_event = asyncio.Event()
        permission_event = asyncio.Event()
        question_event = asyncio.Event()

        self._cancel_events[user_id] = cancel_event
        self._permission_events[user_id] = permission_event
        self._question_events[user_id] = question_event
        self._task_status[user_id] = TaskStatus.RUNNING

        work_dir = working_dir or self.default_working_dir
        output_buffer = []
        result_session_id = session_id
        result_cost_usd: Optional[float] = None
        result_num_turns: Optional[int] = None

        # Validate working directory
        if not os.path.isdir(work_dir):
            error_msg = f"Working directory does not exist: {work_dir}"
            logger.error(f"[{user_id}] {error_msg}")
            if on_error:
                await on_error(error_msg)
            # Reset status before returning (cleanup won't run for early returns)
            self._task_status[user_id] = TaskStatus.IDLE
            self._cancel_events.pop(user_id, None)
            self._permission_events.pop(user_id, None)
            self._question_events.pop(user_id, None)
            return SDKTaskResult(
                success=False,
                output="",
                error=error_msg
            )

        # Create permission handler that integrates with Telegram HITL
        async def can_use_tool(
            tool_name: str,
            tool_input: dict,
            context: ToolPermissionContext
        ):
            """
            Permission callback - this is called BEFORE each tool execution.
            We can allow, deny, or modify the input.

            For dangerous tools (Bash, Write, Edit), we pause and wait for user approval.
            """
            nonlocal user_id

            # Check if cancelled (use local reference to avoid race condition)
            if cancel_event.is_set():
                return PermissionResultDeny(
                    message="Task cancelled by user",
                    interrupt=True
                )

            # Tools that always need approval
            dangerous_tools = {"Bash", "Write", "Edit", "NotebookEdit"}

            # Tools that can run without approval
            safe_tools = {"Read", "Glob", "Grep", "WebFetch", "WebSearch", "LS"}

            # AskUserQuestion is special - we handle it to show Telegram buttons
            if tool_name == "AskUserQuestion":
                # Extract question details
                questions = tool_input.get("questions", [])
                if questions:
                    q = questions[0]
                    question_text = q.get("question", "")
                    options = [opt.get("label", "") for opt in q.get("options", [])]

                    # Create request
                    request_id = f"q_{user_id}_{datetime.now().timestamp()}"
                    self._question_requests[user_id] = QuestionRequest(
                        request_id=request_id,
                        question=question_text,
                        options=options
                    )
                    self._task_status[user_id] = TaskStatus.WAITING_ANSWER

                    # Notify UI
                    if on_question:
                        await on_question(question_text, options)

                    # Wait for user response (use local reference)
                    question_event.clear()

                    try:
                        await asyncio.wait_for(question_event.wait(), timeout=300)  # 5 min timeout
                        # Check if woken up due to cancellation
                        if cancel_event.is_set():
                            return PermissionResultDeny(
                                message="Task cancelled by user",
                                interrupt=True
                            )
                        answer = self._question_responses.get(user_id, "")
                    except asyncio.TimeoutError:
                        answer = ""
                        if on_error:
                            await on_error("Question timed out")

                    # Cleanup and resume
                    self._question_requests.pop(user_id, None)
                    self._task_status[user_id] = TaskStatus.RUNNING

                    # Notify UI that question was answered (for moving streaming to bottom)
                    if on_question_completed:
                        await on_question_completed(answer)

                    # Modify the input to include the answer
                    updated_input = {**tool_input}
                    updated_input["answers"] = {question_text: answer}

                    return PermissionResultAllow(updated_input=updated_input)

            # Safe tools - allow automatically
            if tool_name in safe_tools:
                return PermissionResultAllow(updated_input=tool_input)

            # Check permission mode
            if self.permission_mode == "bypassPermissions":
                return PermissionResultAllow(updated_input=tool_input)

            if self.permission_mode == "acceptEdits" and tool_name in {"Write", "Edit", "NotebookEdit"}:
                return PermissionResultAllow(updated_input=tool_input)

            # Dangerous tool - request permission
            if tool_name in dangerous_tools:
                # Create permission request
                request_id = f"p_{user_id}_{datetime.now().timestamp()}"

                # Format details for display
                if tool_name == "Bash":
                    details = tool_input.get("command", str(tool_input))
                elif tool_name in {"Write", "Edit"}:
                    details = tool_input.get("file_path", str(tool_input))
                else:
                    details = str(tool_input)[:500]

                self._permission_requests[user_id] = PermissionRequest(
                    request_id=request_id,
                    tool_name=tool_name,
                    tool_input=tool_input
                )
                self._task_status[user_id] = TaskStatus.WAITING_PERMISSION

                # Notify UI about permission request
                if on_permission_request:
                    await on_permission_request(tool_name, details, tool_input)

                # Wait for user response (use local reference)
                permission_event.clear()

                try:
                    await asyncio.wait_for(permission_event.wait(), timeout=300)  # 5 min timeout
                    # Check if woken up due to cancellation
                    if cancel_event.is_set():
                        return PermissionResultDeny(
                            message="Task cancelled by user",
                            interrupt=True
                        )
                    approved = self._permission_responses.get(user_id, False)
                except asyncio.TimeoutError:
                    approved = False
                    if on_error:
                        await on_error("Permission request timed out")

                # Cleanup and resume
                self._permission_requests.pop(user_id, None)
                self._task_status[user_id] = TaskStatus.RUNNING

                # Notify UI that permission was handled (for moving streaming to bottom)
                if on_permission_completed:
                    await on_permission_completed(approved)

                if approved:
                    return PermissionResultAllow(updated_input=tool_input)
                else:
                    return PermissionResultDeny(
                        message="User rejected the operation",
                        interrupt=False  # Continue but skip this tool
                    )

            # Default: allow
            return PermissionResultAllow(updated_input=tool_input)

        # Create hooks for tool use notifications
        async def pre_tool_hook(
            input_data: dict,
            tool_use_id: str | None,
            context: HookContext
        ) -> dict:
            """Hook called before tool execution - for UI notifications"""
            tool_name = input_data.get("tool_name", "")
            tool_input = input_data.get("tool_input", {})

            if on_tool_use:
                await on_tool_use(tool_name, tool_input)

            return {}  # Don't modify behavior, just notify

        async def post_tool_hook(
            input_data: dict,
            tool_use_id: str | None,
            context: HookContext
        ) -> dict:
            """Hook called after tool execution"""
            tool_name = input_data.get("tool_name", "")
            tool_response = input_data.get("tool_response", "")

            if on_tool_result:
                # Format response nicely instead of raw dict
                formatted = _format_tool_response(tool_name, tool_response)
                if formatted:  # Only show non-empty results
                    await on_tool_result(tool_use_id or "", formatted)

            return {}

        # Get and apply user-specific environment (for auth mode switching)
        original_env = dict(os.environ)
        user_env = await self.get_env_for_user(user_id)

        # Get user's preferred model (if AccountService is available)
        user_model: Optional[str] = None
        if self.account_service:
            try:
                user_model = await self.account_service.get_model(user_id)
                if user_model:
                    logger.info(f"[{user_id}] Using selected model: {user_model}")
            except Exception as e:
                logger.warning(f"[{user_id}] Error getting user model, using default: {e}")

        # Apply user environment
        env_changes = []
        for key, value in user_env.items():
            if key.startswith("_"):  # Skip internal markers
                continue
            if os.environ.get(key) != value:
                env_changes.append(key)
                os.environ[key] = value

        # Remove keys that should be unset for this mode
        # IMPORTANT: Include ANTHROPIC_MODEL and default model vars to prevent
        # z.ai model (e.g., glm-4.7) from being sent to official Claude API
        keys_to_remove = (
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "ANTHROPIC_MODEL",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL",
        )
        removed_keys = []
        for key in list(os.environ.keys()):
            if key not in user_env and key in keys_to_remove:
                removed_keys.append(key)
                del os.environ[key]

        if env_changes or removed_keys:
            logger.info(f"[{user_id}] Applied env: set={env_changes}, removed={removed_keys}")

        try:
            # Build plugin configurations
            plugins = self._get_plugin_configs()
            if plugins:
                logger.info(f"[{user_id}] Using {len(plugins)} plugins: {[p['path'] for p in plugins]}")

            # Build MCP servers configuration (with dynamic chat_id)
            mcp_servers = self._get_mcp_servers_config(user_id)
            if mcp_servers:
                logger.info(f"[{user_id}] MCP servers enabled: {list(mcp_servers.keys())}")

            # Build options
            options = ClaudeAgentOptions(
                cwd=work_dir,
                max_turns=self.max_turns,
                model=user_model,  # Use user's selected model if set
                permission_mode=self.permission_mode if self.permission_mode != "default" else None,
                can_use_tool=can_use_tool,
                hooks={
                    "PreToolUse": [HookMatcher(hooks=[pre_tool_hook])],
                    "PostToolUse": [HookMatcher(hooks=[post_tool_hook])],
                },
                # Enable session continuity for context memory (disable on retry)
                resume=None if _retry_without_resume else session_id,
                plugins=plugins if plugins else None,
                # MCP servers for custom tools (telegram file sending, etc.)
                mcp_servers=mcp_servers if mcp_servers else None,
            )

            resume_info = f"resume={session_id[:16]}..." if session_id and not _retry_without_resume else "new session"
            logger.info(f"[{user_id}] Starting SDK task in {work_dir} ({resume_info})")
            logger.debug(f"[{user_id}] Prompt: {prompt[:200]}")

            # Use context manager for proper cleanup
            async with ClaudeSDKClient(options=options) as client:
                self._clients[user_id] = client

                # Send the prompt
                logger.debug(f"[{user_id}] Sending query to Claude SDK...")
                await client.query(prompt)
                logger.debug(f"[{user_id}] Query sent, waiting for response...")

                # Process messages
                async for message in client.receive_response():
                    # Check for cancellation (use local reference to avoid race condition)
                    if cancel_event.is_set():
                        logger.info(f"[{user_id}] Task cancelled")
                        break

                    # Handle different message types
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                text = block.text
                                output_buffer.append(text)
                                if on_text:
                                    await on_text(text)

                            elif isinstance(block, ThinkingBlock):
                                if on_thinking:
                                    await on_thinking(block.thinking)

                            elif isinstance(block, ToolUseBlock):
                                # Tool use is handled by hooks and can_use_tool
                                pass

                            elif isinstance(block, ToolResultBlock):
                                # Tool results are handled by post_tool_hook
                                pass

                    elif isinstance(message, ResultMessage):
                        result_session_id = message.session_id
                        result_cost_usd = message.total_cost_usd
                        result_num_turns = message.num_turns
                        if message.result:
                            output_buffer.append(message.result)

                        session_info = f"session={result_session_id[:16]}..." if result_session_id else "no session"
                        logger.info(
                            f"[{user_id}] Task completed: "
                            f"turns={message.num_turns}, "
                            f"cost=${message.total_cost_usd or 0:.4f}, "
                            f"{session_info}"
                        )

                        # Handle 0 turns - retry without resume if session was used
                        if message.num_turns == 0 and session_id and not _retry_without_resume:
                            logger.warning(
                                f"[{user_id}] Session {session_id[:16]}... is invalid (0 turns). "
                                f"This usually means session files in ~/.claude/ were lost. "
                                f"Retrying with fresh session..."
                            )
                            # Cleanup before retry
                            self._clients.pop(user_id, None)
                            # Recursive retry without resume - DO NOT pass old session_id
                            # so that the new session_id will be returned
                            return await self.run_task(
                                user_id=user_id,
                                prompt=prompt,
                                working_dir=working_dir,
                                session_id=None,  # Clear invalid session - new one will be created
                                on_text=on_text,
                                on_tool_use=on_tool_use,
                                on_tool_result=on_tool_result,
                                on_permission_request=on_permission_request,
                                on_permission_completed=on_permission_completed,
                                on_question=on_question,
                                on_question_completed=on_question_completed,
                                on_thinking=on_thinking,
                                on_error=on_error,
                                _retry_without_resume=True,
                            )
                        elif message.num_turns == 0:
                            logger.warning(
                                f"[{user_id}] Task completed with 0 turns (no session). "
                                f"Prompt was: {prompt[:100]}..."
                            )

                # Check final status (use local reference)
                if cancel_event.is_set():
                    return SDKTaskResult(
                        success=False,
                        output="\n".join(output_buffer),
                        session_id=result_session_id,
                        cancelled=True,
                        total_cost_usd=result_cost_usd,
                        num_turns=result_num_turns,
                    )

                return SDKTaskResult(
                    success=True,
                    output="\n".join(output_buffer),
                    session_id=result_session_id,
                    total_cost_usd=result_cost_usd,
                    num_turns=result_num_turns,
                )

        except asyncio.CancelledError:
            # Task was cancelled - this is expected behavior
            logger.info(f"[{user_id}] Task was cancelled")
            return SDKTaskResult(
                success=False,
                output="\n".join(output_buffer),
                session_id=result_session_id,
                cancelled=True,
                total_cost_usd=result_cost_usd,
                num_turns=result_num_turns,
            )

        except Exception as e:
            error_msg = str(e)

            # Check if this was actually a cancellation (use local reference to avoid race condition)
            if cancel_event.is_set():
                logger.info(f"[{user_id}] Task interrupted by user")
                return SDKTaskResult(
                    success=False,
                    output="\n".join(output_buffer),
                    session_id=result_session_id,
                    cancelled=True,
                    total_cost_usd=result_cost_usd,
                    num_turns=result_num_turns,
                )

            logger.error(f"[{user_id}] SDK task error: {error_msg}")

            if on_error:
                await on_error(error_msg)

            return SDKTaskResult(
                success=False,
                output="\n".join(output_buffer),
                session_id=result_session_id,
                error=error_msg,
                total_cost_usd=result_cost_usd,
                num_turns=result_num_turns,
            )

        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)

            # Cleanup
            self._clients.pop(user_id, None)
            self._tasks.pop(user_id, None)
            self._cancel_events.pop(user_id, None)
            self._permission_events.pop(user_id, None)
            self._question_events.pop(user_id, None)
            self._permission_requests.pop(user_id, None)
            self._question_requests.pop(user_id, None)
            self._permission_responses.pop(user_id, None)
            self._question_responses.pop(user_id, None)
            self._task_status[user_id] = TaskStatus.IDLE
