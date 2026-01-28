# План тестирования Streaming механизма в Telegram

## Обзор

Механизм стриминга отвечает за:
- Отображение ответов Claude в реальном времени
- Конвертацию Markdown → Telegram HTML
- Rate limiting (защита от Telegram API limits)
- Отображение статуса выполнения (спиннер, действия)
- Todo/Plan отображение
- Step streaming mode (пошаговое отображение)

---

## 1. Unit тесты (без сети)

### 1.1 Markdown → HTML конвертация

**Файл:** `tests/unit/presentation/test_markdown_to_html.py`

```python
# Тестовые кейсы:

def test_bold_conversion():
    """**bold** → <b>bold</b>"""

def test_italic_conversion():
    """*italic* → <i>italic</i>"""

def test_code_inline():
    """`code` → <code>code</code>"""

def test_code_block():
    """```python\ncode\n``` → <pre>code</pre>"""

def test_unclosed_code_block():
    """```python\ncode (streaming) → <pre>code</pre> (auto-close)"""

def test_unclosed_blockquote():
    """<blockquote>text (streaming) → <blockquote>text</blockquote> (auto-close)"""

def test_nested_formatting():
    """**bold *italic* bold** → корректный HTML"""

def test_html_escape():
    """<script> → &lt;script&gt;"""

def test_preserve_existing_html():
    """Не ломать уже существующий HTML"""

def test_placeholder_protection():
    """Placeholder-ы не должны появляться в финальном тексте"""
```

### 1.2 Placeholder система

**Файл:** `tests/unit/presentation/test_placeholders.py`

```python
def test_placeholder_uniqueness():
    """Каждый placeholder уникален (Unicode PUA)"""

def test_placeholder_survives_json():
    """Placeholder не теряется при JSON serialization"""

def test_placeholder_restoration():
    """Все placeholder-ы заменяются обратно на оригинал"""

def test_no_placeholder_in_output():
    """В финальном HTML нет placeholder-ов"""

def test_many_placeholders():
    """1000+ placeholder-ов работают корректно"""
```

### 1.3 Rate Limiting

**Файл:** `tests/unit/presentation/test_rate_limiting.py`

```python
def test_debounce_interval():
    """Обновления не чаще DEBOUNCE_INTERVAL"""

def test_min_update_interval():
    """Между edit_text не меньше MIN_UPDATE_INTERVAL"""

def test_immediate_update():
    """immediate_update() ждёт rate limit вместо skip"""

def test_adaptive_interval():
    """Большие сообщения → больший интервал"""

def test_retry_after_handling():
    """TelegramRetryAfter → wait and retry"""
```

### 1.4 Message Management

**Файл:** `tests/unit/presentation/test_message_management.py`

```python
def test_message_split_on_overflow():
    """>4000 символов → новое сообщение"""

def test_message_index_increment():
    """Новое сообщение получает Part N"""

def test_finalize_clears_status():
    """finalize() убирает статус-бар"""

def test_buffer_management():
    """Buffer корректно накапливает текст"""
```

---

## 2. Integration тесты (с мок Telegram)

### 2.1 StreamingHandler Integration

**Файл:** `tests/integration/presentation/test_streaming_handler.py`

```python
@pytest.fixture
def mock_bot():
    """Мок aiogram Bot с отслеживанием вызовов"""

def test_start_sends_initial_message(mock_bot):
    """start() отправляет начальное сообщение"""

def test_append_updates_message(mock_bot):
    """append() вызывает edit_text"""

def test_status_line_always_visible(mock_bot):
    """Статус-бар виден в конце сообщения"""

def test_spinner_animation(mock_bot):
    """Спиннер меняется каждый тик"""

def test_action_changes_on_tool(mock_bot):
    """При tool_use меняется action (reading, writing, etc.)"""
```

### 2.2 Todo/Plan Display

**Файл:** `tests/integration/presentation/test_todo_display.py`

```python
def test_todo_creates_separate_message(mock_bot):
    """show_todo_list() создаёт отдельное сообщение"""

def test_todo_updates_in_place(mock_bot):
    """Повторный show_todo_list() редактирует существующее"""

def test_todo_skip_unchanged(mock_bot):
    """Если HTML не изменился - не вызывать API"""

def test_todo_status_icons(mock_bot):
    """✅ completed, ⏳ in_progress, ⬜ pending"""

def test_todo_progress_counter(mock_bot):
    """Прогресс: 3/5"""

def test_plan_mode_enter(mock_bot):
    """show_plan_mode_enter() показывает индикатор"""

def test_plan_mode_exit(mock_bot):
    """show_plan_mode_exit() обновляет статус"""
```

### 2.3 Step Streaming Mode

**Файл:** `tests/integration/presentation/test_step_streaming.py`

```python
def test_step_mode_shows_tool_inline(mock_bot):
    """Инструменты показываются inline, не отдельными сообщениями"""

def test_step_mode_brief_output(mock_bot):
    """Вывод инструментов кратко, не полностью"""

def test_step_handler_wraps_streaming(mock_bot):
    """StepStreamingHandler оборачивает базовый"""
```

### 2.4 Error Handling

**Файл:** `tests/integration/presentation/test_streaming_errors.py`

```python
def test_message_not_modified_ignored(mock_bot):
    """'message is not modified' не ломает flow"""

def test_retry_after_waits_and_retries(mock_bot):
    """TelegramRetryAfter → sleep → retry"""

def test_bad_request_logged(mock_bot):
    """TelegramBadRequest логируется но не ломает"""

def test_network_error_recovery(mock_bot):
    """Сетевая ошибка → retry"""
```

---

## 3. E2E тесты (реальный Telegram API)

**Требования:**
- Тестовый Telegram бот
- Тестовый чат/канал
- `TEST_BOT_TOKEN` и `TEST_CHAT_ID` в env

### 3.1 Real Streaming

**Файл:** `tests/e2e/test_streaming_e2e.py`

```python
@pytest.mark.e2e
async def test_real_message_stream():
    """Реальная отправка и редактирование сообщения"""

@pytest.mark.e2e
async def test_real_long_message_split():
    """Реальное разбиение длинного сообщения"""

@pytest.mark.e2e
async def test_real_rate_limit_handling():
    """Реальное поведение при rate limit"""

@pytest.mark.e2e
async def test_real_todo_display():
    """Реальное отображение todo list"""
```

---

## 4. Manual тесты (checklist)

### 4.1 Базовый стриминг

- [ ] Отправить простое сообщение → текст появляется плавно
- [ ] Отправить длинный запрос → сообщение разбивается на части
- [ ] Статус-бар виден внизу и обновляется
- [ ] Спиннер крутится
- [ ] После завершения статус-бар убирается

### 4.2 Форматирование

- [ ] **bold** отображается жирным
- [ ] *italic* отображается курсивом
- [ ] `code` отображается моноширинным
- [ ] ```code block``` отображается в блоке
- [ ] Во время стриминга незакрытые блоки не ломают HTML
- [ ] Blockquote отображается корректно
- [ ] Нет "мусора" типа BLOCK17, PH21 в тексте

### 4.3 Tool use отображение

- [ ] При Read показывается "📖 Читаю файл..."
- [ ] При Write показывается "✏️ Записываю файл..."
- [ ] При Bash показывается "⚡ Выполняю команду..."
- [ ] При Grep/Glob показывается "🔍 Ищу..."
- [ ] После инструмента показывается результат (кратко)

### 4.4 Todo/Plan

- [ ] TodoWrite создаёт отдельное сообщение с планом
- [ ] План обновляется при смене статуса задач
- [ ] ✅ для completed, ⏳ для in_progress, ⬜ для pending
- [ ] Прогресс "3/5" обновляется
- [ ] Plan mode показывает "Режим планирования"

### 4.5 Step Streaming Mode

- [ ] `/step on` включает режим
- [ ] Операции показываются inline
- [ ] Вывод краткий, не засоряет чат
- [ ] Todo/Plan работают и в этом режиме

### 4.6 Error scenarios

- [ ] Очень быстрые апдейты не ломают бота
- [ ] Отмена во время стриминга работает
- [ ] Сетевой сбой не крашит бота
- [ ] После ошибки можно продолжить работу

---

## 5. Stress тесты

**Файл:** `tests/stress/test_streaming_stress.py`

```python
@pytest.mark.stress
async def test_rapid_updates():
    """100 append() за секунду - debounce работает"""

@pytest.mark.stress
async def test_very_long_message():
    """100KB текст - разбивается корректно"""

@pytest.mark.stress
async def test_many_tool_calls():
    """50 tool calls подряд - все отображаются"""

@pytest.mark.stress
async def test_concurrent_streams():
    """5 пользователей одновременно - изоляция"""
```

---

## 6. Regression тесты (известные баги)

```python
def test_no_block_placeholders_in_output():
    """Регрессия: BLOCK17, BLOCK28 не появляются в тексте"""

def test_no_ph_placeholders_in_output():
    """Регрессия: PH17, PH21 не появляются в тексте"""

def test_blockquote_not_broken_during_stream():
    """Регрессия: <blockquote expandable> не показывается как raw text"""

def test_todo_appears_immediately():
    """Регрессия: план появляется сразу, не в конце"""

def test_message_not_lagging():
    """Регрессия: сообщение отражает состояние backend с минимальной задержкой"""
```

---

## 7. Метрики

| Метрика | Цель | Как измерить |
|---------|------|--------------|
| Задержка обновления | < 1.5s | timestamp backend vs TG |
| Потеря апдейтов | 0% | счётчик skip vs sent |
| Ошибки API | < 1% | логи |
| Placeholder leaks | 0 | regex в output |
| Memory usage | stable | профилирование |

---

## 8. Инструменты

```bash
# Запуск unit тестов стриминга
pytest tests/unit/presentation/test_streaming*.py -v

# Запуск integration тестов
pytest tests/integration/presentation/ -v

# E2E тесты (нужен тестовый бот)
TEST_BOT_TOKEN=xxx TEST_CHAT_ID=yyy pytest tests/e2e/test_streaming_e2e.py -v

# Stress тесты
pytest tests/stress/test_streaming_stress.py -v --timeout=300

# Регрессионные тесты
pytest tests/ -k "regression or placeholder or blockquote" -v

# Coverage для streaming модуля
pytest tests/ --cov=presentation/handlers/streaming --cov-report=html
```

---

## 9. Приоритеты реализации

1. **P0 (блокеры):**
   - Placeholder система (regression)
   - Rate limiting (API bans)
   - Todo display (UX критично)

2. **P1 (важно):**
   - Markdown конвертация
   - Message split
   - Error handling

3. **P2 (желательно):**
   - Stress тесты
   - E2E тесты
   - Метрики

---

## 10. CI интеграция

```yaml
# .github/workflows/streaming-tests.yml
name: Streaming Tests

on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Unit tests
        run: pytest tests/unit/presentation/test_streaming*.py -v

  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Integration tests
        run: pytest tests/integration/presentation/ -v

  e2e:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: E2E tests
        env:
          TEST_BOT_TOKEN: ${{ secrets.TEST_BOT_TOKEN }}
          TEST_CHAT_ID: ${{ secrets.TEST_CHAT_ID }}
        run: pytest tests/e2e/test_streaming_e2e.py -v
```
