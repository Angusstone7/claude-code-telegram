# Legacy Inventory - messages.py (1615 lines)

**Date:** 2026-01-29
**File:** `presentation/handlers/messages.py`
**Lines:** 1615
**Status:** Ready for refactoring

---

## __init__ Parameters (full list)

```python
def __init__(
    self,
    bot_service,  # BotService
    claude_proxy: ClaudeCodeProxyService,
    sdk_service: Optional["ClaudeAgentSDKService"] = None,
    default_working_dir: str = "/root",
    project_service=None,  # ProjectService
    context_service=None,  # ContextService
    file_processor_service: Optional["FileProcessorService"] = None
)
```

**Total: 7 parameters**

---

## Class Attributes (full list)

### From __init__:
- `self.bot_service` - BotService instance
- `self.claude_proxy` - ClaudeCodeProxyService instance
- `self.sdk_service` - Optional ClaudeAgentSDKService
- `self.project_service` - ProjectService
- `self.context_service` - ContextService
- `self.file_processor_service` - Optional FileProcessorService
- `self.use_sdk` - bool (determined from sdk_service availability)

### State Managers (line 106-110):
- `self._state` - UserStateManager
- `self._hitl` - HITLManager
- `self._variables` - VariableInputManager
- `self._plans` - PlanApprovalManager
- `self._files` - FileContextManager

### Other attributes:
- `self._batcher` - MessageBatcher (line 114)
- `self.callback_handlers` - Optional[CallbackHandlers] (line 117)
- `self.default_working_dir` - Legacy compatibility alias (line 120)
- `self._step_handlers` - Dict[int, StepStreamingHandler] (line 146)

**Total: 15+ attributes**

---

## Public Methods (full list with signatures)

### YOLO Mode (lines 124-130):
```python
def is_yolo_mode(self, user_id: int) -> bool
def set_yolo_mode(self, user_id: int, enabled: bool)
```

### Step Streaming Mode (lines 132-138):
```python
def is_step_streaming_mode(self, user_id: int) -> bool
def set_step_streaming_mode(self, user_id: int, enabled: bool)
```

### Step Handler (lines 140-155):
```python
def _get_step_handler(self, user_id: int) -> Optional["StepStreamingHandler"]
def _cleanup_step_handler(self, user_id: int)
```

### Working Directory (lines 157-177):
```python
def get_working_dir(self, user_id: int) -> str
async def get_project_working_dir(self, user_id: int) -> str
def set_working_dir(self, user_id: int, path: str)
```

### Session Management (lines 179-186):
```python
def clear_session_cache(self, user_id: int) -> None
def set_continue_session(self, user_id: int, session_id: str)
```

### HITL State Management (lines 189-219):
```python
def set_expecting_answer(self, user_id: int, expecting: bool)
def set_expecting_path(self, user_id: int, expecting: bool)
def get_pending_question_option(self, user_id: int, index: int) -> str
async def handle_permission_response(self, user_id: int, approved: bool, clarification_text: str = None) -> bool
async def handle_question_response(self, user_id: int, answer: str)
```

### Variable Input State (lines 223-260):
```python
def is_expecting_var_input(self, user_id: int) -> bool
def set_expecting_var_name(self, user_id: int, expecting: bool, menu_msg: Message = None)
def set_expecting_var_value(self, user_id: int, var_name: str, menu_msg: Message = None)
def set_expecting_var_desc(self, user_id: int, var_name: str, var_value: str, menu_msg: Message = None)
def clear_var_state(self, user_id: int)
def get_pending_var_message(self, user_id: int) -> Optional[Message]
def start_var_input(self, user_id: int, menu_msg: Message = None)
def start_var_edit(self, user_id: int, var_name: str, menu_msg: Message = None)
def cancel_var_input(self, user_id: int)
async def save_variable_skip_desc(self, user_id: int, message: Message)
```

### Plan Approval State (lines 264-276):
```python
async def handle_plan_response(self, user_id: int, response: str) -> bool
def set_expecting_plan_clarification(self, user_id: int, expecting: bool)
```

### Task State (lines 280-287):
```python
def _is_task_running(self, user_id: int) -> bool
```

### Message Handlers (lines 468-502, 557-870):
```python
async def handle_document(self, message: Message) -> None
async def handle_photo(self, message: Message) -> None
async def handle_text(
    self,
    message: Message,
    prompt_override: str = None,
    force_new_session: bool = False,
    _from_batcher: bool = False
) -> None
```

**Total: 34 public methods**

---

## Private Methods (full list with signatures)

### CD Command Detection (lines 291-327):
```python
def _detect_cd_command(self, command: str, current_dir: str) -> Optional[str]
```

### File Handling (lines 331-556):
```python
async def _handle_file_message(
    self,
    message: Message,
    file_id: str,
    filename: str,
    file_size: int,
    mime_type: str,
    file_type_label: str = "Файл"
) -> None

async def _process_file_with_caption(
    self,
    message: Message,
    processed: "ProcessedFile",
    caption: str,
    file_type_label: str
) -> None

async def _cache_file_for_reply(
    self,
    message: Message,
    processed: "ProcessedFile",
    file_type_label: str,
    user_id: int
) -> None

async def _extract_reply_file_context(
    self, reply_message: Message, bot: Bot
) -> Optional[tuple["ProcessedFile", str]]

async def _execute_task_with_prompt(self, message: Message, prompt: str) -> None
```

