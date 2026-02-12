"""Settings API routes.

Provides endpoints for reading and updating application settings.
Settings are stored in-memory via the runtime config service with
environment variable fallbacks for initial values.
"""

import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
import httpx

from presentation.api.security import hybrid_auth
from presentation.api.dependencies import get_runtime_config, get_account_service
from presentation.api.schemas.settings import (
    SettingsResponse, UpdateSettingsRequest,
    ProviderValidateRequest, ProviderValidateResponse,
    CustomModelRequest, CustomModelResponse,
    ProxyTestRequest, ProxyTestResponse,
    CredentialsUploadRequest, CredentialsUploadResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])

# Available models per provider
ANTHROPIC_MODELS = [
    "claude-opus-4-6",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
]

ZAI_MODELS = [
    "glm-4.7",
    "glm-4-plus",
    "glm-4-air",
    "glm-4-flash",
]

ZAI_BASE_URL = "https://open.bigmodel.cn/api/anthropic"


def _detect_provider() -> str:
    """Detect current provider from ANTHROPIC_BASE_URL."""
    base_url = os.getenv("ANTHROPIC_BASE_URL", "")
    if base_url and "bigmodel.cn" in base_url:
        return "zai"
    return "anthropic"


def _get_models_for_provider(provider: str) -> list[str]:
    """Return available models based on provider."""
    if provider == "zai":
        return ZAI_MODELS
    return ANTHROPIC_MODELS


def _get_current_settings_dict() -> dict:
    """Read current settings from environment + runtime config defaults."""
    return {
        "yolo_mode": os.getenv("CLAUDE_YOLO_MODE", "false").lower() == "true",
        "step_streaming": os.getenv("CLAUDE_STEP_STREAMING", "true").lower() == "true",
        "backend": os.getenv("CLAUDE_BACKEND", "sdk"),
        "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
        "provider": _detect_provider(),
        "permission_mode": os.getenv("CLAUDE_PERMISSION_MODE", "default"),
        "language": os.getenv("CLAUDE_LANGUAGE", "ru"),
    }


# ---------------------------------------------------------------------------
# Helper functions for nested config objects (T005)
# ---------------------------------------------------------------------------


async def _get_provider_config(config) -> dict:
    """Read provider configuration from RuntimeConfig and env vars.

    Returns dict suitable for ProviderConfigResponse.
    """
    provider = await config.get("settings.provider") or _detect_provider()

    # Check if API key is set per-provider (don't expose the actual key).
    # Only use runtime config storage, not env vars, because env vars are
    # shared (z.ai sets ANTHROPIC_API_KEY which pollutes anthropic detection).
    api_key_set = bool(await config.get(f"settings.provider.{provider}.api_key"))

    # Base URL
    base_url = await config.get(f"settings.provider.{provider}.base_url")
    if not base_url:
        if provider == "zai":
            base_url = os.getenv("ANTHROPIC_BASE_URL", ZAI_BASE_URL)
        elif provider == "local":
            base_url = await config.get("settings.provider.local.base_url")
        else:
            base_url = os.getenv("ANTHROPIC_BASE_URL")

    # Custom models
    custom_models_json = await config.get(f"settings.custom_models.{provider}")
    custom_models = []
    if custom_models_json:
        try:
            custom_models = json.loads(custom_models_json) if isinstance(custom_models_json, str) else custom_models_json
        except (json.JSONDecodeError, TypeError):
            custom_models = []

    return {
        "mode": provider,
        "api_key_set": api_key_set,
        "base_url": base_url,
        "custom_models": custom_models,
    }


