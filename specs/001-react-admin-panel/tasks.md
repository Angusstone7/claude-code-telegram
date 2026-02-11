# Tasks: React Admin Panel

**Input**: Design documents from `/specs/001-react-admin-panel/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/auth.md, contracts/websocket.md, contracts/rest-api.md, research.md, quickstart.md

**Tests**: Включены — конституция проекта (Principle XII) требует покрытия бизнес-логики unit-тестами.

**Organization**: Задачи сгруппированы по user stories для независимой реализации и тестирования каждой.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Можно запускать параллельно (разные файлы, нет зависимостей)
- **[Story]**: К какой user story относится задача (US1, US2, ..., US9)
- Точные пути файлов указаны в описании каждой задачи

## Path Conventions

- **Backend**: Расширение существующей DDD-структуры (`domain/`, `application/`, `infrastructure/`, `presentation/`)
- **Frontend**: Новый модуль `frontend/` (Vite + React + TypeScript)
- **Static build output**: `static/admin/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Инициализация проекта, установка зависимостей

- [x] T001 Добавить backend-зависимости (PyJWT, argon2-cffi) в requirements.txt
- [x] T002 Инициализировать frontend-проект: Vite + React 18 + TypeScript 5.x в frontend/ (включая recharts для графиков дашборда)
- [x] T003 [P] Настроить shadcn/ui + Tailwind CSS + PostCSS в frontend/tailwind.config.ts и frontend/postcss.config.js
- [x] T004 [P] Настроить i18n: react-i18next config в frontend/src/i18n/index.ts и начальные файлы переводов frontend/src/i18n/ru.json, en.json, zh.json

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ядро инфраструктуры, которое ДОЛЖНО быть завершено до начала любой user story

**⚠️ CRITICAL**: Работа над user stories невозможна до завершения этой фазы

### Backend Core

- [x] T005 Создать SQLite миграцию: 3 новые таблицы (web_users, refresh_tokens, login_attempts) per data-model.md в infrastructure/persistence/sqlite_web_user_repository.py (init_db method)
- [x] T006 [P] Создать WebUser entity в domain/entities/web_user.py — поля: id (UUID), username, password_hash, display_name, telegram_id, role, is_active, created_at, updated_at, created_by
- [x] T007 [P] Создать value objects для JWT auth в domain/value_objects/web_auth.py — JWTClaims, Credentials, TokenPair
- [x] T008 Создать WebUser repository interface в domain/repositories/web_user_repository.py — CRUD + find_by_username, find_by_telegram_id
- [x] T009 Реализовать SQLite WebUser repository в infrastructure/persistence/sqlite_web_user_repository.py — имплементация интерфейса из T008
- [x] T010 Реализовать AuthService в application/services/auth_service.py — login, refresh, logout, create_user, update_profile, change_password, rate limiting logic
- [x] T011 Расширить security.py гибридной JWT + API Key авторизацией в presentation/api/security.py — get_current_user (JWT Bearer), hybrid auth dependency (JWT или X-API-Key)
- [x] T012 [P] Реализовать EventBus (async pub/sub) в infrastructure/websocket/event_bus.py — publish/subscribe по каналам, broadcast HITL в Telegram + WebSocket
- [x] T013 [P] Реализовать ConnectionManager в infrastructure/websocket/connection_manager.py — per-user per-session управление WS-соединениями, отправка сообщений, disconnect handling
- [x] T014 [P] Определить Pydantic модели WS-сообщений в infrastructure/websocket/message_types.py — все Client→Server и Server→Client типы per contracts/websocket.md (tool_input: ToolInput typed model, не dict)
- [x] T015 Зарегистрировать новые сервисы в DI-контейнере: AuthService, WebUserRepository, ConnectionManager, EventBus в shared/container.py
- [x] T016 [P] Добавить structured logging (JSON) для новых сервисов: AuthService, ConnectionManager, EventBus — request_id propagation, уровни DEBUG/INFO/WARNING/ERROR в каждом новом модуле

### Backend Tests (Constitution XII)

