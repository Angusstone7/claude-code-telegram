# Tasks: Admin Panel — Full Settings & Provider Authentication

**Input**: Design documents from `/specs/048-admin-full-settings/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/settings-api.md, research.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend all schema/type files with new structures needed by all user stories

- [x] T001 Extend backend Pydantic schemas with nested models (ProviderConfigResponse, ProviderConfigUpdate, ProxyConfigResponse, ProxyConfigUpdate, RuntimeConfigResponse, RuntimeConfigUpdate, ClaudeAccountResponse, InfraConfigResponse, InfraConfigUpdate, ProviderValidateRequest, ProviderValidateResponse, CustomModelRequest, CustomModelResponse, CredentialsUploadRequest, CredentialsUploadResponse) and update SettingsResponse/UpdateSettingsRequest to include optional nested objects; update `provider` field regex to `^(anthropic|zai|local)$` to support all three provider modes in `presentation/api/schemas/settings.py`
- [x] T002 [P] Extend TypeScript types with matching interfaces (ProviderConfig, ProxyConfig, RuntimeConfig, ClaudeAccountInfo, InfraConfig, ProviderValidateRequest, ProviderValidateResponse, CustomModelRequest, CustomModelResponse, CredentialsUploadRequest, CredentialsUploadResponse) and update SettingsResponse/UpdateSettingsRequest in `frontend/src/types/api.ts`
- [x] T003 [P] Add i18n keys for all new settings sections (provider auth, proxy, runtime, claude account, infrastructure) to `frontend/src/i18n/ru.json`, `frontend/src/i18n/en.json`, and `frontend/src/i18n/zh.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend helpers and frontend store extensions that MUST be complete before any user story UI work

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add `get_account_service()` dependency function to `presentation/api/dependencies.py` that returns `AccountService` from the DI container
- [x] T005 Add helper functions to `presentation/api/routes/settings.py`: `_get_provider_config()` to read provider state (mode, api_key_set, base_url, custom_models from RuntimeConfig), `_get_proxy_config()` to read proxy state from RuntimeConfig/env vars, `_get_runtime_config()` to read max_turns/timeout from env vars, `_get_claude_account_info()` to read from AccountService/CredentialsInfo, `_get_infra_config()` to read from SSHConfig/GitLabConfig/MonitoringConfig/Settings env vars
- [x] T006 Extend `frontend/src/stores/settingsStore.ts` with new actions: `validateProvider(provider, apiKey, baseUrl)` calling POST `/settings/provider/validate`, `addCustomModel(provider, modelId)` calling POST `/settings/models/custom`, `removeCustomModel(provider, modelId)` calling DELETE `/settings/models/custom`, `uploadCredentials(json)` calling POST `/settings/claude-account/credentials` — each returns typed response and refreshes settings after success

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Provider Auth & Model Management (Priority: P1) 🎯 MVP

**Goal**: Admin configures API providers (Anthropic, z.ai, Local Model) with credentials and manages custom model lists per provider

**Independent Test**: Open Settings, switch to z.ai, enter API key, validate, save. Add custom model, verify in dropdown. Switch to Anthropic, confirm key preserved.

### Implementation for User Story 1

- [x] T007 [US1] Add POST `/settings/provider/validate` endpoint to `presentation/api/routes/settings.py` — accepts provider, api_key, base_url; for anthropic/zai: makes GET request to provider's /v1/models endpoint; for local: tries GET /v1/models first, if 404 falls back to GET base_url health-check; returns {valid, models, message}; uses httpx async client with 10s timeout
- [x] T008 [US1] Add POST `/settings/models/custom` endpoint to `presentation/api/routes/settings.py` — accepts provider, model_id; stores in RuntimeConfig key `settings.custom_models.{provider}` as JSON list; validates max 20 per provider, no duplicates; returns updated models list merging defaults + custom
- [x] T009 [US1] Add DELETE `/settings/models/custom` endpoint to `presentation/api/routes/settings.py` — accepts provider, model_id; removes from custom models list; if deleted model was currently selected, resets `settings.model` to first available; returns updated models list
- [x] T010 [US1] Update GET `/settings` endpoint to include `provider_config` nested object in response by calling `_get_provider_config()` and merging custom models into `available_models` list in `presentation/api/routes/settings.py`
- [x] T011 [US1] Update PATCH `/settings` handler to process `provider_config` updates: validate API key if provided (call validate endpoint logic), set `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` env vars based on mode, store api_key in RuntimeConfig `settings.provider.{mode}.api_key`, update `settings.provider` in `presentation/api/routes/settings.py`
- [x] T012 [US1] Add Provider Auth UI section to `frontend/src/pages/SettingsPage.tsx` — expand existing Provider & Model section with: "Local Model" as third provider button, API key masked input field (shows dots, clearable), "Validate" button calling `validateProvider()` with status indicator (checkmark/cross), base URL input for zai/local modes, Local Model fields (model name, base URL)
- [x] T013 [US1] Add Custom Model editor UI to `frontend/src/pages/SettingsPage.tsx` — below model dropdown add: "Add model" button that reveals an input + confirm button, list of custom models with delete (X) buttons, badge showing count (e.g., "3 custom"), disable add button at 20 models limit with tooltip

