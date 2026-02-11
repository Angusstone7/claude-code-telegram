# Research: React Admin Panel

**Feature**: 001-react-admin-panel
**Date**: 2026-02-11
**Status**: Complete

## 1. WebSocket + FastAPI: Streaming & HITL Transport

### Decision
Использовать нативный WebSocket FastAPI с ConnectionManager-паттерном и EventBus для широковещательной доставки HITL-событий.

### Rationale
- FastAPI имеет встроенную поддержку WebSocket через Starlette — не нужны сторонние библиотеки
- ConnectionManager обеспечивает per-user, per-session управление соединениями
- EventBus (asyncio pub/sub) позволяет широковещательную доставку HITL-запросов в Telegram и WebSocket одновременно
- JSON-протокол с Pydantic-моделями для типизации всех сообщений
- Heartbeat (ping/pong каждые 30 секунд) для детекции разрывов

### Alternatives Considered
| Вариант | Причина отклонения |
|---------|-------------------|
| Socket.IO | Избыточная зависимость, нативный WS FastAPI достаточен |
| Server-Sent Events (SSE) | Однонаправленный — не подходит для HITL (нужен двусторонний канал) |
| Long polling | Высокая задержка, неэффективно для streaming |

### Implementation Details
- Эндпоинт: `ws://host/api/v1/ws/{session_id}?token={jwt}`
- JWT передаётся через query parameter (WebSocket не поддерживает кастомные заголовки при handshake)
- Протокол сообщений: JSON с полем `type` для маршрутизации
- Типы сообщений: `stream_chunk`, `stream_end`, `hitl_request`, `hitl_response`, `hitl_resolved`, `task_status`, `error`, `ping`, `pong`
- ConnectionManager хранит `dict[user_id, dict[session_id, WebSocket]]`
- EventBus: подписчики — Telegram handler + WebSocket manager; события — `hitl_request`, `hitl_response`

---

## 2. React SPA: Stack & Architecture

### Decision
Vite + React 18 + TypeScript + shadcn/ui + Zustand + TanStack Query.

### Rationale
- **Vite** (не CRA): быстрая сборка, HMR, нативные ES-модули, production-ready
- **shadcn/ui**: копируемые компоненты на Radix UI + Tailwind CSS — полный контроль, нет vendor lock-in
- **Zustand**: минималистичный state management без boilerplate (vs Redux)
- **TanStack Query**: кеширование, инвалидация, оптимистичные обновления для REST API
- **react-markdown + rehype-highlight**: рендеринг markdown с подсветкой синтаксиса в чате
- **react-router-dom v6**: SPA-маршрутизация с защищёнными роутами
- **react-i18next**: интернационализация (RU/EN/ZH по FR-018)
- **react-hook-form + zod**: формы с валидацией (настройки, профиль)

### Alternatives Considered
| Вариант | Причина отклонения |
|---------|-------------------|
| Create React App | Deprecated, медленная сборка |
| Next.js | SSR не нужен для админки, избыточная сложность |
| Material UI | Тяжёлый, менее гибкий чем shadcn/ui |
| Redux Toolkit | Избыточный boilerplate для масштаба проекта |
| Recoil/Jotai | Менее зрелые, меньше экосистема |