- [x] T017 [P] Unit test: WebUser entity в tests/unit/domain/test_web_user.py — создание, валидация полей, уникальность telegram_id
- [x] T018 [P] Unit test: SQLite WebUser repository в tests/unit/infrastructure/test_web_user_repository.py — CRUD, find_by_username, find_by_telegram_id
- [x] T019 [P] Unit test: EventBus в tests/unit/infrastructure/test_event_bus.py — publish/subscribe, multiple subscribers, first-response-wins
- [x] T020 [P] Unit test: ConnectionManager в tests/unit/infrastructure/test_connection_manager.py — connect/disconnect, per-user/per-session, broadcast

### Frontend Core

- [x] T021 [P] Создать API-клиент с JWT interceptor в frontend/src/services/api.ts — axios/fetch, автоматический refresh token, retry на 401
- [x] T022 [P] Создать WebSocket-менеджер в frontend/src/services/websocket.ts — подключение с JWT, reconnection с exponential backoff, ping/pong каждые 30s
- [x] T023 [P] Создать auth store (Zustand) в frontend/src/stores/authStore.ts — user profile, tokens, isAuthenticated, login/logout actions
- [x] T024 [P] Определить TypeScript типы в frontend/src/types/api.ts и frontend/src/types/websocket.ts — зеркало Pydantic-схем из contracts/ (ToolInput typed interface, не Record<string, unknown>)
- [x] T025 Настроить React Router + ProtectedRoute в frontend/src/App.tsx и frontend/src/components/layout/ProtectedRoute.tsx — маршрутизация, редирект на /login для неавторизованных
- [x] T026 Создать AppLayout с Sidebar + Header в frontend/src/components/layout/AppLayout.tsx, Sidebar.tsx, Header.tsx — навигация по всем страницам
- [x] T027 [P] Создать общие компоненты в frontend/src/components/common/ — LoadingSpinner.tsx, ErrorBoundary.tsx, EmptyState.tsx
- [x] T028 [P] Создать утилиты в frontend/src/lib/utils.ts — cn() для classnames, форматирование дат, размеров файлов

**Checkpoint**: Фундамент готов — реализация user stories может начинаться параллельно

---

## Phase 3: User Story 1 — Аутентификация и привязка к Telegram (Priority: P1) 🎯 MVP

**Goal**: Пользователь может войти в панель, привязать Telegram ID и видеть дашборд с метриками и проектами

**Independent Test**: Войти в панель с учётными данными, указать Telegram ID в профиле, увидеть проекты и метрики на дашборде

### Implementation for User Story 1

- [x] T029 [P] [US1] Создать auth request/response схемы в presentation/api/schemas/auth.py — LoginRequest, LoginResponse, UserProfile, UpdateProfileRequest, CreateUserRequest, ResetPasswordRequest, RefreshResponse per contracts/auth.md
- [x] T030 [US1] Реализовать auth routes в presentation/api/routes/auth.py — POST login, POST refresh, POST logout, GET me, PATCH me, POST users, PATCH users/{id}/password per contracts/auth.md и зарегистрировать router в FastAPI app
- [x] T031 [P] [US1] Создать LoginPage в frontend/src/pages/LoginPage.tsx — форма входа (react-hook-form + zod validation), обработка ошибок, rate limiting feedback
- [x] T032 [US1] Создать useAuth hook в frontend/src/hooks/useAuth.ts — TanStack Query мутации login/logout/refresh, profile update, интеграция с authStore
- [x] T033 [US1] Создать DashboardPage в frontend/src/pages/DashboardPage.tsx — текущий проект, последние чаты, метрики CPU/RAM/Disk, статус Claude, статистика использования, графики нагрузки (recharts), лог активности (FR-026)
- [x] T034 [US1] Создать UsersPage в frontend/src/pages/UsersPage.tsx — список пользователей, создание нового аккаунта (admin only), сброс пароля

### Tests for User Story 1 (Constitution XII)

