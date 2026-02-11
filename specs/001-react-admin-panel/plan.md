# Implementation Plan: React Admin Panel

**Branch**: `001-react-admin-panel` | **Date**: 2026-02-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-react-admin-panel/spec.md`

## Summary

Полноценная веб-панель администратора на React, зеркалирующая все возможности Telegram-бота: чат с Claude Code (streaming через WebSocket), HITL, управление проектами/контекстами, файловый браузер, настройки, Docker-мониторинг и плагины. Привязка веб-аккаунтов к Telegram ID для совместного доступа к данным. JWT-аутентификация (access + refresh tokens), EventBus для broadcast HITL-запросов в оба интерфейса (first-response-wins). Развёртывание в едином Docker-контейнере — FastAPI раздаёт собранный SPA.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, PyJWT, argon2-cffi, Vite, React 18, shadcn/ui, Zustand, TanStack Query, react-markdown, rehype-highlight, recharts, react-router-dom v6, react-i18next, react-hook-form, zod
**Storage**: SQLite (существующая — расширение схемы: web_users, refresh_tokens, login_attempts)
**Testing**: pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend)
**Target Platform**: Linux server (Docker), браузеры: Chrome/Firefox/Safari (desktop)
**Project Type**: Web application (backend extension + new frontend)
**Performance Goals**: Streaming latency <2s (SC-002), HITL delivery <1s (SC-004), 5 concurrent users (SC-008)
**Constraints**: Single Docker container, shared SQLite DB, same FastAPI process
**Scale/Scope**: ~5 пользователей, ~10 страниц, ~30 новых REST endpoints, 1 WebSocket endpoint

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | SOLID | PASS | Отдельные сервисы: AuthService, WebSocketManager, EventBus. Каждый — одна ответственность |
| II | DDD | PASS | WebUser — новая сущность в domain layer. Репозиторий — interface + SQLite impl |
| III | OOP & Composition | PASS | Composition: EventBus подписчики, ConnectionManager. Наследование — BaseMessageHandler |
| IV | Root Cause Resolution | PASS | Не применимо к новой фиче |
| V | Modern Stack & Async-First | PASS | FastAPI async, WebSocket async, Pydantic v2, React 18 + hooks |
| VI | DRY | PASS | Переиспользуем ProjectService, ContextService, FileBrowserService. Новые schemas расширяют существующие |
| VII | Modularity | PASS | Frontend — отдельный модуль. WebSocket — отдельный слой. EventBus — независимый компонент |
| VIII | API & Contracts | PASS | Все endpoints документированы через Pydantic. OpenAPI auto-generated. Contracts/ описаны |
| IX | No Hardcoding | PASS | JWT_SECRET_KEY, expiration times, ADMIN_INITIAL_* — всё в env. Языки — в i18n JSON |
| X | Prompt Management | N/A | Нет новых промптов |
| XI | Localization | PASS | UI — русский (по умолчанию) + EN/ZH. Код — английский. react-i18next |
| XII | Code Quality | PASS | pytest (backend), Vitest (frontend). Structured logging. Error handling через HTTPException |

**Post-Phase 1 Re-check**: Все принципы соблюдены. Нет нарушений.

## Project Structure

### Documentation (this feature)

```text
specs/001-react-admin-panel/
├── plan.md              # This file
├── research.md          # Phase 0: technology decisions
├── data-model.md        # Phase 1: entity definitions
├── quickstart.md        # Phase 1: development setup
├── contracts/           # Phase 1: API contracts
│   ├── auth.md         # Authentication endpoints
│   ├── websocket.md    # WebSocket protocol
│   └── rest-api.md     # REST API extensions
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Backend (extension of existing DDD structure)
domain/
├── entities/
│   └── web_user.py              # WebUser entity
├── value_objects/
│   └── web_auth.py              # JWT claims, credentials VOs
└── repositories/
    └── web_user_repository.py   # WebUser repository interface

application/
└── services/
    └── auth_service.py          # JWT auth, user management

infrastructure/
├── persistence/
│   └── sqlite_web_user_repository.py  # WebUser SQLite implementation
└── websocket/
    ├── connection_manager.py    # Per-user, per-session WS management
    ├── event_bus.py             # Async pub/sub for HITL broadcast
    └── message_types.py         # Pydantic models for WS messages

