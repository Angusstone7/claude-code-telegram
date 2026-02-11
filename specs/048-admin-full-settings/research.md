# Research: Admin Panel Full Settings

## R1: How to extend settings API without breaking existing clients

**Decision**: Extend existing `SettingsResponse` and `UpdateSettingsRequest` Pydantic models with new optional fields. New fields have defaults, so existing clients continue to work.

**Rationale**: Adding optional fields to Pydantic v2 models is backward-compatible. Frontend clients that don't know about new fields simply ignore them. This avoids versioning overhead.

**Alternatives considered**:
- Create separate endpoints per settings category (e.g., `/settings/provider`, `/settings/proxy`) — rejected because it fragments the settings UI and requires multiple API calls.
- Create a v2 settings endpoint — rejected as premature; the existing endpoint can be extended cleanly.

## R2: API key storage strategy

**Decision**: Store API keys in `RuntimeConfigService` (in-memory dict with optional file persistence). Keys are set as `os.environ` variables when provider is switched so that the SDK/CLI picks them up. API responses return `api_key_set: true/false` instead of the actual key.

**Rationale**: The existing `AccountService` already manages env vars for provider switching. RuntimeConfig extends this pattern for the REST API. Never returning keys in GET responses prevents accidental exposure.

**Alternatives considered**:
- Store in SQLite via AccountRepository — rejected because the existing pattern uses env vars, and SDK reads from `os.environ` directly.
- Store encrypted in a secrets file — overkill for a single-admin local deployment.

## R3: Custom model list persistence

**Decision**: Store custom models per provider in RuntimeConfig as `settings.custom_models.{provider}` (JSON list). Merge with default models when returning `available_models`.

**Rationale**: Simple key-value storage, no schema changes needed. Custom models are appended to the default list, so defaults are always available.

**Alternatives considered**:
- SQLite table for models — overkill for a list of strings.
- Config file — RuntimeConfig already provides file persistence.

## R4: Proxy configuration mechanism

**Decision**: Store proxy settings in RuntimeConfig. On save, set `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` environment variables. On disable, unset them.

**Rationale**: Python's `httpx`, `aiohttp`, and the Anthropic SDK all respect standard proxy env vars. Setting them at runtime applies immediately without restart.

**Alternatives considered**:
- Pass proxy config directly to each HTTP client — rejected because too many clients to patch (SDK, API service, etc.).
- Docker-level proxy — doesn't allow runtime switching.

## R5: SettingsPage UI organization

**Decision**: Organize settings into collapsible sections (cards) on a single scrollable page. Sections: Profile (read-only), Provider & Auth, Models, Proxy, Claude Code Runtime, Claude Account, Infrastructure.

**Rationale**: Single page avoids navigation overhead. Collapsible sections keep the page manageable. Matches the existing card-based dark theme design.

**Alternatives considered**:
- Tabbed settings page — rejected because it hides information and adds navigation complexity.
- Separate settings pages — rejected because it fragments related settings.

## R6: Provider validation approach

**Decision**: On API key save, make a lightweight `GET /v1/models` request to the provider's base URL to validate the key. Return validation result to the frontend. Store key only on success.

**Rationale**: The models endpoint is available on all Claude-compatible APIs (Anthropic, z.ai) and is low-cost. It confirms both the key and the endpoint are valid.

**Alternatives considered**:
- Skip validation — rejected because invalid keys would cause silent failures later.
- Send a test chat completion — too expensive and slow.
