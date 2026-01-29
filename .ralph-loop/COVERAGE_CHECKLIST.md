# Coverage Checklist - MessageHandlers Refactoring

**Purpose:** Track 100% coverage of all methods, parameters, and attributes
**Status:** Phase 0 - Ready for Phase 1

---

## Checklist: Все методы покрыты в новом коде

### Public Methods (из legacy) - 34 methods:

#### YOLO Mode:
- [ ] is_yolo_mode (line 124)
- [ ] set_yolo_mode (line 128)

#### Step Streaming Mode:
- [ ] is_step_streaming_mode (line 132)
- [ ] set_step_streaming_mode (line 136)
- [ ] _get_step_handler (line 140)
- [ ] _cleanup_step_handler (line 152)

#### Working Directory:
- [ ] get_working_dir (line 157)
- [ ] get_project_working_dir (line 161)
- [ ] set_working_dir (line 175)

#### Session Management:
- [ ] clear_session_cache (line 179)
- [ ] set_continue_session (line 183)

#### HITL State Management:
- [ ] set_expecting_answer (line 189)
- [ ] set_expecting_path (line 193)
- [ ] get_pending_question_option (line 197)
- [ ] handle_permission_response (line 201)
- [ ] handle_question_response (line 212)

#### Variable Input State:
- [ ] is_expecting_var_input (line 223)
- [ ] set_expecting_var_name (line 227)
- [ ] set_expecting_var_value (line 234)
- [ ] set_expecting_var_desc (line 238)
- [ ] clear_var_state (line 242)
- [ ] get_pending_var_message (line 246)
- [ ] start_var_input (line 250)
- [ ] start_var_edit (line 254)
- [ ] cancel_var_input (line 258)
- [ ] save_variable_skip_desc (line 1544)

#### Plan Approval State:
- [ ] handle_plan_response (line 264)
- [ ] set_expecting_plan_clarification (line 274)

#### Task State:
- [ ] _is_task_running (line 280)

#### Message Handlers:
- [ ] handle_document (line 468)
- [ ] handle_photo (line 483)
- [ ] handle_text (line 557)

**Progress:** 0 / 34 public methods

---

### Private Methods (из legacy) - 27 methods:

#### CD Command Detection:
- [ ] _detect_cd_command (line 291)

#### File Handling:
- [ ] _handle_file_message (line 331)
- [ ] _process_file_with_caption (line 395)
- [ ] _cache_file_for_reply (line 439)
- [ ] _extract_reply_file_context (line 504)
- [ ] _execute_task_with_prompt (line 552)

#### Callback Handlers - SDK/CLI:
- [ ] _on_text (line 873)
- [ ] _on_tool_use (line 894)
- [ ] _on_tool_result (line 996)
- [ ] _on_permission (line 1021)
- [ ] _on_question (line 1068)
- [ ] _on_error (line 1109)
- [ ] _on_thinking (line 1119)
- [ ] _on_permission_sdk (line 1139)
- [ ] _on_question_sdk (line 1191)
- [ ] _on_plan_request (line 1221)
- [ ] _on_permission_completed (line 1270)
- [ ] _on_question_completed (line 1303)

#### Task Result Handler:
- [ ] _handle_result (line 1320)

#### Input Handlers:
- [ ] _handle_answer_input (line 1393)
- [ ] _handle_clarification_input (line 1403)
- [ ] _handle_plan_clarification (line 1430)
- [ ] _handle_path_input (line 1450)
- [ ] _handle_var_name_input (line 1460)
- [ ] _handle_var_value_input (line 1484)
- [ ] _handle_var_desc_input (line 1532)
- [ ] _save_variable (line 1554)

**Progress:** 0 / 27 private methods

---

### Module-Level Functions - 2 functions:

- [ ] register_handlers (line 1606)
- [ ] get_message_handlers (line 1613)

**Progress:** 0 / 2 module-level functions

---

## Checklist: Все параметры передаются

### __init__ Parameters (7 total):

- [ ] bot_service (line 79)
- [ ] claude_proxy (line 80)
- [ ] sdk_service (line 81)
- [ ] default_working_dir (line 82)
- [ ] project_service (line 83)
- [ ] context_service (line 84)
- [ ] file_processor_service (line 85)

**Progress:** 0 / 7 parameters verified

---

## Checklist: Все атрибуты инициализированы

### From __init__ (7 attributes):
- [ ] self.bot_service (line 87)
- [ ] self.claude_proxy (line 88)
- [ ] self.sdk_service (line 89)
- [ ] self.project_service (line 90)
- [ ] self.context_service (line 91)
- [ ] self.file_processor_service (line 94-99)
- [ ] self.use_sdk (line 102)

### State Managers (5 attributes):
- [ ] self._state (line 106)
- [ ] self._hitl (line 107)
- [ ] self._variables (line 108)
- [ ] self._plans (line 109)
- [ ] self._files (line 110)

### Other Attributes (3 attributes):
- [ ] self._batcher (line 114)
- [ ] self.callback_handlers (line 117)
- [ ] self.default_working_dir (line 120)
- [ ] self._step_handlers (line 146)

**Progress:** 0 / 15+ attributes

---

## Summary Tracking

**Total Items:** 61 methods + 2 functions + 7 parameters + 15 attributes = **85 items**

**Current Progress:**
- Methods: 0 / 61 (0%)
- Functions: 0 / 2 (0%)
- Parameters: 0 / 7 (0%)
- Attributes: 0 / 15 (0%)
- **Total: 0 / 85 (0%)**

**Target:** 100% coverage (85 / 85 items)

---

## Usage Instructions

During Phase 2 (Logic Copy):
1. Copy a method from legacy to new file
2. Mark checkbox as done: `[x]`
3. Add line number reference in comment
4. Update progress counter

Example:
```markdown
- [x] is_yolo_mode (line 124) - Copied to coordinator.py:45-47
```

**Status:** ✅ Checklist created, ready for Phase 1
**Next:** Create skeleton files with all empty methods
