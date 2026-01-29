# Iteration 2 Plan - MessageHandlers Refactoring

**Status:** Ready to continue
**Starting Point:** Phase 2c - Copy text_handler methods
**Progress:** 52% methods copied (32/61)

---

## Immediate Next Steps

### 1. Copy `text_handler.py` Methods (PRIORITY #1)

**Critical Method: `handle_text()` (313 lines)**
- Location: legacy messages.py:557-870
- Copy ENTIRE method to `presentation/handlers/message/text_handler.py`
- This is the MAIN ENTRY POINT for all text messages
- Contains: file reply handling, special input modes, message batching, SDK/CLI execution

**Input Handler Methods (~200 lines total):**
- `_handle_answer_input()` - messages.py:1393-1401
- `_handle_clarification_input()` - messages.py:1403-1428
- `_handle_plan_clarification()` - messages.py:1430-1448
- `_handle_path_input()` - messages.py:1450-1458
- `_handle_var_name_input()` - messages.py:1460-1482
- `_handle_var_value_input()` - messages.py:1484-1530
- `_handle_var_desc_input()` - messages.py:1532-1542
- `_save_variable()` - messages.py:1554-1603

### 2. Complete `file_handler.py` Methods

**Remaining 5 methods (~180 lines):**
- `_handle_file_message()` - messages.py:331-393
- `_process_file_with_caption()` - messages.py:395-437
- `_cache_file_for_reply()` - messages.py:439-464
- `_extract_reply_file_context()` - messages.py:504-550
- `_execute_task_with_prompt()` - messages.py:552-555

---

## Copying Process

For EACH method:
1. Read method from legacy `messages.py`
2. Copy ENTIRE method body (all lines)
3. Replace `self._state` → `self.user_state`
4. Replace `self._hitl` → `self.hitl_manager`
5. Replace `self._variables` → `self.variable_manager`
6. Replace `self._plans` → `self.plan_manager`
7. Replace `self._files` → `self.file_context_manager`
8. Paste into target file
9. Test compilation: `python -c "from presentation.handlers.message.text_handler import TextMessageHandler"`
10. Check off in `COVERAGE_CHECKLIST.md`

---

## Important Notes

⚠️ **DO NOT change logic** - only structural replacements
⚠️ **DO NOT "improve" code** - copy exactly as is
⚠️ **DO NOT skip parameters** - copy everything
⚠️ **DO test after each file** - ensure compilation

✅ **DO use line number references** - track where each method came from
✅ **DO commit frequently** - can rollback if needed
✅ **DO update checklist** - mark progress as you go

---

## Files to Modify

1. `presentation/handlers/message/text_handler.py` - Add ~500 lines
2. `presentation/handlers/message/file_handler.py` - Add ~180 lines
3. `.ralph-loop/COVERAGE_CHECKLIST.md` - Update checkboxes

---

## Success Criteria

✅ All 61 methods copied (100%)
✅ All files compile without errors
✅ All checkboxes in COVERAGE_CHECKLIST.md marked
✅ Ready for Phase 3 (parameter flow verification)

---

## Estimated Time

- `handle_text()`: 1 hour
- Input handlers (8 methods): 1.5 hours
- File handler methods (5 methods): 1 hour
- Testing and compilation: 30 min

**Total:** ~4 hours

---

**Start with:** `handle_text()` method - it's the biggest and most critical!
