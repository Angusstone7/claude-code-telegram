"""Pydantic v2 request/response schemas for REST API."""

from presentation.api.schemas.common import ErrorResponse, PaginatedResponse
from presentation.api.schemas.projects import (
    ProjectResponse,
    ProjectListResponse,
    CreateProjectRequest,
)
from presentation.api.schemas.sessions import SessionResponse, SessionListResponse
from presentation.api.schemas.claude import TaskRequest, TaskResponse
from presentation.api.schemas.system import HealthResponse, SystemInfoResponse, MetricsResponse

__all__ = [
    "ErrorResponse",
    "PaginatedResponse",
    "ProjectResponse",
    "ProjectListResponse",
    "CreateProjectRequest",
    "SessionResponse",
    "SessionListResponse",
    "TaskRequest",
    "TaskResponse",
    "HealthResponse",
    "SystemInfoResponse",
    "MetricsResponse",
]
