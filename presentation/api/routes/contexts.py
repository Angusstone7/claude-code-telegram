"""Context management endpoints for project contexts."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from presentation.api.dependencies import get_context_service, get_container
from presentation.api.schemas.contexts import (
    ContextListResponse,
    ContextResponse,
    CreateContextRequest,
)
from presentation.api.security import hybrid_auth
from domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/contexts", tags=["Contexts"])


def _resolve_user_id(user: dict) -> int:
    """Extract numeric user ID from auth context."""
    if user.get("auth_method") == "jwt":
        # JWT user_id is a string; may already be numeric
        try:
            return int(user["user_id"])
        except (ValueError, TypeError):
            pass
    # Fallback to default admin ID
    container = get_container()
    admin_ids = container.config.admin_ids
    return admin_ids[0] if admin_ids else 0


@router.get(
    "",
    response_model=ContextListResponse,
    summary="List contexts",
    description="Returns all contexts for the given project.",
)
async def list_contexts(
    project_id: str,
    user: dict = Depends(hybrid_auth),
) -> ContextListResponse:
    """List all contexts for a project."""
    service = get_context_service()
    contexts = await service.list_contexts(project_id)

    items = [
        ContextResponse(
            id=ctx.id,
            name=ctx.name,
            is_active=ctx.is_current,
            message_count=ctx.message_count,
            created_at=getattr(ctx, "created_at", None),
        )
        for ctx in contexts
    ]

    return ContextListResponse(contexts=items, total=len(items))


@router.post(
    "",
    response_model=ContextResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create context",
    description="Create a new context for the project.",
)
async def create_context(
    project_id: str,
    request: CreateContextRequest,
    user: dict = Depends(hybrid_auth),
) -> ContextResponse:
    """Create a new context."""
    uid = UserId(_resolve_user_id(user))
    service = get_context_service()

    try:
        ctx = await service.create_new(
            project_id=project_id,
            user_id=uid,
            name=request.name,
            set_as_current=False,
        )
    except Exception as e:
        logger.error(f"Failed to create context: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    return ContextResponse(
        id=ctx.id,
        name=ctx.name,
        is_active=ctx.is_current,
        message_count=ctx.message_count,
        created_at=getattr(ctx, "created_at", None),
    )


@router.post(
    "/{context_id}/activate",
    response_model=ContextResponse,
    summary="Activate context",
    description="Set a context as the active/current context for the project.",
)
async def activate_context(
    project_id: str,
    context_id: str,
    user: dict = Depends(hybrid_auth),
) -> ContextResponse:
    """Activate (switch to) a context."""
    service = get_context_service()

    ctx = await service.switch_context(project_id, context_id)
    if not ctx:
        raise HTTPException(
            status_code=404,
            detail="Context not found or does not belong to this project.",
        )

    return ContextResponse(
        id=ctx.id,
        name=ctx.name,
        is_active=True,
        message_count=ctx.message_count,
        created_at=getattr(ctx, "created_at", None),
    )


@router.delete(
    "/{context_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete context",
    description="Delete a context and all its messages.",
)
async def delete_context(
    project_id: str,
    context_id: str,
    user: dict = Depends(hybrid_auth),
) -> None:
    """Delete a context."""
    service = get_context_service()

    # Verify context belongs to project
    ctx = await service.get_by_id(context_id)
    if not ctx or ctx.project_id != project_id:
        raise HTTPException(status_code=404, detail="Context not found.")

    deleted = await service.delete_context(context_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Context not found.")


@router.delete(
    "/{context_id}/messages",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear messages",
    description="Clear all messages in a context without deleting it.",
)
async def clear_messages(
    project_id: str,
    context_id: str,
    user: dict = Depends(hybrid_auth),
) -> None:
    """Clear all messages in a context."""
    service = get_context_service()

    # Verify context belongs to project
    ctx = await service.get_by_id(context_id)
    if not ctx or ctx.project_id != project_id:
        raise HTTPException(status_code=404, detail="Context not found.")

    await service.clear_messages(context_id)