### Callback Handlers - SDK/CLI (lines 873-1319):
```python
async def _on_text(self, user_id: int, text: str)
async def _on_tool_use(self, user_id: int, tool_name: str, tool_input: dict, message: Message)
async def _on_tool_result(self, user_id: int, tool_id: str, output: str)
async def _on_permission(self, user_id: int, tool_name: str, details: str, message: Message) -> bool
async def _on_question(self, user_id: int, question: str, options: list[str], message: Message) -> str
async def _on_error(self, user_id: int, error: str)
async def _on_thinking(self, user_id: int, thinking: str)
async def _on_permission_sdk(
    self,
    user_id: int,
    tool_name: str,
    details: str,
    tool_input: dict,
    message: Message
)
async def _on_question_sdk(
    self,
    user_id: int,
    question: str,
    options: list[str],
    message: Message
)
async def _on_plan_request(
    self,
    user_id: int,
    plan_file: str,
    tool_input: dict,
    message: Message
)
async def _on_permission_completed(self, user_id: int, approved: bool)
async def _on_question_completed(self, user_id: int, answer: str)
```

### Task Result Handler (lines 1320-1390):
```python
async def _handle_result(self, user_id: int, result: TaskResult, message: Message)
```

### Input Handlers (lines 1393-1604):
```python
async def _handle_answer_input(self, message: Message)
async def _handle_clarification_input(self, message: Message)
async def _handle_plan_clarification(self, message: Message)
async def _handle_path_input(self, message: Message)
async def _handle_var_name_input(self, message: Message)
async def _handle_var_value_input(self, message: Message)
async def _handle_var_desc_input(self, message: Message)
async def _save_variable(self, message: Message, var_name: str, var_value: str, var_desc: str)
```

**Total: 27 private methods**

---

## Module-Level Functions (lines 1606-1615):

```python
def register_handlers(router: Router, handlers: MessageHandlers) -> None
def get_message_handlers(bot_service, claude_proxy: ClaudeCodeProxyService) -> MessageHandlers
```

---

## Summary Statistics

- **Total Methods:** 61 (34 public + 27 private)
- **Total Parameters:** 7
- **Total Attributes:** 15+
- **Total Lines:** 1615
- **Cyclomatic Complexity:** ~80
- **Functions:** 2 (module-level)

---

## Import Statements (lines 15-61)

### Standard library:
- asyncio, html, logging, os, re, uuid
- typing: Optional, TYPE_CHECKING

### Aiogram:
- Router, F, Bot
- Message
- StateFilter

### Internal:
- presentation.keyboards.keyboards: Keyboards
- presentation.handlers.streaming: StreamingHandler, HeartbeatTracker, StepStreamingHandler
- presentation.handlers.state: UserStateManager, HITLManager, VariableInputManager, PlanApprovalManager, FileContextManager
- infrastructure.claude_code.proxy_service: ClaudeCodeProxyService, TaskResult
- domain.entities.claude_code_session: ClaudeCodeSession, SessionStatus

### TYPE_CHECKING imports:
- infrastructure.claude_code.sdk_service: ClaudeAgentSDKService, SDKTaskResult
- application.services.file_processor_service: FileProcessorService, ProcessedFile

### Optional imports (try/except):
- FileProcessorService, ProcessedFile, FileType
- ClaudeAgentSDKService, SDKTaskResult, TaskStatus

---

## Dependencies Used

**Services:**
- BotService (authorization, messaging)
- ClaudeCodeProxyService (CLI backend)
- ClaudeAgentSDKService (SDK backend)
- ProjectService (project management)
- ContextService (context/global variables)
- FileProcessorService (file processing)

**Managers:**
- UserStateManager (user state)
- HITLManager (human-in-the-loop)
- VariableInputManager (variable input flow)
- PlanApprovalManager (plan approval flow)
- FileContextManager (file upload context)
- MessageBatcher (message batching)
- Keyboards (inline keyboards)

**Streaming:**
- StreamingHandler (main streaming UI)
- HeartbeatTracker (activity indicator)
- StepStreamingHandler (brief output mode)

---

## Files to Create (Phase 1)

1. `presentation/handlers/message/__init__.py` - Package exports
2. `presentation/handlers/message/base.py` - Base handler
3. `presentation/handlers/message/ai_request_handler.py` - SDK/CLI integration
4. `presentation/handlers/message/text_handler.py` - Text message handling
5. `presentation/handlers/message/file_handler.py` - File/photo handling
6. `presentation/handlers/message/hitl_handler.py` - HITL callbacks
7. `presentation/handlers/message/variable_handler.py` - Variable input
8. `presentation/handlers/message/plan_handler.py` - Plan approval
9. `presentation/handlers/message/coordinator.py` - Message routing
10. `presentation/handlers/message/facade.py` - Backward compatibility

---

**Status:** ✅ Phase 0 Complete
**Next:** Phase 1 - Create skeleton files
