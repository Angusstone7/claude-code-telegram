# Ralph Loop - Iteration 6: Refactoring Fixes

**Дата:** 2026-01-29
**Итерация:** 6 из 10
**Статус:** В ПРОЦЕССЕ

---

## 🎯 Цель итерации

**Задача:** Исправить все проблемы в рефакторенном коде, которые привели к откату на legacy версию.

**Проблемы от пользователя:**
- Часть кнопок не работает
- Форматирование и стриминг инфы в Telegram изуродовано
- Рефакторенный код не работает корректно

---

## 🔍 Найденные критические проблемы

### ❌ ПРОБЛЕМА #1: StepStreamingHandler полностью отсутствует

**Где:** `presentation/handlers/message/ai_request_handler.py`

**Что сломано:**
- В legacy коде `StepStreamingHandler` используется в 6+ местах
- В рефакторенном коде полностью отсутствует
- Это влияет на отображение стриминга в step mode

**Legacy код (работает):**
```python
def _get_step_handler(self, user_id: int) -> Optional["StepStreamingHandler"]:
    streaming = self._state.get_streaming_handler(user_id)
    if not streaming:
        return None
    if user_id not in self._step_handlers:
        from presentation.handlers.streaming import StepStreamingHandler
        self._step_handlers[user_id] = StepStreamingHandler(streaming)
    return self._step_handlers[user_id]

async def _on_tool_use(self, user_id: int, tool_name: str, tool_input: dict, message: Message):
    # Step streaming mode: show brief tool notifications
    if self.is_step_streaming_mode(user_id):
        step_handler = self._get_step_handler(user_id)
        if step_handler:
            await step_handler.on_tool_start(tool_name, tool_input)
```

**Рефакторенный код (сломан):**
- Метод `_get_step_handler()` - НЕ СУЩЕСТВУЕТ
- Вызовы `step_handler.on_tool_start()` - НЕ СУЩЕСТВУЮТ
- Вызовы `step_handler.on_thinking()` - НЕ СУЩЕСТВУЮТ
- Вызовы `step_handler.on_permission_request()` - НЕ СУЩЕСТВУЮТ

**Исправление (✅ ПРИМЕНЕНО):**
1. Добавлен импорт `StepStreamingHandler`
2. Добавлен метод `_get_step_handler(user_id)`
3. Добавлен метод `_cleanup_step_handler(user_id)`
4. Добавлен метод `is_step_streaming_mode(user_id)`
5. Обновлен `_on_tool_use()` - добавлен вызов `step_handler.on_tool_start()`
6. Обновлен `_on_tool_result()` - добавлен вызов `step_handler.on_tool_complete()`
7. Обновлен `_on_thinking()` - добавлен вызов `step_handler.on_thinking()`
8. Обновлен `_on_permission_sdk()` - добавлен вызов `step_handler.on_permission_request()`
9. Обновлен `_on_permission_completed()` - добавлен вызов `step_handler.on_permission_granted()`
10. Добавлен cleanup в `_cleanup_after_task()`

---

### ❌ ПРОБЛЕМА #2: callback_handlers не связан с MessageHandlers

**Где:**
- `presentation/handlers/message/facade.py`
- `presentation/handlers/message/coordinator.py`
- `shared/container.py`

**Что сломано:**
- MessageHandlers должен иметь ссылку на callback_handlers для обработки gvar input
- В legacy есть bidirectional link: `msg_handlers.callback_handlers = callback_handlers`
- В рефакторенном коде эта связь НЕ установлена

**Legacy код (работает):**
```python
# В messages.py
self.callback_handlers = None  # Will be set by container

async def handle_text(self, message: Message):
    # Check for global variable input (handled by CallbackHandlers)
    if hasattr(self, 'callback_handlers') and self.callback_handlers:
        if self.callback_handlers.is_gvar_input_active(user_id):
            handled = await self.callback_handlers.process_gvar_input(...)
```

```python
# В container.py
def callback_handlers(self):
    if "callback_handlers" not in self._cache:
        msg_handlers = self.message_handlers()
        # ...
        # Establish bidirectional link for gvar input handling
        msg_handlers.callback_handlers = self._cache["callback_handlers"]
    return self._cache["callback_handlers"]
```