**Checkpoint**: Provider Auth & Model Management fully functional. Admin can switch providers, enter API keys, validate, add/remove custom models.

---

## Phase 4: User Story 2 — Proxy Configuration (Priority: P2)

**Goal**: Admin configures HTTP/HTTPS/SOCKS5 proxy from browser admin panel, applied to outbound API calls without restart

**Independent Test**: Open Settings, enable proxy, fill host:port, save. Verify HTTP_PROXY env var set. Disable proxy, verify env var unset.

### Implementation for User Story 2

- [x] T014 [US2] Update GET `/settings` endpoint to include `proxy` nested object by calling `_get_proxy_config()` in `presentation/api/routes/settings.py` — reads from RuntimeConfig keys `settings.proxy.*` with env var fallbacks (HTTP_PROXY, HTTPS_PROXY, NO_PROXY)
- [x] T015 [US2] Update PATCH `/settings` handler to process `proxy` updates: when enabled, build proxy URL from type/host/port/auth and set `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` env vars; when disabled, unset proxy env vars but preserve config in RuntimeConfig; store all proxy fields in RuntimeConfig `settings.proxy.*` in `presentation/api/routes/settings.py`
- [x] T016 [US2] Add Proxy Configuration UI section to `frontend/src/pages/SettingsPage.tsx` — new card section with Network/Globe icon: enable/disable toggle, proxy type selector (HTTP/HTTPS/SOCKS5 buttons), host input, port input (number), username input (optional), password masked input (optional), NO_PROXY textarea (comma-separated bypass list with default value), test connection status indicator

