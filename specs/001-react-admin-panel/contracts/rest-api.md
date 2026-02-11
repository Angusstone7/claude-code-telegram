# API Contract: REST API Extensions

**Base path**: `/api/v1`
**Auth**: JWT Bearer (если не указано иное)

Данный контракт описывает **новые и расширенные** эндпоинты. Существующие эндпоинты (health, projects, sessions, claude, system, config) сохраняются без изменений и доступны через API Key.

---

## Projects (расширение существующего)

Существующие routes (`/api/v1/projects`) сохраняются. Добавляется поддержка JWT auth.

### GET /api/v1/projects

Список проектов текущего пользователя.

**Auth**: JWT Bearer или API Key

**Response 200**: `ProjectListResponse` (существующая схема)

### POST /api/v1/projects

Создание нового проекта.

**Auth**: JWT Bearer или API Key

**Request**: `CreateProjectRequest` (существующая схема)

**Response 201**: `ProjectResponse`

### DELETE /api/v1/projects/{project_id}

Удаление проекта.

**Auth**: JWT Bearer или API Key

**Response 200**: `MessageResponse`

### POST /api/v1/projects/{project_id}/activate

Сделать проект активным.

**Auth**: JWT Bearer или API Key

**Response 200**: `ProjectResponse`

---

## Contexts

### GET /api/v1/projects/{project_id}/contexts

Список контекстов проекта.

**Response 200**:
```python
class ContextListResponse(BaseModel):
    contexts: list[ContextResponse]
    total: int

class ContextResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    message_count: int
    created_at: datetime
```

### POST /api/v1/projects/{project_id}/contexts

Создание нового контекста.

**Request**:
```python
class CreateContextRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
```

**Response 201**: `ContextResponse`

### POST /api/v1/projects/{project_id}/contexts/{context_id}/activate

Сделать контекст активным.

**Response 200**: `ContextResponse`

### DELETE /api/v1/projects/{project_id}/contexts/{context_id}

Удаление контекста.

**Response 200**: `MessageResponse`

### DELETE /api/v1/projects/{project_id}/contexts/{context_id}/messages

Очистка истории сообщений контекста.

**Response 200**: `MessageResponse`

---

## Context Variables

### GET /api/v1/projects/{project_id}/variables

Список переменных проекта (локальные + глобальные).

**Query**: `?scope=local|global|all` (default: `all`)

**Response 200**:
```python
class VariableListResponse(BaseModel):
    variables: list[VariableResponse]
    total: int

class VariableResponse(BaseModel):
    id: int
    name: str
    value: str
    description: Optional[str]
    scope: str  # "local" | "global"
    created_at: datetime
    updated_at: datetime
```

### POST /api/v1/projects/{project_id}/variables

Создание переменной.

**Request**:
```python
class CreateVariableRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    value: str = Field(...)
    description: Optional[str] = Field(None, max_length=500)
    scope: str = Field("local", pattern=r"^(local|global)$")
```

**Response 201**: `VariableResponse`

### PUT /api/v1/projects/{project_id}/variables/{variable_id}

Обновление переменной.

**Request**: `CreateVariableRequest` (все поля)

**Response 200**: `VariableResponse`

### DELETE /api/v1/projects/{project_id}/variables/{variable_id}

Удаление переменной.

**Response 200**: `MessageResponse`

---

## File Browser

### GET /api/v1/files/browse

Просмотр содержимого директории.

**Query**: `?path=/root/projects/myproject`

**Response 200**:
```python
class FileBrowserResponse(BaseModel):
    current_path: str
    parent_path: Optional[str]  # null если в корне разрешённой зоны
    entries: list[FileEntry]

class FileEntry(BaseModel):
    name: str
    path: str
    is_directory: bool
    size: Optional[int]  # bytes, null для директорий
    modified_at: Optional[datetime]
```

**Errors**:
- `403 Forbidden`: Путь за пределами разрешённой зоны (`/root/projects`)
- `404 Not Found`: Директория не существует

### POST /api/v1/files/mkdir

Создание директории.

**Request**:
```python
class MkdirRequest(BaseModel):
    path: str = Field(..., description="Полный путь новой директории")
```

**Response 201**: `FileEntry`

**Errors**:
- `403 Forbidden`: Путь за пределами разрешённой зоны
- `409 Conflict`: Директория уже существует

---

## Settings

### GET /api/v1/settings

Получение текущих настроек.

**Response 200**:
```python
class SettingsResponse(BaseModel):
    yolo_mode: bool
    step_streaming: bool
    backend: str  # "sdk" | "cli"
    model: str  # текущая модель
    available_models: list[str]
    permission_mode: str  # "default" | "auto" | "never"
    language: str  # "ru" | "en" | "zh"
```

### PATCH /api/v1/settings

Обновление настроек.

**Request**:
```python
class UpdateSettingsRequest(BaseModel):
    yolo_mode: Optional[bool] = None
    step_streaming: Optional[bool] = None
    backend: Optional[str] = Field(None, pattern=r"^(sdk|cli)$")
    model: Optional[str] = None
    permission_mode: Optional[str] = Field(None, pattern=r"^(default|auto|never)$")
    language: Optional[str] = Field(None, pattern=r"^(ru|en|zh)$")
```

**Response 200**: `SettingsResponse`

---

## Docker Management

### GET /api/v1/docker/containers

Список Docker-контейнеров.

**Response 200**:
```python
class ContainerListResponse(BaseModel):
    containers: list[ContainerResponse]

class ContainerResponse(BaseModel):
    name: str
    status: str  # "running" | "stopped" | "restarting" | etc.
    image: str
    ports: list[str]
    uptime: Optional[str]
    created_at: datetime
```

### POST /api/v1/docker/containers/{name}/{action}

Управление контейнером.

**Path**: `action` — `start | stop | restart`

**Response 200**: `ContainerResponse`

### GET /api/v1/docker/containers/{name}/logs

Логи контейнера.

**Query**: `?tail=100`

**Response 200**:
```python
class ContainerLogsResponse(BaseModel):
    name: str
    logs: str
    lines: int
```

---

## Plugins

### GET /api/v1/plugins

Список плагинов Claude Code.

**Response 200**:
```python
class PluginListResponse(BaseModel):
    plugins: list[PluginResponse]

class PluginResponse(BaseModel):
    name: str
    enabled: bool
    description: Optional[str]
    commands: list[PluginCommand]

class PluginCommand(BaseModel):
    name: str
    description: Optional[str]
```

---

## Chat History

### GET /api/v1/projects/{project_id}/contexts/{context_id}/messages

История сообщений контекста.

**Query**: `?limit=50&offset=0`

**Response 200**:
```python
class MessageListResponse(BaseModel):
    messages: list[ChatMessageResponse]
    total: int

class ToolInput(BaseModel):
    """Dynamic tool input — schema varies per tool."""
    model_config = ConfigDict(extra="allow")

class ChatMessageResponse(BaseModel):
    id: int
    role: str  # "user" | "assistant" | "system"
    content: str
    tool_use: Optional[ToolInput] = None  # typed model (Constitution VIII)
    created_at: datetime
```

---

## Claude Task (расширение существующего)

### POST /api/v1/claude/task

Отправка задачи Claude (для REST-клиентов без WebSocket).

**Существующий**: `TaskRequest` / `TaskResponse` — без изменений.

### GET /api/v1/claude/task/{session_id}/status

Статус текущей задачи.

**Response 200**:
```python
class TaskStatusResponse(BaseModel):
    session_id: str
    status: str  # "idle" | "running" | "completed" | "error"
    started_at: Optional[datetime]
    message: Optional[str]
```
