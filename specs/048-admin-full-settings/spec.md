# Feature Specification: Admin Panel — Full Settings & Provider Authentication

**Feature Branch**: `048-admin-full-settings`
**Created**: 2026-02-11
**Status**: Draft
**Input**: User description: "Добавить управление списком моделей, авторизацию в Claude Code и z.ai, настройку прокси и перенос всех оставшихся настроек из Telegram в админ-панель браузера"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Provider Authentication & Model Management (Priority: P1)

Administrator configures API providers (Anthropic, z.ai, Local Model) with their credentials directly from the browser admin panel, and manages the list of available models per provider — including adding custom model IDs.

**Why this priority**: Without provider authentication the admin panel cannot actually control which AI backend is used. This is the foundation for all other settings — if the user cannot authenticate with a provider, nothing else works.

**Independent Test**: Open Settings page, switch provider to z.ai, enter API key, save. Verify that subsequent AI requests go through z.ai. Switch to Local Model, enter endpoint URL and model name, save. Verify connection. Switch back to Anthropic, confirm API key is still stored. Add a new custom model ID to the provider's model list, confirm it appears in the model dropdown.

**Acceptance Scenarios**:

1. **Given** admin is on Settings page, **When** they select "z.ai" provider and enter an API key, **Then** the key is saved and the system uses z.ai for subsequent requests
2. **Given** admin is on Settings page, **When** they select "Local Model" and enter a base URL + model name, **Then** the system validates the connection and saves the configuration
3. **Given** admin is on Settings page, **When** they select "Anthropic" provider, **Then** the system uses the stored Anthropic API key (from environment or previously saved)
4. **Given** admin is viewing the model list, **When** they click "Add model" and type a custom model ID, **Then** the new model appears in the dropdown and can be selected
5. **Given** admin has added a custom model, **When** they remove it from the list, **Then** it disappears from the dropdown and the current model resets to default if it was selected
6. **Given** admin switches provider from "Anthropic" to "z.ai", **Then** the model dropdown updates to show models available for z.ai

---

### User Story 2 — Proxy Configuration (Priority: P2)

Administrator configures HTTP/HTTPS/SOCKS5 proxy settings from the browser admin panel. The proxy is used for outbound API calls to Claude/z.ai and optionally for Telegram API calls.

**Why this priority**: Many deployments operate behind corporate proxies. Without proxy settings in the admin panel, users must SSH into the server to edit environment variables.

**Independent Test**: Open Settings page, navigate to Proxy section, enter proxy address and type, save. Verify that outbound API calls route through the configured proxy. Disable proxy, verify direct connection resumes.

**Acceptance Scenarios**:

1. **Given** admin is on Settings page, **When** they enable proxy and enter host:port with type HTTP, **Then** the proxy configuration is saved and applied to outbound API requests
2. **Given** proxy requires authentication, **When** admin enters username and password, **Then** credentials are stored securely and used for proxy auth
3. **Given** proxy is configured, **When** admin disables it, **Then** direct connection is restored without deleting the saved configuration
4. **Given** admin sets NO_PROXY bypass list, **When** requests are made to bypassed addresses, **Then** those requests skip the proxy

---

### User Story 3 — Claude Code Runtime Settings (Priority: P3)

Administrator configures Claude Code runtime parameters: max conversation turns, request timeout, step streaming, and plugin management — all from the browser admin panel.

**Why this priority**: These settings affect day-to-day AI interaction quality. Currently only accessible via environment variables or Telegram menus.

**Independent Test**: Open Settings, change max turns to 20, timeout to 300s, toggle step streaming off. Save. Send a request and verify the new limits apply.

**Acceptance Scenarios**:

1. **Given** admin is on Settings page, **When** they change max turns to 20, **Then** Claude Code sessions are limited to 20 turns
2. **Given** admin is on Settings page, **When** they change timeout to 300 seconds, **Then** requests exceeding 300s are terminated
3. **Given** admin is on Settings page, **When** they toggle step streaming off, **Then** Claude Code responses arrive as complete messages instead of streamed steps
4. **Given** admin is on Settings page, **When** they view the plugins section, **Then** they see all available plugins with enable/disable toggles

---

### User Story 4 — Claude Account (OAuth) Management (Priority: P4)

Administrator manages Claude Account (OAuth) authentication — viewing subscription status, entering credentials from the `.credentials.json` file, and seeing OAuth expiry information.

**Why this priority**: Claude Account mode is an alternative auth method that some users prefer over direct API keys. It needs to be manageable from the admin panel.

**Independent Test**: Open Settings, switch to Claude Account mode, view subscription status (tier, expiry). If credentials are missing, upload or paste `.credentials.json` content. Save and verify authentication works.

**Acceptance Scenarios**:

1. **Given** admin selects Claude Account mode, **When** credentials exist, **Then** subscription status (tier, expiry, scopes) is displayed
2. **Given** admin selects Claude Account mode, **When** no credentials exist, **Then** a form to paste or upload `.credentials.json` content is shown
3. **Given** admin enters valid credentials, **When** they save, **Then** the system validates and stores them, switching to Claude Account mode

