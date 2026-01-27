# 🔬 Code Review — Claude Code Telegram Proxy

**Reviewer:** Senior Backend Architect (15+ years exp)
**Date:** 2025-01-26
**Project:** Claude Code Telegram Proxy
**Lines of Code:** ~10,000+ (Python)

---

## 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (Priority: High)

### 1. Hardcoded Admin ID в main.py

**Файл:** `main.py:290`

**Проблема:**
```python
admin_id = 664382290  # ← HARDCODED!
```

**Почему это плохо:**
- **Hardcoded** ID пользователя в коде — это дыра в безопасности
- При деплое на другой сервер уведомление не отправится
- Нарушение 12-factor app (конфигурация должна быть в env)

**Как исправить:**
```python
# main.py
admin_id = os.getenv("ADMIN_TELEGRAM_ID", os.getenv("ALLOWED_USER_ID", "").split(",")[0])
if admin_id:
    admin_id = int(admin_id)
else:
    logger.warning("No admin ID configured")
    return
```

---

### 2. Hardcoded прокси-credentials в AccountService

**Файл:** `application/services/account_service.py:23`

**Проблема:**
```python
CLAUDE_PROXY = "http://proxyuser:!QAZ1qaz7@148.253.208.124:3128"  # ← CREDENTIALS IN CODE!
```

**Почему это плохо:**
- **КРИТИЧЕСКАЯ БЕЗОПАСНОСТЬ:** Пароль `!QAZ1qaz7` в открытом виде
- IP-адрес прокси захардкожен
- При компрометации репозитория прокси будет взломан

**Как исправить:**
```python
# application/services/account_service.py
CLAUDE_PROXY = os.getenv("CLAUDE_PROXY", "")
NO_PROXY_VALUE = os.getenv("NO_PROXY", "localhost,127.0.0.1")

# В .env:
# CLAUDE_PROXY=http://proxyuser:password@host:port
# NO_PROXY=localhost,127.0.0.1
```

---

### 3. Отсутствие миграций БД — DIY schema

**Файл:** `infrastructure/persistence/sqlite_repository.py:381-490`

**Проблема:**
- Schema создаётся вручную в `init_database()`
- Нет версионности schema
- Нет механизма rollback
- Нет миграций при изменении структуры

**Почему это плохо:**
- При изменении schema старые базы данных сломаются
- Нельзя откатиться назад
- Нет истории изменений

**Как исправить:**
```bash
# Использовать alembic или aiosqlite с миграциями
pip install alembic

# Создать migrations/versions/*.py
# Пример миграции:
async def upgrade():
    await op.execute("""
        ALTER TABLE project_contexts ADD COLUMN new_field TEXT
    """)

async def downgrade():
    await op.execute("""
        ALTER TABLE project_contexts DROP COLUMN new_field
    """)
```

---

### 4. N+1 проблема в репозиториях

**Файл:** `infrastructure/persistence/sqlite_repository.py:145-149`

**Проблема:**
```python
async def find_by_user(self, user_id: UserId) -> List[Session]:
    async with aiosqlite.connect(self.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(...) as cursor:
            rows = await cursor.fetchall()
            sessions = []
            for row in rows:
                sessions.append(await self._row_to_session(db, row))  # ← N+1!
        return sessions
```

**Почему это плохо:**
- Для каждой сессии выполняется отдельный запрос к `session_messages`
- При 100 сессиях = 100+ запросов к БД
- ВHighload это убьёт БД

**Как исправить:**
```python
async def find_by_user(self, user_id: UserId) -> List[Session]:
    async with aiosqlite.connect(self.db_path) as db:
        db.row_factory = aiosqlite.Row

        # Один запрос с JOIN
        async with db.execute("""
            SELECT s.*, sm.role, sm.content, sm.timestamp
            FROM sessions s
            LEFT JOIN session_messages sm ON s.session_id = sm.session_id
            WHERE s.user_id = ?
            ORDER BY s.updated_at DESC, sm.timestamp
        """, (int(user_id),)) as cursor:
            rows = await cursor.fetchall()

        # Собрать sessions за один проход
        sessions = self._rows_to_sessions_grouped(rows)
        return sessions
```

---

### 5. Потенциальная утечка памяти в MessageHandlers

**Файл:** `presentation/handlers/messages.py:70-99`

**Проблема:**
```python
# В __init__:
self._user_sessions: dict[int, ClaudeCodeSession] = {}  # Не очищается
self._user_working_dirs: dict[int, str] = {}            # Не очищается
self._continue_sessions: dict[int, str] = {}            # Не очищается
self._permission_events: dict[int, asyncio.Event] = {}  # Не очищается
self._yolo_mode: dict[int, bool] = {}                  # Не очищается
```

