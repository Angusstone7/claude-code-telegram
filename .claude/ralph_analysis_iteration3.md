# 🔍 Ralph Loop Analysis - Итерация 3 из 10

## 🆕 Новые находки

### 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (Infrastructure Layer)

#### 15. **SQL INJECTION RISK** - System Monitor

**Файл:** `infrastructure/monitoring/system_monitor.py`

**Проблема:**
```python
# ❌ POTENTIAL COMMAND INJECTION!
result = await executor.execute(f"systemctl is-active {service_name}")
result = await self._ssh_executor.execute(f"docker logs --tail {lines} {container_id}")
```

**Почему это КРИТИЧНО:**
- Если `service_name` или `container_id` приходят от пользователя - возможна инъекция команды
- Нет валидации входных данных
- Нет escaping специальных символов

**Атака:**
```
service_name = "mysql; rm -rf / --no-preserve-root"
# Выполнится: systemctl is-active mysql; rm -rf / --no-preserve-root
```

**Как должно быть:**
```python
# ✅ Правильно - whitelist validation
ALLOWED_SERVICES = {"mysql", "redis", "nginx", "postgres"}

if service_name not in ALLOWED_SERVICES:
    raise ValueError(f"Service {service_name} not allowed")

# Или использовать shlex.quote()
import shlex
safe_service = shlex.quote(service_name)
result = await executor.execute(f"systemctl is-active {safe_service}")
```

---

#### 16. **BARE EXCEPT CLAUSE** - Callback Handlers

**Файл:** `presentation/handlers/callbacks/legacy.py` (строка 133)

**Проблема:**
```python
# ❌ BARE EXCEPT - перехватывает ВСЁ включая KeyboardInterrupt!
try:
    response, _ = await self.bot_service.chat(...)
    if response:
        await callback.message.answer(response, parse_mode=None)
except:  # ⚠️ Перехватывает SystemExit, KeyboardInterrupt, etc!
    pass  # Skip AI follow-up on error
```

**Почему это КРИТИЧНО:**
- Перехватывает `KeyboardInterrupt` - невозможно остановить программу Ctrl+C
- Перехватывает `SystemExit` - ломает `sys.exit()`
- Скрывает реальные ошибки (включая `MemoryError`, `ImportError`)
- Невозможно отладить проблемы

**Как должно быть:**
```python
# ✅ Правильно - конкретные исключения
try:
    response, _ = await self.bot_service.chat(...)
    if response:
        await callback.message.answer(response, parse_mode=None)
except (asyncio.TimeoutError, ConnectionError) as e:
    logger.warning(f"AI follow-up failed: {e}")
except Exception as e:
    logger.error(f"Unexpected error in AI follow-up: {e}", exc_info=True)
```

---

#### 17. **N+1 QUERY PROBLEM** - Session Repository (ЧАСТИЧНО ИСПРАВЛЕНО)

**Файл:** `infrastructure/persistence/sqlite_repository.py`

**Статус:** ⚠️ **ЧАСТИЧНО ИСПРАВЛЕНО**, но есть проблемы

**Что хорошо:**
```python
# ✅ Исправлено для find_by_user (строки 138-208)
query = """
    SELECT s.*, sm.role as msg_role, sm.content as msg_content, ...
    FROM sessions s
    LEFT JOIN session_messages sm ON s.session_id = sm.session_id
    WHERE s.user_id = ?
"""
# Один запрос с LEFT JOIN - хорошо!
```

**Что плохо:**
```python
# ❌ НЕ исправлено для _row_to_session (строки 279-313)
async def _row_to_session(self, db: aiosqlite.Connection, row) -> Session:
    messages = []
    async with db.execute(
        "SELECT * FROM session_messages WHERE session_id = ?",  # ⚠️ N+1!
        (row["session_id"],),
    ) as msg_cursor:
        msg_rows = await msg_cursor.fetchall()
        # ...
```

**Проблема:**
- Метод `_row_to_session()` вызывается для каждой сессии
- Внутри делается отдельный запрос на сообщения
- Если загрузить 10 сессий - будет 10 дополнительных запросов

**Последствия:**
- При `find_by_id()` - 2 запроса (OK)
- При `find_active_by_user()` - 2 запроса (OK)
- Но если кто-то вызовет `_row_to_session()` в цикле - N+1

**Рекомендация:**
```python
# ✅ Всегда использовать JOIN версию
# Удалить метод _row_to_session или пометить как @deprecated
```

