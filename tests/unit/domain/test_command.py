"""Unit tests for Command entity."""

import pytest
from datetime import datetime
import time
from domain.entities.command import Command, CommandStatus


class TestCommand:
    """Tests for Command entity."""

    def test_create_command(self):
        """Test creating a command."""
        cmd = Command(
            command_id="cmd-123",
            user_id=12345,
            command="ls -la"
        )

        assert cmd.command_id == "cmd-123"
        assert cmd.user_id == 12345
        assert cmd.command == "ls -la"
        assert cmd.status == CommandStatus.PENDING
        assert cmd.output is None
        assert cmd.error is None
        assert cmd.exit_code is None
        assert cmd.created_at is not None

    def test_command_created_at_auto_set(self):
        """Test that created_at is auto-set."""
        before = datetime.utcnow()
        cmd = Command(command_id="test", user_id=1, command="echo")
        after = datetime.utcnow()

        assert before <= cmd.created_at <= after

    def test_approve_pending_command(self, command):
        """Test approving a pending command."""
        assert command.status == CommandStatus.PENDING

        command.approve()

        assert command.status == CommandStatus.APPROVED

    def test_approve_non_pending_raises_error(self, approved_command):
        """Test approving non-pending command raises error."""
        with pytest.raises(ValueError, match="Cannot approve command with status"):
            approved_command.approve()

    def test_reject_pending_command(self, command):
        """Test rejecting a pending command."""
        command.reject("Not allowed")

        assert command.status == CommandStatus.REJECTED
        assert command.error == "Not allowed"

    def test_reject_approved_command(self, approved_command):
        """Test rejecting an approved command."""
        approved_command.reject("Changed mind")

        assert approved_command.status == CommandStatus.REJECTED
        assert approved_command.error == "Changed mind"

    def test_reject_default_reason(self, command):
        """Test rejecting with default reason."""
        command.reject()

        assert command.error == "Command rejected by user"

    def test_reject_running_command_raises_error(self, approved_command):
        """Test rejecting running command raises error."""
        approved_command.start_execution()

        with pytest.raises(ValueError, match="Cannot reject command with status"):
            approved_command.reject()

    def test_start_execution(self, approved_command):
        """Test starting command execution."""
        before = datetime.utcnow()

        approved_command.start_execution()

        after = datetime.utcnow()
        assert approved_command.status == CommandStatus.RUNNING
        assert before <= approved_command.started_at <= after

    def test_start_execution_pending_raises_error(self, command):
        """Test starting execution of pending command raises error."""
        with pytest.raises(ValueError, match="Cannot start command with status"):
            command.start_execution()

    def test_complete_command(self, approved_command):
        """Test completing a command."""
        approved_command.start_execution()

        approved_command.complete("output text", exit_code=0)

        assert approved_command.status == CommandStatus.COMPLETED
        assert approved_command.output == "output text"
        assert approved_command.exit_code == 0
        assert approved_command.completed_at is not None

    def test_complete_calculates_execution_time(self, approved_command):
        """Test that complete calculates execution time."""
        approved_command.start_execution()
        time.sleep(0.01)  # Small delay

        approved_command.complete("done")

        assert approved_command.execution_time is not None
        assert approved_command.execution_time >= 0.01

    def test_complete_non_running_raises_error(self, approved_command):
        """Test completing non-running command raises error."""
        with pytest.raises(ValueError, match="Cannot complete command with status"):
            approved_command.complete("output")

    def test_fail_command(self, approved_command):
        """Test failing a command."""
        approved_command.start_execution()

        approved_command.fail("Connection refused")

        assert approved_command.status == CommandStatus.FAILED
        assert approved_command.error == "Connection refused"
        assert approved_command.completed_at is not None

    def test_fail_calculates_execution_time(self, approved_command):
        """Test that fail calculates execution time."""
        approved_command.start_execution()
        time.sleep(0.01)

        approved_command.fail("error")

        assert approved_command.execution_time is not None
        assert approved_command.execution_time >= 0.01

    def test_fail_non_running_raises_error(self, command):
        """Test failing non-running command raises error."""
        with pytest.raises(ValueError, match="Cannot fail command with status"):
            command.fail("error")

    def test_is_dangerous_rm_rf(self, dangerous_command):
        """Test dangerous command detection for rm -rf."""
        assert dangerous_command.is_dangerous is True

    def test_is_dangerous_safe_command(self, command):
        """Test safe command is not marked dangerous."""
        assert command.is_dangerous is False

    def test_is_dangerous_various_keywords(self):
        """Test various dangerous keywords."""
        dangerous_commands = [
            "mkfs.ext4 /dev/sda",
            "dd if=/dev/zero of=/dev/sda",
            "shutdown -h now",
            "reboot",
            "init 0",
            "halt",
            "chmod 000 /etc/passwd",
            "chown -R root:root /",
            "kill -9 1",
        ]

        for cmd_text in dangerous_commands:
            cmd = Command(command_id="test", user_id=1, command=cmd_text)
            assert cmd.is_dangerous is True, f"'{cmd_text}' should be dangerous"

    def test_is_dangerous_case_insensitive(self):
        """Test dangerous detection is case insensitive."""
        cmd = Command(command_id="test", user_id=1, command="RM -RF /tmp")
        assert cmd.is_dangerous is True

    def test_duration_property(self, approved_command):
        """Test duration property."""
        approved_command.start_execution()
        time.sleep(0.01)
        approved_command.complete("done")

        assert approved_command.duration is not None
        assert approved_command.duration == approved_command.execution_time

    def test_duration_none_before_completion(self, command):
        """Test duration is None before completion."""
        assert command.duration is None


class TestCommandStatusTransitions:
    """Tests for command status state machine."""

    def test_full_success_flow(self):
        """Test full successful command flow: PENDING -> APPROVED -> RUNNING -> COMPLETED."""
        cmd = Command(command_id="test", user_id=1, command="echo hello")

        assert cmd.status == CommandStatus.PENDING

        cmd.approve()
        assert cmd.status == CommandStatus.APPROVED

        cmd.start_execution()
        assert cmd.status == CommandStatus.RUNNING

        cmd.complete("hello", exit_code=0)
        assert cmd.status == CommandStatus.COMPLETED

    def test_full_failure_flow(self):
        """Test failed command flow: PENDING -> APPROVED -> RUNNING -> FAILED."""
        cmd = Command(command_id="test", user_id=1, command="bad_command")

        cmd.approve()
        cmd.start_execution()
        cmd.fail("command not found")

        assert cmd.status == CommandStatus.FAILED

    def test_rejection_flow(self):
        """Test rejection flow: PENDING -> REJECTED."""
        cmd = Command(command_id="test", user_id=1, command="dangerous")

        cmd.reject("Too dangerous")

        assert cmd.status == CommandStatus.REJECTED
