# 🔍 RALPH LOOP - Code Review

**Дата:** 2026-01-26
**Проект:** Claude Code Telegram Proxy
**Язык:** Python 3.10+
**Архитектура:** DDD (Domain-Driven Design)

---

## 1. 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (Priority: High)

### 1.1 GOD OBJECT - MessageHandlers (1085 строк)
**Файл:** `presentation/handlers/messages.py`
**Класс:** `MessageHandlers`

**Суть проблемы:**
Класс `MessageHandlers` нарушает SRP (Single Responsibility Principle) и выполняет более 15 различных обязанностей:
- Обработка текстовых сообщений
- HITL (Human-in-the-Loop) для разрешений
- Обработка вопросов от Claude
- Управление state machines (15+ разных состояний)
- Валидация переменных (3-этапный flow)
- Определение cd-команд через regex
- Управление сессиями
- YOLO mode
- Project/Context интеграция
- И это только верхушка айсберга...

**Почему это плохо:**
```python
# Линии 70-98: 15+ словарей для state management
self._user_sessions: dict[int, ClaudeCodeSession] = {}
self._user_working_dirs: dict[int, str] = {}
self._continue_sessions: dict[int, str] = {}
self._expecting_answer: dict[int, bool] = {}
self._expecting_path: dict[int, bool] = {}
self._pending_questions: dict[int, list[str]] = {}
self._pending_permission_messages: dict[int, Message] = {}
self._permission_events: dict[int, asyncio.Event] = {}
self._permission_responses: dict[int, bool] = {}
self._question_events: dict[int, asyncio.Event] = {}
self._question_responses: dict[int, str] = {}
self._yolo_mode: dict[int, bool] = {}
self._expecting_var_name: dict[int, bool] = {}
self._expecting_var_value: dict[int, str] = {}
self._expecting_var_desc: dict[int, tuple] = {}
self._pending_var_message: dict[int, Message] = {}
self._editing_var_name: dict[int, str] = {}
```

**Последствия:**
1. Невозможность тестировать отдельные части
2. Любое изменение может сломать всё остальное
3. Критическая сложность отладки (15+ race conditions возможны)
4. Невозможность переиспользования компонентов

**Как исправить:**

```python
# Разделить на отдельные классы:

class UserStateManager:
    """Управление состоянием пользователя"""
    def __init__(self):
        self._sessions: dict[int, UserSession] = {}

    def get_state(self, user_id: int) -> UserSession:
        ...

class HITLManager:
    """Human-in-the-Loop менеджер"""
    def __init__(self, state_manager: UserStateManager):
        self._state = state_manager
        self._permissions = PermissionHandler()
        self._questions = QuestionHandler()

    async def request_permission(self, user_id: int, tool: str, details: str) -> bool:
        ...

class VariableInputFlow:
    """Flow для ввода переменных (State Machine)"""
    def __init__(self):
        self._current_step: dict[int, InputStep] = {}

    async def handle_name_input(self, user_id: int, name: str) -> ValidationResult:
        ...

class MessageHandler:
    """Только обработка сообщений, делегирует остальное"""
    def __init__(self, hitl: HITLManager, variables: VariableInputFlow, sessions: SessionManager):
        self._hitl = hitl
        self._variables = variables
        self._sessions = sessions

    async def handle_text(self, message: Message) -> None:
        # Простая маршрутизация
        if self._variables.is_active(message.from_user.id):
            await self._variables.handle_input(message)
        elif self._hitl.is_waiting(message.from_user.id):
            await self._hitl.handle_response(message)
        else:
            await self._sessions.start_new_task(message)
```

---

### 1.2 Прямая зависимость от конкретных реализаций (Dependency Inversion Violation)

**Файл:** `main.py` (линии 172-257)

**Суть проблемы:**
```python
# Прямое создание конкретных реализаций в Application.setup()
account_repo = SQLiteAccountRepository()
self.account_service = AccountService(account_repo)

project_repo = SQLiteProjectRepository()
context_repo = SQLiteProjectContextRepository()
self.project_service = ProjectService(project_repo, context_repo)

self.claude_proxy = ClaudeCodeProxyService(
    claude_path=os.getenv("CLAUDE_PATH", "claude"),
    default_working_dir=default_working_dir,
    max_turns=int(os.getenv("CLAUDE_MAX_TURNS", "50")),
    timeout_seconds=int(os.getenv("CLAUDE_TIMEOUT", "600")),
)
```