- [x] T035 [P] [US1] Unit test: AuthService в tests/unit/application/test_auth_service.py — login flow, token generation, rate limiting, user CRUD, password change
- [x] T036 [US1] Integration test: Auth endpoints в tests/integration/test_auth_endpoints.py — login/refresh/logout/me/users endpoints, 401/403/429 responses

**Checkpoint**: US1 полностью функциональна — вход, профиль с TG ID, дашборд с метриками, управление пользователями

---

## Phase 4: User Story 2 — Чат с Claude Code (Priority: P1)

**Goal**: Полноценный чат с Claude через WebSocket: streaming, HITL, вопросы, планы, отмена, загрузка файлов

**Independent Test**: Отправить сообщение Claude, получить streaming-ответ, одобрить HITL-запрос, прикрепить файл

### Implementation for User Story 2

- [x] T037 [P] [US2] Создать WebSocket-схемы в presentation/api/schemas/websocket_schemas.py — все message types per contracts/websocket.md (ClientChatMessage, ServerStreamChunk, ServerHITLRequest и др., tool_input: ToolInput typed model)
- [x] T038 [US2] Реализовать WebSocket route в presentation/api/routes/websocket_route.py — подключение с JWT auth, маршрутизация сообщений, интеграция с SDK/CLI service, streaming ответов, обработка HITL/question/plan через EventBus и зарегистрировать в FastAPI app
- [x] T039 [US2] Интегрировать EventBus с существующим HITL handler — подписка WebSocket на HITL-события из SDK service, broadcast в Telegram + Web, first-response-wins логика в infrastructure/websocket/event_bus.py и presentation/handlers/message/hitl_handler.py
- [x] T040 [US2] Реализовать chat routes в presentation/api/routes/chat.py — GET /api/v1/projects/{project_id}/contexts/{context_id}/messages (история сообщений) и GET /api/v1/claude/task/{session_id}/status (статус задачи, TaskStatusResponse) per contracts/rest-api.md и зарегистрировать router
- [x] T041 [US2] Создать useWebSocket hook в frontend/src/hooks/useWebSocket.ts — подключение/отключение, обработка всех server message types, reconnection
- [x] T042 [US2] Создать chat store (Zustand) в frontend/src/stores/chatStore.ts — messages, streaming state, HITL requests, active session
- [x] T043 [US2] Создать useChat hook в frontend/src/hooks/useChat.ts — отправка сообщений, обработка streaming, HITL approve/reject, question answer, plan response, cancel task
- [x] T044 [P] [US2] Создать ChatWindow component в frontend/src/components/chat/ChatWindow.tsx — список сообщений, auto-scroll, загрузка истории
- [x] T045 [P] [US2] Создать MessageBubble component в frontend/src/components/chat/MessageBubble.tsx — рендеринг markdown (react-markdown), подсветка кода (rehype-highlight), tool_use результаты
- [x] T046 [P] [US2] Создать StreamingText component в frontend/src/components/chat/StreamingText.tsx — посимвольный рендеринг streaming-ответа, анимация курсора
- [x] T047 [P] [US2] Создать HITLCard, QuestionCard, PlanCard components в frontend/src/components/chat/ — approve/reject кнопки, варианты ответов, markdown плана с feedback
- [x] T048 [US2] Создать FileUpload component + backend upload endpoint в frontend/src/components/chat/FileUpload.tsx и presentation/api/routes/upload.py (POST /api/v1/files/upload) — drag&drop, preview, передача Claude как контекст (FR-025)
- [x] T049 [US2] Создать ChatPage — сборка всех компонентов чата в frontend/src/pages/ChatPage.tsx — ChatWindow, input area, file upload, session selector, session busy indicator

**Checkpoint**: US2 полностью функциональна — чат со streaming, HITL, вопросы, планы, отмена задачи, загрузка файлов

---

## Phase 5: User Story 3 — Управление проектами и контекстами (Priority: P2)

**Goal**: CRUD проектов, контекстов и переменных через веб-панель

**Independent Test**: Создать проект, добавить контекст, переключиться между контекстами, управлять переменными

