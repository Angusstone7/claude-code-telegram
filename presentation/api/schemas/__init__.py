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
from presentation.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshResponse,
    UserProfile,
    UpdateProfileRequest,
    CreateUserRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from presentation.api.schemas.contexts import (
    ContextResponse,
    ContextListResponse,
    CreateContextRequest,
)
from presentation.api.schemas.variables import (
    VariableResponse,
    VariableListResponse,
    CreateVariableRequest,
    UpdateVariableRequest,
)
from presentation.api.schemas.files import (
    FileEntry,
    FileBrowserResponse,
    MkdirRequest,
)
from presentation.api.schemas.settings import (
    SettingsResponse,
    UpdateSettingsRequest,
)
from presentation.api.schemas.plugins import (
    PluginCommand,
    PluginResponse,
    PluginListResponse,
)
from presentation.api.schemas.ssh import (
    SSHCommandRequest,
    SSHCommandResponse,
    SSHHistoryResponse,
)

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
    "LoginRequest",
    "LoginResponse",
    "RefreshResponse",
    "UserProfile",
    "UpdateProfileRequest",
    "CreateUserRequest",
    "ResetPasswordRequest",
    "MessageResponse",
    "ContextResponse",
    "ContextListResponse",
    "CreateContextRequest",
    "VariableResponse",
    "VariableListResponse",
    "CreateVariableRequest",
    "UpdateVariableRequest",
    "FileEntry",
    "FileBrowserResponse",
    "MkdirRequest",
    "SettingsResponse",
    "UpdateSettingsRequest",
    "PluginCommand",
    "PluginResponse",
    "PluginListResponse",
    "SSHCommandRequest",
    "SSHCommandResponse",
    "SSHHistoryResponse",
]
