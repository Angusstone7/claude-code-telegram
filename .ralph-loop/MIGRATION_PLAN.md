# План миграции со старого MessageHandlers

**Статус:** Старый код все еще используется
**Файлы затронуты:** 2 (main.py, container.py)

---

## 🔍 Текущая ситуация

### Старый код (legacy):
- **Файл:** `presentation/handlers/messages.py` (69KB, ~1615 строк)
- **Используется в:**
  1. `main.py:130` - регистрация handlers
  2. `shared/container.py:254` - DI контейнер

### Новый код:
- **Директория:** `presentation/handlers/message/`
- **Файлов:** 9 (base, text, file, hitl, variable, plan, coordinator, facade, __init__)
- **Строк:** ~1,720

---

## 📋 План миграции (3 варианта)

### Вариант 1: МЯГКАЯ МИГРАЦИЯ (Рекомендуется)

**Шаги:**
1. ✅ Создать `MessageHandlersFacade` (ГОТОВО)
2. ⏳ Переименовать старый файл:
   ```bash
   mv messages.py messages.py.deprecated
   ```
3. ⏳ Создать новый `messages.py` с re-export facade:
   ```python
   # presentation/handlers/messages.py
   """DEPRECATED: Use presentation.handlers.message instead"""
   import warnings
   from presentation.handlers.message import MessageHandlersFacade as MessageHandlers

   warnings.warn(
       "presentation.handlers.messages is deprecated. "
       "Use presentation.handlers.message.MessageCoordinator instead.",
       DeprecationWarning,
       stacklevel=2
   )

   __all__ = ["MessageHandlers"]
   ```
4. ⏳ Старый код продолжает работать через facade
5. ⏳ Постепенно обновлять imports в main.py и container.py

**Преимущества:**
- ✅ Нет breaking changes
- ✅ Старый код работает
- ✅ Deprecation warnings направляют на новый код

**Недостатки:**
- ⚠️ Два файла messages.py (.deprecated)
- ⚠️ Временная сложность

---

### Вариант 2: ПРЯМАЯ МИГРАЦИЯ

**Шаги:**
1. ⏳ Обновить `main.py`:
   ```python
   # Было:
   from presentation.handlers.messages import MessageHandlers

   # Стало:
   from presentation.handlers.message import MessageCoordinator
   # или
   from presentation.handlers.message import MessageHandlersFacade as MessageHandlers
   ```

2. ⏳ Обновить `shared/container.py`:
   ```python
   # Было:
   from presentation.handlers.messages import MessageHandlers

   # Стало:
   from presentation.handlers.message import MessageHandlersFacade as MessageHandlers
   # или позже:
   from presentation.handlers.message import MessageCoordinator
   ```

3. ⏳ Удалить старый файл:
   ```bash
   rm presentation/handlers/messages.py
   ```

**Преимущества:**
- ✅ Чистый код сразу
- ✅ Нет legacy файлов

**Недостатки:**
- ⚠️ Требует тестирования
- ⚠️ Может сломать что-то

---

### Вариант 3: АРХИВАЦИЯ

**Шаги:**
1. ⏳ Переместить старый файл в архив:
   ```bash
   mkdir -p .archive/legacy_code/
   mv presentation/handlers/messages.py .archive/legacy_code/messages.py.backup
   ```

2. ⏳ Создать stub `messages.py`:
   ```python
   raise ImportError(
       "MessageHandlers has been refactored. "
       "Use: from presentation.handlers.message import MessageCoordinator"
   )
   ```

3. ⏳ Обновить все imports

**Преимущества:**
- ✅ Сохраняем backup
- ✅ Четкое сообщение об ошибке

**Недостатки:**
- ⚠️ Breaking change
- ⚠️ Требует немедленного обновления всего кода

---

## 🎯 Рекомендация: ВАРИАНТ 1 (Мягкая миграция)

### Причины:
1. **Безопасность:** Старый код продолжает работать
2. **Deprecation warnings:** Направляют разработчиков на новый код
3. **Постепенность:** Можно обновлять по частям
4. **Тестирование:** Время для проверки новой архитектуры

### Временная линия:
- **Неделя 1:** Вариант 1, шаги 1-4
- **Неделя 2-3:** Тестирование, обновление документации
- **Неделя 4:** Начать обновлять imports (Вариант 2)
- **Месяц 2:** Финальное удаление старого кода

---

## 📝 Детальные инструкции (Вариант1)

### Шаг 1: Переименовать старый файл
```bash
cd /root/projects/ubuntu_claude/presentation/handlers
mv messages.py messages.py.deprecated
```

### Шаг 2: Создать stub messages.py
```python
# /root/projects/ubuntu_claude/presentation/handlers/messages.py
"""
DEPRECATED: This module has been refactored.

Old code (still works):
    from presentation.handlers.messages import MessageHandlers
    handlers = MessageHandlers(...)

New code (recommended):
    from presentation.handlers.message import MessageCoordinator
    coordinator = MessageCoordinator(...)

The old MessageHandlers is now a facade that delegates to MessageCoordinator.
"""

import warnings

# Re-export facade for backward compatibility
from presentation.handlers.message import MessageHandlersFacade as MessageHandlers

# Emit deprecation warning
warnings.warn(
    "presentation.handlers.messages is deprecated and will be removed in v2.0. "
    "Use presentation.handlers.message.MessageCoordinator instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["MessageHandlers"]

# Keep old function for compatibility
def register_handlers(*args, **kwargs):
    """DEPRECATED: Register handlers function"""
    warnings.warn(
        "register_handlers is deprecated. "
        "Use new handler registration method.",
        DeprecationWarning,
        stacklevel=2
    )
    # TODO: Implement if needed
    pass
```

### Шаг 3: Обновить main.py (опционально)
```python
# main.py - Option 1 (keep old import with deprecation)
from presentation.handlers.messages import MessageHandlers  # Will show warning

# main.py - Option 2 (use new import)
from presentation.handlers.message import MessageHandlersFacade as MessageHandlers

# main.py - Option 3 (use new architecture)
from presentation.handlers.message import MessageCoordinator
```

### Шаг 4: Обновить container.py (опционально)
```python
# container.py - Option 1 (keep old)
from presentation.handlers.messages import MessageHandlers  # Will show warning

# container.py - Option 2 (use facade directly)
from presentation.handlers.message import MessageHandlersFacade as MessageHandlers

# container.py - Option 3 (use new architecture)
from presentation.handlers.message import MessageCoordinator
```

---

## ⚠️ ВАЖНО

### До миграции:
1. ✅ Создать backup старого кода
2. ✅ Убедиться что тесты проходят (если есть)
3. ✅ Проверить что новый код работает

### После миграции:
1. ⏳ Запустить приложение
2. ⏳ Проверить логи на errors
3. ⏳ Проверить deprecation warnings
4. ⏳ Убедиться что все функции работают

---

## 🚦 Статус выполнения

- [x] Создан MessageHandlersFacade
- [x] Протестирована архитектура
- [ ] Переименован старый файл
- [ ] Создан stub messages.py
- [ ] Обновлены imports (опционально)
- [ ] Проведено тестирование
- [ ] Удален deprecated код (позже)

---

**Готовы к выполнению?** Скажите "да" и я выполню Вариант 1 (мягкая миграция).