**Почему это плохо:**
1. Невозможно подменить реализации для тестов
2. Жёсткая привязка к SQLite
3. При смене базы данных нужно переписывать Application
4. Нарушение DIP (Dependency Inversion Principle)

**Как исправить:**

```python
# Использовать Dependency InjectionContainer

from dependency_injector import containers, providers
from domain.repositories import IUserRepository, ISessionRepository

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Репозитории
    user_repository = providers.Singleton(
        SQLiteUserRepository,
        db_path=config.database.url
    )

    session_repository = providers.Singleton(
        SQLiteSessionRepository,
        db_path=config.database.url
    )

    # Сервисы (зависят от абстракций)
    account_service = providers.Factory(
        AccountService,
        account_repository=user_repository  # Может быть любой реализацией IUserRepository
    )

    project_service = providers.Factory(
        ProjectService,
        project_repository=providers.Singleton(IProjectRepository),  # Абстракция!
        context_repository=providers.Singleton(IContextRepository),
    )

# В main.py:
container = Container()
container.config.from_yaml("config.yml")

app = Application(
    account_service=container.account_service,
    project_service=container.project_service,
)
```

---

### 1.3 Race Conditions в state management

**Файл:** `infrastructure/claude_code/sdk_service.py` (линии 556-566)

**Суть проблемы:**
```python
# Создаём локальные ссылки, но потом используем self._... которые могут быть перезаписаны
cancel_event = asyncio.Event()
permission_event = asyncio.Event()
question_event = asyncio.Event()

self._cancel_events[user_id] = cancel_event
self._permission_events[user_id] = permission_event
self._question_events[user_id] = question_event
```

**Почему это плохо:**
Если придёт второе сообщение от того же пользователя пока первое выполняется, `self._permission_events[user_id]` будет перезаписан, и первое событие никогда не дождётся ответа.

**Как исправить:**

```python
# Использовать immutable state
class TaskContext:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.cancel_event = asyncio.Event()
        self.permission_event = asyncio.Event()
        self.question_event = asyncio.Event()
        self.created_at = datetime.now()

class SDKService:
    def __init__(self):
        self._active_tasks: dict[int, TaskContext] = {}

    async def run_task(self, user_id: int, ...) -> SDKTaskResult:
        # Проверяем, что нет активной задачи
        if user_id in self._active_tasks:
            raise RuntimeError(f"Task already running for user {user_id}")

        # Создаём новый контекст
        context = TaskContext(user_id)
        self._active_tasks[user_id] = context

        try:
            # Используем context.cancel_event вместо self._cancel_events[user_id]
            await self._execute_with_context(context, ...)
        finally:
            self._active_tasks.pop(user_id, None)
```

---

### 1.4 N+1 Query Problem в SQLite repositories

**Файл:** `infrastructure/persistence/sqlite_repository.py` (линии 220-254)

**Суть проблемы:**
```python
async def _row_to_session(self, db: aiosqlite.Connection, row) -> Session:
    messages = []
    async with db.execute(
        "SELECT * FROM session_messages WHERE session_id = ? ORDER BY timestamp",
        (row["session_id"],),
    ) as msg_cursor:
        msg_rows = await msg_cursor.fetchall()
        for msg_row in msg_rows:
            messages.append(Message(...))

    return Session(...)
```

**Почему это плохо:**
При загрузке 100 сессий делается 100 дополнительных запросов для загрузки сообщений.

**Как исправить:**

