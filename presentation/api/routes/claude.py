"""Claude task execution endpoints."""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from presentation.api.dependencies import get_claude_sdk, get_claude_proxy, get_container
from presentation.api.schemas.claude import TaskRequest, TaskResponse
from presentation.api.security import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/claude", tags=["Claude"], dependencies=[Depends(verify_api_key)])


def _get_default_user_id() -> int:
    """Get the default (admin) user ID from config."""
    container = get_container()
    admin_ids = container.config.admin_ids
    return admin_ids[0] if admin_ids else 0


@router.post(
    "/task",
    response_model=TaskResponse,
    summary="Submit Claude task",
    description="Submit a task to Claude and wait for completion. "
    "This is a synchronous endpoint — it blocks until the task finishes.",
)
async def submit_task(request: TaskRequest) -> TaskResponse:
    """
    Submit a task to Claude Code.

    Uses SDK backend if available, falls back to CLI proxy.
    Note: This endpoint runs the task to completion (blocking).
    For long-running tasks, consider setting max_turns.
    """
    sdk = get_claude_sdk()
    user_id = _get_default_user_id()
    start_time = time.time()

    if not sdk:
        raise HTTPException(
            status_code=503,
            detail="Claude SDK backend not available. Cannot execute tasks via API.",
        )

    try:
        # Run task via SDK in permissive mode (no HITL for API calls)
        result = await sdk.run_task(
            user_id=user_id,
            prompt=request.prompt,
            working_dir=request.working_dir,
            session_id=request.session_id,
            max_turns=request.max_turns or 25,
            permission_mode="acceptEdits",
            # No UI callbacks for API mode
            on_message=None,
            on_error=None,
            on_input_request=None,
            on_plan_request=None,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        return TaskResponse(
            status="completed" if result.get("success") else "error",
            result=result.get("output", ""),
            session_id=result.get("session_id"),
            cost_usd=result.get("cost_usd"),
            duration_ms=duration_ms,
            num_turns=result.get("num_turns"),
        )

    except asyncio.TimeoutError:
        return TaskResponse(
            status="timeout",
            result="Task timed out",
            duration_ms=int((time.time() - start_time) * 1000),
        )
    except Exception as e:
        logger.error(f"API task execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")


# Fix missing import
import asyncio
