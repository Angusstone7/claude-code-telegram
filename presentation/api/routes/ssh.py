"""SSH command execution endpoints."""

import logging
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from presentation.api.dependencies import get_container
from presentation.api.schemas.ssh import (
    SSHCommandRequest,
    SSHCommandResponse,
    SSHHistoryResponse,
)
from presentation.api.security import get_current_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ssh", tags=["SSH"])

# In-memory history — recent commands kept for the current process lifetime.
# Max 200 entries to avoid unbounded growth.
_command_history: deque[SSHCommandResponse] = deque(maxlen=200)


@router.post(
    "/execute",
    response_model=SSHCommandResponse,
    summary="Execute SSH command",
    description=(
        "Execute a command on the remote host via SSH. "
        "Requires admin privileges. The command is validated for safety before execution."
    ),
)
async def execute_ssh_command(
    body: SSHCommandRequest,
    _user: dict = Depends(get_current_admin),
) -> SSHCommandResponse:
    """Execute a command via SSH and return the result."""
    container = get_container()
    executor = container.command_executor()

    # Validate command safety
    is_valid, error_msg = executor.validate_command(body.command)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Command rejected: {error_msg}",
        )

    logger.info(
        "SSH execute: user=%s command=%s timeout=%d",
        _user.get("username", "?"),
        body.command[:100],
        body.timeout,
    )

    try:
        result = await executor.execute(body.command, timeout=body.timeout)
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=f"Command timed out after {body.timeout} seconds.",
        )
    except Exception as e:
        logger.error("SSH execution error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SSH execution failed: {str(e)}",
        )

    # Combine stdout and stderr into output
    output = result.stdout
    if result.stderr:
        if output:
            output += "\n"
        output += result.stderr

    duration_ms = int(result.execution_time * 1000)

    response = SSHCommandResponse(
        command=body.command,
        output=output,
        exit_code=result.exit_code,
        executed_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
    )

    # Append to history
    _command_history.append(response)

    return response


@router.get(
    "/history",
    response_model=SSHHistoryResponse,
    summary="SSH command history",
    description="Returns recently executed SSH commands (in-memory, current process only).",
)
async def ssh_history(
    limit: int = 50,
    _user: dict = Depends(get_current_admin),
) -> SSHHistoryResponse:
    """Return recent SSH command history."""
    # Return most recent first, up to limit
    items = list(reversed(_command_history))[:limit]
    return SSHHistoryResponse(commands=items, total=len(_command_history))
