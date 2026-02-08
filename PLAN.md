# P0 — Критические доработки (Неделя 1)

## Обзор

5 задач из аудита Ralph Loop, приоритет P0. Каждая задача — отдельный коммит.

---

## Задача 1: Добавить `aiofiles`, заменить blocking I/O в hot-path

**Проблема:** 24 блокирующих вызова (`open()`, `os.makedirs()`, `os.path.exists()`) внутри `async def` функций блокируют event loop.

**Что делаем:**
1. Добавить `aiofiles>=24.1.0` в `requirements.txt`
2. Заменить blocking I/O **только в HIGH-severity файлах** (горячий путь):

| Файл | Что заменить | На что |
|------|-------------|--------|
| `application/services/file_processor_service.py` | `open()`, `os.makedirs()` | `aiofiles.open()`, `await asyncio.to_thread(os.makedirs, ...)` |
| `application/services/account_service.py` | `open()`, `os.path.exists()`, `os.makedirs()`, `os.remove()` | `aiofiles.open()`, `await asyncio.to_thread(os.path.exists, ...)` |
| `presentation/handlers/messages.py` (_on_plan_request) | `open()`, `os.path.exists()`, `os.listdir()`, `os.path.isdir()` | `aiofiles.open()`, `asyncio.to_thread()` обёртки |
| `presentation/handlers/message/ai_request_handler.py` | То же что messages.py (дубликат) | То же |
| `presentation/handlers/commands.py` | `os.path.exists()`, `os.makedirs()` | `asyncio.to_thread()` обёртки |

**Не трогаем (LOW/MEDIUM):** `main.py` (startup), `sqlite_repository.py` (init), `diagnostics.py` (admin only)

**Паттерн замены:**
```python
# Было:
if os.path.exists(path):
    with open(path, 'r') as f:
        data = f.read()

# Стало:
if await asyncio.to_thread(os.path.exists, path):
    async with aiofiles.open(path, 'r') as f:
        data = await f.read()
```

---

## Задача 2: Исправить `subprocess.run` → `asyncio.create_subprocess_exec`

**Проблема:** `subprocess.run()` в `diagnostics.py` блокирует event loop.

**Что делаем:**
- `infrastructure/claude_code/diagnostics.py` строки 65, 79:
```python
# Было:
result = subprocess.run(["which", claude_path], capture_output=True, text=True, timeout=5)

# Стало:
proc = await asyncio.create_subprocess_exec(
    "which", claude_path,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
```

**Трудозатраты:** 15-30 мин

---

## Задача 3: JSON structured logging

**Проблема:** Plain text формат `%(asctime)s | %(name)s | %(levelname)s | %(message)s`. 553 logger вызовов. Невозможно парсить в Grafana/Loki.

**Что делаем:**

1. Добавить `python-json-logger>=2.0.0` в `requirements.txt`

2. Создать `shared/logging/config.py`:
```python
"""Centralized JSON logging configuration"""
import logging
import sys
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = record.created
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        # Remove redundant fields
        log_record.pop('levelname', None)
        log_record.pop('name', None)

def setup_logging(level: str = "INFO"):
    """Configure JSON structured logging"""
    formatter = CustomJsonFormatter(
        fmt='%(timestamp)s %(level)s %(logger)s %(message)s'
    )

    # Console handler (JSON)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    # File handler (JSON, with rotation)
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        "logs/bot.log", maxBytes=50*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)

    # Root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, level))
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)
```

3. Обновить `main.py` строки 42-50:
```python
# Было:
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(...)

# Стало:
Path("logs").mkdir(exist_ok=True)
from shared.logging.config import setup_logging
setup_logging(os.getenv("LOG_LEVEL", "INFO"))
```

4. Обновить `shared/logging/__init__.py` — реэкспорт `setup_logging`

**Не трогаем:** 553 вызова logger.info/error/etc — они совместимы с JSON formatter as-is. Постепенно можно переводить на `extra={}`.

---

## Задача 4: Prometheus metrics endpoint

**Проблема:** `METRICS_PORT=9090` определён, `SystemMonitor` собирает метрики, но не экспортирует. Нет `/metrics` endpoint.

**Что делаем:**

1. Добавить `prometheus-client>=0.21.0` в `requirements.txt`