**Note**: FR-003 (двусторонняя синхронизация) покрывается архитектурно — общая SQLite DB + telegram_id linking. Отдельная задача не требуется.

### Implementation for User Story 3

- [x] T050 [P] [US3] Создать context schemas в presentation/api/schemas/contexts.py — ContextResponse, ContextListResponse, CreateContextRequest per contracts/rest-api.md
- [x] T051 [P] [US3] Создать variable schemas в presentation/api/schemas/variables.py — VariableResponse, VariableListResponse, CreateVariableRequest per contracts/rest-api.md
- [x] T052 [US3] Реализовать context routes в presentation/api/routes/contexts.py — GET/POST contexts, POST activate, DELETE context, DELETE messages и зарегистрировать router (Note: GET messages endpoint — в presentation/api/routes/chat.py T040)
- [x] T053 [US3] Реализовать variable routes в presentation/api/routes/variables.py — GET/POST/PUT/DELETE variables с scope filter и зарегистрировать router
- [x] T054 [US3] Расширить существующие project routes для поддержки JWT auth — добавить hybrid auth dependency в presentation/api/routes/ (existing project routes)
- [x] T055 [US3] Создать useProjects hook + project store в frontend/src/hooks/useProjects.ts и frontend/src/stores/projectStore.ts — TanStack Query для CRUD проектов/контекстов/переменных
- [x] T056 [P] [US3] Создать ProjectList + ProjectCard components в frontend/src/components/project/ProjectList.tsx и ProjectCard.tsx — список проектов, активный индикатор, создание/удаление
- [x] T057 [P] [US3] Создать ContextList + VariableManager components в frontend/src/components/project/ContextList.tsx и VariableManager.tsx — список контекстов, переключение, CRUD переменных
- [x] T058 [US3] Создать ProjectsPage — сборка компонентов в frontend/src/pages/ProjectsPage.tsx — проекты, контексты, переменные на одной странице

**Checkpoint**: US3 полностью функциональна — управление проектами, контекстами и переменными

---

## Phase 6: User Story 4 — Файловый браузер (Priority: P2)

**Goal**: Навигация по файловой системе проекта, выбор рабочей директории, создание папок

**Independent Test**: Открыть файловый браузер, перейти по папкам, выбрать рабочую директорию

### Implementation for User Story 4

- [x] T059 [P] [US4] Создать file browser schemas в presentation/api/schemas/files.py — FileBrowserResponse, FileEntry, MkdirRequest per contracts/rest-api.md
- [x] T060 [US4] Реализовать file browser routes в presentation/api/routes/files.py — GET /files/browse, POST /files/mkdir с path validation (только /root/projects) и зарегистрировать router (Note: POST /files/upload — в presentation/api/routes/upload.py T048)
- [x] T061 [US4] Создать FileBrowserPage в frontend/src/pages/FileBrowserPage.tsx — навигация по папкам, breadcrumb path, создание директорий, выбор как рабочую директорию

**Checkpoint**: US4 полностью функциональна — файловый браузер с навигацией и созданием папок

---

## Phase 7: User Story 5 — Настройки и управление аккаунтом (Priority: P3)

**Goal**: Управление настройками Claude Code: backend, модель, YOLO-режим, язык — единые для всех интерфейсов

**Independent Test**: Переключить YOLO-режим, сменить модель, убедиться что изменения применяются

### Implementation for User Story 5

- [x] T062 [P] [US5] Создать settings schemas в presentation/api/schemas/settings.py — SettingsResponse, UpdateSettingsRequest per contracts/rest-api.md
- [x] T063 [US5] Реализовать settings routes в presentation/api/routes/settings.py — GET /settings, PATCH /settings с интеграцией в существующий config и зарегистрировать router
- [x] T064 [US5] Создать settings store (Zustand) в frontend/src/stores/settingsStore.ts — текущие настройки, update actions
- [x] T065 [US5] Создать SettingsPage в frontend/src/pages/SettingsPage.tsx — формы настроек: YOLO toggle, backend select, model select, language select, permission mode

**Checkpoint**: US5 полностью функциональна — единые настройки, мгновенное применение

