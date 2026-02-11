# API Contract: WebSocket

**Endpoint**: `ws://host/api/v1/ws/{session_id}?token={jwt}`
**Auth**: JWT в query parameter

---

## Connection

### Handshake
```
GET /api/v1/ws/{session_id}?token=<jwt_access_token>
Upgrade: websocket
Connection: Upgrade
```

**Параметры**:
- `session_id`: ID сессии/контекста проекта
- `token`: JWT access token

**Errors**:
- `4001`: Invalid token — JWT недействителен или истёк
- `4003`: Forbidden — нет доступа к сессии
- `1011`: Server error — внутренняя ошибка

---

## Message Protocol

Все сообщения — JSON с обязательным полем `type`.

### Client → Server

#### Отправка сообщения Claude
```python
class ClientChatMessage(BaseModel):
    type: Literal["chat_message"] = "chat_message"
    content: str  # текст сообщения
    context_id: Optional[int] = None  # ID контекста (если отличается от session)
```

#### Ответ на HITL-запрос
```python
class ClientHITLResponse(BaseModel):
    type: Literal["hitl_response"] = "hitl_response"
    request_id: str  # ID запроса
    approved: bool
```

#### Ответ на уточняющий вопрос
```python
class ClientQuestionAnswer(BaseModel):
    type: Literal["question_answer"] = "question_answer"
    request_id: str
    answer: str  # выбранный вариант или произвольный текст
```

#### Ответ на план
```python
class ClientPlanResponse(BaseModel):
    type: Literal["plan_response"] = "plan_response"
    request_id: str
    approved: bool
    feedback: Optional[str] = None  # комментарий при отклонении
```

#### Отмена задачи
```python
class ClientCancelTask(BaseModel):
    type: Literal["cancel_task"] = "cancel_task"
```

#### Ping
```python
class ClientPing(BaseModel):
    type: Literal["ping"] = "ping"
```

---

### Server → Client

#### Chunk streaming-ответа
```python
class ServerStreamChunk(BaseModel):
    type: Literal["stream_chunk"] = "stream_chunk"
    content: str  # фрагмент текста
    message_id: str  # ID сообщения для группировки chunks
```

#### Завершение streaming
```python
class ServerStreamEnd(BaseModel):
    type: Literal["stream_end"] = "stream_end"
    message_id: str
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    session_id: Optional[str] = None
```

#### HITL-запрос
```python
class ToolInput(BaseModel):
    """Dynamic tool input — schema varies per tool."""
    model_config = ConfigDict(extra="allow")

class ServerHITLRequest(BaseModel):
    type: Literal["hitl_request"] = "hitl_request"
    request_id: str  # уникальный ID запроса
    tool_name: str  # имя инструмента
    tool_input: ToolInput  # параметры инструмента (typed model, Constitution VIII)
    description: str  # человекочитаемое описание
```

#### HITL разрешён другим интерфейсом
```python
class ServerHITLResolved(BaseModel):
    type: Literal["hitl_resolved"] = "hitl_resolved"
    request_id: str
    approved: bool
    resolved_by: str  # "telegram" | "web"
```

#### Уточняющий вопрос от Claude
```python
class ServerQuestion(BaseModel):
    type: Literal["question"] = "question"
    request_id: str
    question: str
    options: Optional[list[str]] = None  # варианты ответа (null = свободный ввод)
```

#### План от Claude
```python
class ServerPlan(BaseModel):
    type: Literal["plan"] = "plan"
    request_id: str
    content: str  # markdown-содержимое плана
```

#### Статус задачи
```python
class ServerTaskStatus(BaseModel):
    type: Literal["task_status"] = "task_status"
    status: str  # "running" | "completed" | "error" | "cancelled"
    message: Optional[str] = None
```

#### Уведомление о блокировке сессии
```python
class ServerSessionBusy(BaseModel):
    type: Literal["session_busy"] = "session_busy"
    message: str = "Задача уже выполняется в этой сессии"
    busy_since: datetime
```

#### Уведомление об использовании инструмента
```python
class ServerToolUse(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    tool_name: str
    tool_input: ToolInput  # typed model (Constitution VIII)
    result: Optional[str] = None
```

#### Ошибка
```python
class ServerError(BaseModel):
    type: Literal["error"] = "error"
    message: str
    code: Optional[str] = None
```

#### Pong
```python
class ServerPong(BaseModel):
    type: Literal["pong"] = "pong"
```

---

## Heartbeat

- Client отправляет `ping` каждые 30 секунд
- Server отвечает `pong`
- Если pong не получен за 60 секунд — клиент переподключается
- Server закрывает соединение после 90 секунд молчания

## Reconnection

- Клиент автоматически переподключается с экспоненциальным backoff (1s, 2s, 4s, 8s, max 30s)
- При переподключении клиент получает текущий статус задачи через `task_status`
- Пропущенные stream_chunk'ы не восстанавливаются (клиент может запросить полный ответ через REST)
