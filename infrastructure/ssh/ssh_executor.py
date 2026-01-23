import asyncio
import logging
from typing import Tuple, Optional
from domain.services.command_execution_service import ICommandExecutionService, CommandExecutionResult
from shared.config.settings import settings

logger = logging.getLogger(__name__)


class SSHCommandExecutor(ICommandExecutionService):
    """SSH-based command execution service"""

    def __init__(self, ssh_config=None):
        self.config = ssh_config or settings.ssh

    async def execute(self, command: str, timeout: int = 300) -> CommandExecutionResult:
        """Execute command via SSH"""
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-i", self.config.key_path,
            f"{self.config.user}@{self.config.host}",
            "-p", str(self.config.port),
            command
        ]

        logger.info(f"Executing SSH command: {command[:100]}...")

        try:
            start_time = asyncio.get_event_loop().time()
            process = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise TimeoutError(f"Command timed out after {timeout} seconds")

            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time

            stdout_str = stdout.decode('utf-8', errors='replace').strip()
            stderr_str = stderr.decode('utf-8', errors='replace').strip()
            exit_code = process.returncode or 0

            return CommandExecutionResult(
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=exit_code,
                execution_time=execution_time
            )

        except FileNotFoundError:
            return CommandExecutionResult(
                stdout="",
                stderr="SSH client not found. Please ensure openssh-client is installed.",
                exit_code=1,
                execution_time=0
            )
        except Exception as e:
            logger.error(f"SSH execution error: {e}")
            return CommandExecutionResult(
                stdout="",
                stderr=f"SSH Execution Error: {str(e)}",
                exit_code=1,
                execution_time=0
            )

    async def execute_script(self, script: str, timeout: int = 300) -> CommandExecutionResult:
        """Execute multi-line script via SSH"""
        # Escape the script for shell
        escaped_script = script.replace("'", "'\\''")
        command = f"bash -c '{escaped_script}'"
        return await self.execute(command, timeout)

    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Validate command for safety"""
        dangerous_patterns = [
            ("rm -rf /", "Attempting to remove root directory"),
            ("mkfs", "Attempting to format filesystem"),
            ("> /dev/sda", "Attempting to write directly to disk"),
            ("dd if=", "Using dd command which can destroy data"),
            ("shutdown", "Attempting to shutdown system"),
            ("reboot", "Attempting to reboot system"),
            ("init 0", "Attempting to change runlevel to 0"),
            ("chmod 000", "Attempting to remove all permissions"),
        ]

        command_lower = command.lower()
        for pattern, reason in dangerous_patterns:
            if pattern in command_lower:
                return False, f"Dangerous command detected: {reason}"

        # Check for suspicious shell constructs
        suspicious = ["&& rm", "; rm", "| rm", "> /dev/null", "&>/dev/null"]
        for susp in suspicious:
            if susp in command_lower and "rm" in command_lower:
                return False, f"Potentially dangerous command: contains '{susp}'"

        return True, None