2. Создать `infrastructure/monitoring/prometheus_exporter.py`:
```python
"""Prometheus metrics exporter running alongside Telegram bot"""
from prometheus_client import Gauge, Counter, Info, start_http_server
import asyncio

# Gauges
cpu_usage = Gauge('bot_cpu_usage_percent', 'CPU usage percentage')
memory_usage = Gauge('bot_memory_usage_percent', 'Memory usage percentage')
memory_used_gb = Gauge('bot_memory_used_gb', 'Memory used in GB')
disk_usage = Gauge('bot_disk_usage_percent', 'Disk usage percentage')
load_avg_1m = Gauge('bot_load_average_1m', '1-minute load average')

# Counters
messages_total = Counter('bot_messages_total', 'Total messages processed', ['type'])
claude_requests_total = Counter('bot_claude_requests_total', 'Total Claude API requests')
claude_errors_total = Counter('bot_claude_errors_total', 'Claude API errors')

# Info
bot_info = Info('bot', 'Bot information')

async def update_system_metrics(monitor):
    """Periodic task to update system metrics from SystemMonitor"""
    while True:
        try:
            metrics = await monitor.get_metrics()
            cpu_usage.set(metrics.cpu_percent)
            memory_usage.set(metrics.memory_percent)
            memory_used_gb.set(metrics.memory_used_gb)
            disk_usage.set(metrics.disk_percent)
            load_avg_1m.set(metrics.load_avg_1)
        except Exception:
            pass
        await asyncio.sleep(15)

def start_metrics_server(port: int = 9090):
    """Start Prometheus HTTP metrics server (non-blocking, runs in background thread)"""
    start_http_server(port)
```

3. Обновить `main.py` — запустить metrics server перед polling:
```python
# В Application.start(), перед start_polling:
if settings.monitoring.enabled:
    from infrastructure.monitoring.prometheus_exporter import (
        start_metrics_server, update_system_metrics, bot_info
    )
    start_metrics_server(settings.monitoring.metrics_port)
    bot_info.info({'username': info.username, 'id': str(info.id)})
    # Запустить фоновую задачу обновления метрик
    monitor = self.container.system_monitor()
    asyncio.create_task(update_system_metrics(monitor))
```

4. Обновить `Dockerfile` — добавить `EXPOSE 9090`

5. Обновить `docker-compose.prod.yml` — добавить порт:
```yaml
ports:
  - "${METRICS_PORT:-9090}:9090"
```

6. Инструментировать ключевые точки:
   - `sdk_service.py` → `claude_requests_total.inc()` при запуске задачи
   - `messages.py` → `messages_total.labels(type='text').inc()` при получении сообщения

**Преимущество prometheus_client:** `start_http_server()` запускает HTTP в фоновом потоке — не нужен aiohttp/FastAPI, не конфликтует с polling.

---

## Задача 5: Извлечь DRY утилиты

**Проблема:** ~500 строк дублированного кода между `messages.py` и `ai_request_handler.py`.

**Что делаем — создать 3 утилитных модуля:**

### 5a. `shared/utils/bash_utils.py` (экономия ~74 строки)
```python
def detect_cd_command(command: str, current_dir: str) -> Optional[str]:
    """Detect if bash command changes directory, return new path."""
```
- Извлечь из `messages.py:291-327` и `ai_request_handler.py:89-125`
- Оба файла вызывают новую функцию

### 5b. `shared/utils/plan_utils.py` (экономия ~124 строки)
```python
async def read_plan_content(
    plan_file: str, tool_input: dict, working_dir: str, user_id: int
) -> str:
    """Read plan content with fallback chain: tool_input → file → latest .claude/plans/"""
```
- Извлечь из `messages.py:1237-1296` и `ai_request_handler.py:489-548`
- Использовать `aiofiles` (задача 1) вместо sync I/O

### 5c. `shared/utils/message_formatters.py` (экономия ~56 строк)
```python
def format_permission_request(tool_name: str, details: str, max_len: int = 500) -> str:
    """Format permission request HTML for Telegram."""
```
- Извлечь из 4 мест в `messages.py` и `ai_request_handler.py`

**Структура:**
```
shared/utils/
├── __init__.py          (реэкспорт)
├── bash_utils.py        (detect_cd_command)
├── plan_utils.py        (read_plan_content)
└── message_formatters.py (format_permission_request)
```

---

## Порядок выполнения

1. **Задача 1** (aiofiles) → фундамент для остальных
2. **Задача 5** (DRY utils) → зависит от aiofiles для plan_utils
3. **Задача 2** (subprocess) → маленький, независимый
4. **Задача 3** (JSON logging) → независимый
5. **Задача 4** (Prometheus) → независимый, делается последним

**Общие трудозатраты:** ~12-16 часов агентского времени

## Зависимости (requirements.txt)

Добавить:
```
aiofiles>=24.1.0
python-json-logger>=2.0.0
prometheus-client>=0.21.0
```
