# Quickstart: React Admin Panel

**Feature**: 001-react-admin-panel
**Date**: 2026-02-11

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm 10+
- Существующий проект ubuntu_claude с работающим ботом

## Backend Setup

### 1. Установка новых Python-зависимостей

```bash
pip install PyJWT argon2-cffi
```

Добавить в `requirements.txt`:
```
PyJWT>=2.8.0
argon2-cffi>=23.1.0
```

### 2. Переменные окружения

Добавить в `.env`:
```bash
# JWT
JWT_SECRET_KEY=<random-256-bit-key>  # python -c "import secrets; print(secrets.token_hex(32))"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Admin panel
ADMIN_INITIAL_USERNAME=admin
ADMIN_INITIAL_PASSWORD=<secure-password>
```

### 3. Инициализация БД

При первом запуске система автоматически:
- Создаёт таблицы `web_users`, `refresh_tokens`, `login_attempts`
- Создаёт начального администратора из `ADMIN_INITIAL_*` переменных

### 4. Запуск backend

```bash
python main.py  # FastAPI + Telegram bot стартуют вместе
```

API доступен на `http://localhost:8090/api/v1/`
WebSocket: `ws://localhost:8090/api/v1/ws/{session_id}?token={jwt}`

## Frontend Setup

### 1. Инициализация проекта

```bash
cd frontend
npm install
```

### 2. Конфигурация

`frontend/.env`:
```bash
VITE_API_BASE_URL=http://localhost:8090
VITE_WS_BASE_URL=ws://localhost:8090
```

### 3. Запуск dev-сервера

```bash
npm run dev
```

Dev-сервер: `http://localhost:5173`
С proxy на `/api` → `http://localhost:8090`

### 4. Production build

```bash
npm run build
# Output: frontend/dist/
```

## Docker Build

Multi-stage Dockerfile (обновлённый):

```dockerfile
# Stage 1: Build React SPA
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python app
FROM python:3.11-slim
# ... existing Dockerfile steps ...
COPY --from=frontend-builder /app/frontend/dist /app/static/admin
```

FastAPI раздаёт `static/admin/` через `StaticFiles`.

## Verification

### Backend health check
```bash
curl http://localhost:8090/api/v1/health
```

### Login test
```bash
curl -X POST http://localhost:8090/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

### WebSocket test (wscat)
```bash
npx wscat -c "ws://localhost:8090/api/v1/ws/test?token=<jwt>"
```

### Frontend
Открыть `http://localhost:5173` (dev) или `http://localhost:8090/admin` (production).

## Project Structure After Implementation

```
ubuntu_claude/
├── frontend/                    # React SPA (NEW)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── stores/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── i18n/
│   │   ├── types/
│   │   └── lib/
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── package.json
├── domain/
│   └── repositories/
│       └── web_user_repository.py   # NEW: WebUser repo interface
├── application/
│   └── services/
│       └── auth_service.py          # NEW: JWT auth service
├── infrastructure/
│   ├── persistence/
│   │   └── sqlite_web_user_repository.py  # NEW: WebUser SQLite impl
│   └── websocket/                         # NEW: WebSocket layer
│       ├── connection_manager.py
│       ├── event_bus.py
│       └── message_types.py
├── presentation/
│   └── api/
│       ├── routes/
│       │   ├── auth.py              # NEW: Auth routes
│       │   ├── websocket.py         # NEW: WS endpoint
│       │   ├── files.py             # NEW: File browser
│       │   ├── contexts.py          # NEW: Context management
│       │   ├── variables.py         # NEW: Variable management
│       │   ├── docker.py            # NEW: Docker management (REST)
│       │   └── plugins.py           # NEW: Plugin info
│       ├── schemas/
│       │   ├── auth.py              # NEW: Auth schemas
│       │   ├── websocket.py         # NEW: WS message schemas
│       │   ├── files.py             # NEW: File browser schemas
│       │   ├── contexts.py          # NEW: Context schemas
│       │   ├── variables.py         # NEW: Variable schemas
│       │   ├── docker.py            # NEW: Docker schemas
│       │   └── plugins.py           # NEW: Plugin schemas
│       └── security.py             # EXTENDED: JWT + API Key hybrid
├── static/
│   └── admin/                      # Built React SPA (production)
└── ...
```