### Project Structure
```
frontend/
├── src/
│   ├── components/         # Переиспользуемые UI-компоненты (shadcn/ui)
│   │   ├── ui/            # shadcn/ui примитивы
│   │   ├── chat/          # Чат-компоненты (MessageBubble, StreamingText, HITLCard)
│   │   ├── project/       # Компоненты проектов
│   │   └── layout/        # Layout, Sidebar, Header
│   ├── pages/             # Страницы (Dashboard, Chat, Projects, Settings, Docker)
│   ├── stores/            # Zustand stores (auth, chat, projects, settings)
│   ├── services/          # API-клиент, WebSocket-менеджер
│   ├── hooks/             # Кастомные React hooks
│   ├── i18n/              # Переводы (ru.json, en.json, zh.json)
│   ├── types/             # TypeScript типы/интерфейсы
│   └── lib/               # Утилиты
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

---

## 3. JWT Authentication

### Decision
PyJWT с access token (15 мин) + refresh token (7 дней), Argon2 для хеширования паролей. Гибридная схема: JWT для веб-панели, API Key для программных клиентов.

### Rationale
- **PyJWT**: лёгкая библиотека, полная поддержка стандарта JWT
- **Access + Refresh**: короткоживущий access token минимизирует окно атаки; refresh token в HTTP-only cookie предотвращает XSS
- **Argon2**: рекомендован OWASP как лучший алгоритм хеширования (vs bcrypt, scrypt)
- **Гибридная схема**: существующий API Key auth (`X-API-Key`) сохраняется для обратной совместимости
- Middleware определяет тип аутентификации по наличию заголовка `Authorization: Bearer` vs `X-API-Key`

### Alternatives Considered
| Вариант | Причина отклонения |
|---------|-------------------|
| Session cookies only | Не подходит для SPA + WebSocket |
| OAuth2 / OIDC | Избыточен для закрытой системы без внешних провайдеров |
| Paseto | Менее распространён, меньше поддержки в экосистеме |

### Implementation Details
- Access token: JWT с claims `{sub: user_id, role: "admin", exp: 15min}`
- Refresh token: случайный UUID, хранится в БД + HTTP-only Secure SameSite=Strict cookie
- Login: `POST /api/v1/auth/login` → возвращает access token в теле + refresh cookie
- Refresh: `POST /api/v1/auth/refresh` → новый access token из refresh cookie
- Logout: `POST /api/v1/auth/logout` → инвалидация refresh token в БД
- WebSocket auth: JWT передаётся в query parameter `?token=xxx` при handshake
- Пароли: Argon2id с salt, параметры по OWASP рекомендациям
- Rate limiting на login: 5 попыток за 15 минут

---

## 4. HITL Broadcast Pattern

### Decision
Расширить существующий HITLManager через EventBus с паттерном first-response-wins.

### Rationale
- Текущий HITLManager (`presentation/handlers/state/hitl_manager.py`) использует `asyncio.Event` + `asyncio.Lock` — это хорошая база
- EventBus (внутренний pub/sub на asyncio) позволяет добавить WebSocket как дополнительный подписчик без изменения Telegram-кода
- First-response-wins через `asyncio.Event.set()` — тот, кто первым вызвал `set()`, определяет результат; остальные получают уведомление `hitl_resolved`

### Alternatives Considered
| Вариант | Причина отклонения |
|---------|-------------------|
| Redis pub/sub | Внешняя зависимость, избыточна для single-container |
| Polling | Высокая задержка для HITL (~1 сек неприемлемо) |
| Callback chain | Тесная связанность, сложнее масштабировать |

### Implementation Details
- EventBus: `asyncio` очереди с подписчиками `{event_type: list[callback]}`
- При HITL-запросе SDK: `can_use_tool()` → EventBus публикует `hitl_request` → подписчики (TG handler + WS manager) получают событие
- Ответ из любого интерфейса → EventBus публикует `hitl_response` → `asyncio.Event.set()`
- Остальные подписчики получают `hitl_resolved` с результатом для обновления UI

---

## 5. Single-Container Deployment (React SPA + FastAPI)

### Decision
Multi-stage Docker build: Node.js собирает SPA → Python-образ копирует статику → FastAPI раздаёт через `StaticFiles`.

### Rationale
- Единый контейнер упрощает deployment (уже есть docker-compose)
- FastAPI `StaticFiles` + catch-all route для SPA routing
- Нет необходимости в nginx — FastAPI справляется с раздачей статики для ~5 пользователей
- Multi-stage build минимизирует размер итогового образа (Node.js не попадает в production)

### Alternatives Considered
| Вариант | Причина отклонения |
|---------|-------------------|
| Отдельный контейнер (nginx + React) | Усложняет deployment, нужен внутренний routing |
| CDN для статики | Избыточно для внутреннего инструмента |
| Nginx sidecar в том же контейнере | Усложняет Dockerfile, нет выигрыша при 5 пользователях |

### Implementation Details
- Dockerfile: stage 1 (`node:20-alpine`) — `npm ci && npm run build`
- Dockerfile: stage 2 (`python:3.11-slim`) — копирует `frontend/dist/` → `/app/static/admin/`
- FastAPI: `app.mount("/admin", StaticFiles(directory="static/admin", html=True))`
- SPA catch-all: для client-side routing все неизвестные пути под `/admin` отдают `index.html`
- API prefix: `/api/v1/` (без изменений)
- WebSocket: `ws://host/api/v1/ws/`
