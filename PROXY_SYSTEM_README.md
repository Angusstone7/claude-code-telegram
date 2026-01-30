# Proxy Management System

## Обзор

Полная система управления прокси через меню Telegram бота с поддержкой HTTP, HTTPS, SOCKS5.

## Архитектура (DDD)

```
domain/
├── value_objects/proxy_config.py       # ProxyConfig value object
├── entities/proxy_settings.py          # ProxySettings entity
└── repositories/proxy_repository.py    # Repository interface

application/
└── services/proxy_service.py           # Business logic

infrastructure/
└── persistence/sqlite_proxy_repository.py  # SQLite implementation

presentation/
├── handlers/proxy_handlers.py          # Telegram UI handlers
└── keyboards/keyboards.py              # Proxy keyboards (добавлено)
```

## Использование через Telegram

### Настройка прокси

1. Откройте меню: `/start`
2. Зайдите в: **⚙️ Настройки** → **🌐 Прокси**
3. Нажмите: **➕ Настроить прокси**
4. Выберите тип: HTTP / HTTPS / SOCKS5
5. Введите: `host:port` (например: `148.253.208.124:3128`)
6. Выберите авторизацию:
   - 🔓 Без авторизации
   - 🔐 С логином/паролем
7. Если нужна авторизация, введите: `username:password`
8. Выберите область:
   - 👤 Только для меня (user-specific)
   - 🌍 Глобально (для всех пользователей)
9. Система автоматически протестирует прокси
10. Подтвердите сохранение

### Управление прокси

- **🧪 Тест**: Проверить подключение к httpbin.org
- **🔄 Изменить**: Изменить настройки
- **❌ Отключить**: Отключить прокси

## Приоритет настроек

1. **User-specific proxy** (если настроен)
2. **Global proxy** (fallback)
3. **No proxy** (если ничего не настроено)

## API (Programmatic Usage)

### ProxyService

```python
from application.services.proxy_service import ProxyService
from domain.value_objects.user_id import UserId

# Get effective proxy for user
proxy_config = await proxy_service.get_effective_proxy(UserId(user_id))

# Set global proxy from URL
await proxy_service.set_global_proxy("http://user:pass@host:port")

# Set user-specific proxy
await proxy_service.set_user_proxy(
    UserId(user_id),
    "socks5://host:port"
)

# Set custom proxy with parameters
from domain.value_objects.proxy_config import ProxyType

await proxy_service.set_custom_proxy(
    proxy_type=ProxyType.SOCKS5,
    host="148.253.208.124",
    port=1080,
    username="user",
    password="pass",
    user_id=None  # None = global
)

# Test proxy
success, message = await proxy_service.test_proxy(proxy_config)

# Get environment variables
env_dict = proxy_service.get_env_dict(proxy_config)
# Returns: {"HTTP_PROXY": "...", "HTTPS_PROXY": "...", "NO_PROXY": "..."}
```

### ProxyConfig Value Object

```python
from domain.value_objects.proxy_config import ProxyConfig, ProxyType

# Create from URL
proxy = ProxyConfig.from_url("http://user:pass@host:3128")

# Create manually
proxy = ProxyConfig(
    proxy_type=ProxyType.HTTP,
    host="148.253.208.124",
    port=3128,
    username="user",
    password="pass",
    enabled=True
)

# Convert to URL
url = proxy.to_url()  # "http://user:pass@host:3128"

# Masked for logging
masked = proxy.mask_credentials()  # "http://user:***@host:3128"

# For aiohttp/httpx
proxy_dict = proxy.to_dict()  # {"http": "...", "https": "..."}

# For environment variables
env_dict = proxy.to_env_dict()  # {"HTTP_PROXY": "...", ...}
```

## База данных

### Таблица proxy_settings

```sql
CREATE TABLE proxy_settings (
    id TEXT PRIMARY KEY,
    user_id INTEGER,              -- NULL = global settings
    proxy_type TEXT,              -- 'http', 'https', 'socks5'
    host TEXT,
    port INTEGER,
    username TEXT,
    password TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
```