---

## Phase 8: User Story 6 — Мониторинг системы и Docker (Priority: P3)

**Goal**: Системные метрики, управление Docker-контейнерами, просмотр логов

**Independent Test**: Увидеть метрики CPU/RAM/Disk, перезапустить контейнер, просмотреть логи

### Implementation for User Story 6

- [x] T066 [P] [US6] Создать Docker schemas в presentation/api/schemas/docker_schemas.py — ContainerResponse, ContainerListResponse, ContainerLogsResponse per contracts/rest-api.md
- [x] T067 [US6] Реализовать Docker routes в presentation/api/routes/docker_route.py — GET /docker/containers, POST /docker/containers/{name}/{action}, GET /docker/containers/{name}/logs и зарегистрировать router
- [x] T068 [US6] Расширить существующий /api/v1/system endpoint для поддержки JWT auth — добавить hybrid auth dependency
- [x] T069 [US6] Создать DockerPage в frontend/src/pages/DockerPage.tsx — таблица контейнеров со статусами, кнопки start/stop/restart, просмотр логов, системные метрики с визуальными индикаторами

**Checkpoint**: US6 полностью функциональна — мониторинг и управление Docker

---

## Phase 9: User Story 7 — Плагины Claude Code (Priority: P3)

**Goal**: Просмотр списка плагинов с описаниями, статусами и доступными командами

**Independent Test**: Открыть список плагинов, увидеть описания и slash-команды

### Implementation for User Story 7

- [x] T070 [P] [US7] Создать plugin schemas в presentation/api/schemas/plugins.py — PluginResponse, PluginListResponse, PluginCommand per contracts/rest-api.md
- [x] T071 [US7] Реализовать plugin routes в presentation/api/routes/plugins.py — GET /plugins с интеграцией в существующий PluginManager и зарегистрировать router
- [x] T072 [US7] Создать PluginsPage в frontend/src/pages/PluginsPage.tsx — карточки плагинов, enabled/disabled badge, раскрываемый список команд

**Checkpoint**: US7 полностью функциональна — информация о плагинах

---

## Phase 10: User Story 8 — SSH-команды (Priority: P3)

**Goal**: Выполнение SSH-команд на сервере через веб-панель, история команд

**Independent Test**: Ввести `ls -la`, увидеть результат, проверить историю

### Implementation for User Story 8

- [x] T073 [P] [US8] Создать SSH schemas в presentation/api/schemas/ssh.py — SSHCommandRequest, SSHCommandResponse, SSHHistoryResponse
- [x] T074 [US8] Реализовать SSH routes в presentation/api/routes/ssh.py — POST /ssh/execute, GET /ssh/history с интеграцией в существующий SSHExecutor (infrastructure/ssh/ssh_executor.py) и зарегистрировать router
- [x] T075 [US8] Создать SSHPage в frontend/src/pages/SSHPage.tsx — terminal-style input, вывод результатов, история команд, кнопка отмены

**Checkpoint**: US8 полностью функциональна — SSH-команды через веб

---

## Phase 11: User Story 9 — GitLab-интеграция (Priority: P3)

**Goal**: Просмотр GitLab проектов, пайплайнов и статусов CI/CD

**Independent Test**: Открыть раздел GitLab, увидеть проекты с пайплайнами

### Implementation for User Story 9

- [x] T076 [P] [US9] Создать GitLab schemas в presentation/api/schemas/gitlab.py — GitLabProjectResponse, PipelineResponse, PipelineStageResponse
- [x] T077 [US9] Реализовать GitLab routes в presentation/api/routes/gitlab.py — GET /gitlab/projects, GET /gitlab/projects/{id}/pipelines, GET /gitlab/pipelines/{id}/stages с интеграцией в существующий GitLab service (infrastructure/gitlab/) и зарегистрировать router
- [x] T078 [US9] Создать GitLabPage в frontend/src/pages/GitLabPage.tsx — список проектов, пайплайны со статусами (success/failed/running), детали этапов

