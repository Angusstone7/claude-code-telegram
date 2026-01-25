# REFACTORING.md - SOLID/DDD Improvement Plan

This document outlines discovered SOLID and DDD violations and proposes refactoring steps for future iterations.

## Audit Summary

**Date**: 2025-01-25
**Tests**: 143 passed, 0 failures
**Coverage**: ~40% domain layer, ~30% application layer

---

## Completed Fixes

### DDD - Critical Issues (Fixed)

| Issue | File | Fix Applied |
|-------|------|-------------|
| `AIProviderConfig` not frozen | `domain/value_objects/ai_provider_config.py` | Added `frozen=True` |
| `AIModelConfig` not frozen | `domain/value_objects/ai_provider_config.py` | Added `frozen=True` |
| `__post_init__` mutation in frozen class | `ai_provider_config.py:42-44` | Use `object.__setattr__()` |
| `with_model()` mutated self | `ai_provider_config.py:67-75` | Use local variable instead |

### Bug Fixes

| Bug | File | Fix |
|-----|------|-----|
| `chown -R` not detected as dangerous | `domain/entities/command.py:93` | Changed to lowercase `chown -r` |
| `get_conversation_history()` returns enum | `domain/entities/session.py:67` | Use `.value` for string |
| `execute_command()` returns unbound var | `application/services/bot_service.py:199-219` | Initialize `result = None` |

---

## Pending SOLID Violations (For Future Refactoring)

### Single Responsibility Principle (SRP)

#### 1. `MessageHandlers` - 784 lines, 12+ responsibilities

**File**: `presentation/handlers/messages.py`

**Current responsibilities**:
- Message routing
- State management (14 state dictionaries!)
- Photo handling
- Code execution
- Docker management
- Streaming responses
- Error handling
- File uploads
- Settings management
- Context management
- Plugin management
- YOLO mode management

**Proposed split**:

```
presentation/handlers/
├── messages/
│   ├── __init__.py           # Exports main MessageRouter
│   ├── router.py             # MessageRouter - routing only
│   ├── state.py              # UserStateManager - state tracking
│   ├── code_handler.py       # CodeExecutionHandler
│   ├── docker_handler.py     # DockerCommandHandler
│   ├── file_handler.py       # FileUploadHandler
│   └── settings_handler.py   # SettingsHandler
```

**Priority**: HIGH

---

#### 2. `CallbackHandlers` - 1194 lines, 40+ methods

**File**: `presentation/handlers/callbacks.py`

**Current responsibilities**:
- Command approval/rejection
- Docker container management
- GitLab operations
- System monitoring
- Disk management
- Process management
- Network management
- Cron job management
- User settings
- Context menu handling
- Plugin callbacks
- YOLO mode callbacks

**Proposed split**:

```
presentation/handlers/
├── callbacks/
│   ├── __init__.py              # Exports main CallbackRouter
│   ├── router.py                # CallbackRouter - routing only
│   ├── command_callbacks.py     # CommandApprovalHandler
│   ├── docker_callbacks.py      # DockerCallbackHandler
│   ├── monitoring_callbacks.py  # MonitoringCallbackHandler
│   ├── gitlab_callbacks.py      # GitLabCallbackHandler
│   └── settings_callbacks.py    # SettingsCallbackHandler
```

**Priority**: HIGH

---

### Dependency Inversion Principle (DIP)

#### Direct instantiation of `SystemMonitor`

**Files**: Multiple locations

```python
# Current (BAD):
from infrastructure.monitoring.system_monitor import SystemMonitor
monitor = SystemMonitor()

# Proposed (GOOD):
class SomeHandler:
    def __init__(self, system_monitor: SystemMonitorInterface):
        self.monitor = system_monitor
```

**Affected files**:
- `presentation/handlers/callbacks.py` - lines 129, 162, 198, 235, 271, 308
- `application/services/bot_service.py` - line 232

**Fix**: Inject `SystemMonitor` via constructor

**Priority**: MEDIUM

---

### Interface Segregation Principle (ISP)

#### Fat constructors in handlers

**Issue**: Handler constructors take too many dependencies

```python
# Current:
class MessageHandlers:
    def __init__(
        self,
        bot_service: BotService,
        ai_service: ClaudeAIService,
        ssh_executor: SSHCommandExecutor,
        claude_proxy: ClaudeCodeProxy,
        # ... 10+ more dependencies
    ):
```

