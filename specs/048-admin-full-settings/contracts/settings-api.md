# API Contract: Settings Endpoints

**Feature**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

## Base Path: `/api/settings`

All endpoints require authentication via `hybrid_auth` (JWT token or Telegram session).

---

## GET /api/settings

**Summary**: Get all current settings (extended response)

**Response 200** — `SettingsResponse`:

```json
{
  "yolo_mode": false,
  "step_streaming": true,
  "backend": "sdk",
  "model": "claude-sonnet-4-5-20250929",
  "provider": "anthropic",
  "available_models": ["claude-opus-4-6", "claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001"],

  "provider_config": {
    "mode": "anthropic",
    "api_key_set": true,
    "base_url": null,
    "custom_models": []
  },

  "proxy": {
    "enabled": false,
    "type": "http",
    "host": "",
    "port": 0,
    "username": "",
    "password_set": false,
    "no_proxy": "localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8"
  },

  "runtime": {
    "max_turns": 50,
    "timeout": 600,
    "step_streaming": true,
    "permission_mode": "default",
    "yolo_mode": false
  },

  "claude_account": {
    "active": false,
    "credentials_exist": false,
    "subscription_type": null,
    "rate_limit_tier": null,
    "expires_at": null,
    "scopes": []
  },

  "infra": {
    "ssh_host": "host.docker.internal",
    "ssh_port": 22,
    "ssh_user": "root",
    "gitlab_url": "https://gitlab.com",
    "gitlab_token_set": false,
    "alert_cpu": 80.0,
    "alert_memory": 85.0,
    "alert_disk": 90.0,
    "debug": false,
    "log_level": "INFO"
  },

  "permission_mode": "default",
  "language": "ru"
}
```

**Notes**:
- Top-level `yolo_mode`, `step_streaming`, `backend`, `model`, `provider`, `permission_mode`, `language` remain as **backward-compatible aliases** for existing clients
- New nested objects (`provider_config`, `proxy`, `runtime`, `claude_account`, `infra`) are the **canonical source of truth**
- Field duplication mapping: `provider` ↔ `provider_config.mode`, `step_streaming` ↔ `runtime.step_streaming`, `yolo_mode` ↔ `runtime.yolo_mode`, `permission_mode` ↔ `runtime.permission_mode`
- When updating via PATCH, both top-level alias and nested field are synced automatically
- Existing clients ignore new fields (Pydantic v2 backward-compatible)

---

## PATCH /api/settings

**Summary**: Update settings (partial update)

**Request Body** — `UpdateSettingsRequest`:

```json
{
  "yolo_mode": true,
  "model": "claude-opus-4-6",
  "provider": "zai",

  "provider_config": {
    "mode": "zai",
    "api_key": "sk-...",
    "base_url": "https://open.bigmodel.cn/api/anthropic"
  },

  "proxy": {
    "enabled": true,
    "type": "http",
    "host": "proxy.corp.com",
    "port": 8080,
    "username": "admin",
    "password": "secret123",
    "no_proxy": "localhost,127.0.0.1,192.168.0.0/16"
  },

  "runtime": {
    "max_turns": 20,
    "timeout": 300
  },

  "infra": {
    "debug": true,
    "alert_cpu": 90.0
  }
}
```

**Validation Rules**:
- All fields are optional (partial update)
- `provider_config.mode`: must be `anthropic`, `zai`, or `local`
- `provider_config.api_key`: validated against provider before saving; on failure returns 422
- `proxy.port`: 1–65535
- `runtime.max_turns`: 1–999
- `runtime.timeout`: 10–3600
- `infra.alert_*`: 0.0–100.0
- `infra.log_level`: `DEBUG`, `INFO`, `WARNING`, `ERROR`

**Response 200** — returns full `SettingsResponse` (same as GET)

**Response 422** — validation error:

```json
{
  "detail": [
    {
      "loc": ["body", "provider_config", "api_key"],
      "msg": "API key validation failed: 401 Unauthorized",
      "type": "value_error"
    }
  ]
}
```

---

## POST /api/settings/provider/validate

**Summary**: Validate API key against provider without saving

**Request Body**:

```json
{
  "provider": "zai",
  "api_key": "sk-...",
  "base_url": "https://open.bigmodel.cn/api/anthropic"
}
```

**Response 200**:

```json
{
  "valid": true,
  "models": ["claude-opus-4-6", "claude-sonnet-4-5-20250929"],
  "message": "API key is valid"
}
```

**Response 200 (invalid key)**:

```json
{
  "valid": false,
  "models": [],
  "message": "Invalid API key (401 Unauthorized)"
}
```

---

## POST /api/settings/models/custom

**Summary**: Add a custom model ID to the current provider's model list

**Request Body**:

```json
{
  "provider": "anthropic",
  "model_id": "claude-custom-model-v1"
}
```

**Validation**:
- `model_id` must be non-empty string, max 128 chars
- Max 20 custom models per provider
- No duplicate model IDs (across default + custom)

**Response 200** — returns updated model list:

```json
{
  "provider": "anthropic",
  "models": ["claude-opus-4-6", "claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001", "claude-custom-model-v1"],
  "custom_models": ["claude-custom-model-v1"]
}
```

**Response 422** — limit exceeded or duplicate:

```json
{
  "detail": "Maximum 20 custom models per provider"
}
```

---

## DELETE /api/settings/models/custom

**Summary**: Remove a custom model from the provider's model list

**Request Body**:

```json
{
  "provider": "anthropic",
  "model_id": "claude-custom-model-v1"
}
```

**Response 200** — returns updated model list (same format as POST)

**Side effect**: If the deleted model was currently selected, resets to first available model

---

## POST /api/settings/claude-account/credentials

**Summary**: Upload Claude Account credentials (`.credentials.json` content)

**Request Body**:

```json
{
  "credentials_json": "{\"claudeAiOauth\": {\"accessToken\": \"...\", \"refreshToken\": \"...\", ...}}"
}
```

**Response 200**:

```json
{
  "success": true,
  "subscription_type": "claude_pro_monthly",
  "rate_limit_tier": "tier4",
  "message": "Credentials saved successfully"
}
```

**Response 422** — invalid format:

```json
{
  "detail": "Invalid credentials format: missing claudeAiOauth"
}
```

---

## POST /api/settings/proxy/test

**Summary**: Test proxy connection without saving configuration

**Request Body**:

```json
{
  "type": "http",
  "host": "proxy.corp.com",
  "port": 8080,
  "username": "admin",
  "password": "secret"
}
```

**Response 200**:

```json
{
  "success": true,
  "message": "Proxy connection successful",
  "latency_ms": 142
}
```

**Response 200 (failed)**:

```json
{
  "success": false,
  "message": "Connection refused: proxy.corp.com:8080",
  "latency_ms": null
}
```

---

## Error Responses (all endpoints)

| Status | Description |
|--------|-------------|
| 401 | Not authenticated |
| 403 | Not authorized (non-admin) |
| 422 | Validation error (Pydantic or business logic) |
| 500 | Internal server error |