**Checkpoint**: US9 полностью функциональна — GitLab обзор через веб

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Сборка, развёртывание, безопасность, типизация, финальная доводка

- [x] T079 Обновить Dockerfile: multi-stage build — собрать React SPA (npm run build), скопировать в static/admin/
- [x] T080 [P] Настроить CORS middleware в FastAPI для frontend dev server (localhost:5173) в main.py
- [x] T081 [P] Добавить StaticFiles mount для раздачи SPA из static/admin/ в main.py — fallback на index.html для client-side routing
- [x] T082 [P] Завершить i18n-переводы: полные ru.json, en.json, zh.json для всех страниц в frontend/src/i18n/
- [x] T083 Security hardening: rate limiting для login endpoint (presentation/api/routes/auth.py), input sanitization для пользовательского ввода, path traversal protection в file browser (presentation/api/routes/files.py), CSRF token middleware
- [x] T084 Создать initial admin seed: скрипт/env переменные (ADMIN_INITIAL_USERNAME, ADMIN_INITIAL_PASSWORD) для первого запуска в application/services/auth_service.py (init method)
- [x] T085 [P] Настроить mypy для нового backend-кода: конфигурация в pyproject.toml/mypy.ini, проверка всех новых модулей (domain/entities/web_user.py, application/services/auth_service.py, infrastructure/websocket/)
- [x] T086 [P] Smoke test: 5 параллельных WebSocket-соединений — валидация SC-008 (concurrent users без деградации) в tests/integration/test_concurrent_ws.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Нет зависимостей — начинать немедленно
- **Foundational (Phase 2)**: Зависит от Phase 1 — **БЛОКИРУЕТ** все user stories
- **US1 (Phase 3)**: Зависит от Phase 2 — 🎯 MVP
- **US2 (Phase 4)**: Зависит от Phase 2 — может идти параллельно с US1
- **US3 (Phase 5)**: Зависит от Phase 2 — может идти параллельно с US1/US2
- **US4 (Phase 6)**: Зависит от Phase 2 — может идти параллельно
- **US5–US9 (Phases 7–11)**: Зависят от Phase 2 — могут идти параллельно
- **Polish (Phase 12)**: Зависит от завершения всех желаемых user stories

### User Story Dependencies

- **US1 (P1)**: ← Phase 2 only. Нет зависимостей от других stories
- **US2 (P1)**: ← Phase 2 only. EventBus + ConnectionManager из Phase 2. Chat routes в отдельном файле (chat.py) — нет конфликтов с US3
- **US3 (P2)**: ← Phase 2 only. Независима. Context routes в contexts.py (GET messages — в chat.py, T040)
- **US4 (P2)**: ← Phase 2 only. Независима. File browser routes в files.py (upload — в upload.py, T048)
- **US5 (P3)**: ← Phase 2 only. Независима
- **US6 (P3)**: ← Phase 2 only. Использует существующие Docker/System services
- **US7 (P3)**: ← Phase 2 only. Использует существующий PluginManager
- **US8 (P3)**: ← Phase 2 only. Использует существующий SSHExecutor
- **US9 (P3)**: ← Phase 2 only. Использует существующий GitLab service

### File Collision Prevention

- **chat.py** (T040, US2): GET messages + GET task status — отдельно от contexts.py
- **upload.py** (T048, US2): POST /files/upload — отдельно от files.py (browse/mkdir)
- **contexts.py** (T052, US3): context CRUD без messages endpoint
- **files.py** (T060, US4): browse/mkdir без upload endpoint

### Within Each User Story

- Schemas (Pydantic) → Routes (FastAPI) → Frontend hooks → Frontend components → Page assembly
- Backend tasks before frontend tasks within story
- Tests can run parallel with frontend tasks (backend already complete)
- [P]-marked tasks within story can run in parallel

### Parallel Opportunities