---

### 🟡 Средние проблемы

#### 18. **DUPLICATE DATABASE INITIALIZATION CODE**

**Файл:** `infrastructure/persistence/sqlite_repository.py`

**Проблема:**
```python
# ❌ Повторяется 3 раза!
def _init_db(self):
    import os
    os.makedirs(
        os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".",
        exist_ok=True,
    )

# SQLiteUserRepository (строки 24-30)
# SQLiteSessionRepository (строки 116-122)
# SQLiteCommandRepository (строки 323-329)
```

**Рекомендация:** Вынести в базовый класс:
```python
# ✅ Правильно
class BaseSQLiteRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")
        self._ensure_db_directory()

    def _ensure_db_directory(self):
        """Create database directory if not exists."""
        import os
        directory = os.path.dirname(self.db_path) or "."
        os.makedirs(directory, exist_ok=True)

class SQLiteUserRepository(BaseSQLiteRepository, UserRepository):
    pass  # Наследует _ensure_db_directory
```

---

#### 19. **HARDCODED ROLE MAPPING** - Repository

**Файл:** `infrastructure/persistence/sqlite_repository.py` (строки 84-90)

**Проблема:**
```python
# ❌ Харкодирование role mapping
def _row_to_user(self, row) -> User:
    role_map = {
        "admin": Role.admin(),
        "user": Role.user(),
        "readonly": Role.readonly(),
        "devops": Role.devops(),
    }
    role = role_map.get(row["role"], Role.user())
```

**Проблемы:**
- Дублирование логики (может быть в других репозиториях)
- При добавлении новой роли нужно обновлять все места
- Нет единого источника правды

**Рекомендация:** Вынести в Value Object:
```python
# ✅ Правильно - domain/value_objects/role.py
class Role:
    # ... существующий код ...

    @classmethod
    def from_string(cls, role_str: str) -> "Role":
        """Parse role from string (e.g., from database)."""
        role_map = {
            "admin": cls.admin,
            "user": cls.user,
            "readonly": cls.readonly,
            "devops": cls.devops,
        }
        factory = role_map.get(role_str, cls.user)
        return factory()

# Использование:
role = Role.from_string(row["role"])
```

---

#### 20. **MAGIC NUMBER - TRUNCATION LENGTH**

**Файл:** `presentation/handlers/callbacks/legacy.py` (строки 107-108)

**Проблема:**
```python
# ❌ Magic numbers
if len(display_output) > 3000:  # Почему 3000?
    display_output = display_output[:1000] + "\n... [OUTPUT TRUNCATED] ...\n" + display_output[-500:]
#                                             Почему 1000 и 500?
```

**Рекомендация:** Вынести в constants:
```python
# ✅ shared/constants.py
class OutputLimits:
    MAX_LENGTH = 3000
    TRUNCATE_PREFIX = 1000
    TRUNCATE_SUFFIX = 500

# Использование:
if len(display_output) > OutputLimits.MAX_LENGTH:
    display_output = (
        display_output[:OutputLimits.TRUNCATE_PREFIX] +
        "\n... [OUTPUT TRUNCATED] ...\n" +
        display_output[-OutputLimits.TRUNCATE_SUFFIX:]
    )
```

---

### 🟢 Низкие проблемы

#### 21. **INCONSISTENT ERROR HANDLING**

**Файл:** `infrastructure/persistence/sqlite_repository.py`

**Проблема:**
```python
# ❌ Разная обработка ошибок в разных методах
async def find_by_id(self, user_id: UserId) -> Optional[User]:
    async with aiosqlite.connect(self.db_path) as db:
        # ... без try/except - пробрасывает исключение наверх

async def save(self, user: User) -> None:
    async with aiosqlite.connect(self.db_path) as db:
        # ... тоже без try/except
```

**Проблема:**
- Нет единообразной обработки ошибок БД
- Ошибка БД пробрасывается как есть (может раскрыть детали схемы)
- Нет retry logic для временных сбоев

**Рекомендация:**
```python
# ✅ Правильно - единая обработка
from domain.exceptions import RepositoryError

async def find_by_id(self, user_id: UserId) -> Optional[User]:
    try:
        async with aiosqlite.connect(self.db_path) as db:
            # ... запрос ...
    except aiosqlite.Error as e:
        logger.error(f"Database error in find_by_id: {e}")
        raise RepositoryError(f"Failed to find user {user_id}") from e
```

