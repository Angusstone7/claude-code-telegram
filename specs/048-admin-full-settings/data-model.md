# Data Model: Admin Panel — Full Settings & Provider Authentication

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Entities

### ProviderConfig

Represents an API provider configuration with credentials and model list.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| mode | enum | `anthropic` \| `zai` \| `local` | Active provider mode |
| api_key_set | bool | read-only | Whether an API key is stored (never expose actual key) |
| base_url | string? | valid URL | Custom endpoint URL (required for `zai` and `local`) |
| custom_models | string[] | max 20 per provider | User-added model IDs |

**State transitions**: `anthropic` ↔ `zai` ↔ `local` (any-to-any switching allowed)

**Validation rules**:
- `api_key` validated against provider's `/v1/models` endpoint before save
- `base_url` required for `zai` and `local` modes; auto-set for `zai` to `https://open.bigmodel.cn/api/anthropic`
- `custom_models` merged with default models when returning `available_models` list

**Storage**: RuntimeConfigService keys:
- `settings.provider` → mode
- `settings.provider.{mode}.api_key` → encrypted/env key
- `settings.provider.{mode}.base_url` → endpoint URL
- `settings.custom_models.{mode}` → JSON list of custom model IDs

---

### ProxyConfig

Represents HTTP/HTTPS/SOCKS5 proxy configuration.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| enabled | bool | default `false` | Whether proxy is active |
| type | enum | `http` \| `https` \| `socks5` | Proxy protocol |
| host | string | non-empty when enabled | Proxy hostname or IP |
| port | int | 1–65535 | Proxy port |
| username | string? | — | Optional auth username |
| password | string? | — | Optional auth password (masked in responses) |
| no_proxy | string | default `localhost,127.0.0.1,...` | Comma-separated bypass list |

**Validation rules**:
- When `enabled=true`, `host` and `port` are required
- `password` never returned in API responses; only `password_set: bool`
- Disabling preserves configuration (re-enable without re-entering)

**Side effects on save**:
- Sets `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` environment variables
- Unsets them when disabled

**Storage**: RuntimeConfigService keys:
- `settings.proxy.enabled` → bool
- `settings.proxy.type` → string
- `settings.proxy.host` → string
- `settings.proxy.port` → int
- `settings.proxy.username` → string
- `settings.proxy.password` → string (sensitive)
- `settings.proxy.no_proxy` → string

---

### RuntimeSettings

Represents Claude Code runtime parameters.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| max_turns | int | 1–999, default 50 | Max conversation turns per session |
| timeout | int | 10–3600, default 600 | Request timeout in seconds |
| step_streaming | bool | default `true` | Stream SDK tool-use steps individually |
| permission_mode | enum | `default` \| `auto` \| `never` | SDK permission handling |
| yolo_mode | bool | default `false` | Auto-approve all operations |
| language | enum | `ru` \| `en` \| `zh` | UI and response language |
| backend | enum | `sdk` \| `cli` | Claude Code backend mode |

**Side effects on save**:
- `max_turns` → sets `CLAUDE_MAX_TURNS` env var
- `timeout` → sets `CLAUDE_TIMEOUT` env var
- `step_streaming` → sets `CLAUDE_STEP_STREAMING` env var

**Storage**: RuntimeConfigService keys (existing pattern):
- `settings.max_turns`, `settings.timeout`, `settings.step_streaming`
- `settings.permission_mode`, `settings.yolo_mode`, `settings.language`, `settings.backend`

---

### ClaudeAccountInfo

Represents Claude Account (OAuth) status and credentials — read-mostly.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| active | bool | read-only | Whether Claude Account mode is active |
| credentials_exist | bool | read-only | Whether `.credentials.json` file exists |
| subscription_type | string? | read-only | e.g., "claude_pro_monthly" |
| rate_limit_tier | string? | read-only | e.g., "tier4" |
| expires_at | datetime? | read-only | OAuth token expiry |
| scopes | string[] | read-only | OAuth scopes granted |

**Source**: Read from `CredentialsInfo.from_file()` in `AccountService`

**Write path**: Upload/paste `.credentials.json` content → `AccountService.save_credentials()`

---

### InfraConfig

Represents infrastructure settings — SSH, GitLab, monitoring, debug.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| ssh_host | string | default from `SSHConfig` | SSH server hostname |
| ssh_port | int | 1–65535, default 22 | SSH server port |
| ssh_user | string | default "root" | SSH username |
| gitlab_url | string | valid URL | GitLab instance URL |
| gitlab_token_set | bool | read-only | Whether GitLab token is stored |
| alert_cpu | float | 0–100, default 80.0 | CPU alert threshold % |
| alert_memory | float | 0–100, default 85.0 | Memory alert threshold % |
| alert_disk | float | 0–100, default 90.0 | Disk alert threshold % |
| debug | bool | default `false` | Debug mode toggle |
| log_level | enum | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` | Log verbosity |

**Source**: `SSHConfig`, `GitLabConfig`, `MonitoringConfig` from `shared/config/settings.py`

**Side effects on save**:
- SSH params → update `SSHConfig` env vars
- GitLab token → set `GITLAB_TOKEN` env var
- Debug mode → set `DEBUG` env var, adjust logging level
- Alert thresholds → set `ALERT_THRESHOLD_*` env vars

## Entity Relationships

```
ProviderConfig ──uses──→ available_models (default + custom)
     │
     ├── mode=anthropic → uses ANTHROPIC_API_KEY
     ├── mode=zai       → uses ANTHROPIC_BASE_URL + AUTH_TOKEN
     └── mode=local     → uses custom base_url + model_name

ProxyConfig ──applies-to──→ outbound HTTP (API calls, Telegram)
     │
     └── used-by → ClaudeAccountInfo (OAuth needs proxy for claude.ai)

RuntimeSettings ──controls──→ Claude Code SDK/CLI behavior
     │
     └── backend ──selects──→ SDK or CLI execution path

InfraConfig ──configures──→ SSH, GitLab, Monitoring subsystems
```

## Storage Strategy

All settings use **RuntimeConfigService** (in-memory dict with env var fallbacks):

1. **Read priority**: RuntimeConfig override → environment variable → code default
2. **Write**: PATCH endpoint stores in RuntimeConfig + sets `os.environ` for side effects
3. **Persistence**: RuntimeConfig optionally writes to file for restart survival
4. **Sensitive fields**: API keys stored but never returned in GET responses; only `*_set: bool` flags