```python
# Использовать JOIN или загрузку всеми сообщениями сразу

async def find_by_user(self, user_id: UserId) -> List[Session]:
    async with aiosqlite.connect(self.db_path) as db:
        # Один запрос с LEFT JOIN
        query = """
            SELECT
                s.*,
                sm.role, sm.content, sm.timestamp, sm.tool_use_id, sm.tool_result
            FROM sessions s
            LEFT JOIN session_messages sm ON s.session_id = sm.session_id
            WHERE s.user_id = ?
            ORDER BY s.updated_at DESC, sm.timestamp
        """
        async with db.execute(query, (int(user_id),)) as cursor:
            rows = await cursor.fetchall()

        # Группируем сообщения по session_id
        sessions_dict = {}
        for row in rows:
            session_id = row["session_id"]
            if session_id not in sessions_dict:
                sessions_dict[session_id] = {
                    "session": self._row_to_session_partial(row),
                    "messages": []
                }
            if row["role"]:  # Есть сообщение
                sessions_dict[session_id]["messages"].append(
                    self._row_to_message(row)
                )

        return [self._build_session(s["session"], s["messages"])
                for s in sessions_dict.values()]
```

---

### 1.5 Hardcoded admin_id

**Файл:** `main.py` (линия 290)

**Суть проблемы:**
```python
admin_id = 664382290  # <- HARDCODED!
```

**Почему это плохо:**
1. Небезопасно - ID в открытом виде
2. При смене админа нужно переписывать код
3. Нельзя добавить нескольких админов

**Как исправить:**

```python
# В settings.py:
@admin_ids = list(map(int, os.getenv("ADMIN_IDS", "664382290").split(",")))

# В main.py:
admin_ids = settings.admin_ids
for admin_id in admin_ids:
    try:
        await self.bot.send_message(admin_id, message)
    except Exception as e:
        logger.warning(f"Failed to notify admin {admin_id}: {e}")
```

---

## 2. 🟠 АРХИТЕКТУРНЫЕ НАРУШЕНИЯ (Priority: Medium)

### 2.1 Протекание бизнес-логики в presentation layer

**Файл:** `presentation/handlers/messages.py` (линии 914-1073)

**Суть проблемы:**
```python
async def _handle_var_name_input(self, message: Message):
    """Handle variable name input during add flow"""
    var_name = message.text.strip().upper()  # Бизнес-логика uppercase!

    # Валидация - это бизнес-логика!
    if not re.match(r'^[A-Z][A-Z0-9_]*$', var_name):
        await message.answer("❌ Неверное имя переменной...")
        return
```

**Как исправить:**

```python
# domain/services/variable_validation_service.py
class VariableValidationService:
    def validate_name(self, name: str) -> ValidationResult:
        """Validate variable name according to domain rules"""
        if not re.match(r'^[A-Z][A-Z0-9_]*$', name):
            return ValidationResult.invalid(
                "Имя должно начинаться с буквы и содержать только буквы, цифры и _"
            )
        return ValidationResult.valid()

# Presentation layer только делегирует:
async def _handle_var_name_input(self, message: Message):
    var_name = message.text.strip().upper()
    result = await self._variable_service.validate_name(var_name)
    if not result.is_valid:
        await message.answer(f"❌ {result.error}")
        return
```

---

### 2.2 Violation of Open/Closed Principle

**Файл:** `infrastructure/claude_code/sdk_service.py` (линии 50-123)

**Суть проблемы:**
```python
def _format_tool_response(tool_name: str, response: Any, max_length: int = 500) -> str:
    """Format tool response fordisplay in Telegram."""
    tool_lower = tool_name.lower()

    # Giant if-elif chain для каждого инструмента!
    if tool_lower == "glob" and "filenames" in response:
        files = response.get("filenames", [])
        ...
    elif tool_lower == "read" and "file" in response:
        ...
    elif tool_lower == "grep" and "matches" in response:
        ...
```

**Как исправить:**

```python
# Использовать Strategy Pattern
from abc import ABC, abstractmethod

class ToolResponseFormatter(ABC):
    @abstractmethod
    async def format(self, response: dict) -> str:
        pass

class GlobResponseFormatter(ToolResponseFormatter):
    async def format(self, response: dict) -> str:
        files = response.get("filenames", [])
        if not files:
            return "Файлов не найдено"
        file_list = "\n".join(f"  {f}" for f in files[:20])
        return f"Найдено {len(files)} файлов:\n{file_list}"

class ReadResponseFormatter(ToolResponseFormatter):
    async def format(self, response: dict) -> str:
        ...

class FormatterRegistry:
    def __init__(self):
        self._formatters = {
            "glob": GlobResponseFormatter(),
            "read": ReadResponseFormatter(),
            "grep": GrepResponseFormatter(),
        }

    def get_formatter(self, tool_name: str) -> ToolResponseFormatter:
        return self._formatters.get(tool_name.lower(), DefaultFormatter())

# Использование:
registry = FormatterRegistry()
formatter = registry.get_formatter(tool_name)
formatted = await formatter.format(response)
```