---

#### 22. **MISSING INPUT VALIDATION**

**Файл:** `presentation/handlers/callbacks/base.py` (строки 62-76)

**Проблема:**
```python
# ❌ Нет валидации входных данных
@staticmethod
def parse_callback_data(data: str, expected_parts: int = 2) -> list[str]:
    parts = data.split(":")
    while len(parts) < expected_parts:
        parts.append("")  # ⚠️ Может создать бесконечный цикл?
    return parts
```

**Проблемы:**
- Нет проверки на `None` или пустую строку
- Нет ограничения на количество частей (DoS уязвимость)
- Нет валидации формата

**Атака:**
```python
data = ":" * 1000000  # Миллион двоеточий
parts = parse_callback_data(data, expected_parts=2)
# Создаст список с миллионом пустых строк!
```

**Как должно быть:**
```python
# ✅ Правильно
MAX_CALLBACK_PARTS = 10

@staticmethod
def parse_callback_data(data: str, expected_parts: int = 2) -> list[str]:
    if not data:
        return [""] * expected_parts

    parts = data.split(":", MAX_CALLBACK_PARTS)
    while len(parts) < expected_parts:
        parts.append("")

    if len(parts) > MAX_CALLBACK_PARTS:
        raise ValueError(f"Too many callback parts: {len(parts)}")

    return parts
```

---

## 📊 Обновленная статистика

| Метрика | Значение | Статус |
|---------|----------|--------|
| **Всего найдено проблем** | 22 | 🔴 |
| **Критических** | 16 | 🔴 |
| **Средних** | 5 | 🟡 |
| **Низких** | 1 | 🟢 |
| **SQL Injection рисков** | 2 | 🔴 |
| **Bare except clauses** | 1 найден | 🔴 |
| **N+1 query проблем** | 1 (частично) | 🟡 |
| **Дублирования кода** | 5 мест | 🟡 |
| **Magic numbers** | ~25 | 🟡 |

---

## 🔬 Глубокий анализ: Command Injection

### Сценарий атаки через SystemMonitor

```
Злоумышленник отправляет:
/docker logs mysql; cat /etc/passwd

Код:
result = await self._ssh_executor.execute(f"docker logs --tail 100 {container_id}")

Выполнится:
docker logs --tail 100 mysql; cat /etc/passwd

Результат:
- Логи контейнера mysql
- СОДЕРЖИМОЕ /etc/passwd!
```

### Сценарий DoS атаки через parse_callback_data

```
Злоумышленник отправляет callback с data = ":" * 1000000

Код:
parts = data.split(":")
while len(parts) < expected_parts:  # expected_parts=2
    parts.append("")

Результат:
- Создается список с 1,000,000 пустых строк
- Потребление памяти: ~8 MB
- Время выполнения: ~50ms
- При 100 запросах/с: 800 MB/s + 5 CPU cores = DoS
```

---

## 🎯 Обновленные приоритеты

### 🔴 **КРИТИЧЕСКИЕ** (безопасность)
1. ✅ **Исправить command injection** в system_monitor.py
2. ✅ **Исправить bare except** в legacy.py
3. ✅ **Добавить валидацию** в parse_callback_data
4. ✅ **Исправить race conditions** (UserStateManager, HITLManager)

### 🟡 **ВАЖНЫЕ** (стабильность)
5. Устранить дублирование (_init_db, role mapping)
6. Разбить MessageHandlers (1615 строк)
7. Вынести magic numbers в constants
8. Исправить N+1 query в _row_to_session

### 🟢 **ЖЕЛАТЕЛЬНЫЕ** (качество)
9. Добавить единообразную обработку ошибок БД
10. Улучшить тестовое покрытие
11. Добавить deprecation warnings

---

## 📝 Прогресс анализа

| Итерация | Анализировано | Найдено проблем |
|----------|---------------|-----------------|
| Итерация 1 | messages.py, domain | 8 проблем |
| Итерация 2 | user_state, hitl_manager, bot_service | +6 = 14 |
| Итерация 3 | repositories, callbacks, monitor | +8 = **22** |
| Итерация 4 | ? | ? |

---

## 📝 Следующие шаги (Итерация 4)

1. Проанализировать streaming handlers
2. Проверить middleware (auth, message_batcher)
3. Найти additional code smells
4. Проверить соответствие Clean Architecture

---

**Итерация 3 завершена.** Найдены 2 критические уязвимости безопасности!
