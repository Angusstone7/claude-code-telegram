"""GitLab integration schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class GitLabProjectResponse(BaseModel):
    id: int
    name: str
    path_with_namespace: str
    web_url: str
    default_branch: Optional[str] = None
    last_activity_at: Optional[datetime] = None


class PipelineStageResponse(BaseModel):
    name: str
    status: str  # "success" | "failed" | "running" | "pending" | "skipped"


class PipelineResponse(BaseModel):
    id: int
    status: str  # "success" | "failed" | "running" | "pending"
    ref: str  # branch name
    sha: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    web_url: Optional[str] = None
    stages: list[PipelineStageResponse] = []


class PipelineListResponse(BaseModel):
    pipelines: list[PipelineResponse]
    total: int


class GitLabProjectListResponse(BaseModel):
    projects: list[GitLabProjectResponse]
    total: int