---

### 2.3 Anemic Domain Model

**Файл:** `domain/entities/session.py` (весь файл)

**Суть проблемы:**
```python
@dataclass
class Session:
    """Chat session entity"""
    session_id: str
    user_id: UserId
    messages: List[Message] = field(default_factory=list)
    context: Dict = field(default_factory=dict)

    # Только getters/setters! Никакой бизнес-логики!
    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def clear_messages(self) -> None:
        self.messages.clear()
```

**Почему это плохо:**
Domain entities должны содержать бизнес-логику, а не быть просто контейнерами данных.

**Как исправить:**

```python
class Session:
    """Rich domain model with business logic"""

    def __init__(self, session_id: str, user_id: UserId):
        self.session_id = session_id
        self.user_id = user_id
        self._messages: List[Message] = []
        self._created_at = datetime.utcnow()

    def add_message(self, message: Message) -> None:
        """Add message with business rules validation"""
        if len(self._messages) >= self.MAX_MESSAGES:
            raise DomainException(
                f"Session cannot have more than {self.MAX_MESSAGES} messages"
            )

        if self._is_duplicate(message):
            return  # Бизнес-правило: не добавляем дубликаты

        self._messages.append(message)

    def can_continue(self) -> bool:
        """Check if session can be continued (business rule)"""
        if not self._messages:
            return True
        last_message = self._messages[-1]
        return (datetime.utcnow() - last_message.timestamp) < timedelta(hours=24)

    def get_conversation_summary(self) -> str:
        """Generate summary (business logic)"""
        pass
```

---

### 2.4 Feature Envy - процедуры лезут в чужие объекты

**Файл:** `application/services/bot_service.py` (линии 232-241)

**Суть проблемы:**
```python
async def get_user_stats(self, user_id: int) -> Dict:
    user = await self.user_repository.find_by_id(UserId.from_int(user_id))
    if not user:
        return {}

    commands = await self.command_repository.find_by_user(user_id, limit=1000)
    sessions = await self.session_repository.find_by_user(UserId.from_int(user_id))

    # Service знает, как форматить статистику пользователя!
    return {
        "user": {
            "id": user.user_id,
            "username": user.username,
            "role": user.role.name,
            ...
        },
        "commands": {
            "total": len(commands),
            "by_status": await self.command_repository.get_statistics(user_id)
        },
        ...
    }
```

**Как исправить:**

```python
# Domain entity должна сама уметь предоставлять свою статистику
class User:
    def get_stats(self, commands: List[Command], sessions: List[Session]) -> UserStats:
        return UserStats(
            user_id=self.user_id,
            username=self.username,
            role=self.role,
            total_commands=len(commands),
            active_sessions=sum(1 for s in sessions if s.is_active),
            last_command_at=max((c.created_at for c in commands), default=None)
        )

# Service просто собирает данные
class BotService:
    async def get_user_stats(self, user_id: int) -> UserStats:
        user = await self.user_repository.find_by_id(UserId.from_int(user_id))
        commands = await self.command_repository.find_by_user(user_id)
        sessions = await self.session_repository.find_by_user(user.user_id)

        return user.get_stats(commands, sessions)
```

---

### 2.5 Primitive Obsession

**Файл:** `infrastructure/claude_code/proxy_service.py` (линии 24-48)

**Суть проблемы:**
```python
# Использование tuple вместо value object
async def check_claude_installed(self) -> tuple[bool, str]:
    try:
        proc = await asyncio.create_subprocess_exec(...)
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return True, f"Claude Code: {version}"  # tuple
        else:
            return False, f"Claude Code error: {stderr.decode()}"  # tuple
```

**Как исправить:**

