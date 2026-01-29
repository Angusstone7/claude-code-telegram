# Code Review Report

**Проект:** ubuntu_claude
**Дата:** 2026-01-29
**Анализируемые директории:** application/, domain/, infrastructure/, presentation/, shared/

---

## 1. God Objects (Файлы >500 строк, классы с >10 методами)

### presentation/handlers/callbacks.py
- **Строки:** 2608
- **Критичность:** RED
- **Описание:** Класс `CallbackHandlers` содержит **80+ методов** обработки callback-запросов. Это крайне сложный для поддержки God Object, объединяющий логику: Docker, проектов, контекстов, переменных, плагинов, HITL, планов.
- **Рекомендация:** Разделить на специализированные хендлеры:
  - `DockerCallbackHandlers` (docker_*, metrics_*)
  - `ProjectCallbackHandlers` (project_*, cd_*)
  - `ContextCallbackHandlers` (context_*, vars_*, gvar_*)
  - `ClaudeCallbackHandlers` (claude_*, plan_*)
  - `PluginCallbackHandlers` (plugin_*)

### presentation/handlers/streaming.py
- **Строки:** 1871
- **Критичность:** RED
- **Описание:** Содержит 6 классов разной ответственности: `StreamingHandler`, `StableHTMLFormatter`, `ProgressTracker`, `HeartbeatTracker`, `FileChangeTracker`, `StepStreamingHandler`. Смешаны UI-форматирование, rate limiting, отслеживание файлов.
- **Рекомендация:** Вынести в отдельные модули:
  - `streaming_ui/formatter.py` - HTML форматирование
  - `streaming_ui/tracker.py` - FileChangeTracker, ProgressTracker
  - `streaming_ui/heartbeat.py` - HeartbeatTracker

### presentation/keyboards/keyboards.py
- **Строки:** 1628
- **Критичность:** YELLOW
- **Описание:** Класс `Keyboards` - фабрика клавиатур с 60+ статических методов. Хотя это фабрика, размер усложняет навигацию.
- **Рекомендация:** Сгруппировать по доменам в подмодули:
  - `keyboards/menu.py`
  - `keyboards/docker.py`
  - `keyboards/claude.py`
  - `keyboards/account.py`

### presentation/handlers/messages.py
- **Строки:** 1621
- **Критичность:** YELLOW
- **Описание:** Класс `MessageHandlers` управляет обработкой сообщений с 40+ методами. Содержит бизнес-логику, state management, UI взаимодействие.
- **Рекомендация:** Продолжить рефакторинг с делегированием в state managers (уже частично сделано с `HITLManager`, `VariableInputManager`).

### infrastructure/claude_code/sdk_service.py
- **Строки:** 1353
- **Критичность:** YELLOW
- **Описание:** `ClaudeAgentSDKService` - центральный сервис взаимодействия с Claude SDK. Много состояния и callback-логики.
- **Рекомендация:** Вынести HITL state management в отдельный класс `SDKHITLManager`.

### presentation/handlers/account_handlers.py
- **Строки:** 1307
- **Критичность:** YELLOW
- **Описание:** Содержит `AccountHandlers` + `OAuthLoginSession`. OAuth логика занимает ~200 строк.
- **Рекомендация:** Вынести `OAuthLoginSession` в отдельный модуль `infrastructure/auth/oauth_session.py`.

### presentation/handlers/menu_handlers.py
- **Строки:** 1167
- **Критичность:** YELLOW
- **Описание:** Обработка системы меню. Много switch-case логики через callback.data.
- **Рекомендация:** Использовать паттерн Command или словарь callback -> handler.

### application/services/account_service.py
- **Строки:** 635
- **Критичность:** YELLOW
- **Описание:** Управление аккаунтами, auth modes, credentials - много ответственностей.
- **Рекомендация:** Разделить на `AuthModeService` и `CredentialsService`.

### infrastructure/persistence/sqlite_repository.py
- **Строки:** 549
- **Критичность:** GREEN
- **Описание:** Базовый репозиторий SQLite - приемлемый размер для persistence layer.

---

## 2. Legacy код (файлы _old, deprecated)

