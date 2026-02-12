"""Project management endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from presentation.api.dependencies import get_project_service, get_container
from presentation.api.schemas.projects import (
    CreateProjectRequest,
    ProjectListResponse,
    ProjectResponse,
)
from presentation.api.security import hybrid_auth
from domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["Projects"])


def _get_default_user_id() -> int:
    """Get the default (admin) user ID from config."""
    container = get_container()
    admin_ids = container.config.admin_ids
    return admin_ids[0] if admin_ids else 0


def _resolve_user_id(user: dict, query_user_id: Optional[int] = None) -> int:
    """
    Resolve the effective user ID.

    For JWT auth, prefer user_id from claims.
    For API Key auth, use query parameter or fallback to default admin.
    """
    if user.get("auth_method") == "jwt":
        try:
            return int(user["user_id"])
        except (ValueError, TypeError):
            pass
    # API Key or dev-mode: use query param or default
    return query_user_id or _get_default_user_id()


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects",
    description="Returns all projects for the authenticated user.",
)
async def list_projects(
    user: dict = Depends(hybrid_auth),
    user_id: Optional[int] = Query(None, description="User ID (defaults to admin, used with API Key auth)"),
) -> ProjectListResponse:
    """List all projects."""
    uid = UserId(_resolve_user_id(user, user_id))
    service = get_project_service()

    projects = await service.list_projects(uid)

    # Get current project for is_current flag
    current = await service.get_current(uid)
    current_id = current.id if current else None

    items = [
        ProjectResponse(
            id=p.id,
            name=p.name,
            path=str(p.path) if hasattr(p, "path") else "",
            is_current=(p.id == current_id) if current_id else False,
            created_at=getattr(p, "created_at", None),
        )
        for p in projects
    ]

    return ProjectListResponse(projects=items, total=len(items))


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new project with the given name.",
)
async def create_project(
    request: CreateProjectRequest,
    user: dict = Depends(hybrid_auth),
    user_id: Optional[int] = Query(None, description="User ID (defaults to admin, used with API Key auth)"),
) -> ProjectResponse:
    """Create a new project."""
    uid = UserId(_resolve_user_id(user, user_id))
    service = get_project_service()

    path = request.path or f"/root/projects/{request.name}"

    try:
        project = await service.create_project(uid, request.name, path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProjectResponse(
        id=project.id,
        name=project.name,
        path=str(project.path) if hasattr(project, "path") else "",
        is_current=False,
        created_at=getattr(project, "created_at", None),
    )


@router.post(
    "/{project_id}/activate",
    response_model=ProjectResponse,
    summary="Activate project",
    description="Set a project as the current/active project.",
)
async def activate_project(
    project_id: str,
    user: dict = Depends(hybrid_auth),
    user_id: Optional[int] = Query(None, description="User ID"),
) -> ProjectResponse:
    """Activate (switch to) a project."""
    uid = UserId(_resolve_user_id(user, user_id))
    service = get_project_service()

    project = await service.switch_project(uid, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project.id,
        name=project.name,
        path=str(project.path) if hasattr(project, "path") else "",
        is_current=True,
        created_at=getattr(project, "created_at", None),
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project",
    description="Get project details by ID.",
)
async def get_project(
    project_id: str,
    user: dict = Depends(hybrid_auth),
    user_id: Optional[int] = Query(None, description="User ID (defaults to admin, used with API Key auth)"),
) -> ProjectResponse:
    """Get a specific project by ID."""
    uid = UserId(_resolve_user_id(user, user_id))
    service = get_project_service()

    project = await service.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    current = await service.get_current(uid)
    is_current = current and current.id == project.id

    return ProjectResponse(
        id=project.id,
        name=project.name,
        path=str(project.path) if hasattr(project, "path") else "",
        is_current=bool(is_current),
        created_at=getattr(project, "created_at", None),
    )