- [x] T016a [US2] Add POST `/settings/proxy/test` endpoint to `presentation/api/routes/settings.py` — accepts current proxy config (type, host, port, auth); attempts connection to a known URL (e.g., https://api.anthropic.com) through the proxy; returns {success, message, latency_ms}; uses httpx async client with 10s timeout

**Checkpoint**: Proxy Configuration functional. Admin can enable/disable proxy, configure type/host/port/auth, set bypass list, test connection.

---

## Phase 5: User Story 3 — Claude Code Runtime Settings (Priority: P3)

**Goal**: Admin configures runtime parameters: max turns, timeout, step streaming, and views plugin list

**Independent Test**: Open Settings, change max turns to 20, timeout to 300, toggle streaming off. Save. Verify env vars updated.

### Implementation for User Story 3

- [x] T017 [US3] Update GET `/settings` endpoint to include `runtime` nested object by calling `_get_runtime_config()` in `presentation/api/routes/settings.py` — reads `CLAUDE_MAX_TURNS` (default 50), `CLAUDE_TIMEOUT` (default 600) from env/RuntimeConfig; includes existing step_streaming, permission_mode, yolo_mode values
- [x] T018 [US3] Update PATCH `/settings` handler to process `runtime` updates: set `CLAUDE_MAX_TURNS`, `CLAUDE_TIMEOUT`, `CLAUDE_STEP_STREAMING` env vars; validate max_turns 1-999, timeout 10-3600; store in RuntimeConfig `settings.*` in `presentation/api/routes/settings.py`
- [x] T019 [US3] Add Runtime Settings UI section to `frontend/src/pages/SettingsPage.tsx` — new card with Cpu/Sliders icon: max_turns number input (1-999) with label and current value, timeout number input (10-3600) with label showing seconds, move existing step_streaming toggle here from top-level, move existing permission_mode selector here, move existing YOLO toggle here, move existing backend (SDK/CLI) selector here; consolidate scattered settings into one Runtime section
- [x] T019a [US3] Add GET `/settings/plugins` endpoint to `presentation/api/routes/settings.py` — reads plugin list from existing plugin system (CLAUDE_PLUGINS env var + /plugins directory scan); returns list of {name, enabled, description}; reuses existing PluginListResponse schema from `presentation/api/schemas/plugins.py`
- [x] T019b [US3] Add Plugins sub-section to Runtime Settings UI in `frontend/src/pages/SettingsPage.tsx` — below runtime params: list all plugins with enable/disable toggles, plugin name and description; uses GET `/settings/plugins` endpoint; enable/disable calls PATCH `/settings` with updated plugin list

**Checkpoint**: Runtime Settings functional. All Claude Code runtime params and plugin management configurable from one section.

---

## Phase 6: User Story 4 — Claude Account (OAuth) Management (Priority: P4)

**Goal**: Admin views Claude Account subscription status, uploads .credentials.json, manages OAuth auth

**Independent Test**: Open Settings, see Claude Account section. If no credentials, paste JSON. Save. Verify subscription info displayed.

### Implementation for User Story 4

- [x] T020 [US4] Update GET `/settings` endpoint to include `claude_account` nested object by calling `_get_claude_account_info()` in `presentation/api/routes/settings.py` — calls AccountService.get_credentials_info() for subscription_type, rate_limit_tier, expires_at, scopes; checks has_valid_credentials() for active status
- [x] T021 [US4] Add POST `/settings/claude-account/credentials` endpoint to `presentation/api/routes/settings.py` — accepts credentials_json string; calls AccountService.save_credentials(); returns success status with subscription info; returns 422 on invalid format
- [x] T022 [US4] Add Claude Account UI section to `frontend/src/pages/SettingsPage.tsx` — new card with Key/Lock icon: if credentials exist — show subscription type badge, rate limit tier, expiry date (formatted), scopes list; if no credentials — show textarea to paste .credentials.json content, "Save credentials" button calling `uploadCredentials()`; show "Delete credentials" button if credentials exist; status indicator (valid/expired/missing)

**Checkpoint**: Claude Account management functional. Admin can view status, upload credentials, see subscription info.

---

## Phase 7: User Story 5 — Infrastructure Settings (Priority: P5)

**Goal**: Admin views and configures SSH, GitLab, monitoring thresholds, and debug settings

**Independent Test**: Open Settings, see Infrastructure section. Change SSH host, GitLab token, debug toggle. Save. Verify env vars updated.

### Implementation for User Story 5

- [x] T023 [US5] Update GET `/settings` endpoint to include `infra` nested object by calling `_get_infra_config()` in `presentation/api/routes/settings.py` — reads SSH_HOST, SSH_PORT, HOST_USER from env/RuntimeConfig; reads GITLAB_URL, checks GITLAB_TOKEN existence (gitlab_token_set bool); reads ALERT_THRESHOLD_CPU/MEMORY/DISK from env; reads DEBUG, LOG_LEVEL from env
- [x] T024 [US5] Update PATCH `/settings` handler to process `infra` updates: set SSH_HOST, SSH_PORT, HOST_USER env vars; set GITLAB_URL, GITLAB_TOKEN env vars; set ALERT_THRESHOLD_CPU/MEMORY/DISK env vars; set DEBUG, LOG_LEVEL env vars and update logging config; store all in RuntimeConfig `settings.infra.*` in `presentation/api/routes/settings.py`
- [x] T025 [US5] Add Infrastructure Settings UI section as collapsible card to `frontend/src/pages/SettingsPage.tsx` — with Wrench/Server icon, collapsed by default with expand button: SSH sub-section (host input, port number input, user input), GitLab sub-section (URL input, token masked input, token_set indicator), Monitoring sub-section (CPU/Memory/Disk threshold sliders 0-100%), Debug sub-section (debug toggle, log level selector: DEBUG/INFO/WARNING/ERROR)

**Checkpoint**: Infrastructure settings accessible from admin panel. SSH, GitLab, monitoring thresholds, and debug mode configurable.

---

## Phase 8: Tests & Polish

**Purpose**: Unit tests (constitution XII compliance) and quality improvements

### Unit Tests (Constitution XII: business logic MUST be covered)

- [x] T026 [P] Unit tests for provider validate endpoint — test valid key returns {valid: true}, invalid key returns {valid: false}, local model fallback to health-check, timeout handling in `tests/unit/presentation/test_settings_provider_validate.py`
- [x] T027 [P] Unit tests for custom model CRUD — test add model, add duplicate rejected, max 20 limit, remove model, remove selected model resets to default in `tests/unit/presentation/test_settings_custom_models.py`
- [x] T028 [P] Unit tests for proxy save/apply — test enable sets HTTP_PROXY/HTTPS_PROXY env vars, disable unsets them, NO_PROXY preserved, password not in GET response in `tests/unit/presentation/test_settings_proxy.py`
- [x] T029 [P] Unit tests for credentials upload — test valid JSON saved, invalid JSON rejected 422, missing claudeAiOauth rejected, subscription info returned on success in `tests/unit/presentation/test_settings_credentials.py`
- [x] T030 [P] Unit tests for infra settings PATCH — test SSH env vars updated, GitLab token stored but not returned, debug mode toggles logging level, alert thresholds validated 0-100 in `tests/unit/presentation/test_settings_infra.py`

### Quality & Validation

- [x] T031 [P] Verify sensitive field masking across all endpoints — confirm API keys, passwords, tokens never appear in GET /settings response; only `*_set: bool` flags returned; audit all response schemas in `presentation/api/routes/settings.py`
- [x] T032 [P] Add error handling and validation feedback to all settings sections — show inline validation errors for invalid ranges (max_turns, timeout, port), display API validation results (provider key check), add toast notifications for save success/failure in `frontend/src/pages/SettingsPage.tsx`
- [x] T033 Run end-to-end validation of all 6 quickstart.md integration scenarios — test provider switching, custom model add/remove, proxy enable/disable, runtime param changes, credentials upload, infrastructure settings save

---

## Dependencies & Execution Order

### Phase Mapping (tasks.md → plan.md)

| tasks.md Phase | plan.md Phase | Content |
|---------------|---------------|---------|
| Phase 1: Setup | (pre-phase) | Schemas, types, i18n |
| Phase 2: Foundational | (pre-phase) | DI, helpers, store |
| Phase 3: US1 | Phase 1 | Provider Auth & Models |
| Phase 4: US2 | Phase 2 | Proxy Configuration |
| Phase 5: US3 | Phase 3 | Runtime Settings + Plugins |
| Phase 6: US4 | Phase 4 | Claude Account OAuth |
| Phase 7: US5 | Phase 5 | Infrastructure Settings |
| Phase 8: Tests & Polish | (post-phase) | Unit tests, masking audit, e2e |

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001-T003) completion — BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - Stories can proceed sequentially in priority order (P1 → P2 → P3 → P4 → P5)
  - Some parallel execution possible (see below)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) — Independent of US1
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) — Independent of US1/US2
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) — Uses AccountService (existing)
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) — Independent of other stories

