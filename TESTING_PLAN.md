# План тестирования Ubuntu Claude Bot

## Цель
Комплексное тестирование Telegram-бота с интеграцией Claude Code SDK через Ralph Loop (10 итераций).

---

## Итерация 1: Базовая инфраструктура и запуск

### Задачи:
1. **Unit-тесты для domain слоя**
   - `domain/entities/` - все сущности (Project, ProjectContext, ClaudeCodeSession)
   - `domain/value_objects/` - UserId, ProjectId и др.
   - `domain/services/` - ProjectMatcher

2. **Проверить:**
   - Создание и валидация сущностей
   - Корректность value objects
   - Паттерн-матчинг для проектов

### Файлы для тестов:
```
tests/unit/domain/
├── test_entities.py
├── test_value_objects.py
└── test_project_matcher.py
```

---

## Итерация 2: Репозитории и persistence

### Задачи:
1. **Integration-тесты для репозиториев**
   - `ProjectContextRepository` - SQLite операции
   - `SettingsRepository` - настройки пользователей
   - Проверка миграций БД

2. **Тестовые сценарии:**
   - CRUD операций для проектов
   - CRUD для контекстов
   - Глобальные переменные (SET/GET/DELETE)
   - Конкурентный доступ к БД

### Файлы:
```
tests/integration/
├── test_project_context_repository.py
├── test_settings_repository.py
└── conftest.py (fixtures для БД)
```

---

## Итерация 3: Application Services

### Задачи:
1. **Unit-тесты сервисов с моками**
   - `ContextService` - работа с контекстами и переменными
   - `ProjectService` - управление проектами
   - `FileProcessorService` - обработка файлов

2. **Ключевые тесты:**
   - `get_enriched_prompt()` с глобальными переменными ✅ (баг исправлен)
   - `get_merged_variables()` - слияние глобальных и контекстных
   - Автоопределение проекта по пути

### Файлы:
```
tests/unit/application/
├── test_context_service.py
├── test_project_service.py
└── test_file_processor_service.py
```

---

## Итерация 4: Claude Code SDK Service

### Задачи:
1. **Integration-тесты SDK сервиса**
   - `SdkService.run_task()` - основной flow
   - Permission handling (HITL)
   - Question handling
   - Task cancellation

2. **Mock-тесты:**
   - Эмуляция ответов Claude SDK
   - Тестирование callbacks (on_text, on_tool_use, on_tool_result)
   - Race conditions с `_task_lock` ✅ (баг исправлен)

3. **Сценарии:**
   - Успешное выполнение задачи
   - Отмена задачи пользователем
   - Timeout и retry логика
   - Восстановление сессии (resume)

### Файлы:
```
tests/integration/claude_code/
├── test_sdk_service.py
├── test_permission_flow.py
├── test_session_resume.py
└── mocks/
    └── mock_claude_sdk.py
```

---

## Итерация 5: Streaming Handler

### Задачи:
1. **Unit-тесты StreamingHandler**
   - `StableHTMLFormatter` - конвертация markdown → HTML
   - Rate limiting и debounce
   - Overflow handling (длинные сообщения)

2. **Тестовые кейсы:**
   - Markdown с незакрытыми блоками кода
   - Очень длинный текст (>4000 символов)
   - Rate limit recovery ✅ (баг исправлен)
   - Fallback для "нестабильного" HTML ✅ (баг исправлен)

3. **HeartbeatTracker тесты:**
   - Анимация спиннера
   - Смена action при tool use

### Файлы:
```
tests/unit/presentation/
├── test_streaming_handler.py
├── test_stable_html_formatter.py
├── test_heartbeat_tracker.py
└── test_file_change_tracker.py
```

---

## Итерация 6: Telegram Handlers

### Задачи:
1. **Integration-тесты handlers**
   - `MessageHandlers` - обработка текста, файлов, голоса
   - `CallbackHandlers` - inline кнопки
   - `MenuHandlers` - меню настроек

2. **Mock Telegram Bot:**
   - Эмуляция aiogram Bot и Message
   - Тестирование reply_markup
   - Проверка parse_mode (HTML vs plain)

3. **Сценарии:**
   - Отправка текстового сообщения → Claude
   - Отправка файла с caption
   - Голосовое сообщение → транскрипция → Claude
   - Отмена задачи через кнопку

### Файлы:
```
tests/integration/presentation/
├── test_message_handlers.py
├── test_callback_handlers.py
├── test_menu_handlers.py
└── fixtures/
    ├── mock_bot.py
    └── mock_messages.py
```

