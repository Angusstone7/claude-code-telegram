"""GitLab integration endpoints.

Provides access to GitLab projects and CI/CD pipelines
via the GitLab REST API v4.
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from presentation.api.schemas.gitlab import (
    GitLabProjectListResponse,
    GitLabProjectResponse,
    PipelineListResponse,
    PipelineResponse,
    PipelineStageResponse,
)
from presentation.api.security import hybrid_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gitlab", tags=["GitLab"])


def _get_gitlab_config():
    """Get GitLab configuration from settings."""
    from shared.config.settings import settings

    url = settings.gitlab.url.rstrip("/")
    token = settings.gitlab.token
    if not token:
        raise HTTPException(
            status_code=503,
            detail="GitLab integration not configured. Set GITLAB_TOKEN env variable.",
        )
    return url, token


def _gitlab_headers(token: str) -> dict[str, str]:
    """Build GitLab API request headers."""
    return {
        "PRIVATE-TOKEN": token,
        "Accept": "application/json",
    }


# ── Projects ────────────────────────────────────────────────────────────────


@router.get(
    "/projects",
    response_model=GitLabProjectListResponse,
    summary="List GitLab projects",
    description="Returns a list of GitLab projects accessible with the configured token.",
)
async def list_projects(
    user: dict = Depends(hybrid_auth),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search project by name"),
) -> GitLabProjectListResponse:
    """List GitLab projects."""
    url, token = _get_gitlab_config()

    params: dict = {
        "membership": "true",
        "order_by": "last_activity_at",
        "sort": "desc",
        "page": page,
        "per_page": per_page,
    }
    if search:
        params["search"] = search

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{url}/api/v4/projects",
                headers=_gitlab_headers(token),
                params=params,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("GitLab API error: %s %s", exc.response.status_code, exc.response.text[:200])
        raise HTTPException(
            status_code=502,
            detail=f"GitLab API returned {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        logger.error("GitLab connection error: %s", exc)
        raise HTTPException(status_code=502, detail="Cannot connect to GitLab")

    raw_projects = resp.json()
    total = int(resp.headers.get("x-total", len(raw_projects)))

    projects = [
        GitLabProjectResponse(
            id=p["id"],
            name=p["name"],
            path_with_namespace=p["path_with_namespace"],
            web_url=p["web_url"],
            default_branch=p.get("default_branch"),
            last_activity_at=p.get("last_activity_at"),
        )
        for p in raw_projects
    ]

    return GitLabProjectListResponse(projects=projects, total=total)


# ── Pipelines ───────────────────────────────────────────────────────────────


@router.get(
    "/projects/{project_id}/pipelines",
    response_model=PipelineListResponse,
    summary="List pipelines for a project",
    description="Returns recent CI/CD pipelines for the given GitLab project.",
)
async def list_pipelines(
    project_id: int,
    user: dict = Depends(hybrid_auth),
    limit: int = Query(20, ge=1, le=100, description="Max pipelines to return"),
    ref: Optional[str] = Query(None, description="Filter by branch/tag name"),
) -> PipelineListResponse:
    """List pipelines for a GitLab project."""
    url, token = _get_gitlab_config()

    params: dict = {
        "per_page": limit,
        "order_by": "id",
        "sort": "desc",
    }
    if ref:
        params["ref"] = ref

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{url}/api/v4/projects/{project_id}/pipelines",
                headers=_gitlab_headers(token),
                params=params,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("GitLab API error: %s %s", exc.response.status_code, exc.response.text[:200])
        raise HTTPException(
            status_code=502,
            detail=f"GitLab API returned {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        logger.error("GitLab connection error: %s", exc)
        raise HTTPException(status_code=502, detail="Cannot connect to GitLab")

    raw_pipelines = resp.json()

    pipelines = [
        PipelineResponse(
            id=p["id"],
            status=p["status"],
            ref=p["ref"],
            sha=p["sha"],
            created_at=p["created_at"],
            updated_at=p.get("updated_at"),
            web_url=p.get("web_url"),
            stages=[],
        )
        for p in raw_pipelines
    ]

    return PipelineListResponse(
        pipelines=pipelines,
        total=len(pipelines),
    )


# ── Pipeline Stages ─────────────────────────────────────────────────────────


@router.get(
    "/projects/{project_id}/pipelines/{pipeline_id}/stages",
    response_model=list[PipelineStageResponse],
    summary="Get pipeline stages (jobs grouped by stage)",
    description="Returns the stages and their statuses for a specific pipeline.",
)
async def get_pipeline_stages(
    project_id: int,
    pipeline_id: int,
    user: dict = Depends(hybrid_auth),
) -> list[PipelineStageResponse]:
    """Get stages for a specific pipeline.

    GitLab doesn't have a direct "stages" endpoint, so we fetch jobs
    and group them by stage name, deriving an aggregate status per stage.
    """
    url, token = _get_gitlab_config()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs",
                headers=_gitlab_headers(token),
                params={"per_page": 100},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("GitLab API error: %s %s", exc.response.status_code, exc.response.text[:200])
        raise HTTPException(
            status_code=502,
            detail=f"GitLab API returned {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        logger.error("GitLab connection error: %s", exc)
        raise HTTPException(status_code=502, detail="Cannot connect to GitLab")

    jobs = resp.json()

    # Group jobs by stage name, preserving order of first appearance
    stage_order: list[str] = []
    stage_jobs: dict[str, list[str]] = {}
    for job in jobs:
        stage_name = job.get("stage", "unknown")
        if stage_name not in stage_jobs:
            stage_order.append(stage_name)
            stage_jobs[stage_name] = []
        stage_jobs[stage_name].append(job.get("status", "unknown"))

    # Derive aggregate status per stage
    # Priority: failed > running > pending > skipped > success
    def _aggregate_status(statuses: list[str]) -> str:
        status_set = set(statuses)
        if "failed" in status_set:
            return "failed"
        if "running" in status_set:
            return "running"
        if "pending" in status_set or "created" in status_set:
            return "pending"
        if "manual" in status_set:
            return "manual"
        if "skipped" in status_set and len(status_set) == 1:
            return "skipped"
        if "success" in status_set:
            return "success"
        return statuses[0] if statuses else "unknown"

    stages = [
        PipelineStageResponse(
            name=stage_name,
            status=_aggregate_status(stage_jobs[stage_name]),
        )
        for stage_name in stage_order
    ]

    return stages
