"""Session management endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from presentation.api.dependencies import get_bot_service, get_container
from presentation.api.schemas.sessions import SessionListResponse, SessionResponse
from presentation.api.security import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["Sessions"], dependencies=[Depends(verify_api_key)])


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List sessions",
    description="Returns active session info for the user. "
    "Note: Full session listing requires database query extension.",
)
async def list_sessions(
    user_id: Optional[int] = Query(None, description="User ID (defaults to admin)"),
) -> SessionListResponse:
    """List sessions — returns current active session if exists."""
    container = get_container()
    admin_ids = container.config.admin_ids
    uid = user_id or (admin_ids[0] if admin_ids else 0)

    service = get_bot_service()

    items = []
    try:
        # Get active session for the user
        session = await service.get_or_create_session(uid)
        if session:
            items.append(
                SessionResponse(
                    session_id=session.session_id,
                    user_id=uid,
                    message_count=len(session.messages) if hasattr(session, "messages") else 0,
                    created_at=getattr(session, "created_at", None),
                    is_active=True,
                )
            )
    except Exception as e:
        logger.warning(f"Failed to get session for user {uid}: {e}")

    return SessionListResponse(sessions=items, total=len(items))