### Within Each User Story

- Backend route changes before frontend UI
- GET endpoint changes before PATCH endpoint changes
- New endpoints (validate, custom models) before existing endpoint updates
- All tasks within a story are sequential (same files modified)

### File Conflict Map

The following files are modified by multiple stories (sequential execution required):

| File | Stories |
|------|---------|
| `presentation/api/routes/settings.py` | US1, US2, US3, US4, US5 |
| `frontend/src/pages/SettingsPage.tsx` | US1, US2, US3, US4, US5 |

### Parallel Opportunities

- **Phase 1**: T002 and T003 can run in parallel (different files)
- **Phase 2**: T004 and T006 can run in parallel (different files), but T005 depends on T004
- **Phase 8**: T026 and T027 can run in parallel (backend audit vs frontend improvements)

---

## Parallel Example: Phase 1

```bash
# All three tasks touch different files — can run in parallel:
Task T001: "Extend Pydantic schemas in presentation/api/schemas/settings.py"
Task T002: "Extend TypeScript types in frontend/src/types/api.ts"
Task T003: "Add i18n keys in frontend/src/i18n/{ru,en,zh}.json"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T006)
3. Complete Phase 3: User Story 1 (T007-T013)
4. **STOP and VALIDATE**: Test provider switching, API key validation, custom model management
5. Deploy/demo if ready — admin can now manage providers and models from browser

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy (MVP: Provider Auth & Models!)
3. Add User Story 2 → Test independently → Deploy (Proxy!)
4. Add User Story 3 → Test independently → Deploy (Runtime Settings!)
5. Add User Story 4 → Test independently → Deploy (Claude Account!)
6. Add User Story 5 → Test independently → Deploy (Infrastructure!)
7. Polish phase → Final quality pass

---

## Notes

- All changes extend existing files — no new files created (per plan.md decision)
- Existing SettingsPage sections (Profile, Provider & Model, Backend, Permission, Language) are preserved and reorganized
- US3 consolidates scattered toggles (step_streaming, permission_mode, YOLO, backend) into one Runtime section
- API keys and passwords are NEVER returned in GET responses — only `*_set: bool` flags
- Proxy env vars (HTTP_PROXY, HTTPS_PROXY, NO_PROXY) are set at process level for immediate effect
- Maximum 20 custom models per provider to prevent dropdown overflow
- All validation follows Pydantic v2 patterns with clear error messages
- Total tasks: 33 (T001-T033, including T016a, T019a, T019b)