```python
# Value object
@dataclass(frozen=True)
class InstallationStatus:
    is_installed: bool
    message: str

    @classmethod
    def installed(cls, version: str) -> "InstallationStatus":
        return cls(is_installed=True, message=f"Claude Code: {version}")

    @classmethod
    def not_installed(cls, error: str) -> "InstallationStatus":
        return cls(is_installed=False, message=f"Claude Code error: {error}")

    @classmethod
    def not_found(cls) -> "InstallationStatus":
        return cls(
            is_installed=False,
            message="Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
        )

# Использование:
status = await self.check_claude_installed()
if status.is_installed:
    logger.info(status.message)
else:
    logger.warning(status.message)
```

---

## 3. 🟡 КОД-СМЕЛЛЫ И ОПТИМИЗАЦИЯ (Priority: Low)

### 3.1 Magic Numbers

**Файл:** `presentation/handlers/messages.py` (линия 594)
```python
await asyncio.wait_for(event.wait(), timeout=300)  # Что такое 300?

# Лучше:
HITL_PERMISSION_TIMEOUT = 300  # seconds
await asyncio.wait_for(event.wait(), timeout=HITL_PERMISSION_TIMEOUT)
```

---

### 3.2 Inconsistent logging

**Файл:** `infrastructure/claude_code/proxy_service.py` (линии 162, 216, 236, 447)

```python
logger.info(f"[{user_id}] Full command: {' '.join(cmd)}")  # INFO
logger.debug(f"[{user_id}] RAW: {line_str[:200]}")  # DEBUG
logger.info(f"Unknown event type: {event_type}, keys: {list(data.keys())}")  # INFO?? Должно быть WARNING
```

**Рекомендация:**
Использовать уровни логирования консистентно:
- DEBUG: детальная отладочная информация
- INFO: важные бизнес-события
- WARNING: подозрительные ситуации (unknown event type!)
- ERROR: ошибки

---

### 3.3 Too many parameters

**Файл:** `infrastructure/claude_code/sdk_service.py` (линии 515-531)

```python
async def run_task(
    self,
    user_id: int,
    prompt: str,
    working_dir: Optional[str] = None,
    session_id: Optional[str] = None,
    on_text: Optional[Callable[[str], Awaitable[None]]] = None,
    on_tool_use: Optional[Callable[[str, dict], Awaitable[None]]] = None,
    on_tool_result: Optional[Callable[[str, str], Awaitable[None]]] = None,
    on_permission_request: Optional[Callable[[str, str, dict], Awaitable[None]]] = None,
    on_permission_completed: Optional[Callable[[bool], Awaitable[None]]] = None,
    on_question: Optional[Callable[[str, list[str]], Awaitable[None]]] = None,
    on_question_completed: Optional[Callable[[str], Awaitable[None]]] = None,
    on_thinking: Optional[Callable[[str], Awaitable[None]]] = None,
    on_error: Optional[Callable[[str], Awaitable[None]]] = None,
) -> SDKTaskResult:
```

**Рекомендация:**

```python
@dataclass
class TaskCallbacks:
    on_text: Optional[Callable[[str], Awaitable[None]]] = None
    on_tool_use: Optional[Callable[[str, dict], Awaitable[None]]] = None
    on_tool_result: Optional[Callable[[str, str], Awaitable[None]]] = None
    on_permission_request: Optional[Callable[[str, str, dict], Awaitable[None]]] = None
    on_permission_completed: Optional[Callable[[bool], Awaitable[None]]] = None
    on_question: Optional[Callable[[str, list[str]], Awaitable[None]]] = None
    on_question_completed: Optional[Callable[[str], Awaitable[None]]] = None
    on_thinking: Optional[Callable[[str], Awaitable[None]]] = None
    on_error: Optional[Callable[[str], Awaitable[None]]] = None

@dataclass
class TaskConfig:
    user_id: int
    prompt: str
    working_dir: Optional[str] = None
    session_id: Optional[str] = None
    callbacks: TaskCallbacks = field(default_factory=TaskCallbacks)

async def run_task(self, config: TaskConfig) -> SDKTaskResult:
    ...
```

---

### 3.4 Long parameter list (ещё один пример)

**Файл:** `main.py` (линии 214-272) - `_register_handlers`

**Рекомендация:** Использовать builder pattern или configuration object.

---

### 3.5 Inconsistent error handling

