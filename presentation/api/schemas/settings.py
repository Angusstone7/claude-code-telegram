"""Settings schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------


class ProviderConfigResponse(BaseModel):
    mode: str
    api_key_set: bool
    base_url: Optional[str] = None
    custom_models: list[str] = []


class ProviderConfigUpdate(BaseModel):
    mode: Optional[str] = Field(None, pattern=r"^(anthropic|zai|local)$")
    api_key: Optional[str] = None
    base_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Provider validation
# ---------------------------------------------------------------------------


class ProviderValidateRequest(BaseModel):
    provider: str
    api_key: str
    base_url: Optional[str] = None


class ProviderValidateResponse(BaseModel):
    valid: bool
    models: list[str] = []
    message: str


# ---------------------------------------------------------------------------
# Custom models
# ---------------------------------------------------------------------------


class CustomModelRequest(BaseModel):
    provider: str
    model_id: str = Field(..., max_length=128)


class CustomModelResponse(BaseModel):
    provider: str
    models: list[str] = []
    custom_models: list[str] = []


# ---------------------------------------------------------------------------
# Proxy configuration
# ---------------------------------------------------------------------------


class ProxyConfigResponse(BaseModel):
    enabled: bool
    type: str
    host: str
    port: int
    username: str
    password_set: bool
    no_proxy: str


class ProxyConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    type: Optional[str] = Field(None, pattern=r"^(http|https|socks5)$")
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    no_proxy: Optional[str] = None


class ProxyTestRequest(BaseModel):
    type: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class ProxyTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Runtime configuration
# ---------------------------------------------------------------------------


class RuntimeConfigResponse(BaseModel):
    max_turns: int
    timeout: int
    step_streaming: bool
    permission_mode: str
    yolo_mode: bool
    backend: str


class RuntimeConfigUpdate(BaseModel):
    max_turns: Optional[int] = Field(None, ge=1, le=999)
    timeout: Optional[int] = Field(None, ge=10, le=3600)
    step_streaming: Optional[bool] = None
    permission_mode: Optional[str] = None
    yolo_mode: Optional[bool] = None
    backend: Optional[str] = None


# ---------------------------------------------------------------------------
# Claude account / credentials
# ---------------------------------------------------------------------------


class ClaudeAccountResponse(BaseModel):
    active: bool
    credentials_exist: bool
    subscription_type: Optional[str] = None
    rate_limit_tier: Optional[str] = None
    expires_at: Optional[str] = None
    scopes: list[str] = []


class CredentialsUploadRequest(BaseModel):
    credentials_json: str


class CredentialsUploadResponse(BaseModel):
    success: bool
    subscription_type: Optional[str] = None
    rate_limit_tier: Optional[str] = None
    message: str


# ---------------------------------------------------------------------------
# Infrastructure configuration
# ---------------------------------------------------------------------------


class InfraConfigResponse(BaseModel):
    ssh_host: str
    ssh_port: int
    ssh_user: str
    gitlab_url: str
    gitlab_token_set: bool
    alert_cpu: float
    alert_memory: float
    alert_disk: float
    debug: bool
    log_level: str


class InfraConfigUpdate(BaseModel):
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = Field(None, ge=1, le=65535)
    ssh_user: Optional[str] = None
    gitlab_url: Optional[str] = None
    gitlab_token: Optional[str] = None
    alert_cpu: Optional[float] = Field(None, ge=0, le=100)
    alert_memory: Optional[float] = Field(None, ge=0, le=100)
    alert_disk: Optional[float] = Field(None, ge=0, le=100)
    debug: Optional[bool] = None
    log_level: Optional[str] = Field(None, pattern=r"^(DEBUG|INFO|WARNING|ERROR)$")


# ---------------------------------------------------------------------------
# Aggregate settings (top-level request / response)
# ---------------------------------------------------------------------------


class SettingsResponse(BaseModel):
    yolo_mode: bool
    step_streaming: bool
    backend: str  # "sdk" | "cli"
    model: str
    provider: str  # "anthropic" | "zai" | "local"
    available_models: list[str]
    permission_mode: str  # "default" | "auto" | "never"
    language: str  # "ru" | "en" | "zh"
    provider_config: Optional[ProviderConfigResponse] = None
    provider_api_keys: dict[str, bool] = {}  # {provider: api_key_set} for all providers
    provider_proxies: dict[str, dict] = {}  # {provider: ProxyConfig} for all providers
    proxy: Optional[ProxyConfigResponse] = None
    runtime: Optional[RuntimeConfigResponse] = None
    claude_account: Optional[ClaudeAccountResponse] = None
    infra: Optional[InfraConfigResponse] = None


class UpdateSettingsRequest(BaseModel):
    yolo_mode: Optional[bool] = None
    step_streaming: Optional[bool] = None
    backend: Optional[str] = Field(None, pattern=r"^(sdk|cli)$")
    model: Optional[str] = None
    provider: Optional[str] = Field(None, pattern=r"^(anthropic|zai|local)$")
    permission_mode: Optional[str] = Field(None, pattern=r"^(default|auto|never)$")
    language: Optional[str] = Field(None, pattern=r"^(ru|en|zh)$")
    provider_config: Optional[ProviderConfigUpdate] = None
    proxy: Optional[ProxyConfigUpdate] = None
    runtime: Optional[RuntimeConfigUpdate] = None
    infra: Optional[InfraConfigUpdate] = None
