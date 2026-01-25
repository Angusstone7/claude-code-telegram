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

# Docker deployment (development)
docker-compose up -d --build

# Docker deployment (production via CI/CD)
# The GitLab CI/CD pipeline builds and deploys automatically on push to main/master
# Manual deployment:
docker-compose -f docker-compose.prod.yml up -d --build
```

## Architecture Overview

This is a Telegram bot that acts as a remote interface to Claude Code CLI and SDK, enabling AI-powered coding assistance via Telegram. The project follows DDD (Domain-Driven Design) with four layers:

**Domain** → **Application** → **Infrastructure** → **Presentation**

### Core Functionality

The bot provides two backends for interacting with Claude Code:

1. **SDK Backend** (Preferred): Uses `claude-agent-sdk` for direct Python integration with HITL (Human-in-the-Loop) support
   - Located in `infrastructure/claude_code/sdk_service.py`
   - Supports streaming responses and tool execution
   - Integrates with official Claude plugins from `/plugins` directory

2. **CLI Backend** (Fallback): Proxies to `@anthropic-ai/claude-code` npm package
   - Located in `infrastructure/claude_code/proxy_service.py`
   - Runs Claude Code commands in subprocess
   - Includes diagnostics via `infrastructure/claude_code/diagnostics.py`

### Request Flow

1. **Telegram message arrives** → `presentation/handlers/messages.py` or `presentation/handlers/streaming.py`
2. **Auth middleware checks user** → `presentation/middleware/auth.py`
3. **Handler calls appropriate service**:
   - For Claude Code interactions: `ClaudeAgentSDKService` or `ClaudeCodeProxyService`
   - For project/context management: `ProjectService`, `ContextService`, `FileBrowserService`
   - For legacy features: `BotService`
4. **Response sent back** to Telegram (with streaming support for SDK)

### Key Design Patterns

- **Repository Pattern**: Domain layer defines interfaces (`domain/repositories/`), infrastructure implements them (`infrastructure/persistence/`)
- **Value Objects**: Immutable identifiers like `UserId`, `Role` in `domain/value_objects/`
- **Application Services**: Each service handles a specific capability (BotService, ProjectService, ContextService, FileBrowserService)
- **Dependency Injection**: All services are initialized in `main.py:Application.setup()`

### Project and Context Management

The bot manages multiple projects with persistent conversation contexts:

- **Projects**: Stored via `SQLiteProjectRepository`, track working directories
- **Contexts**: Stored via `SQLiteProjectContextRepository`, maintain conversation history per project
- **File Browser**: `FileBrowserService` provides file system navigation within `/root/projects`

### AI Provider Abstraction

The bot supports multiple Claude-compatible APIs (Anthropic, ZhipuAI). Configuration is handled through:
- `domain/value_objects/ai_provider_config.py` - Provider configuration value object
- `shared/config/settings.py:AnthropicConfig` - Environment-based configuration facade
- `infrastructure/messaging/claude_service.py:ClaudeAIService` - Implementation

Use `ANTHROPIC_BASE_URL` for alternative API endpoints and `ANTHROPIC_AUTH_TOKEN` for non-standard auth.

### Claude Code Integration

**SDK Service** (`infrastructure/claude_code/sdk_service.py`):
- Wraps `claude-agent-sdk` for Python-native Claude Code access
- Manages agent lifecycle, session persistence, and streaming responses
- Loads plugins from `/plugins` directory (official plugins from anthropic/claude-plugins-official)
- Supports permission modes: `default`, `auto`, `never`

**CLI Proxy Service** (`infrastructure/claude_code/proxy_service.py`):
- Fallback when SDK is unavailable
- Executes `claude` CLI commands via subprocess
- Parses CLI output for Telegram display
- Includes command diagnostics

### Session Management

Sessions maintain conversation history per user:
- `Session` entity holds `List[Message]` with role-based messages
- Sessions persist to SQLite via `SQLiteSessionRepository`
- AI receives full session context on each `chat_with_session()` call

## Configuration

All config loads from environment variables via `shared/config/settings.py`. The global `settings` instance is used throughout.

### Required Environment Variables

- `TELEGRAM_TOKEN` - Bot token from @BotFather
- `ALLOWED_USER_ID` - Telegram user ID for authorization
- Either `ANTHROPIC_API_KEY` (official Anthropic) OR `ANTHROPIC_AUTH_TOKEN` (compatible APIs)

### Optional Claude Code Variables

- `CLAUDE_WORKING_DIR` - Default working directory (default: `/root`)
- `CLAUDE_PATH` - Path to claude CLI (default: `claude`)
- `CLAUDE_MAX_TURNS` - Max conversation turns (default: `50`)
- `CLAUDE_TIMEOUT` - Command timeout in seconds (default: `600`)
- `CLAUDE_PERMISSION_MODE` - SDK permission mode: `default|auto|never`
- `CLAUDE_PLUGINS_DIR` - Plugins directory (default: `/plugins`)
- `CLAUDE_PLUGINS` - Comma-separated enabled plugins

### Optional AI Provider Variables

- `ANTHROPIC_BASE_URL` - Alternative API endpoint (e.g., ZhipuAI)
- `ANTHROPIC_MODEL` - Model to use
- `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL` - Model aliases

## Docker and Deployment

**Development**:
```bash
docker-compose up -d --build
```

**Production** (via GitLab CI/CD):
- Push to `main` or `master` branch triggers automatic deployment
- Pipeline builds Docker image, transfers to server via SSH, deploys with docker-compose
- Server: `192.168.0.116:2222`, app path: `/opt/ubuntu_claude`
- Container is configured with persistent volumes for `./data`, `./logs`, `./projects`

**Dockerfile Highlights**:
- Base: `python:3.11-slim`
- Installs Node.js 20.x for Claude Code CLI
- Installs `@anthropic-ai/claude-code` globally via npm
- Clones official plugins to `/plugins`
- Runs `python main.py` as entrypoint

## Testing

Tests are in `tests/` with `pytest-asyncio` for async support. Run with `-v` for verbose output or `--tb=short` for shorter tracebacks.
