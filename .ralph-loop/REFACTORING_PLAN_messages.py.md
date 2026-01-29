# План рефакторинга God Object: messages.py (1615 строк)

## Текущая проблема
MessageHandlers - это God Object с 1615 строками, который смешивает 10+ обязанностей.

## Целевая архитектура

Разбить на **6 специализированных классов**:

### 1. TextMessageHandler (~300 строк)
**Ответственность:** Обработка обычных текстовых сообщений
**Методы:**
- handle_text_message()
- _process_text_input()
- _detect_cd_command()
- _format_response()

### 2. FileMessageHandler (~200 строк)
**Ответственность:** Обработка файлов (документы, фото)
**Методы:**
- handle_document()
- handle_photo()
- _save_file()
- _generate_file_context()

### 3. HITLHandler (~150 строк)
**Ответственность:** Human-in-the-Loop (permissions, questions)
**Методы:**
- handle_permission_request()
- handle_question_request()
- respond_to_permission()
- respond_to_question()
- set_expecting_answer()
- set_expecting_path()

### 4. VariableInputHandler (~200 строк)
**Ответственность:** Variable input (3-шаговый процесс)
**Методы:**
- start_var_input()
- start_var_edit()
- handle_var_name()
- handle_var_value()
- handle_var_desc()
- cancel_var_input()
- is_expecting_var_input()

### 5. PlanApprovalHandler (~100 строк)
**Ответственность:** Plan approval workflow
**Методы:**
- handle_plan_approval()
- set_expecting_plan_clarification()
- handle_plan_clarification()

### 6. MessageCoordinator (~150 строк)
**Ответственность:** Координация между всеми обработчиками
**Методы:**
- route_message()
- _determine_handler()
- _is_task_running()
- cleanup()

## Shared State

Вынести общее состояние в `MessageHandlerState`:

```python
@dataclass
class MessageHandlerState:
    user_state_manager: UserStateManager
    hitl_manager: HITLManager
    file_context_manager: FileContextManager
    variable_manager: VariableManager
    plan_manager: PlanManager
    streaming_handler: Optional[StreamingHandler]
```

## План миграции (поэтапный)

### Этап 1: Создать новые классы (не breaking changes)
1. Создать `presentation/handlers/message/` директорию
2. Создать базовый класс `BaseMessageHandler`
3. Создать 6 специализированных классов
4. Протестировать каждый класс отдельно

### Этап 2: Добавить фасад для backward compatibility
1. Создать `MessageHandlersFacade` который делегирует к новым классам
2. Старый `MessageHandlers` наследует от `MessageHandlersFacade`
3. Все методы работают через делегирование

### Этап 3: Миграция кода
1. Обновить imports в коде
2. Заменить `MessageHandlers` на `MessageCoordinator`
3. Убрать deprecated классы

### Этап 4: Cleanup
1. Удалить старый messages.py
2. Обновить тесты

## Риски
- **High:** Breaking changes для существующего кода
- **Medium:** Race conditions при работе с shared state
- **Low:** Потеря функциональности

## Mitigation
- Использовать фасад для backward compatibility
- Добавить интеграционные тесты
- Делать миграцию поэтапно (не всё сразу)

## Оценка времени
- Этап 1: 3-4 часа (создание классов)
- Этап 2: 1-2 часа (фасад)
- Этап 3: 2-3 часа (миграция)
- Этап 4: 1 час (cleanup)

**Итого:** 7-10 часов работы

## Следующие шаги
1. ✅ Создать этот план
2. ⏳ Создать директорию `presentation/handlers/message/`
3. ⏳ Создать `BaseMessageHandler`
4. ⏳ Создать `TextMessageHandler`
5. ... остальные классы

---
**Создано:** Ralph Loop Iteration 1
**Статус:** PLAN CREATED - READY FOR IMPLEMENTATION