### presentation/handlers/messages_old.py
- **Строки:** 1603
- **Критичность:** RED
- **Описание:** Полная копия старого `MessageHandlers` с устаревшей архитектурой (15+ отдельных словарей для состояния вместо state managers).
- **Рекомендация:** УДАЛИТЬ файл. Новая версия в `messages.py` использует `UserStateManager`, `HITLManager` и другие менеджеры.

---

## 3. TODO/FIXME (Технический долг)

Поиск по кодовой базе не выявил явных TODO/FIXME комментариев. Это либо хорошо (код чистый), либо технический долг скрыт в реализации.

**Скрытый технический долг обнаружен:**

### presentation/handlers/streaming.py:380
- **Критичность:** GREEN
- **Описание:** `IncrementalFormatter = StableHTMLFormatter` - alias для обратной совместимости.
- **Рекомендация:** Убрать alias после проверки всех использований.

### presentation/handlers/streaming.py:937-942
- **Критичность:**GREEN
- **Описание:** `_schedule_update()` помечен как Deprecated, но не удалён.
- **Рекомендация:** Удалить deprecated метод.

---

## 4. Дублирование кода

### Docker операции (handle_docker_*)
- **Файл:** callbacks.py:181-334
- **Критичность:** YELLOW
- **Описание:** Методы `handle_docker_stop`, `handle_docker_start`, `handle_docker_restart` имеют идентичную структуру: parse callback -> get monitor -> execute -> answer.
- **Рекомендация:** Создать обобщённый метод `_docker_action(action: str, callback)`.

### Паттерн проверки user_id в callbacks
- **Файлы:** callbacks.py (множественные места)
- **Критичность:** YELLOW
- **Описание:** Повторяется код:
  ```python
  if user_id != callback.from_user.id:
      await callback.answer("...")
      return
  ```
- **Рекомендация:** Создать декоратор `@require_same_user`.

### Паттерн truncate text > 3500
- **Файл:** callbacks.py:659, 689, 719
- **Критичность:** GREEN
- **Описание:** Повторяется:
  ```python
  if len(original_text) > 3500:
      original_text = original_text[:3500] + "\n... (truncated)"
  ```
- **Рекомендация:** Вынести в утилиту `truncate_for_telegram(text, limit=3500)`.

### Global variables vs Context variables handlers
- **Файл:** callbacks.py:1569-1798 и 1804-2007
- **Критичность:** YELLOW
- **Описание:** Методы `handle_vars_*` и `handle_gvar_*` почти идентичны, отличаются только source (context vs global).
- **Рекомендация:** Создать общий `VariableHandlerMixin` с параметризацией.

### messages.py vs messages_old.py
- **Критичность:** RED
- **Описание:** Файл messages_old.py - полная копия с устаревшей архитектурой.
- **Рекомендация:** Удалить messages_old.py.

---

## 5. Magic Numbers

### shared/constants.py (хорошо вынесены)
```python
HITL_PERMISSION_TIMEOUT_SECONDS = 300  # 5 minutes
HITL_QUESTION_TIMEOUT_SECONDS = 300    # 5 minutes
HITL_PLAN_APPROVAL_TIMEOUT_SECONDS = 600  # 10 minutes
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
STREAMING_MESSAGE_CHAR_LIMIT = 4096
CLAUDE_DEFAULT_MAX_TURNS = 50
```
- **Критичность:** GREEN
- **Описание:** Константы правильно вынесены в shared/constants.py.

### Невынесенные magic numbers:

#### callbacks.py:69-70
```python
display_output = display_output[:1000] + "..." + display_output[-500:]
```
- **Критичность:** YELLOW
- **Рекомендация:** Вынести OUTPUT_HEAD_LIMIT, OUTPUT_TAIL_LIMIT.

#### callbacks.py:244
```python
lines_per_page = 30
```
- **Критичность:** YELLOW
- **Рекомендация:** Вынести DOCKER_LOGS_PAGE_SIZE.

#### callbacks.py:252
```python
total_lines = 200  # Max lines to fetch
```
- **Критичность:** YELLOW
- **Рекомендация:** Вынести DOCKER_LOGS_MAX_LINES.