**Почему это плохо:**
- Словари растут бесконечно при использовании бота
- Каждому пользователю — отдельная запись в памяти
- Через месяц работы бота съедит всю RAM

**Как исправить:**
```python
# Добавить TTL-очистку:
import time
from collections import defaultdict

class TTLDict(dict):
    def __init__(self, ttl_seconds=3600):
        super().__init__()
        self._ttl = ttl_seconds
        self._timestamps = {}

    def __getitem__(self, key):
        self._timestamps[key] = time.time()
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        self._timestamps[key] = time.time()
        super().__setitem__(key, value)
        self._cleanup_expired()

    def _cleanup_expired(self):
        now = time.time()
        expired = [k for k, t in self._timestamps.items() if now - t > self._ttl]
        for k in expired:
            self.pop(k, None)
            self._timestamps.pop(k, None)

# Использовать:
self._user_sessions = TTLDict(ttl_seconds=86400)  # 24 часа
```

---

### 6. Отсутствие валидации входных данных от Telegram

**Файл:** `presentation/handlers/messages.py:275-323`

**Проблема:**
```python
async def handle_text(self, message: Message) -> None:
    user_id = message.from_user.id
    # ← Нет проверки длины сообщения!
    # ← Нет проверки на инъекции!
    # ← Нет rate limiting!

    enriched_prompt = message.text  # Может быть 1МБ текст!
```

**Почему это плохо:**
- Пользователь может отправить мегабайт текста и убить процессор
- Rate limiting отсутствует — можно DOS-атакой положить бота
- Отсутствие валидации — вектор для атак

**Как исправить:**
```python
MAX_MESSAGE_LENGTH = 10000  # 10KB

async def handle_text(self, message: Message) -> None:
    user_id = message.from_user.id

    # Rate limiting
    if not self.rate_limiter.is_allowed(user_id):
        await message.answer("⏱️ Слишком много сообщений. Подождите.")
        return

    # Валидация длины
    if len(message.text) > MAX_MESSAGE_LENGTH:
        await message.answer(
            f"❌ Слишком длинное сообщение (макс {MAX_MESSAGE_LENGTH} символов)"
        )
        return

    # Sanitization (если нужно)
    text = message.text[:MAX_MESSAGE_LENGTH]
```

---

### 7. Environment pollution в sdk_service.py

**Файл:** `infrastructure/claude_code/sdk_service.py:779-823`

**Проблема:**
```python
# Модифицирует ГЛОБАЛЬНЫЙ os.environ!
os.environ["GIT_TERMINAL_PROMPT"] = "0"
for key, value in user_env.items():
    os.environ[key] = value  # ← ГЛОБАЛЬНЫЕ SIDE EFFECTS!

# Критично: в async среде несколько пользователей могут
# одновременно менять os.environ — это RACE CONDITION!
```

**Почему это плохо:**
- В async среде несколько задач одновременно меняют `os.environ`
- Один пользователь может перезаписать env другого
- Непредсказуемое поведение при concurrency

**Как исправить:**
```python
import copy

async def run_task(self, ...):
    # Локальная копия окружения для subprocess
    local_env = copy.deepcopy(os.environ)
    local_env.update(user_env)
    local_env["GIT_TERMINAL_PROMPT"] = "0"

    # Передать в subprocess явно
    process = await asyncio.create_subprocess_exec(
        *cmd,
        env=local_env,  # ← Локальное env, не глобальное!
        ...
    )
```

---

## 🟠 АРХИТЕКТУРНЫЕ НАРУШЕНИЯ (Priority: Medium)

### 8. God Object: MessageHandlers

**Файл:** `presentation/handlers/messages.py:46-1074`

**Проблема:**
- Класс `MessageHandlers` делает **ВСЁ**: обработку сообщений, HITL, управление сессиями, переменными, YOLO-режимом, файловый браузер...
- **1000+ строк** в одном классе
- 20+ dictionaries для состояния

**Почему это плохо:**
- Нарушение SRP (Single Responsibility Principle)
- Невозможно тестировать
- Невозможно переиспользовать