- Phase 1: T003, T004 параллельно (разные конфиги)
- Phase 2: T006, T007, T012, T013, T014, T016 параллельно (backend, разные файлы); T017-T020 параллельно (backend tests); T021-T024, T027, T028 параллельно (frontend, разные файлы)
- Phase 3+: Все user stories МОГУТ выполняться параллельно после Phase 2
- Внутри story: все задачи с [P] маркером параллельны

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Backend — запустить параллельно:
Task: "Создать WebUser entity в domain/entities/web_user.py"          # T006
Task: "Создать value objects в domain/value_objects/web_auth.py"      # T007
Task: "Реализовать EventBus в infrastructure/websocket/event_bus.py"  # T012
Task: "Реализовать ConnectionManager в infrastructure/websocket/"     # T013
Task: "Определить WS message types в infrastructure/websocket/"      # T014
Task: "Добавить structured logging для новых сервисов"                # T016

# Backend tests — запустить параллельно (после соответствующих impl):
Task: "Unit test: WebUser entity"                                     # T017
Task: "Unit test: WebUser repository"                                 # T018
Task: "Unit test: EventBus"                                           # T019
Task: "Unit test: ConnectionManager"                                  # T020

# Frontend — запустить параллельно:
Task: "Создать API-клиент в frontend/src/services/api.ts"            # T021
Task: "Создать WebSocket-менеджер в frontend/src/services/websocket.ts" # T022
Task: "Создать auth store в frontend/src/stores/authStore.ts"        # T023
Task: "Определить TypeScript типы в frontend/src/types/"             # T024
Task: "Создать общие компоненты в frontend/src/components/common/"   # T027
Task: "Создать утилиты в frontend/src/lib/utils.ts"                  # T028
```

## Parallel Example: User Stories (after Phase 2)

```bash
# Все stories параллельны — нет file collisions:
Agent A: US1 (Phase 3) — Auth + Dashboard
Agent B: US2 (Phase 4) — Chat with Claude (chat.py, upload.py — отдельные файлы)
Agent C: US3 (Phase 5) — Projects & Contexts (contexts.py — без messages endpoint)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Завершить Phase 1: Setup
2. Завершить Phase 2: Foundational (**CRITICAL — блокирует всё**)
3. Завершить Phase 3: US1 — Аутентификация + Дашборд
4. **STOP и VALIDATE**: Войти → привязать TG ID → увидеть проекты + метрики
5. Deploy/demo если готово

### Incremental Delivery

1. Setup + Foundational → Фундамент готов
2. + US1 → Тестируем → Deploy/Demo (**MVP!**)
3. + US2 → Тестируем → Deploy/Demo (Чат с Claude — основная ценность)
4. + US3 + US4 → Тестируем → Deploy/Demo (Проекты + файлы)
5. + US5–US9 → Тестируем → Deploy/Demo (Настройки, Docker, плагины, SSH, GitLab)
6. Phase 12: Polish → Production release

### Parallel Agent Strategy

С несколькими агентами:

1. Все агенты вместе завершают Setup + Foundational
2. После Foundational:
   - Agent A: US1 (Auth + Dashboard) 🎯 MVP
   - Agent B: US2 (Chat with Claude)
   - Agent C: US3 + US4 (Projects + Files)
3. После US1–US4:
   - Agent A: US5 (Settings)
   - Agent B: US6 + US7 (Docker + Plugins)
   - Agent C: US8 + US9 (SSH + GitLab)
4. Все: Phase 12 (Polish)

---

## Notes

- [P] задачи = разные файлы, нет зависимостей
- [Story] label привязывает задачу к конкретной user story для трассировки
- Каждая user story независимо завершаема и тестируема
- File collisions устранены: chat.py (messages + status), upload.py (file upload), contexts.py (context CRUD), files.py (browse/mkdir)
- Коммит после каждой задачи или логической группы
- Остановка на любом checkpoint для валидации story
- Избегать: нечётких задач, конфликтов в одном файле, cross-story зависимостей
- Existing services (SSHExecutor, Docker, GitLab, SystemMonitor, ProjectService, ContextService, FileBrowserService) переиспользуются — новые routes создают тонкие REST-обёртки
- Тесты включены для соблюдения Constitution XII (business logic MUST be covered by unit tests)
