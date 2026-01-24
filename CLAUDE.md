# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Run the bot locally
python main.py

# Run all tests
pytest tests/

# Run a single test file
pytest tests/unit/domain/test_ai_provider_config.py

# Run a specific test function
pytest tests/unit/domain/test_ai_provider_config.py::test_function_name -v

# Code formatting
black application/ domain/ infrastructure/ presentation/ shared/

# Type checking
mypy application/ domain/ infrastructure/ presentation/ shared/

# Docker deployment
docker-compose up -d --build
```

## Architecture Overview

This is a Telegram bot for server management using Claude AI. It follows DDD (Domain-Driven Design) with four layers:

**Domain** → **Application** → **Infrastructure** → **Presentation**

### Request Flow

1. **Telegram message arrives** → `presentation/handlers/messages.py`
2. **Auth middleware checks user** → `presentation/middleware/auth.py`
3. **Handler calls BotService** → `application/services/bot_service.py`
4. **BotService orchestrates**:
   - User/Session lookup via repositories (domain interfaces → infrastructure implementations)
   - AI calls via `ClaudeAIService` → `infrastructure/messaging/claude_service.py`
   - Command execution via `SSHCommandExecutor` → `infrastructure/ssh/ssh_executor.py`
5. **Response sent back** to Telegram

### Key Design Patterns

- **Repository Pattern**: Domain layer defines interfaces (`domain/repositories/`), infrastructure implements them (`infrastructure/persistence/sqlite_repository.py`)
- **Value Objects**: Immutable identifiers like `UserId`, `Role` in `domain/value_objects/`
- **Application Service**: `BotService` is the single orchestrator - all presentation layer code calls through it
- **Dependency Injection**: All services are injected in `main.py:Application.setup()`

### AI Provider Abstraction

The bot supports multiple Claude-compatible APIs (Anthropic, ZhipuAI). Configuration is handled through:
- `domain/value_objects/ai_provider_config.py` - Provider configuration value object
- `shared/config/settings.py:AnthropicConfig` - Environment-based configuration facade
- `infrastructure/messaging/claude_service.py:ClaudeAIService` - Implementation

Use `ANTHROPIC_BASE_URL` for alternative API endpoints and `ANTHROPIC_AUTH_TOKEN` for non-standard auth.

### Command Approval Workflow

Commands follow a state machine: `PENDING` → `APPROVED`/`REJECTED` → `EXECUTING` → `COMPLETED`/`FAILED`

The flow is:
1. AI suggests command → `BotService.create_pending_command()`
2. User sees approval keyboard → `presentation/keyboards/keyboards.py`
3. Callback handler processes → `presentation/handlers/callbacks.py`
4. Approved: `BotService.execute_command()` runs via SSH
5. Rejected: `BotService.reject_command()` logs and notifies

### Session Management

Sessions maintain conversation history per user:
- `Session` entity holds `List[Message]` with role-based messages
- Sessions persist to SQLite via `SQLiteSessionRepository`
- AI receives full session context on each `chat_with_session()` call

## Configuration

All config loads from environment variables via `shared/config/settings.py`. The global `settings` instance is used throughout. Key required vars:
- `TELEGRAM_TOKEN`, `ANTHROPIC_API_KEY` (or `ANTHROPIC_AUTH_TOKEN`), `ALLOWED_USER_ID`

## Testing

Tests are in `tests/` with `pytest-asyncio` for async support. Run with `-v` for verbose output or `--tb=short` for shorter tracebacks.