**Как исправить:**
```python
# Разбить на отдельные классы:

class SessionManager:
    """Управляет сессиями пользователей"""
    def __init__(self):
        self._sessions = TTLDict(ttl_seconds=86400)

    def get_session(self, user_id: int) -> ClaudeCodeSession:
        ...

class HITLManager:
    """Управляет HITL-состоянием"""
    def __init__(self):
        self._permissions = TTLDict(ttl_seconds=300)
        self._questions = TTLDict(ttl_seconds=300)

    async def request_permission(self, user_id: int, tool: str, details: str) -> bool:
        ...

class VariableInputManager:
    """Управляет вводом переменных"""
    ...

class MessageHandlers:
    """Только маршрутизация сообщений"""
    def __init__(self, session_mgr: SessionManager, hitl_mgr: HITLManager, ...):
        self.session_mgr = session_mgr
        self.hitl_mgr = hitl_mgr

    async def handle_text(self, message: Message):
        if self.hitl_mgr.is_pending(user_id):
            return await self.hitl_mgr.handle_response(message)

        session = self.session_mgr.get_session(user_id)
        ...
```

---

### 9. God Object: CallbackHandlers

**Файл:** `presentation/handlers/callbacks.py:12-1857`

**Проблема:**
- **1857 строк** в одном классе
- Обрабатывает ВСЕ callback'и: команды, Docker, проекты, контексты, переменные, плагины, файловый браузер...

**Почему это плохо:**
- Невозможно поддерживать
- Любое изменение может сломать всё
- Тестирование невозможно

**Как исправить:**
```python
# Разбить на отдельные хендлеры:

class ClaudeCallbackHandlers:
    """HITL callbacks"""
    async def handle_approve(self, callback): ...
    async def handle_reject(self, callback): ...
    async def handle_answer(self, callback): ...

class ProjectCallbackHandlers:
    """Project management"""
    async def handle_switch(self, callback): ...
    async def handle_delete(self, callback): ...

class ContextCallbackHandlers:
    """Context management"""
    async def handle_list(self, callback): ...
    async def handle_switch(self, callback): ...

# Регистрация:
router.register(ClaudeCallbackHandlers(), prefix="claude")
router.register(ProjectCallbackHandlers(), prefix="project")
router.register(ContextCallbackHandlers(), prefix="ctx")
```

---

### 10. Нарушение Dependency Inversion

**Файлы:**
- `application/services/account_service.py:634`
- `infrastructure/claude_code/sdk_service.py:196-197`

**Проблема:**
```python
# account_service.py (строка 634):
from infrastructure.persistence.sqlite_account_repository import SQLiteAccountRepository

# sdk_service.py (строка 196):
self.account_service: "AccountService" = None
```

**Почему это плохо:**
- Application layer зависит от Infrastructure layer (account_service.py)
- Circular dependency между слоёми
- Невозможно заменить реализацию репозитория в тестах

**Как исправить:**
```python
# domain/repositories/account_repository.py (создать интерфейс):
from abc import ABC, abstractmethod

class IAccountRepository(ABC):
    @abstractmethod
    async def find_by_user_id(self, user_id: int) -> Optional[AccountSettings]:
        ...

    @abstractmethod
    async def save(self, settings: AccountSettings) -> None:
        ...

# application/services/account_service.py:
from domain.repositories.account_repository import IAccountRepository

class AccountService:
    def __init__(self, repository: IAccountRepository):  # ← Зависимость от абстракции
        self.repository = repository

# main.py (композиция):
from infrastructure.persistence.sqlite_account_repository import SQLiteAccountRepository

account_repo = SQLiteAccountRepository()
account_service = AccountService(account_repo)  # ← DIP соблюдён
```

---

### 11. Magic Numbers и Strings

**Файлы:** Множество

**Проблемы:**
```python
# messages.py:200
timeout=60  # ← Magic number

# messages.py:920
if not re.match(r'^[A-Z][A-Z0-9_]*$', var_name):  # ← Magic regex

# proxy_service.py:392
tool_result = str(content)[:500]  # ← Magic 500

# sdk_service.py:646
await asyncio.wait_for(question_event.wait(), timeout=300)  # ← Magic 300

# file_browser_service.py:47-48
MAX_ENTRIES = 50  # ← Почему 50?
MAX_DEPTH = 3     # ← Почему 3?
```

**Почему это плохо:**
- Непонятно происхождение чисел
- Трудно изменять (нужно искать по всему коду)
- Нет единого источника правды

**Как исправить:**
```python
# shared/constants.py
class Timeouts:
    PERMISSION_REQUEST = 300  # 5 минут
    QUESTION_RESPONSE = 300
    STREAM_LINE_READ = 60

class Limits:
    MAX_MESSAGE_LENGTH = 10000
    MAX_TOOL_RESULT_LENGTH = 500
    MAX_FILE_BROWSER_ENTRIES = 50
    MAX_FILE_BROWSER_DEPTH = 3

class Patterns:
    VARIABLE_NAME = r'^[A-Z][A-Z0-9_]*$'

# Использование:
await asyncio.wait_for(event.wait(), timeout=Timeouts.PERMISSION_REQUEST)
```