---

### User Story 5 — Infrastructure Settings (Priority: P5)

Administrator views and configures infrastructure parameters: SSH connection, GitLab integration, monitoring thresholds, and debug/logging settings.

**Why this priority**: These are advanced settings that most users rarely change. Nice to have in the admin panel but not critical for daily operations.

**Independent Test**: Open Settings, change SSH host, save. Open Settings, change GitLab token, save. Toggle debug mode on, verify increased log verbosity.

**Acceptance Scenarios**:

1. **Given** admin is on Settings page, **When** they edit SSH host/port/user, **Then** subsequent SSH commands use the new configuration
2. **Given** admin is on Settings page, **When** they enter GitLab URL and token, **Then** GitLab page shows repositories from the configured instance
3. **Given** admin is on Settings page, **When** they change alert thresholds for CPU/memory/disk, **Then** dashboard metrics use the new thresholds for visual indicators
4. **Given** admin toggles debug mode on, **When** they check logs, **Then** debug-level messages are present

---

### Edge Cases

- What happens when admin enters an invalid API key? System validates and shows error before saving.
- What happens when proxy is misconfigured? System attempts a test connection and warns if it fails, but still saves the configuration.
- What happens when max turns is set to 0 or a negative number? System rejects with validation error, enforcing minimum of 1.
- What happens when admin switches provider while a chat session is active? Current session continues with old provider; new provider applies to next session.
- What happens when the custom model list exceeds reasonable size? System limits to 20 custom models per provider.
- What happens when admin removes a model that is currently selected? System resets to the first available model and shows a notification.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support three provider modes: Anthropic (direct API), z.ai (compatible API), and Local Model (custom endpoint)
- **FR-002**: System MUST store API keys securely per provider and recall them when switching between providers
- **FR-003**: System MUST allow administrators to add and remove custom model IDs to each provider's model list
- **FR-004**: System MUST display the current provider's model list in the model selector dropdown, updating dynamically when provider changes
- **FR-005**: System MUST support proxy configuration with type (HTTP/HTTPS/SOCKS5), host, port, and optional username/password
- **FR-006**: System MUST apply proxy settings to outbound API calls within the same runtime session (no restart required)
- **FR-007**: System MUST provide configurable runtime parameters: max turns (1-999), timeout (10-3600 seconds), step streaming toggle
- **FR-008**: System MUST display Claude Account subscription information (tier, expiry) when OAuth mode is active
- **FR-009**: System MUST allow input of Claude Account credentials (`.credentials.json` content)
- **FR-010**: System MUST provide infrastructure settings: SSH connection params, GitLab integration, monitoring thresholds, debug mode
- **FR-011**: System MUST validate API keys before saving by making a lightweight test request to the provider
- **FR-012**: System MUST persist all settings in runtime config with environment variable fallbacks for initial values
- **FR-013**: System MUST provide a NO_PROXY bypass list for addresses that should skip the proxy

### Key Entities

- **ProviderConfig**: Represents an API provider with mode (anthropic/zai/local), credentials (API key or OAuth), base URL, and custom model list
- **ProxyConfig**: Represents proxy settings with type, host, port, optional auth credentials, enabled flag, and bypass list
- **RuntimeSettings**: Represents Claude Code runtime parameters — max turns, timeout, step streaming, permission mode, YOLO mode, language
- **InfraConfig**: Represents infrastructure settings — SSH params, GitLab credentials, monitoring thresholds, debug/log level

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All settings currently manageable only via Telegram menus or environment variables are accessible from the browser admin panel within 2 clicks from the Settings page
- **SC-002**: Provider switching (including credential entry) completes in under 30 seconds from the Settings page
- **SC-003**: 100% of settings changes take effect immediately without requiring application restart
- **SC-004**: Admin can add a new custom model and select it within 10 seconds
- **SC-005**: Proxy configuration can be fully set up (type, host, port, auth) in under 1 minute from the Settings page
- **SC-006**: All sensitive fields (API keys, passwords, proxy credentials) are masked in the UI and never exposed in API responses beyond confirmation of existence

## Assumptions

- API key validation is done via a lightweight models/list or health-check request to the provider
- Local Model mode supports any OpenAI-compatible API endpoint (LMStudio, Ollama, vLLM, etc.)
- The `.credentials.json` format for Claude Account follows the existing structure used by Claude CLI
- Proxy settings apply at the application level (not per-user), as there is a single deployment
- Step streaming refers to `CLAUDE_STEP_STREAMING` which controls whether SDK tool-use steps are streamed individually
- SSH, GitLab, and monitoring settings are editable from the admin panel (same as all other settings categories)
- Maximum of 20 custom models per provider to prevent dropdown overflow
- "Securely" for API key storage means: stored in-memory via RuntimeConfig, never exposed in GET API responses (only `*_set: bool` flags), no at-rest encryption (acceptable for single-admin local deployment)