#### streaming.py:399-413
```python
MAX_MESSAGE_LENGTH = 4000  # Leave buffer from 4096
DEBOUNCE_INTERVAL = 2.0
LARGE_TEXT_BYTES = 2500
VERY_LARGE_TEXT_BYTES = 3500
MAX_RATE_LIMIT_RETRIES = 3
CHARS_PER_TOKEN = 4
DEFAULT_CONTEXT_LIMIT = 200_000
```
- **Критичность:** GREEN
- **Описание:** Константы определены как class attributes - приемлемо.

#### account_handlers.py:104
```python
timeout_seconds = 30
```
- **Критичность:** YELLOW
- **Рекомендация:** Вынести OAUTH_URL_TIMEOUT_SECONDS.

---

## 6. Длинные методы (>50 строк)

### callbacks.py::handle_docker_logs
- **Строки:** 235-316 (81 строка)
- **Критичность:** YELLOW
- **Описание:** Сложная логика пагинации логов Docker.
- **Рекомендация:** Разбить на: `_parse_logs_offset()`, `_paginate_logs()`, `_format_logs_message()`.

### streaming.py::_markdown_to_html_impl
- **Строки:** 59-196 (137 строк)
- **Критичность:** YELLOW
- **Описание:** Комплексная конвертация Markdown -> HTML с обработкой edge cases.
- **Рекомендация:** Разбить на этапы: `_protect_code_blocks()`, `_protect_inline_code()`, `_convert_formatting()`.

### streaming.py::_handle_overflow
- **Строки:** 1096-1184 (88 строк)
- **Критичность:** YELLOW
- **Описание:** Логика разбиения сообщения при переполнении.
- **Рекомендация:** Вынести вычисление split point в отдельный метод.

### messages.py::handle_document
- **Строки:** 331-423 (92 строки)
- **Критичность:** YELLOW
- **Описание:** Обработка документов с множеством веток.
- **Рекомендация:** Разбить на `_process_document_with_caption()` и `_cache_document_for_reply()`.

### messages.py::handle_photo
- **Строки:** 425-562 (137 строк)
- **Критичность:** YELLOW
- **Описание:** Очень похож на handle_document - дублирование.
- **Рекомендация:** Создать общий метод `_handle_file_message(message, file_type)`.

### account_handlers.py::handle_account_callback
- **Строки:** 362-785 (423 строки!)
- **Критичность:** RED
- **Описание:** Гигантский switch-case через if-elif для разных action.
- **Рекомендация:** Использовать словарь action -> handler или отдельные методы.

### sdk_service.py::execute_task
- **Строки:** (>100 строк, требует детального анализа)
- **Критичность:** YELLOW
- **Описание:** Основной метод выполнения задач с множеством callback-ов.
- **Рекомендация:** Вынести callback handlers в отдельные методы.

---

## Сводная таблица

| Категория | RED | YELLOW | GREEN |
|-----------|-----|--------|-------|
| God Objects | 2 | 6 | 1 |
| Legacy | 1 | 0 | 0 |
| TODO/FIXME | 0 | 0 | 2 |
| Дублирование | 1 | 4 | 1 |
| Magic Numbers | 0 | 4 | 2 |
| Длинные методы | 1 | 6 | 0 |
| **ИТОГО** | **5** | **20** | **6** |

---

## Приоритетные действия

1. **CRITICAL:** Удалить `messages_old.py` - устаревший legacy код
2. **HIGH:** Разделить `CallbackHandlers` (2608 строк) на 5+ специализированных классов
3. **HIGH:** Рефакторинг `handle_account_callback` (423 строки switch-case)
4. **MEDIUM:** Вынести OAuth логику из account_handlers.py
5. **MEDIUM:** Унифицировать handle_document/handle_photo
6. **MEDIUM:** Создать общий VariableHandlerMixin для vars/gvar
7. **LOW:** Вынести оставшиеся magic numbers в constants.py

---

## Архитектурные наблюдения

### Положительные стороны:
- Чистая доменная модель (domain/)
- Хорошее разделение слоёв (DDD структура)
- Константы вынесены в shared/constants.py
- State managers введены для уменьшения связности (HITLManager, VariableInputManager)
- MessageUpdateCoordinator для rate limiting

### Области для улучшения:
- Presentation layer перегружен бизнес-логикой
- Callback handlers нуждаются в декомпозиции
- Отсутствует dependency injection container
- Тесты не покрывают presentation layer

---

*Отчёт сгенерирован автоматически. Для детального анализа конкретных проблем используйте IDE.*