---

### 12. Дублирование кода (DRY violation)

**Файл:** `application/services/account_service.py:462-610`

**Проблема:**
```python
def get_env_for_mode(self, mode: AuthMode, local_config = None) -> dict:
    env = {}
    if mode == AuthMode.ZAI_API:
        # 15 строк кода
    elif mode == AuthMode.CLAUDE_ACCOUNT:
        # 30 строк кода
    elif mode == AuthMode.LOCAL_MODEL:
        # 15 строк кода
    return env

def apply_env_for_mode(self, mode, base_env = None, local_config = None):
    # 60 строк кода с ДУБЛИРОВАНИЕМ логики выше!
```

**Почему это плохо:**
- Логика дублируется
- При изменении нужно править в 2 местах
- Вероятность расхождения логики

**Как исправить:**
```python
def _build_env_config(self, mode: AuthMode, local_config = None) -> dict:
    """Единый источник правды для env конфигурации"""
    env = {}

    if mode == AuthMode.ZAI_API:
        env = self._zai_api_config()
    elif mode == AuthMode.CLAUDE_ACCOUNT:
        env = self._claude_account_config()
    elif mode == AuthMode.LOCAL_MODEL:
        env = self._local_model_config(local_config)

    return env

def get_env_for_mode(self, mode, local_config=None) -> dict:
    return self._build_env_config(mode, local_config)

def apply_env_for_mode(self, mode, base_env=None, local_config=None):
    env_updates = self._build_env_config(mode, local_config)
    return self._apply_env_updates(base_env or os.environ, env_updates)
```

---

## 🟡 КОД-СМЕЛЛЫ И ОПТИМИЗАЦИЯ (Priority: Low)

### 13. Отсутствие type hints во многих местах

**Файлы:** Различные

**Проблемы:**
```python
# settings.py:211
settings = Settings.from_env()  # ← Какой тип?

# main.py:80
self.bot: Bot = None  # ← Не может быть None если Bot!

# messages.py:70
self._user_sessions: dict[int, ClaudeCodeSession] = {}  # ← Хорошо!
# Но много мест без type hints
```

**Как исправить:**
```python
# Добавить type hints везде:
from typing import Final

settings: Final[Settings] = Settings.from_env()

self.bot: Optional[Bot] = None  # Или инициализировать сразу
```

---

### 14. Длинные методы (Complexity)

**Файл:** `infrastructure/claude_code/sdk_service.py:515-1018`

**Проблема:**
```python
async def run_task(self, ...) -> SDKTaskResult:
    # 500+ строк в одном методе!
    # Вложенность 5+ уровней
    # Множественные responsibility
```

**Как исправить:**
```python
async def run_task(self, ...) -> SDKTaskResult:
    await self._validate_working_dir(working_dir)
    await self._setup_state(user_id)

    result = await self._execute_with_sdk(user_id, prompt, ...)

    await self._cleanup_state(user_id)
    return result

async def _execute_with_sdk(self, ...) -> SDKTaskResult:
    # Разбить на подметоды
    options = self._build_sdk_options(...)
    async with ClaudeSDKClient(options=options) as client:
        return await self._process_client_response(client, ...)
```

---

### 15. Отсутствие логирования критичных операций

**Файлы:** Различные

**Проблемы:**
```python
# account_service.py:414-460
def save_credentials(self, credentials_json: str) -> tuple[bool, str]:
    # Критичная операция (сохранение токенов!)
    # Но нет ни одного logger.info()!

    with open(CREDENTIALS_PATH, "w") as f:
        json.dump(data, f, indent=2)  # ← Нет логирования!
```

**Как исправить:**
```python
def save_credentials(self, credentials_json: str) -> tuple[bool, str]:
    logger.info(f"Saving credentials to {CREDENTIALS_PATH}")

    try:
        data = json.loads(credentials_json)
        logger.debug(f"Credentials parsed: subscription={data.get('claudeAiOauth', {}).get('subscriptionType')}")

        with open(CREDENTIALS_PATH, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"✓ Credentials saved successfully")
        return True, "Credentials saved"

    except Exception as e:
        logger.error(f"✗ Failed to save credentials: {e}")
        return False, f"Error: {e}"
```

---

### 16. Неправильная обработка исключений

**Файл:** `application/services/account_service.py:143-145`

