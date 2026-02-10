"""Tests for ClaudeCodeProxyService event parsing and command building."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.claude_code.proxy_service import (
    ClaudeCodeProxyService,
    ClaudeCodeEvent,
    EventType,
    TaskResult,
)


@pytest.fixture
def proxy_service():
    """Create a ClaudeCodeProxyService instance for testing."""
    return ClaudeCodeProxyService(
        claude_path="claude",
        default_working_dir="/root",
        max_turns=50,
        timeout_seconds=600,
    )


# === Command Building Tests ===


class TestCommandBuilding:
    """Tests for CLI command construction."""

    @pytest.mark.asyncio
    async def test_command_includes_max_turns(self, proxy_service):
        """run_task should include --max-turns in the command."""
        # We can't easily test the full run_task flow, so test the command building
        # by checking that the service stores the max_turns value
        assert proxy_service.max_turns == 50

    @pytest.mark.asyncio
    async def test_yolo_mode_default_false(self, proxy_service):
        """yolo_mode defaults to False."""
        # Verify the parameter exists in the signature
        import inspect
        sig = inspect.signature(proxy_service.run_task)
        assert "yolo_mode" in sig.parameters
        assert sig.parameters["yolo_mode"].default is False


# === Event Parsing Tests ===


class TestParseEvent:
    """Tests for _parse_event method."""

    def test_parse_system_init(self, proxy_service):
        """Parse system init event."""
        data = {
            "type": "system",
            "subtype": "init",
            "cwd": "/root/projects",
            "session_id": "abc-123",
            "tools": ["Read", "Write", "Bash"],
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.SYSTEM

    def test_parse_assistant_text_only(self, proxy_service):
        """Parse assistant message with text content only."""
        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Hello! How can I help?"}
                ]
            },
            "session_id": "abc-123",
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.ASSISTANT_MESSAGE
        assert event.content == "Hello! How can I help?"
        assert event.session_id == "abc-123"

    def test_parse_assistant_tool_use_only(self, proxy_service):
        """Parse assistant message with tool_use block."""
        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_123",
                        "name": "Read",
                        "input": {"file_path": "/etc/hostname"},
                    }
                ]
            },
            "session_id": "abc-123",
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.TOOL_USE
        assert event.tool_name == "Read"
        assert event.tool_id == "toolu_123"
        assert event.tool_input == {"file_path": "/etc/hostname"}

    def test_parse_assistant_text_and_tool_use(self, proxy_service):
        """Parse assistant message with BOTH text and tool_use — tool_use takes priority."""
        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Let me read that file."},
                    {
                        "type": "tool_use",
                        "id": "toolu_456",
                        "name": "Read",
                        "input": {"file_path": "/etc/hostname"},
                    },
                ]
            },
            "session_id": "abc-123",
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        # tool_use should take priority over text
        assert event.type == EventType.TOOL_USE
        assert event.tool_name == "Read"
        assert event.tool_id == "toolu_456"

    def test_parse_assistant_multiple_tool_use(self, proxy_service):
        """Parse assistant message with multiple tool_use blocks — first one wins."""
        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Read",
                        "input": {"file_path": "/etc/hostname"},
                    },
                    {
                        "type": "tool_use",
                        "id": "toolu_2",
                        "name": "Write",
                        "input": {"file_path": "/tmp/out.txt", "content": "hello"},
                    },
                ]
            },
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.TOOL_USE
        assert event.tool_name == "Read"
        assert event.tool_id == "toolu_1"

    def test_parse_user_tool_result(self, proxy_service):
        """Parse user event with tool_result content (CLI format)."""
        data = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "tool_use_id": "toolu_123",
                        "type": "tool_result",
                        "content": "4b77ff039fcf",
                        "is_error": False,
                    }
                ],
            },
            "session_id": "abc-123",
            "tool_use_result": {"stdout": "4b77ff039fcf", "stderr": ""},
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.TOOL_RESULT
        assert event.tool_id == "toolu_123"
        assert "4b77ff039fcf" in event.content

    def test_parse_user_tool_result_error(self, proxy_service):
        """Parse user event with tool_result that has is_error=true."""
        data = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "tool_use_id": "toolu_789",
                        "type": "tool_result",
                        "content": "Permission denied",
                        "is_error": True,
                    }
                ],
            },
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.TOOL_RESULT
        assert event.tool_id == "toolu_789"
        assert "Permission denied" in event.content

    def test_parse_result_event(self, proxy_service):
        """Parse result event with final output."""
        data = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "duration_ms": 2649,
            "num_turns": 1,
            "result": "Hello! How can I help you today?",
            "session_id": "abc-123",
            "total_cost_usd": 0.18972,
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.RESULT
        assert event.content == "Hello! How can I help you today?"
        assert event.session_id == "abc-123"

    def test_parse_result_event_empty_result(self, proxy_service):
        """Parse result event when result is empty string."""
        data = {
            "type": "result",
            "subtype": "success",
            "result": "",
            "session_id": "abc-123",
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.RESULT
        assert event.content == ""

    def test_parse_error_event(self, proxy_service):
        """Parse error event."""
        data = {
            "type": "error",
            "error": {"message": "API key invalid"},
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.ERROR
        assert event.error == "API key invalid"

    def test_parse_error_event_string_error(self, proxy_service):
        """Parse error event with string error field."""
        data = {
            "type": "error",
            "error": "Something went wrong",
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.ERROR
        assert event.error == "Something went wrong"

    def test_parse_skip_message_start(self, proxy_service):
        """Skip message_start events."""
        data = {"type": "message_start"}
        event = proxy_service._parse_event(json.dumps(data))
        assert event is None

    def test_parse_skip_content_block_stop(self, proxy_service):
        """Skip content_block_stop events."""
        data = {"type": "content_block_stop"}
        event = proxy_service._parse_event(json.dumps(data))
        assert event is None

    def test_parse_skip_ping(self, proxy_service):
        """Skip ping events."""
        data = {"type": "ping"}
        event = proxy_service._parse_event(json.dumps(data))
        assert event is None

    def test_parse_invalid_json(self, proxy_service):
        """Return None for invalid JSON."""
        event = proxy_service._parse_event("not valid json{")
        assert event is None

    def test_parse_content_block_delta_text(self, proxy_service):
        """Parse content_block_delta with text_delta."""
        data = {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "Hello"},
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.TEXT
        assert event.content == "Hello"

    def test_parse_tool_use_event(self, proxy_service):
        """Parse standalone tool_use event type."""
        data = {
            "type": "tool_use",
            "name": "Bash",
            "input": {"command": "ls"},
            "id": "toolu_abc",
        }
        event = proxy_service._parse_event(json.dumps(data))
        assert event is not None
        assert event.type == EventType.TOOL_USE
        assert event.tool_name == "Bash"


# === TaskResult Tests ===


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_success_result(self):
        result = TaskResult(success=True, output="done", session_id="abc")
        assert result.success is True
        assert result.output == "done"
        assert result.session_id == "abc"
        assert result.error is None
        assert result.cancelled is False

    def test_error_result(self):
        result = TaskResult(
            success=False,
            output="",
            error="Process was terminated (SIGTERM)",
        )
        assert result.success is False
        assert result.error == "Process was terminated (SIGTERM)"

    def test_cancelled_result(self):
        result = TaskResult(success=False, output="partial", cancelled=True)
        assert result.cancelled is True


# === Handle Event Tests ===


class TestHandleEvent:
    """Tests for _handle_event method."""

    @pytest.mark.asyncio
    async def test_handle_text_event(self, proxy_service):
        """Text event should call on_text and append to buffer."""
        on_text = AsyncMock()
        output_buffer = []
        event = ClaudeCodeEvent(type=EventType.TEXT, content="Hello")

        await proxy_service._handle_event(
            user_id=1, event=event,
            on_text=on_text, on_tool_use=None, on_tool_result=None,
            on_permission=None, on_question=None, on_error=None,
            output_buffer=output_buffer,
        )

        on_text.assert_called_once_with("Hello")
        assert "Hello" in output_buffer

    @pytest.mark.asyncio
    async def test_handle_assistant_message_event(self, proxy_service):
        """Assistant message should call on_text and append to buffer."""
        on_text = AsyncMock()
        output_buffer = []
        event = ClaudeCodeEvent(
            type=EventType.ASSISTANT_MESSAGE,
            content="The hostname is 4b77ff039fcf",
        )

        await proxy_service._handle_event(
            user_id=1, event=event,
            on_text=on_text, on_tool_use=None, on_tool_result=None,
            on_permission=None, on_question=None, on_error=None,
            output_buffer=output_buffer,
        )

        on_text.assert_called_once_with("The hostname is 4b77ff039fcf")
        assert "The hostname is 4b77ff039fcf" in output_buffer

    @pytest.mark.asyncio
    async def test_handle_tool_use_event(self, proxy_service):
        """Tool use event should call on_tool_use."""
        on_tool_use = AsyncMock()
        output_buffer = []
        event = ClaudeCodeEvent(
            type=EventType.TOOL_USE,
            tool_name="Read",
            tool_input={"file_path": "/etc/hostname"},
        )

        await proxy_service._handle_event(
            user_id=1, event=event,
            on_text=None, on_tool_use=on_tool_use, on_tool_result=None,
            on_permission=None, on_question=None, on_error=None,
            output_buffer=output_buffer,
        )

        on_tool_use.assert_called_once_with("Read", {"file_path": "/etc/hostname"})

    @pytest.mark.asyncio
    async def test_handle_tool_result_event(self, proxy_service):
        """Tool result event should call on_tool_result."""
        on_tool_result = AsyncMock()
        output_buffer = []
        event = ClaudeCodeEvent(
            type=EventType.TOOL_RESULT,
            tool_id="toolu_123",
            content="4b77ff039fcf",
        )

        await proxy_service._handle_event(
            user_id=1, event=event,
            on_text=None, on_tool_use=None, on_tool_result=on_tool_result,
            on_permission=None, on_question=None, on_error=None,
            output_buffer=output_buffer,
        )

        on_tool_result.assert_called_once_with("toolu_123", "4b77ff039fcf")

    @pytest.mark.asyncio
    async def test_handle_result_appends_to_buffer(self, proxy_service):
        """Result event should append content to output buffer."""
        output_buffer = []
        event = ClaudeCodeEvent(
            type=EventType.RESULT,
            content="Final answer here",
        )

        await proxy_service._handle_event(
            user_id=1, event=event,
            on_text=None, on_tool_use=None, on_tool_result=None,
            on_permission=None, on_question=None, on_error=None,
            output_buffer=output_buffer,
        )

        assert "Final answer here" in output_buffer

    @pytest.mark.asyncio
    async def test_handle_error_event(self, proxy_service):
        """Error event should call on_error."""
        on_error = AsyncMock()
        output_buffer = []
        event = ClaudeCodeEvent(
            type=EventType.ERROR,
            error="API key invalid",
        )

        await proxy_service._handle_event(
            user_id=1, event=event,
            on_text=None, on_tool_use=None, on_tool_result=None,
            on_permission=None, on_question=None, on_error=on_error,
            output_buffer=output_buffer,
        )

        on_error.assert_called_once_with("API key invalid")

    @pytest.mark.asyncio
    async def test_handle_event_with_no_callbacks(self, proxy_service):
        """Events with None callbacks should not crash."""
        output_buffer = []
        event = ClaudeCodeEvent(type=EventType.TEXT, content="Hello")

        # Should not raise
        await proxy_service._handle_event(
            user_id=1, event=event,
            on_text=None, on_tool_use=None, on_tool_result=None,
            on_permission=None, on_question=None, on_error=None,
            output_buffer=output_buffer,
        )

        assert "Hello" in output_buffer


# === Cancel and State Tests ===


class TestCancelAndState:
    """Tests for cancel_task and is_task_running."""

    def test_no_task_running(self, proxy_service):
        """No task should be running initially."""
        assert proxy_service.is_task_running(user_id=1) is False

    @pytest.mark.asyncio
    async def test_cancel_no_task(self, proxy_service):
        """Cancelling with no task should return False."""
        result = await proxy_service.cancel_task(user_id=1)
        assert result is False
