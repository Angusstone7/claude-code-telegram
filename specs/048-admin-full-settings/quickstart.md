# Quickstart: Admin Panel — Full Settings & Provider Authentication

**Feature**: [spec.md](spec.md) | **Contracts**: [contracts/settings-api.md](contracts/settings-api.md)

## Integration Scenarios

### Scenario 1: Switch Provider to z.ai with API Key

**User Story**: US1 — Provider Authentication & Model Management

```
1. Open Settings page → GET /api/settings
2. Click "z.ai" provider button → local state update
3. Enter API key in the text field
4. Click "Validate" → POST /api/settings/provider/validate
   Body: { "provider": "zai", "api_key": "sk-...", "base_url": "https://open.bigmodel.cn/api/anthropic" }
   Response: { "valid": true, "models": [...] }
5. Click "Save" → PATCH /api/settings
   Body: { "provider": "zai", "provider_config": { "mode": "zai", "api_key": "sk-...", "base_url": "..." } }
6. UI updates: model dropdown shows z.ai models
7. Subsequent AI requests use z.ai backend
```

**Expected backend side effects**:
- `os.environ["ANTHROPIC_BASE_URL"]` = `"https://open.bigmodel.cn/api/anthropic"`
- `os.environ["ANTHROPIC_AUTH_TOKEN"]` = `"sk-..."`
- RuntimeConfig `settings.provider` = `"zai"`

---

### Scenario 2: Add Custom Model

**User Story**: US1 — Provider Authentication & Model Management

```
1. Settings page loaded, provider is "anthropic"
2. Click "Add model" button
3. Enter model ID "my-fine-tuned-model-v3" in input
4. Click confirm → POST /api/settings/models/custom
   Body: { "provider": "anthropic", "model_id": "my-fine-tuned-model-v3" }
   Response: { "models": [..., "my-fine-tuned-model-v3"], "custom_models": ["my-fine-tuned-model-v3"] }
5. Model dropdown updates to include the new model
6. Select the custom model → local state update
7. Save → PATCH /api/settings { "model": "my-fine-tuned-model-v3" }
```

---

### Scenario 3: Configure Proxy

**User Story**: US2 — Proxy Configuration

```
1. Open Settings → GET /api/settings
2. Toggle proxy "enabled" on
3. Fill: type=http, host=proxy.corp.com, port=8080, username=admin, password=***
4. Optionally edit NO_PROXY list
5. Save → PATCH /api/settings
   Body: {
     "proxy": {
       "enabled": true, "type": "http",
       "host": "proxy.corp.com", "port": 8080,
       "username": "admin", "password": "secret",
       "no_proxy": "localhost,127.0.0.1,192.168.0.0/16"
     }
   }
6. Backend sets HTTP_PROXY=http://admin:secret@proxy.corp.com:8080
7. All outbound API calls now route through proxy
```

**Disable proxy** (preserves config):
```
PATCH /api/settings { "proxy": { "enabled": false } }
→ Backend unsets HTTP_PROXY, HTTPS_PROXY
→ Next GET returns proxy config with enabled=false but host/port preserved
```

---

### Scenario 4: Change Runtime Parameters

**User Story**: US3 — Claude Code Runtime Settings

```
1. Open Settings → GET /api/settings
2. Change max_turns input to 20
3. Change timeout slider to 300
4. Toggle step_streaming off
5. Save → PATCH /api/settings
   Body: { "runtime": { "max_turns": 20, "timeout": 300, "step_streaming": false } }
6. Backend sets CLAUDE_MAX_TURNS=20, CLAUDE_TIMEOUT=300, CLAUDE_STEP_STREAMING=false
7. Next AI session uses new limits
```

---

### Scenario 5: Upload Claude Account Credentials

**User Story**: US4 — Claude Account OAuth

```
1. Open Settings → GET /api/settings
   Response includes: claude_account.credentials_exist = false
2. User pastes .credentials.json content into textarea
3. Click "Save credentials" → POST /api/settings/claude-account/credentials
   Body: { "credentials_json": "{\"claudeAiOauth\": {...}}" }
   Response: { "success": true, "subscription_type": "claude_pro_monthly" }
4. UI updates to show subscription status
5. Provider mode can be switched to "claude_account" if desired
```

---

### Scenario 6: View and Edit Infrastructure Settings

**User Story**: US5 — Infrastructure Settings

```
1. Open Settings → GET /api/settings
   Response includes: infra.ssh_host, infra.gitlab_url, etc.
2. Change SSH host to "192.168.1.100"
3. Enter GitLab token
4. Toggle debug mode on
5. Save → PATCH /api/settings
   Body: {
     "infra": {
       "ssh_host": "192.168.1.100",
       "gitlab_token": "glpat-...",
       "debug": true
     }
   }
6. Backend updates SSH_HOST env, GITLAB_TOKEN env, DEBUG=true
```

## Edge Case Scenarios

### Invalid API Key
```
POST /api/settings/provider/validate
Body: { "provider": "zai", "api_key": "invalid-key" }
Response 200: { "valid": false, "message": "Invalid API key (401 Unauthorized)" }
→ UI shows error toast, does NOT save the key
```

### Custom Model Limit Exceeded
```
POST /api/settings/models/custom  (21st model)
Response 422: { "detail": "Maximum 20 custom models per provider" }
→ UI shows validation error
```

### Remove Currently Selected Custom Model
```
DELETE /api/settings/models/custom
Body: { "provider": "anthropic", "model_id": "currently-selected-model" }
Response 200: { "models": [defaults...], "custom_models": [] }
→ Backend resets settings.model to first available model
→ UI model dropdown resets, notification shown
```

### Max Turns = 0
```
PATCH /api/settings { "runtime": { "max_turns": 0 } }
Response 422: validation error — minimum is 1
```

## Frontend State Management

```
settingsStore (Zustand):
  settings: SettingsResponse | null    // full server state
  isLoading: boolean
  error: string | null

  fetchSettings() → GET /api/settings → updates settings
  updateSettings(patch) → PATCH /api/settings → updates settings
  validateProvider(data) → POST /api/settings/provider/validate → returns result
  addCustomModel(provider, modelId) → POST /api/settings/models/custom → refreshes settings
  removeCustomModel(provider, modelId) → DELETE /api/settings/models/custom → refreshes settings
  uploadCredentials(json) → POST /api/settings/claude-account/credentials → refreshes settings
```