**Проблема:**
```python
except Exception as e:
    logger.error(f"Error reading credentials: {e}")
    return cls(exists=False)  # ← Проглатываем ВСЕ исключения!
```

**Почему это плохо:**
- `FileNotFoundError`, `PermissionError`, `JSONDecodeError` — всё игнорируется
- Невозможно diagnose проблему

**Как исправить:**
```python
except FileNotFoundError:
    logger.debug(f"Credentials file not found: {path}")
    return cls(exists=False)
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON in credentials file: {e}")
    raise CredentialsCorruptedError(f"Invalid JSON: {e}") from e
except PermissionError as e:
    logger.error(f"Permission denied reading credentials: {e}")
    raise
except Exception as e:
    logger.exception(f"Unexpected error reading credentials: {e}")
    raise
```

---

### 17. Отсутствие документации (docstrings)

**Файлы:** Множество

**Проблема:**
- Многие методы без docstrings
- Нет описания параметров
- Нет описания возвращаемых значений
- Нет примеров использования

**Как исправить:**
```python
def get_env_for_mode(
    self,
    mode: AuthMode,
    local_config: Optional[LocalModelConfig] = None
) -> dict[str, str]:
    """
    Build environment variables for the specified auth mode.

    Each mode requires different environment variables:
    - ZAI_API: ANTHROPIC_BASE_URL, ANTHROPIC_API_KEY, ANTHROPIC_MODEL
    - CLAUDE_ACCOUNT: HTTP_PROXY, NO_PROXY (removes API keys)
    - LOCAL_MODEL: ANTHROPIC_BASE_URL (custom), ANTHROPIC_API_KEY (dummy)

    Args:
        mode: Authorization mode to use
        local_config: Required for LOCAL_MODEL mode

    Returns:
        Dictionary of environment variables to set

    Raises:
        ValueError: If LOCAL_MODEL mode without local_config

    Example:
        >>> env = service.get_env_for_mode(AuthMode.ZAI_API)
        >>> "ANTHROPIC_BASE_URL" in env
        True
    """
```

---

### 18. Неконсистентное именование

**Файлы:** Различные

**Проблемы:**
```python
# Где-то user_id: int
async def get_or_create_user(self, user_id: int, ...)

# Где-то uid: UserId (но это тоже user_id!)
uid = UserId.from_int(user_id)

# Где-то переменные var_name, где-то name
def set_variable(self, name: str, ...):  # ← Не var_name!
def _handle_var_name_input(...):         # ← А здесь var_name!

# Методы то async то sync:
def is_task_running(self, user_id: int) -> bool:  # ← sync
async def get_task_status(self, user_id: int) -> TaskStatus:  # ← async
```

**Как исправить:**
```python
# Единый стиль:
- user_id везде для ID пользователя (int)
- user_vo для UserId VO
- var_name для названия переменной
- Все методы изменения состояния — async
```

---

## ✅ ВЕРДИКТ

### Общая оценка: **5.5 / 10**

**Положительные стороны:**
- ✅ Чистая слоистая архитектура (Domain, Application, Infrastructure, Presentation)
- ✅ Использование Value Objects (UserId, Role, ProjectPath)
- ✅ Async/await во всех I/O операциях
- ✅ Хорошая организация репозиториев
- ✅ Использование dataclasses для entities

**Отрицательные стороны:**
- ❌ **2 критические уязвимости безопасности** (hardcoded пароль и admin ID)
- ❌ **N+1 проблема** в репозиториях
- ❌ **God Objects** (MessageHandlers, CallbackHandlers)
- ❌ **Потенциальные утечки памяти**
- ❌ **Отсутствие миграций БД**
- ❌ **Нарушение DIP** (зависимость от Infrastructure)

---

### Главный совет разработчику:

> **"Твой код хорошо структурирован архитектурно, но имеет критические проблемы безопасности и утечки памяти. Срочно вынеси все секреты в environment variables, разбей God Objects на отдельные классы и добавь TTL-очистку для словарей. Начни с исправления hardcoded пароля — это бомба замедленного действия."**

---

### Приоритет действий:

1. **НЕМЕДЛЕННО:** Убрать hardcoded пароль и admin ID (безопасность)
2. **КРИТИЧНО:** Исправить N+1 в репозиториях
3. **ВАЖНО:** Разбить MessageHandlers и CallbackHandlers
4. **ВАЖНО:** Добавить TTL-очистку для словарей
5. **СРЕДНЕ:** Добавить миграции БД (alembic)
6. **СРЕДНЕ:** Исправить DIP violations
7. **НИЗКИЙ:** Улучшить документацию и type hints