async def _get_proxy_config(config) -> dict:
    """Read proxy configuration from RuntimeConfig and env vars.

    Returns dict suitable for ProxyConfigResponse.
    """
    enabled = await config.get("settings.proxy.enabled")
    if enabled is None:
        # Check if proxy env vars are set
        enabled = bool(os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"))
    elif isinstance(enabled, str):
        enabled = enabled.lower() == "true"

    proxy_type = await config.get("settings.proxy.type") or "http"
    host = await config.get("settings.proxy.host") or ""
    port_val = await config.get("settings.proxy.port")
    port = int(port_val) if port_val else 0
    username = await config.get("settings.proxy.username") or ""
    password_stored = await config.get("settings.proxy.password")
    password_set = bool(password_stored)
    no_proxy = await config.get("settings.proxy.no_proxy") or os.getenv(
        "NO_PROXY", "localhost,127.0.0.1,192.168.0.0/16"
    )

    # If no stored config, try to parse from env var
    if not host and enabled:
        proxy_url = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or ""
        if proxy_url:
            _parse_proxy_env(proxy_url, locals())

    return {
        "enabled": bool(enabled),
        "type": proxy_type,
        "host": host,
        "port": port,
        "username": username,
        "password_set": password_set,
        "no_proxy": no_proxy,
    }


def _parse_proxy_env(proxy_url: str, target: dict) -> None:
    """Parse proxy URL like http://user:pass@host:port into components."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(proxy_url)
        if parsed.hostname:
            target["host"] = parsed.hostname
        if parsed.port:
            target["port"] = parsed.port
        if parsed.username:
            target["username"] = parsed.username
        if parsed.password:
            target["password_set"] = True
        if parsed.scheme:
            target["proxy_type"] = parsed.scheme
    except Exception:
        pass


async def _get_runtime_params(config) -> dict:
    """Read runtime parameters from RuntimeConfig and env vars.

    Returns dict suitable for RuntimeConfigResponse.
    """
    max_turns_val = await config.get("settings.runtime.max_turns")
    max_turns = int(max_turns_val) if max_turns_val else int(os.getenv("CLAUDE_MAX_TURNS", "50"))

    timeout_val = await config.get("settings.runtime.timeout")
    timeout = int(timeout_val) if timeout_val else int(os.getenv("CLAUDE_TIMEOUT", "600"))

    step_streaming_val = await config.get("settings.step_streaming")
    if step_streaming_val is not None:
        step_streaming = step_streaming_val if isinstance(step_streaming_val, bool) else str(step_streaming_val).lower() == "true"
    else:
        step_streaming = os.getenv("CLAUDE_STEP_STREAMING", "true").lower() == "true"

    permission_mode_val = await config.get("settings.permission_mode")
    permission_mode = permission_mode_val or os.getenv("CLAUDE_PERMISSION_MODE", "default")

    yolo_mode_val = await config.get("settings.yolo_mode")
    if yolo_mode_val is not None:
        yolo_mode = yolo_mode_val if isinstance(yolo_mode_val, bool) else str(yolo_mode_val).lower() == "true"
    else:
        yolo_mode = os.getenv("CLAUDE_YOLO_MODE", "false").lower() == "true"

    backend_val = await config.get("settings.backend")
    backend = backend_val or os.getenv("CLAUDE_BACKEND", "sdk")

    return {
        "max_turns": max_turns,
        "timeout": timeout,
        "step_streaming": step_streaming,
        "permission_mode": permission_mode,
        "yolo_mode": yolo_mode,
        "backend": backend,
    }


async def _get_claude_account_info(account_service) -> dict:
    """Read Claude Account info from AccountService.

    Returns dict suitable for ClaudeAccountResponse.
    """
    cred_info = account_service.get_credentials_info()
    active = account_service.has_valid_credentials()

    expires_at = None
    if cred_info.expires_at:
        expires_at = cred_info.expires_at.isoformat()

    return {
        "active": active,
        "credentials_exist": cred_info.exists,
        "subscription_type": cred_info.subscription_type,
        "rate_limit_tier": cred_info.rate_limit_tier,
        "expires_at": expires_at,
        "scopes": cred_info.scopes or [],
    }


async def _get_infra_config() -> dict:
    """Read infrastructure configuration from env vars.

    Returns dict suitable for InfraConfigResponse.
    """
    return {
        "ssh_host": os.getenv("SSH_HOST", "host.docker.internal"),
        "ssh_port": int(os.getenv("SSH_PORT", "22")),
        "ssh_user": os.getenv("HOST_USER", "root"),
        "gitlab_url": os.getenv("GITLAB_URL", "https://gitlab.com"),
        "gitlab_token_set": bool(os.getenv("GITLAB_TOKEN")),
        "alert_cpu": float(os.getenv("ALERT_THRESHOLD_CPU", "80.0")),
        "alert_memory": float(os.getenv("ALERT_THRESHOLD_MEMORY", "85.0")),
        "alert_disk": float(os.getenv("ALERT_THRESHOLD_DISK", "90.0")),
        "debug": os.getenv("DEBUG", "false").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Get settings",
    description="Return current application settings.",
)
async def get_settings(
    user: dict = Depends(hybrid_auth),
) -> SettingsResponse:
    """Return current settings, merging runtime overrides over env defaults."""
    config = get_runtime_config()
    account_service = get_account_service()

    # Start with env defaults
    defaults = _get_current_settings_dict()

    # Override with runtime config values if present
    for key in defaults:
        runtime_val = await config.get(f"settings.{key}")
        if runtime_val is not None:
            if isinstance(defaults[key], bool):
                defaults[key] = runtime_val if isinstance(runtime_val, bool) else str(runtime_val).lower() == "true"
            else:
                defaults[key] = runtime_val

    provider = defaults["provider"]

    # Build nested config objects
    provider_config = await _get_provider_config(config)
    proxy = await _get_proxy_config(config)
    runtime = await _get_runtime_params(config)
    claude_account = await _get_claude_account_info(account_service)
    infra = await _get_infra_config()

    # Merge custom models into available_models, respecting removed base models
    base_models = _get_models_for_provider(provider)
    custom_models = provider_config.get("custom_models", [])
    removed_raw = await config.get(f"settings.removed_models.{provider}")
    removed_models: list[str] = []
    if removed_raw:
        try:
            removed_models = json.loads(removed_raw) if isinstance(removed_raw, str) else removed_raw
        except (json.JSONDecodeError, TypeError):
            removed_models = []
    filtered_base = [m for m in base_models if m not in removed_models]
    all_models = list(dict.fromkeys(filtered_base + custom_models))  # deduplicated, order preserved

    # Build per-provider api_key_set map for UI badge display
    provider_api_keys = {}
    for p in ("anthropic", "zai", "local"):
        provider_api_keys[p] = bool(await config.get(f"settings.provider.{p}.api_key"))

    return SettingsResponse(
        yolo_mode=defaults["yolo_mode"],
        step_streaming=defaults["step_streaming"],
        backend=defaults["backend"],
        model=defaults["model"],
        provider=provider,
        available_models=all_models,
        permission_mode=defaults["permission_mode"],
        language=defaults["language"],
        provider_config=provider_config,
        provider_api_keys=provider_api_keys,
        proxy=proxy,
        runtime=runtime,
        claude_account=claude_account,
        infra=infra,
    )


@router.patch(
    "",
    response_model=SettingsResponse,
    summary="Update settings",
    description="Update application settings. Only provided fields are changed.",
)
async def update_settings(
    request: UpdateSettingsRequest,
    user: dict = Depends(hybrid_auth),
) -> SettingsResponse:
    """Update settings in runtime config and return the new state."""
    config = get_runtime_config()

    # Apply only the fields that were provided
    update_data = request.model_dump(exclude_unset=True)

    # Handle provider switching
    if "provider" in update_data:
        new_provider = update_data["provider"]
        if new_provider == "zai":
            os.environ["ANTHROPIC_BASE_URL"] = ZAI_BASE_URL
        else:
            os.environ.pop("ANTHROPIC_BASE_URL", None)

    # Handle nested provider_config updates
    if "provider_config" in update_data:
        pc = update_data.pop("provider_config")
        if pc:
            provider = update_data.get("provider") or await config.get("settings.provider") or _detect_provider()
            if pc.get("mode"):
                await config.set("settings.provider", pc["mode"])
                provider = pc["mode"]
            if pc.get("api_key"):
                await config.set(f"settings.provider.{provider}.api_key", pc["api_key"])
                # Also set env var for immediate effect
                if provider == "anthropic":
                    os.environ["ANTHROPIC_API_KEY"] = pc["api_key"]
                elif provider == "zai":
                    os.environ["ANTHROPIC_AUTH_TOKEN"] = pc["api_key"]
                    os.environ["ANTHROPIC_API_KEY"] = pc["api_key"]
            if "base_url" in pc:
                await config.set(f"settings.provider.{provider}.base_url", pc["base_url"])
                if pc["base_url"]:
                    os.environ["ANTHROPIC_BASE_URL"] = pc["base_url"]

    # Handle nested proxy updates
    if "proxy" in update_data:
        px = update_data.pop("proxy")
        if px:
            for pk, pv in px.items():
                await config.set(f"settings.proxy.{pk}", pv)
            # Apply proxy env vars
            proxy_enabled = px.get("enabled")
            if proxy_enabled is None:
                proxy_enabled = await config.get("settings.proxy.enabled")
            if proxy_enabled:
                host = px.get("host") or await config.get("settings.proxy.host") or ""
                port = px.get("port") or await config.get("settings.proxy.port") or 0
                ptype = px.get("type") or await config.get("settings.proxy.type") or "http"
                username = px.get("username") or await config.get("settings.proxy.username") or ""
                password = px.get("password") or await config.get("settings.proxy.password") or ""
                no_proxy = px.get("no_proxy") or await config.get("settings.proxy.no_proxy") or "localhost,127.0.0.1,192.168.0.0/16"

                if host and port:
                    if username and password:
                        proxy_url = f"{ptype}://{username}:{password}@{host}:{port}"
                    else:
                        proxy_url = f"{ptype}://{host}:{port}"
                    os.environ["HTTP_PROXY"] = proxy_url
                    os.environ["HTTPS_PROXY"] = proxy_url
                    os.environ["http_proxy"] = proxy_url
                    os.environ["https_proxy"] = proxy_url
                    os.environ["NO_PROXY"] = no_proxy
                    os.environ["no_proxy"] = no_proxy
            elif proxy_enabled is False:
                for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                    os.environ.pop(var, None)

    # Handle nested runtime updates
    if "runtime" in update_data:
        rt = update_data.pop("runtime")
        if rt:
            for rk, rv in rt.items():
                await config.set(f"settings.runtime.{rk}", rv)
                # Mirror to top-level for backward compat
                if rk in ("step_streaming", "yolo_mode", "backend", "permission_mode"):
                    await config.set(f"settings.{rk}", rv)

    # Handle nested infra updates
    if "infra" in update_data:
        inf = update_data.pop("infra")
        if inf:
            env_mapping = {
                "ssh_host": "SSH_HOST",
                "ssh_port": "SSH_PORT",
                "ssh_user": "HOST_USER",
                "gitlab_url": "GITLAB_URL",
                "gitlab_token": "GITLAB_TOKEN",
                "alert_cpu": "ALERT_THRESHOLD_CPU",
                "alert_memory": "ALERT_THRESHOLD_MEMORY",
                "alert_disk": "ALERT_THRESHOLD_DISK",
                "debug": "DEBUG",
                "log_level": "LOG_LEVEL",
            }
            for ik, iv in inf.items():
                env_key = env_mapping.get(ik)
                if env_key:
                    os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    # Store remaining top-level fields
    for key, value in update_data.items():
        await config.set(f"settings.{key}", value)
        logger.info(
            "Setting updated: %s = %r (user=%s)",
            key,
            value,
            user.get("user_id"),
        )

    # Return the full updated settings
    return await get_settings(user=user)


# ---------------------------------------------------------------------------
# T007: Provider validation
# ---------------------------------------------------------------------------


@router.post(
    "/provider/validate",
    response_model=ProviderValidateResponse,
    summary="Validate provider credentials",
    description="Check that the given API key and base URL work for the specified provider.",
)
async def validate_provider(
    request: ProviderValidateRequest,
    user: dict = Depends(hybrid_auth),
) -> ProviderValidateResponse:
    """Validate provider API key by fetching the models list."""
    timeout = httpx.Timeout(10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if request.provider == "anthropic":
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": request.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
            elif request.provider == "zai":
                base = request.base_url or ZAI_BASE_URL
                resp = await client.get(
                    f"{base.rstrip('/')}/v1/models",
                    headers={"Authorization": f"Bearer {request.api_key}"},
                )
            elif request.provider == "local":
                if not request.base_url:
                    return ProviderValidateResponse(
                        valid=False, models=[], message="base_url is required for local provider"
                    )
                base = request.base_url.rstrip("/")
                resp = await client.get(f"{base}/v1/models")
                if resp.status_code == 404:
                    # Fallback: try /health
                    resp = await client.get(f"{base}/health")
                    if resp.is_success:
                        return ProviderValidateResponse(
                            valid=True, models=[], message="Server is reachable (health OK), but /v1/models not available"
                        )
            else:
                return ProviderValidateResponse(
                    valid=False, models=[], message=f"Unknown provider: {request.provider}"
                )

            if resp.is_success:
                models: list[str] = []
                try:
                    data = resp.json()
                    # Anthropic returns {"data": [{"id": "..."}, ...]}
                    if isinstance(data, dict) and "data" in data:
                        models = [m["id"] for m in data["data"] if isinstance(m, dict) and "id" in m]
                    elif isinstance(data, list):
                        models = [m["id"] for m in data if isinstance(m, dict) and "id" in m]
                except Exception:
                    pass
                return ProviderValidateResponse(
                    valid=True, models=models, message="API key is valid"
                )
            else:
                return ProviderValidateResponse(
                    valid=False, models=[], message=f"API returned status {resp.status_code}"
                )

    except httpx.TimeoutException:
        return ProviderValidateResponse(
            valid=False, models=[], message="Connection timed out"
        )
    except httpx.ConnectError:
        return ProviderValidateResponse(
            valid=False, models=[], message="Connection error: unable to reach server"
        )
    except Exception as exc:
        return ProviderValidateResponse(
            valid=False, models=[], message=f"Validation failed: {exc}"
        )


# ---------------------------------------------------------------------------
# T008: Add custom model
# ---------------------------------------------------------------------------


@router.post(
    "/models/custom",
    response_model=CustomModelResponse,
    summary="Add custom model",
    description="Add a custom model ID for the given provider.",
)
async def add_custom_model(
    request: CustomModelRequest,
    user: dict = Depends(hybrid_auth),
) -> CustomModelResponse:
    """Add a custom model to the provider's model list."""
    config = get_runtime_config()
    key = f"settings.custom_models.{request.provider}"

    # Read existing custom models
    raw = await config.get(key)
    custom_models: list[str] = []
    if raw:
        try:
            custom_models = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            custom_models = []

    # Validate limits
    if len(custom_models) >= 20:
        raise HTTPException(status_code=400, detail="Maximum 20 custom models per provider")

    if request.model_id in custom_models:
        raise HTTPException(status_code=400, detail="Model already exists in custom list")

    # Also check against base models
    base_models = _get_models_for_provider(request.provider)
    if request.model_id in base_models:
        raise HTTPException(status_code=400, detail="Model already exists in base models")

    custom_models.append(request.model_id)
    await config.set(key, json.dumps(custom_models))

    all_models = list(dict.fromkeys(base_models + custom_models))

    return CustomModelResponse(
        provider=request.provider,
        models=all_models,
        custom_models=custom_models,
    )


# ---------------------------------------------------------------------------
# T009: Delete custom model
# ---------------------------------------------------------------------------


@router.delete(
    "/models/custom",
    response_model=CustomModelResponse,
    summary="Remove custom model",
    description="Remove a custom model ID from the given provider.",
)
async def delete_custom_model(
    request: CustomModelRequest,
    user: dict = Depends(hybrid_auth),
) -> CustomModelResponse:
    """Remove a custom model from the provider's model list."""
    config = get_runtime_config()
    key = f"settings.custom_models.{request.provider}"

    # Read existing custom models
    raw = await config.get(key)
    custom_models: list[str] = []
    if raw:
        try:
            custom_models = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            custom_models = []

    base_models = _get_models_for_provider(request.provider)

    if request.model_id in custom_models:
        # Remove from custom models
        custom_models.remove(request.model_id)
        await config.set(key, json.dumps(custom_models))
    elif request.model_id in base_models:
        # Hide a base model by adding to removed list
        removed_key = f"settings.removed_models.{request.provider}"
        raw_removed = await config.get(removed_key)
        removed: list[str] = []
        if raw_removed:
            try:
                removed = json.loads(raw_removed) if isinstance(raw_removed, str) else raw_removed
            except (json.JSONDecodeError, TypeError):
                removed = []
        if request.model_id not in removed:
            removed.append(request.model_id)
            await config.set(removed_key, json.dumps(removed))
    else:
        raise HTTPException(status_code=404, detail="Model not found")

    # Rebuild all_models respecting removed base models
    removed_key2 = f"settings.removed_models.{request.provider}"
    raw_rm = await config.get(removed_key2)
    all_removed: list[str] = []
    if raw_rm:
        try:
            all_removed = json.loads(raw_rm) if isinstance(raw_rm, str) else raw_rm
        except (json.JSONDecodeError, TypeError):
            all_removed = []
    filtered_base = [m for m in base_models if m not in all_removed]
    all_models = list(dict.fromkeys(filtered_base + custom_models))

    # Check if deleted model was the currently selected model
    current_model = await config.get("settings.model")
    if not current_model:
        current_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

    if current_model == request.model_id:
        # Reset to first available model
        if all_models:
            await config.set("settings.model", all_models[0])
        else:
            await config.set("settings.model", "claude-sonnet-4-5-20250929")

    return CustomModelResponse(
        provider=request.provider,
        models=all_models,
        custom_models=custom_models,
    )


# ---------------------------------------------------------------------------
# T016a: Proxy test
# ---------------------------------------------------------------------------


@router.post(
    "/proxy/test",
    response_model=ProxyTestResponse,
    summary="Test proxy connection",
)
async def test_proxy(
    request: ProxyTestRequest,
    user: dict = Depends(hybrid_auth),
) -> ProxyTestResponse:
    """Test proxy connectivity by making a request through it."""
    import time

    if request.username and request.password:
        proxy_url = f"{request.type}://{request.username}:{request.password}@{request.host}:{request.port}"
    else:
        proxy_url = f"{request.type}://{request.host}:{request.port}"

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            proxy=proxy_url,
        ) as client:
            resp = await client.get("https://api.anthropic.com")
            elapsed = int((time.monotonic() - start) * 1000)
            if resp.status_code < 500:
                return ProxyTestResponse(success=True, message="Proxy connection successful", latency_ms=elapsed)
            return ProxyTestResponse(success=False, message=f"Server returned {resp.status_code}", latency_ms=elapsed)
    except httpx.TimeoutException:
        elapsed = int((time.monotonic() - start) * 1000)
        return ProxyTestResponse(success=False, message="Connection timed out", latency_ms=elapsed)
    except httpx.ConnectError as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return ProxyTestResponse(success=False, message=f"Connection error: {e}", latency_ms=elapsed)
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return ProxyTestResponse(success=False, message=f"Error: {e}", latency_ms=elapsed)