## Безопасность

### ✅ Исправлено

- **УДАЛЕНО**: Hardcoded proxy credentials из `account_service.py`
- **БЫЛО**: `CLAUDE_PROXY = "http://proxyuser:!QAZ1qaz7@148.253.208.124:3128"`
- **СТАЛО**: Credentials хранятся в БД (SQLite), доступны только через ProxyService

### Хранение credentials

- Credentials хранятся в SQLite (`data/bot.db`)
- Доступ только через ProxyService
- Masked logging (`proxy.mask_credentials()`)
- NO_PROXY для локальных адресов

## Интеграция с AccountService

`AccountService` теперь использует `ProxyService` для получения настроек прокси:

```python
# В application/services/account_service.py

if self.proxy_service:
    proxy_config = await self.proxy_service.get_effective_proxy(UserId(user_id))
    if proxy_config and proxy_config.enabled:
        proxy_env = self.proxy_service.get_env_dict(proxy_config)
        env.update(proxy_env)
```

## NO_PROXY Configuration

Локальные адреса автоматически bypass прокси:

```python
NO_PROXY_VALUE = "localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,host.docker.internal,.local"
```

## Тестирование

### Автоматический тест при настройке

Система автоматически тестирует прокси при сохранении:
- URL: `https://httpbin.org/ip`
- Timeout: 10 секунд
- Показывает IP адрес прокси

### Ручной тест

В меню прокси: **🧪 Тест** → тест подключения

## State Management

Промежуточное состояние во время настройки хранится в:

```python
proxy_setup_state: Dict[int, Dict] = {}
```

Ключи:
- `type`: Тип прокси (http/https/socks5)
- `host`: Хост
- `port`: Порт
- `username`: Логин (опционально)
- `password`: Пароль (опционально)

## Поддерживаемые типы прокси

1. **HTTP** - стандартный HTTP proxy
2. **HTTPS** - HTTPS proxy
3. **SOCKS5** - SOCKS5 proxy (для повышенной анонимности)

## Миграция из старого кода

### Было (hardcoded):
```python
CLAUDE_PROXY = "http://proxyuser:!QAZ1qaz7@148.253.208.124:3128"
env["HTTP_PROXY"] = CLAUDE_PROXY
```

### Стало (через ProxyService):
```python
proxy_config = await proxy_service.get_effective_proxy(user_id)
if proxy_config:
    env.update(proxy_service.get_env_dict(proxy_config))
```

## Deployment

После деплоя GitLab CI/CD:

1. Бот автоматически создаст таблицу `proxy_settings` при первом запуске
2. Настройте прокси через меню Telegram
3. Старые hardcoded credentials больше не используются

## Troubleshooting

### Прокси не работает

1. Проверьте настройки: Меню → Настройки → Прокси
2. Запустите тест: **🧪 Тест**
3. Проверьте логи: `curl "http://192.168.0.116:9999/logs/claude_agent?tail=100"`
4. Проверьте доступность прокси-сервера

### База данных

```bash
# Проверить настройки прокси в БД
docker exec -it claude_agent sqlite3 /app/data/bot.db "SELECT * FROM proxy_settings;"
```

## Дон Дон Удон

Система успешно реализована! 🎉

**Выполнено:**
- ✅ Domain layer (ProxyConfig, ProxySettings, ProxyRepository)
- ✅ Infrastructure layer (SQLiteProxyRepository)
- ✅ Application layer (ProxyService)
- ✅ Presentation layer (ProxyHandlers, keyboards)
- ✅ Integration (DI Container, main.py)
- ✅ Security fix (удалены hardcoded credentials)
- ✅ Testing (автоматический и ручной тест)
- ✅ Documentation

**Коммит:** `3cbe608` - "feat: implement proxy management system via Telegram bot menu"