presentation/
└── api/
    ├── routes/
    │   ├── auth.py              # Auth endpoints (login, refresh, logout, users)
    │   ├── websocket_route.py   # WebSocket endpoint
    │   ├── chat.py              # Chat history + task status endpoints
    │   ├── upload.py            # File upload endpoint (POST /files/upload)
    │   ├── files.py             # File browser endpoints (browse, mkdir)
    │   ├── contexts.py          # Context management (CRUD, activate)
    │   ├── variables.py         # Variable management
    │   ├── settings.py          # Settings endpoints (GET, PATCH)
    │   ├── docker_route.py      # Docker management (REST)
    │   ├── ssh.py               # SSH command execution
    │   ├── gitlab.py            # GitLab projects & pipelines
    │   └── plugins.py           # Plugin info
    ├── schemas/
    │   ├── auth.py              # Auth request/response schemas
    │   ├── websocket_schemas.py # WS message schemas (ToolInput typed model)
    │   ├── files.py             # File browser schemas
    │   ├── contexts.py          # Context schemas
    │   ├── variables.py         # Variable schemas
    │   ├── settings.py          # Settings schemas
    │   ├── docker_schemas.py    # Docker schemas
    │   ├── ssh.py               # SSH command schemas
    │   ├── gitlab.py            # GitLab schemas
    │   └── plugins.py           # Plugin schemas
    └── security.py              # EXTENDED: hybrid JWT + API Key auth

# Frontend (new)
frontend/
├── src/
│   ├── components/
│   │   ├── ui/                  # shadcn/ui primitives
│   │   ├── chat/                # ChatWindow, MessageBubble, StreamingText, HITLCard
│   │   ├── project/             # ProjectList, ProjectCard, ContextList
│   │   ├── layout/              # AppLayout, Sidebar, Header, ProtectedRoute
│   │   └── common/              # LoadingSpinner, ErrorBoundary, EmptyState
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── ChatPage.tsx
│   │   ├── ProjectsPage.tsx
│   │   ├── FileBrowserPage.tsx
│   │   ├── SettingsPage.tsx
│   │   ├── DockerPage.tsx
│   │   ├── PluginsPage.tsx
│   │   └── UsersPage.tsx        # Admin: user management
│   ├── stores/
│   │   ├── authStore.ts
│   │   ├── chatStore.ts
│   │   ├── projectStore.ts
│   │   └── settingsStore.ts
│   ├── services/
│   │   ├── api.ts               # Axios/fetch API client with JWT interceptor
│   │   └── websocket.ts         # WebSocket manager with reconnection
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useWebSocket.ts
│   │   ├── useChat.ts
│   │   └── useProjects.ts
│   ├── i18n/
│   │   ├── index.ts
│   │   ├── ru.json
│   │   ├── en.json
│   │   └── zh.json
│   ├── types/
│   │   ├── api.ts               # API response types (mirroring Pydantic schemas)
│   │   └── websocket.ts         # WS message types
│   └── lib/
│       └── utils.ts
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── vitest.config.ts
└── package.json

# Tests
tests/
├── unit/
│   ├── domain/
│   │   └── test_web_user.py
│   ├── application/
│   │   └── test_auth_service.py
│   └── infrastructure/
│       ├── test_web_user_repository.py
│       ├── test_connection_manager.py
│       └── test_event_bus.py
└── integration/
    └── test_auth_endpoints.py

# Static (production build output)
static/
└── admin/                       # Built React SPA (copied from frontend/dist)
```

**Structure Decision**: Web application — backend расширяет существующую DDD-структуру (domain/application/infrastructure/presentation), frontend — новый модуль `frontend/` с Vite + React. Единый Docker-контейнер: multi-stage build собирает SPA → копирует в `static/admin/` → FastAPI раздаёт через `StaticFiles`.

## Complexity Tracking

> Нарушений конституции нет. Таблица пуста.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `tool_input: dict` в WS-контрактах | Claude tools имеют динамические входные схемы — невозможно определить единую строгую модель | Использовать Pydantic `BaseModel` с `model_config = ConfigDict(extra="allow")` вместо raw `dict`. Формально typed model, но принимает произвольные поля. Принцип VIII соблюдён по форме |