# ---------------------------------------------------------------------------
# T019a: Plugins list
# ---------------------------------------------------------------------------


@router.get(
    "/plugins",
    summary="Get plugins list",
)
async def get_plugins(
    user: dict = Depends(hybrid_auth),
):
    """Return list of available plugins with their enabled status."""
    plugins_str = os.getenv("CLAUDE_PLUGINS", "")
    plugins_dir = os.getenv("CLAUDE_PLUGINS_DIR", "/plugins")
    enabled_plugins = [p.strip() for p in plugins_str.split(",") if p.strip()]

    # Try to discover plugins from directory
    all_plugins = set(enabled_plugins)
    try:
        import pathlib
        plugins_path = pathlib.Path(plugins_dir)
        if plugins_path.exists():
            for item in plugins_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    all_plugins.add(item.name)
    except Exception:
        pass

    result = []
    for name in sorted(all_plugins):
        result.append({
            "name": name,
            "enabled": name in enabled_plugins,
            "description": None,
            "source": plugins_dir,
            "commands": [],
        })

    return {"plugins": result, "total": len(result)}


# ---------------------------------------------------------------------------
# T021: Claude account credentials upload
# ---------------------------------------------------------------------------


@router.post(
    "/claude-account/credentials",
    response_model=CredentialsUploadResponse,
    summary="Upload Claude credentials",
)
async def upload_credentials(
    request: CredentialsUploadRequest,
    user: dict = Depends(hybrid_auth),
) -> CredentialsUploadResponse:
    """Upload .credentials.json for Claude Account OAuth."""
    account_service = get_account_service()

    success, message = account_service.save_credentials(request.credentials_json)

    if not success:
        raise HTTPException(status_code=422, detail=message)

    # Read back the saved info
    cred_info = account_service.get_credentials_info()

    return CredentialsUploadResponse(
        success=True,
        subscription_type=cred_info.subscription_type,
        rate_limit_tier=cred_info.rate_limit_tier,
        message=message,
    )
