"""Variable management endpoints for project context variables."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from presentation.api.dependencies import get_context_service, get_container
from presentation.api.schemas.variables import (
    CreateVariableRequest,
    UpdateVariableRequest,
    VariableListResponse,
    VariableResponse,
)
from presentation.api.security import hybrid_auth
from domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/variables", tags=["Variables"])


def _resolve_user_id(user: dict) -> int:
    """Extract numeric user ID from auth context."""
    if user.get("auth_method") == "jwt":
        try:
            return int(user["user_id"])
        except (ValueError, TypeError):
            pass
    container = get_container()
    admin_ids = container.config.admin_ids
    return admin_ids[0] if admin_ids else 0


async def _get_active_context_id(project_id: str) -> Optional[str]:
    """Get the active context ID for a project, or None."""
    service = get_context_service()
    ctx = await service.get_current(project_id)
    return ctx.id if ctx else None


def _var_to_response(name: str, var, scope: str, idx: int) -> VariableResponse:
    """Convert a ContextVariable to VariableResponse."""
    return VariableResponse(
        id=idx,
        name=var.name,
        value=var.value,
        description=var.description or None,
        scope=scope,
        created_at=None,
        updated_at=None,
    )


@router.get(
    "",
    response_model=VariableListResponse,
    summary="List variables",
    description="Returns variables for the project. "
    "Use ?scope=local|global|all to filter (default: all).",
)
async def list_variables(
    project_id: str,
    scope: str = Query("all", pattern=r"^(local|global|all)$", description="Scope filter"),
    user: dict = Depends(hybrid_auth),
) -> VariableListResponse:
    """List variables for a project (local, global, or both)."""
    service = get_context_service()
    uid = UserId(_resolve_user_id(user))
    items: list[VariableResponse] = []
    idx = 1

    # Local variables come from the active context
    if scope in ("local", "all"):
        context_id = await _get_active_context_id(project_id)
        if context_id:
            local_vars = await service.get_variables(context_id)
            for name, var in sorted(local_vars.items()):
                items.append(_var_to_response(name, var, "local", idx))
                idx += 1

    # Global variables
    if scope in ("global", "all"):
        global_vars = await service.get_global_variables(uid)
        for name, var in sorted(global_vars.items()):
            items.append(_var_to_response(name, var, "global", idx))
            idx += 1

    return VariableListResponse(variables=items, total=len(items))


@router.post(
    "",
    response_model=VariableResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create variable",
    description="Create a new variable in local (context) or global scope.",
)
async def create_variable(
    project_id: str,
    request: CreateVariableRequest,
    user: dict = Depends(hybrid_auth),
) -> VariableResponse:
    """Create a new variable."""
    service = get_context_service()
    uid = UserId(_resolve_user_id(user))

    try:
        if request.scope == "global":
            await service.set_global_variable(
                user_id=uid,
                name=request.name,
                value=request.value,
                description=request.description or "",
            )
        else:
            # Local variable — requires active context
            context_id = await _get_active_context_id(project_id)
            if not context_id:
                raise HTTPException(
                    status_code=400,
                    detail="No active context for this project. Create or activate a context first.",
                )
            await service.set_variable(
                context_id=context_id,
                name=request.name,
                value=request.value,
                description=request.description or "",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create variable: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    return VariableResponse(
        id=0,
        name=request.name,
        value=request.value,
        description=request.description,
        scope=request.scope,
        created_at=None,
        updated_at=None,
    )


@router.put(
    "/{variable_name}",
    response_model=VariableResponse,
    summary="Update variable",
    description="Update an existing variable by name. "
    "Specify ?scope=local|global to target the correct scope (default: local).",
)
async def update_variable(
    project_id: str,
    variable_name: str,
    request: UpdateVariableRequest,
    scope: str = Query("local", pattern=r"^(local|global)$", description="Variable scope"),
    user: dict = Depends(hybrid_auth),
) -> VariableResponse:
    """Update an existing variable."""
    service = get_context_service()
    uid = UserId(_resolve_user_id(user))

    if scope == "global":
        existing = await service.get_global_variable(uid, variable_name)
        if not existing:
            raise HTTPException(status_code=404, detail="Global variable not found.")
        new_value = request.value if request.value is not None else existing.value
        new_desc = request.description if request.description is not None else existing.description
        await service.set_global_variable(uid, variable_name, new_value, new_desc)
    else:
        context_id = await _get_active_context_id(project_id)
        if not context_id:
            raise HTTPException(
                status_code=400,
                detail="No active context for this project.",
            )
        existing = await service.get_variable(context_id, variable_name)
        if not existing:
            raise HTTPException(status_code=404, detail="Local variable not found.")
        new_value = request.value if request.value is not None else existing.value
        new_desc = request.description if request.description is not None else existing.description
        await service.set_variable(context_id, variable_name, new_value, new_desc)

    return VariableResponse(
        id=0,
        name=variable_name,
        value=new_value,
        description=new_desc or None,
        scope=scope,
        created_at=None,
        updated_at=None,
    )


@router.delete(
    "/{variable_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete variable",
    description="Delete a variable by name. "
    "Specify ?scope=local|global to target the correct scope (default: local).",
)
async def delete_variable(
    project_id: str,
    variable_name: str,
    scope: str = Query("local", pattern=r"^(local|global)$", description="Variable scope"),
    user: dict = Depends(hybrid_auth),
) -> None:
    """Delete a variable."""
    service = get_context_service()
    uid = UserId(_resolve_user_id(user))

    if scope == "global":
        deleted = await service.delete_global_variable(uid, variable_name)
    else:
        context_id = await _get_active_context_id(project_id)
        if not context_id:
            raise HTTPException(
                status_code=400,
                detail="No active context for this project.",
            )
        deleted = await service.delete_variable(context_id, variable_name)

    if not deleted:
        raise HTTPException(status_code=404, detail="Variable not found.")