**Файл:** `presentation/handlers/callbacks.py` (линии 72-73, 962-977)

```python
# Иногда игнорируем ошибки:
try:
    response, _ = await self.bot_service.chat(...)
except:
    pass  # Skip AI follow-up on error - ПЛОХО!

# Иногда логируем:
except Exception as e:
    logger.error(f"Error handling command: {e}")
```

**Рекомендация:**
```python
# Всегда логировать и NEVER использовать bare except
try:
    response, _ = await self.bot_service.chat(...)
except ClaudeServiceUnavailable as e:
    logger.warning(f"AI service unavailable for follow-up: {e}")
except Exception as e:
    logger.error(f"Unexpected error in AI follow-up: {e}", exc_info=True)
```

---

### 3.6 Comments instead of self-documenting code

**Файл:** `infrastructure/persistence/sqlite_repository.py` (линия 17)

```python
# SQLite implementation of UserRepository  # <- Избыточный комментарий
class SQLiteUserRepository(UserRepository):
```

**Рекомендация:**
Имя класса уже говорит, что это SQLite реализация. Комментарий нужен только если есть неочевидная логика.

---

### 3.7 Dead code

**Файл:** `domain/services/command_execution_service.py` (весь файл - 46 строк)

Интерфейс `ICommandExecutionService` определён, но нигде не используется (есть только `CommandExecutionResult`). Либо удалить, либо реализовать.

---

### 3.8 Duplicate string literals

**Файл:** `infrastructure/claude_code/sdk_service.py` (линии 333-342)

```python
plugin_descriptions = {
    "commit-commands": "Git workflow: commit, push, PR",
    "code-review": "Ревью кода и PR",
    ...
}

# Этот же словарь дублируется в callbacks.py (линии 1503-1515)!
```

**Рекомендация:** Вынести в `shared/constants.py` или domain.

---

### 3.9 Missing type hints

**Файл:** `infrastructure/claude_code/proxy_service.py` (линии 474-539)

Многие методы не имеют полных type hints для параметров и return values.

---

### 3.10 Complex boolean expressions

**Файл:** `presentation/handlers/messages.py` (линии 166-172)

```python
def is_expecting_var_input(self, user_id: int) -> bool:
    return (
        self._expecting_var_name.get(user_id, False) or
        user_id in self._expecting_var_value or
        user_id in self._expecting_var_desc
    )
```

**Рекомендация:**

```python
def is_expecting_var_input(self, user_id: int) -> bool:
    states = [
        self._expecting_var_name,
        self._expecting_var_value,
        self._expecting_var_desc,
    ]
    return any(user_id in state for state in states)
```

---

## 4. ✅ ВЕРДИКТ

### Общая оценка: **5.5 / 10**

**Плюсы:**
+ ✅ Хорошая структура папок (Domain, Application, Infrastructure, Presentation)
+ ✅ Использование DDD концепций (entities, value objects, repositories)
+ ✅ Async/await везде
+ ✅ AIOsqlite вместо синхронного sqlite3
+ ✅ Попытка разделить бизнес-логику от инфраструктуры

**Минусы:**
- ❌ GOD Object (MessageHandlers) делает код невозможным для поддержки
- ❌ Прямые зависимости вместо DI
- ❌ Race conditions в state management
- ❌ N+1 queries
- ❌ Множество code smells (magic numbers, long parameter lists, etc.)

---

## 🔧 Главный совет разработчику

> **"Начни с рефакторинга MessageHandlers - это бомба замедленного действия. Разбей его на 5-7 отдельных классов с чёткими обязанностями, затем внедри Dependency Injection для всех сервисов."**

---

## 📋 Приоритет действий

1. **Critical:** Разбить MessageHandlers на отдельные менеджеры
2. **Critical:** Внедрить DI Container
3. **High:** Исправить race conditions в SDK service
4. **High:** Оптимизировать N+1 queries в репозиториях
5. **Medium:** Убрать hardcoded admin_id
6. **Medium:** Рефакторинг _format_tool_response через Strategy pattern
7. **Low:** Добавить type hints везде
8. **Low:** Убрать magic numbers в константы

---

**Код можно спасти, но нужен серьёзный рефакторинг.**
