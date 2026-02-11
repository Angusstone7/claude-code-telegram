"""Chat message history and task status endpoints."""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from presentation.api.dependencies import get_container
from presentation.api.security import hybrid_auth

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chat"])


# ==================== Schemas ====================


class ToolInput(BaseModel):
    """Dynamic tool input — schema varies per tool."""

    model_config = ConfigDict(extra="allow")


class ChatMessageResponse(BaseModel):
    id: int
    role: str  # "user" | "assistant" | "system"
    content: str
    tool_use: Optional[ToolInput] = None
    created_at: datetime


class MessageListResponse(BaseModel):
    messages: list[ChatMessageResponse]
    total: int


class TaskStatusResponse(BaseModel):
    session_id: str
    status: str  # "idle" | "running" | "completed" | "error"
    started_at: Optional[datetime] = None
    message: Optional[str] = None


# ==================== Endpoints ====================


@router.get(
    "/projects/{project_id}/contexts/{context_id}/messages",
    response_model=MessageListResponse,
    summary="Get message history",
    description="Returns message history for a specific project context.",
)
async def get_context_messages(
    project_id: str,
    context_id: str,
    limit: int = Query(50, ge=1, le=500, description="Max messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    _user: dict = Depends(hybrid_auth),
) -> MessageListResponse:
    """
    Get message history for a context.

    Retrieves messages from the context repository ordered chronologically.
    The context must belong to the specified project.
    """
    container = get_container()

    try:
        context_repo = container.context_repository()
    except Exception:
        raise HTTPException(
            status_code=501,
            detail="Context repository not available.",
        )

    # Verify context exists and belongs to the specified project
    context = await context_repo.find_by_id(context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Context not found.")
    if context.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Context does not belong to this project.",
        )

    # Fetch messages via repository (returns List[ContextMessage])
    messages = await context_repo.get_messages(context_id, limit=limit, offset=offset)

    items = [
        ChatMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            tool_use=(
                ToolInput(tool_name=msg.tool_name, tool_result=msg.tool_result)
                if msg.tool_name
                else None
            ),
            created_at=msg.timestamp,
        )
        for msg in messages
    ]

    # Total count: context stores message_count
    total = context.message_count

    return MessageListResponse(messages=items, total=total)


@router.get(
    "/claude/task/{session_id}/status",
    response_model=TaskStatusResponse,
    summary="Get task status",
    description="Returns the current status of a Claude task for the given session.",
)
async def get_task_status(
    session_id: str,
    _user: dict = Depends(hybrid_auth),
) -> TaskStatusResponse:
    """
    Get current task status.

    The session_id is treated as a user_id (int) for the SDK service lookup.
    If the SDK service is not available, returns idle status.
    """
    container = get_container()
    sdk = container.claude_sdk()

    if not sdk:
        return TaskStatusResponse(
            session_id=session_id,
            status="idle",
            message="SDK backend not available.",
        )

    # session_id may map to a user_id (int); try to parse it
    try:
        user_id = int(session_id)
    except (ValueError, TypeError):
        # If session_id is not an integer, we cannot look up task status directly.
        # Return idle with explanation.
        return TaskStatusResponse(
            session_id=session_id,
            status="idle",
            message="Session ID is not a numeric user ID; cannot determine task status.",
        )

    task_status = sdk.get_task_status(user_id)

    # Map SDK TaskStatus enum to simplified API status string
    status_mapping = {
        "idle": "idle",
        "running": "running",
        "waiting_permission": "running",
        "waiting_answer": "running",
        "completed": "completed",
        "failed": "error",
        "cancelled": "error",
    }
    api_status = status_mapping.get(task_status.value, "idle")

    return TaskStatusResponse(
        session_id=session_id,
        status=api_status,
        message=f"Task status: {task_status.value}",
    )
