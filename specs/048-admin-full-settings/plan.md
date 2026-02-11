# Implementation Plan: Admin Panel — Full Settings & Provider Authentication

**Branch**: `048-admin-full-settings` | **Date**: 2026-02-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/048-admin-full-settings/spec.md`

## Summary

Extend the admin panel Settings page and its backend API to provide full provider authentication (Anthropic, z.ai, Local Model), custom model list management, proxy configuration, Claude Code runtime settings, Claude Account OAuth management, and infrastructure settings — replacing the need to use Telegram menus or edit environment variables for configuration.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI + Pydantic v2 (backend API), React 18 + Zustand + TanStack Query (frontend)
**Storage**: Runtime config service (in-memory) with environment variable fallbacks; SQLite for persistent account data via existing `SQLiteAccountRepository`
**Testing**: pytest + pytest-asyncio (backend), TypeScript compilation check (frontend)
**Target Platform**: Linux server (Docker), browser admin panel (SPA)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Settings CRUD < 200ms, provider validation < 5s
**Constraints**: No application restart for settings changes; sensitive fields masked in UI
**Scale/Scope**: Single admin user, ~50 total settings across 5 categories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | SOLID | PASS | New API routes follow SRP; settings service extends existing pattern |
| II | DDD | PASS | Settings route remains in presentation layer; AccountService in application layer |
| III | OOP & Composition | PASS | Extending existing Pydantic schemas, no new inheritance hierarchies |
| IV | Root Cause Resolution | PASS | Moving settings from env-only to runtime config addresses root limitation |
| V | Modern Stack & Async | PASS | All new endpoints async, Pydantic v2 for validation |
| VI | DRY | PASS | Reuses existing RuntimeConfigService, AccountService, settings patterns |
| VII | Modularity | PASS | Provider-agnostic design; new endpoints extend existing router |
| VIII | API & Contracts | PASS | All new settings exposed as typed Pydantic endpoints |
| IX | No Hardcoding | PASS | This feature is literally about moving hardcoded values to configurable settings |
| X | Prompt Management | N/A | No prompts involved |
| XI | Localization | PASS | UI in Russian (via i18n), code in English |
| XII | Code Quality | PASS | Backend tests for new endpoints; TypeScript type safety |

**Gate result: PASS** — No violations. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/048-admin-full-settings/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── settings-api.md  # Extended settings API contract
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
# Backend (Python / FastAPI)
presentation/api/
├── routes/
│   └── settings.py          # MODIFY — extend with provider, proxy, runtime, infra endpoints
├── schemas/
│   └── settings.py          # MODIFY — extend SettingsResponse, UpdateSettingsRequest + new schemas
└── dependencies.py          # EXISTING — get_runtime_config()

application/services/
└── account_service.py       # EXISTING — reuse AuthMode, provider switching, model fetching

# Frontend (React / TypeScript)
frontend/src/
├── types/
│   └── api.ts               # MODIFY — extend SettingsResponse, UpdateSettingsRequest types
├── stores/
│   └── settingsStore.ts     # MODIFY — add provider/proxy/runtime fields
├── pages/
│   └── SettingsPage.tsx      # MODIFY — add new sections for all settings categories
└── i18n/
    ├── ru.json               # MODIFY — add Russian labels for new settings
    ├── en.json               # MODIFY — add English labels for new settings
    └── zh.json               # MODIFY — add Chinese labels for new settings
```

**Structure Decision**: All changes extend existing files — no new files created. This follows DRY (Principle VI) and keeps the settings management centralized in the existing `settings.py` route and `SettingsPage.tsx` component.

## Color Palette & Design

Reuse the existing dark theme from `048-admin-ui-modernize`:
- Background: `#0B0F17`, Card: `rgba(255,255,255,0.04)`
- Primary: `#7C6CFF` (purple), Accent: `#4DE1FF` (cyan)
- Glass morphism: `backdrop-blur-[14px] backdrop-saturate-[140%]`
- All new form elements follow existing Tailwind semantic tokens

## Phased Implementation

### Phase 1: Provider Auth & Models (P1 — MVP)
- Extend `SettingsResponse` with provider config (mode, api_key_set, base_url, custom_models)
- Add API endpoints for: provider switching, API key save/validate, custom model CRUD
- Update SettingsPage with provider auth section and model list editor

### Phase 2: Proxy Configuration (P2)
- Add proxy config to `SettingsResponse` (type, host, port, auth, enabled, no_proxy)
- Add API endpoint for proxy CRUD
- Update SettingsPage with proxy section
- Apply proxy to `os.environ` HTTP_PROXY/HTTPS_PROXY on save

### Phase 3: Claude Code Runtime (P3)
- Add runtime params to `SettingsResponse` (max_turns, timeout, step_streaming)
- Add plugin list endpoint (read from existing plugin system)
- Update SettingsPage with runtime section

### Phase 4: Claude Account OAuth (P4)
- Add Claude Account status endpoint (reads from AccountService)
- Add credentials upload endpoint
- Update SettingsPage with Claude Account section

### Phase 5: Infrastructure Settings (P5)
- Add infrastructure read endpoints (SSH, GitLab, monitoring, debug)
- Add infrastructure update endpoints
- Update SettingsPage with collapsible infrastructure section

## Complexity Tracking

No constitution violations — no entries needed.