**Рефакторенный код (сломан):**
- `facade.py` - НЕТ атрибута `callback_handlers`
- `coordinator.py` - принимает `callback_handlers` НО не передает в facade
- `text_handler.py` - ожидает `callback_handlers` НО не получает его через facade

**Исправление (✅ ЧАСТИЧНО ПРИМЕНЕНО):**
1. В `facade.py` добавлен атрибут:
   ```python
   self.callback_handlers = None  # Will be set by container
   ```
2. В `text_handler.py` логика УЖЕ ЕСТЬ (проверяет callback_handlers)
3. В `coordinator.py` УЖЕ принимает callback_handlers и передает в text_handler

**TODO:**
- Обновить `container.py` чтобы использовать рефакторенную версию
- Установить bidirectional link как в legacy

---

### ⚠️  ПРОБЛЕМА #3: Методы могут отсутствовать в facade

**Где:** `presentation/handlers/message/facade.py`

**Потенциальная проблема:**
- Legacy MessageHandlers имеет ~40+ методов
- Facade должен делегировать ВСЕ методы в coordinator
- Нужно проверить что все методы присутствуют

**Проверить:**
- `save_variable_skip_desc()`
- `set_continue_session()`
- `clear_session_cache()`
- `get_pending_question_option()`
- `start_var_input()` / `start_var_edit()` / `cancel_var_input()`
- И другие...

**Статус:** НЕ ПРОВЕРЕНО

---

## 📊 Статус исправлений

### Исправлено ✅

1. **StepStreamingHandler полностью восстановлен**
   - Импорт добавлен
   - Методы _get_step_handler и _cleanup_step_handler добавлены
   - Интеграция во всех callbacks восстановлена
   - Cleanup добавлен

2. **callback_handlers частично восстановлен**
   - Атрибут в facade добавлен
   - Логика в text_handler уже была

### В процессе ⏳

3. **Проверка всех методов facade**
   - Нужно сравнить legacy и facade построчно
   - Убедиться что все методы делегируются

### Не начато ❌

4. **Обновление container.py для использования рефакторенной версии**
5. **Тестирование всех исправлений**
6. **Проверка работы кнопок**
7. **Проверка форматирования стриминга**

---

## 📝 План дальнейших действий

### Immediate (Iteration 6):

1. ✅ Исправить StepStreamingHandler
2. ✅ Добавить callback_handlers в facade
3. ⏳ Проверить все методы facade vs legacy
4. Обновить container.py для использования рефакторенной версии
5. Протестировать

### Next iterations (7-10):

6. Исправить остальные найденные проблемы
7. Проверить работу всех кнопок
8. Проверить форматирование стриминга
9. Интеграционные тесты
10. Финальная проверка и отчет

---

## 🔧 Технические детали

### Файлы изменены в Iteration 6:

1. `presentation/handlers/message/ai_request_handler.py`
   - +1 импорт (StepStreamingHandler)
   - +3 метода (_get_step_handler, _cleanup_step_handler, is_step_streaming_mode)
   - +1 атрибут (_step_handlers)
   - Модифицировано 6 методов (_on_tool_use, _on_tool_result, _on_thinking, _on_permission_sdk, _on_permission_completed, _cleanup_after_task)

2. `presentation/handlers/message/facade.py`
   - +1 атрибут (callback_handlers)
   - +3 строки комментария

### Сравнение size:

**Legacy messages.py:**
- 1615 строк
- 40+ методов
- ~80 cyclomatic complexity

**Рефакторенный (после исправлений):**
- ai_request_handler.py: ~620 строк (+30 от исправлений)
- facade.py: ~230 строк (+3 от исправлений)
- coordinator.py: ~220 строк
- text_handler.py: ~250 строк
- file_handler.py: ~280 строк
- И другие...

---

**Следующая задача:** Проверить ВСЕ методы legacy vs facade построчно

**Время итерации 6:** ~30 минут
**Прогресс:** 40% (2 из 5 задач)