---

## Итерация 7: Plugins System

### Задачи:
1. **Тесты загрузки плагинов**
   - Парсинг plugin.json
   - Валидация манифестов
   - Hooks injection

2. **Тесты каждого плагина:**
   - `commit-commands` - git commit, push, PR
   - `code-review` - review PR
   - `feature-dev` - feature development flow
   - `frontend-design` - UI generation
   - `ralph-loop` - итеративная разработка

### Файлы:
```
tests/integration/plugins/
├── test_plugin_loader.py
├── test_commit_commands.py
├── test_code_review.py
├── test_feature_dev.py
└── test_ralph_loop.py
```

---

## Итерация 8: End-to-End тесты

### Задачи:
1. **E2E сценарии (с реальным Claude API в sandbox)**
   - Полный цикл: сообщение → Claude → ответ в TG
   - Файловые операции (Read/Write/Edit)
   - Bash команды с permission flow

2. **Тестовые проекты:**
   - Создать тестовый проект в `/tmp/test_project`
   - Выполнить типичные задачи
   - Проверить file change tracking

3. **Мониторинг:**
   - Проверка логов через Docker API
   - Время ответа
   - Потребление памяти

### Файлы:
```
tests/e2e/
├── test_full_flow.py
├── test_file_operations.py
├── test_bash_permissions.py
└── test_project/
    └── sample_code.py
```

---

## Итерация 9: Стресс-тестирование и edge cases

### Задачи:
1. **Нагрузочные тесты:**
   - Множественные параллельные запросы от одного пользователя
   - Множественные пользователи одновременно
   - Длинные сессии (>100 сообщений)

2. **Edge cases:**
   - Пустые сообщения
   - Очень длинные сообщения (>100KB)
   - Невалидный markdown
   - Битые файлы
   - Отключение сети во время запроса

3. **Recovery тесты:**
   - Restart контейнера во время задачи
   - Потеря сессии
   - Database corruption recovery

### Файлы:
```
tests/stress/
├── test_concurrent_users.py
├── test_long_sessions.py
├── test_edge_cases.py
└── test_recovery.py
```

---

## Итерация 10: CI/CD и финальная интеграция

### Задачи:
1. **CI Pipeline:**
   - GitHub Actions / GitLab CI конфигурация
   - Автоматический запуск тестов на PR
   - Coverage отчёты

2. **Docker тесты:**
   - Build контейнера
   - Health checks
   - Graceful shutdown

3. **Документация:**
   - README с инструкциями по тестированию
   - Badges для coverage
   - Примеры запуска тестов

### Файлы:
```
.github/workflows/
├── test.yml
└── coverage.yml

docker/
└── test.Dockerfile

docs/
└── TESTING.md
```

---

## Структура тестов (итоговая)

```
tests/
├── conftest.py              # Общие fixtures
├── pytest.ini               # Конфигурация pytest
│
├── unit/                    # Быстрые изолированные тесты
│   ├── domain/
│   ├── application/
│   └── presentation/
│
├── integration/             # Тесты с реальными зависимостями
│   ├── persistence/
│   ├── claude_code/
│   └── presentation/
│
├── e2e/                     # End-to-end тесты
│   └── test_full_flow.py
│
├── stress/                  # Нагрузочные тесты
│   └── test_concurrent.py
│
└── fixtures/                # Общие тестовые данные
    ├── sample_files/
    └── mock_responses/
```

---

## Команды запуска

```bash
# Все тесты
pytest tests/ -v

# Только unit тесты (быстро)
pytest tests/unit/ -v

# Integration тесты
pytest tests/integration/ -v --docker

# E2E тесты (требуют API ключ)
ANTHROPIC_API_KEY=xxx pytest tests/e2e/ -v

# С coverage
pytest tests/ --cov=. --cov-report=html

# Конкретная итерация (по маркерам)
pytest tests/ -m "iteration1" -v
```

---

## Метрики успеха

| Метрика | Цель |
|---------|------|
| Unit test coverage | >80% |
| Integration test coverage | >60% |
| E2E сценариев | 10+ |
| Время unit тестов | <30 сек |
| Время full suite | <10 мин |
| Flaky tests | 0 |

---

## Приоритеты (по критичности багов)

1. **Критично** - SDK Service, Permission flow, Streaming
2. **Высоко** - Context/Variables, Session resume
3. **Средне** - Plugins, Menu handlers
4. **Низко** - UI polish, edge cases
