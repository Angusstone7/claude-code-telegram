# Data Model: React Admin Panel

**Feature**: 001-react-admin-panel
**Date**: 2026-02-11

## Entities

### 1. WebUser (новая)

Пользователь веб-панели. Связан с Telegram-пользователем через `telegram_id`.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Уникальный идентификатор |
| username | str | UNIQUE, 3-50 chars | Логин для входа |
| password_hash | str | NOT NULL | Argon2id хеш пароля |
| display_name | str | 1-100 chars | Отображаемое имя |
| telegram_id | int | UNIQUE, nullable | Привязанный Telegram ID |
| role | str | "admin" | Роль (пока только admin) |
| is_active | bool | default True | Активен ли аккаунт |
| created_at | datetime | auto | Дата создания |
| updated_at | datetime | auto | Дата обновления |
| created_by | UUID | FK → WebUser.id, nullable | Кто создал аккаунт |

**Validation Rules**:
- `username`: только `[a-zA-Z0-9_-]`, от 3 до 50 символов
- `telegram_id`: уникальный глобально (FR-019)
- `password_hash`: Argon2id, минимальная длина пароля 8 символов

**Relationships**:
- `telegram_id` → связь с `users.telegram_id` (существующая таблица Telegram-бота)
- `created_by` → self-reference (кто создал аккаунт)

---

### 2. RefreshToken (новая)

Хранилище refresh-токенов для JWT-аутентификации.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Уникальный идентификатор |
| user_id | UUID | FK → WebUser.id, NOT NULL | Владелец токена |
| token_hash | str | UNIQUE, NOT NULL | SHA-256 хеш токена |
| expires_at | datetime | NOT NULL | Время истечения |
| created_at | datetime | auto | Дата создания |
| revoked_at | datetime | nullable | Дата отзыва (null = активен) |
| user_agent | str | nullable | User-Agent браузера |

**Validation Rules**:
- `expires_at` > `created_at`
- Token lifetime: 7 дней по умолчанию
- При logout: `revoked_at` заполняется

**State Transitions**:
```
active → revoked (logout/manual)
active → expired (time-based)
```

---

### 3. Project (существующая, без изменений)

Используется совместно Telegram-ботом и веб-панелью.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | str | PK | ID проекта |
| name | str | NOT NULL | Имя проекта |
| path | str | NOT NULL | Путь к директории |
| user_id | int | FK | Telegram user ID владельца |
| is_current | bool | default False | Текущий активный проект |
| created_at | datetime | auto | Дата создания |

**Note**: Веб-панель обращается к проектам через `telegram_id` привязку WebUser → users → projects.

---

### 4. ProjectContext (существующая, без изменений)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | int | PK, autoincrement | ID контекста |
| project_id | str | FK → Project.id | Проект-владелец |
| name | str | NOT NULL | Имя контекста |
| messages | JSON | default [] | История сообщений |
| is_active | bool | default False | Текущий активный контекст |
| created_at | datetime | auto | Дата создания |

---

### 5. LoginAttempt (новая)

Отслеживание попыток входа для rate limiting.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | int | PK, autoincrement | ID записи |
| username | str | NOT NULL | Логин попытки |
| ip_address | str | NOT NULL | IP-адрес |
| success | bool | NOT NULL | Успешна ли попытка |
| created_at | datetime | auto | Время попытки |

**Validation Rules**:
- Rate limit: 5 неудачных попыток за 15 минут → блокировка на 15 минут
- Блокировка по паре (username, ip_address)

---

## Entity Relationship Diagram

```
WebUser (web_users)
  ├── 1:N → RefreshToken (refresh_tokens)
  ├── 1:N → LoginAttempt (login_attempts) [by username]
  └── 1:1 → users (existing, via telegram_id)
              └── 1:N → Project (projects)
                          └── 1:N → ProjectContext (project_contexts)
```

## Data Flow

### Аутентификация
```
Login → verify credentials → create access token + refresh token → store refresh in DB + cookie
Refresh → verify refresh cookie → check DB → issue new access token
Logout → revoke refresh token in DB → clear cookie
```

### Привязка Telegram ID
```
WebUser sets telegram_id → validate uniqueness (FR-019) →
→ query projects WHERE user_id = (SELECT telegram_id FROM users WHERE telegram_id = X) →
→ web panel shows projects
```

### HITL Broadcast
```
Claude SDK can_use_tool() →
  EventBus.publish("hitl_request", {tool, args, session_id}) →
    Subscriber 1: Telegram handler (sends inline keyboard) →
    Subscriber 2: WebSocket manager (sends JSON to all user's WS connections) →
  First response → EventBus.publish("hitl_response") → asyncio.Event.set() →
    Other subscribers receive "hitl_resolved"
```

## Runtime-Only Entities (не персистируются отдельно)

Следующие сущности из spec.md не имеют отдельных таблиц — они хранятся иначе:

### ChatMessage
Сообщения чата хранятся как JSON-массив в `ProjectContext.messages`. Не имеют отдельной таблицы.
- Доступ: через `ProjectContext.messages` field
- Формат: `[{"role": "user"|"assistant"|"system", "content": "...", "tool_use": {...}, "created_at": "..."}]`

### ToolPermissionRequest (HITL)
Запросы на разрешение инструментов — **эфемерные** события в памяти, управляемые через EventBus.
- Не персистируются в БД
- Живут в памяти до получения ответа (approve/reject) или тайм-аута (5 минут)
- Broadcast через EventBus в Telegram + WebSocket

---

## Migration Notes

- Новые таблицы: `web_users`, `refresh_tokens`, `login_attempts`
- Существующие таблицы (`users`, `projects`, `project_contexts`, `sessions`, `commands`, `accounts`) — без изменений
- Связь через `telegram_id` — нет FK constraint между SQLite базами (если разные файлы), используется application-level join