**Proposed**: Use smaller, focused interfaces

```python
class CommandExecutionCapability(Protocol):
    async def execute_command(self, cmd: str) -> CommandResult: ...

class AICapability(Protocol):
    async def chat(self, message: str) -> str: ...
```

**Priority**: MEDIUM

---

### Open/Closed Principle (OCP)

#### Hard-coded tool definitions

**File**: `application/services/bot_service.py:105-140`

```python
# Current (BAD):
tools = [
    {"name": "bash", "description": "...", ...},
    {"name": "get_metrics", ...},
    {"name": "list_containers", ...},
]

# Proposed (GOOD):
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def schema(self) -> dict: ...

class BashTool(Tool): ...
class MetricsTool(Tool): ...
```

**Priority**: LOW

---

## Repository Layer Issues

### `CommandRepository` uses `int` instead of `UserId`

**File**: `domain/repositories/command_repository.py`

```python
# Current:
async def find_by_user(self, user_id: int, ...) -> List[Command]

# Proposed:
async def find_by_user(self, user_id: UserId, ...) -> List[Command]
```

**Priority**: LOW (cosmetic consistency)

---

## Entity Validation Gaps

### `Session.add_message()` lacks validation

**File**: `domain/entities/session.py:25-28`

```python
# Current:
def add_message(self, message: Message) -> None:
    self.messages.append(message)
    self.updated_at = datetime.utcnow()

# Proposed:
def add_message(self, message: Message) -> None:
    if not isinstance(message, Message):
        raise TypeError("Expected Message instance")
    if message.content is None:
        raise ValueError("Message content cannot be None")
    self.messages.append(message)
    self.updated_at = datetime.now(datetime.UTC)
```

**Priority**: LOW

---

## Deprecation Warnings (190 total)

### `datetime.utcnow()` deprecated

**Affected entities**:
- `domain/entities/command.py` (lines 36, 56, 65, 75)
- `domain/entities/session.py` (lines 22, 23, 28, 39, 44, 53, 58)
- `domain/entities/message.py` (line 27)
- `domain/entities/user.py` (line 23, 43)

**Fix**: Replace with `datetime.now(datetime.UTC)`

```python
# Current:
from datetime import datetime
self.created_at = datetime.utcnow()

# Proposed:
from datetime import datetime, UTC
self.created_at = datetime.now(UTC)
```

**Priority**: MEDIUM (will break in Python 3.14+)

---

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 hours)
- [ ] Fix all `datetime.utcnow()` deprecations
- [ ] Add validation to `Session.add_message()`
- [ ] Update `CommandRepository` to use `UserId`

### Phase 2: DIP Fix (2-3 hours)
- [ ] Create `SystemMonitorInterface` protocol
- [ ] Inject `SystemMonitor` via DI in `main.py`
- [ ] Update all direct instantiations

### Phase 3: Split MessageHandlers (4-6 hours)
- [ ] Extract `UserStateManager` class
- [ ] Extract `CodeExecutionHandler` class
- [ ] Extract `DockerCommandHandler` class
- [ ] Create `MessageRouter` for routing

### Phase 4: Split CallbackHandlers (4-6 hours)
- [ ] Extract `CommandApprovalHandler`
- [ ] Extract `DockerCallbackHandler`
- [ ] Extract `MonitoringCallbackHandler`
- [ ] Create `CallbackRouter` for routing

### Phase 5: Tool Abstraction (2-3 hours)
- [ ] Create `Tool` abstract base class
- [ ] Implement `BashTool`, `MetricsTool`, etc.
- [ ] Update `BotService` to use tool registry

---

## Testing Requirements

After each refactoring phase:

1. Run full regression: `pytest tests/ -v`
2. Verify no new warnings: `pytest tests/ -v --strict-markers`
3. Run mypy: `mypy application/ domain/ infrastructure/ presentation/`
4. Manual smoke test: Start bot and execute basic commands

---

## Notes

- All refactoring should be done incrementally with tests passing at each step
- Each PR should address ONE SOLID principle violation
- Maintain backward compatibility during transition
- Document any breaking changes in CHANGELOG.md
