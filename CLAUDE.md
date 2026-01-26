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

# Run tests with verbose output and short tracebacks
pytest tests/ -v --tb=short

# Code formatting
black application/ domain/ infrastructure/ presentation/ shared/

# Type checking
mypy application/ domain/ infrastructure/ presentation/ shared/

# Docker deployment (development)
docker-compose up -d --build

# View logs (development)
docker-compose logs -f claude-bot

# Docker deployment (production via CI/CD)
# The GitLab CI/CD pipeline builds and deploys automatically on push to main/master
# Manual deployment:
docker-compose -f docker-compose.prod.yml up -d --build

# View production logs
docker logs -f claude_agent

# Build telegram-mcp TypeScript plugin
cd telegram-mcp && npm run build
```

## Architecture Overview

This is a Telegram bot that acts as a remote interface to Claude Code CLI and SDK, enabling AI-powered coding assistance via Telegram. The project follows DDD (Domain-Driven Design) with four layers:

**Domain** → **Application** → **Infrastructure** → **Presentation**

### Core Functionality

The bot is a **Telegram remote interface to Claude Code**, enabling AI-powered coding assistance via Telegram messages. It provides two backends for interacting with Claude Code:

1. **SDK Backend** (Preferred): Uses `claude-agent-sdk` for direct Python integration with HITL (Human-in-the-Loop) support
   - Located in `infrastructure/claude_code/sdk_service.py`
   - Supports streaming responses and tool execution
   - Integrates with official Claude plugins from `/plugins` directory
   - Provides async permission callbacks (`can_use_tool`) that pause execution until user approves via Telegram
   - Manages agent lifecycle, session persistence, and tool use notifications

2. **CLI Backend** (Fallback): Proxies to `@anthropic-ai/claude-code` npm package
   - Located in `infrastructure/claude_code/proxy_service.py`
   - Runs Claude Code commands in subprocess
   - Includes diagnostics via `infrastructure/claude_code/diagnostics.py`
   - Falls back automatically if SDK is not available

### Request Flow

1. **Telegram message arrives** → `presentation/handlers/messages.py` or `presentation/handlers/streaming.py`
2. **Auth middleware checks user** → `presentation/middleware/auth.py` (verifies against `ALLOWED_USER_ID`)
3. **Handler calls appropriate service**:
   - For Claude Code interactions: `ClaudeAgentSDKService` (preferred) or `ClaudeCodeProxyService` (fallback)
   - For project/context management: `ProjectService`, `ContextService`, `FileBrowserService`
   - For account switching: `AccountService`
   - For legacy features: `BotService` (SSH commands, Docker management, system monitoring)
4. **Response sent back** to Telegram (with streaming support for SDK backend)

**Important**: The bot operates within the working directory set via project management. Use the file browser to navigate to the correct project directory before sending coding requests.

### Key Design Patterns

- **Repository Pattern**: Domain layer defines interfaces (`domain/repositories/`), infrastructure implements them (`infrastructure/persistence/`)
- **Value Objects**: Immutable identifiers like `UserId`, `Role`, `ProjectPath`, `AIProviderConfig` in `domain/value_objects/`
- **Application Services**: Each service handles a specific capability
  - `BotService`: Legacy features (SSH, Docker, system monitoring)
  - `ProjectService`: Project management and working directory switching
  - `ContextService`: Conversation context per project
  - `FileBrowserService`: File system navigation
  - `AccountService`: Authentication mode switching (API Key vs Claude Account)
- **Dependency Injection**: All services are initialized in `main.py:Application.setup()` (~300 lines of setup code)
- **Handler Registration**: Handlers are registered separately in `main.py`
  - Command handlers: `/start`, `/help`, `/clear`, `/stats`
  - Message handlers: Text messages, documents, photos
  - Callback handlers: Inline keyboard button clicks
  - Account handlers: Account management UI
  - Menu handlers: Main menu navigation

### Project and Context Management

The bot manages multiple projects with persistent conversation contexts:

- **Projects**: Stored via `SQLiteProjectRepository`, track working directories and active project per user
- **Contexts**: Stored via `SQLiteProjectContextRepository`, maintain conversation history per project
- **File Browser**: `FileBrowserService` provides file system navigation within `/root/projects`
  - Browse directories via inline keyboard navigation
  - Navigate up/down directory tree
  - Select project directories to work with
  - Creates new project directories when needed

When you switch projects, the bot changes `CLAUDE_WORKING_DIR` and loads the project's conversation context. This allows Claude Code to maintain separate contexts per project.

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

### MCP Integration

**Telegram MCP Server** (`telegram-mcp/`):
- TypeScript-based MCP (Model Context Protocol) server for Claude Code
- Provides tools that Claude can invoke directly:
  - `send_message`: Send text notifications to Telegram (supports HTML formatting)
  - `send_file`: Send files to Telegram with optional captions
  - `send_plan`: Create and send plan documents as .md files
- Allows Claude to proactively send notifications/files to Telegram without bot intervention
- Build with `cd telegram-mcp && npm run build`
- Configured in `.claude/` directory for Claude Code CLI
- Uses `@modelcontextprotocol/sdk` package
- Requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables

### Session Management (Legacy)

The bot maintains two session systems:

1. **Project Contexts** (Current): Per-project conversation history managed by `ContextService`
   - Used for Claude Code interactions via SDK/CLI
   - Stored in `SQLiteProjectContextRepository`
   - Maintains separate context per project

2. **User Sessions** (Legacy): Global per-user sessions for legacy BotService features
   - `Session` entity holds `List[Message]` with role-based messages
   - Sessions persist to SQLite via `SQLiteSessionRepository`
   - AI receives full session context on each `chat_with_session()` call
   - Used for SSH commands, Docker management, and direct Claude API calls

### Account Management

**Account Service** (`application/services/account_service.py`):
- Manages authentication mode switching between:
  - **API Key mode**: Uses `ANTHROPIC_API_KEY` for direct API access (standard Anthropic API)
  - **Claude Account mode**: Uses OAuth credentials from `~/.config/claude/config.json` (claude.ai account)
- Automatically selects compatible models based on auth mode:
  - API Key mode: Access to all API models (including latest sonnet-4)
  - Claude Account mode: Access to web-tier models
- Stores account credentials in SQLite via `SQLiteAccountRepository`
- Handles account deletion and credential validation
- Provides inline keyboard interface in Telegram for account switching
- **Important**: When switching to Claude Account mode, remove `ANTHROPIC_API_KEY` from environment to avoid conflicts

**Account switching UI** (`presentation/handlers/account_handlers.py`):
- 378+ lines of inline keyboard handlers
- Guides user through account setup process
- Validates credentials before switching
- Displays current account status and available models

## Telegram Bot UI

The bot provides a comprehensive inline keyboard interface (`presentation/keyboards/keyboards.py`, 189+ lines):

### Main Menu
- **💬 Чат с Claude Code**: Start coding session with Claude Code SDK/CLI
- **📁 Проекты**: Browse and switch between projects
- **👤 Аккаунт**: Switch between API Key and Claude Account modes
- **⚙️ Настройки**: Configure bot settings
- Legacy menu items: Metrics, Docker, Commands, SSH, GitLab

### Project Browser
- Navigate directory tree with ⬆️ (up) and folder buttons
- Select project directory to set as working directory
- Create new project directories

### Account Management
- View current account status
- Switch between authentication modes
- Display available models based on account type
- Validate credentials before switching

### Conversation Flow
1. User sends message in Telegram
2. Bot checks if user has active project (if not, prompts to select)
3. Message forwarded to Claude Code (SDK or CLI)
4. Streaming response sent back to Telegram
5. HITL requests (tool permissions) shown as inline keyboards for approval

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
- `CLAUDE_PLUGINS` - Comma-separated enabled plugins (default: `commit-commands,code-review,feature-dev,frontend-design,ralph-loop`)

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
- Installs Node.js 20.x for Claude Code CLI and telegram-mcp
- Installs `@anthropic-ai/claude-code` globally via npm
- Clones official plugins from `anthropic/claude-plugins-official` to `/plugins`
- Builds telegram-mcp TypeScript server
- Runs `python main.py` as entrypoint

**Persistent Volumes** (docker-compose.prod.yml):
- `./data` → `/app/data` - SQLite databases
- `./logs` → `/app/logs` - Application logs
- `./projects` → `/root/projects` - User project directories
- `./claude_sessions` → `/root/.claude` - Claude Code session history and context compression
- `./bot_key` → `/app/bot_key:ro` - SSH key for host access (read-only)

## Testing

Tests are in `tests/` with `pytest-asyncio` for async support. Run with `-v` for verbose output or `--tb=short` for shorter tracebacks.

Current test coverage:
- Domain layer: ~40%
- Application layer: ~30%
- 143+ tests passing

## Known Issues & Refactoring Needs

See `REFACTORING.md` for detailed SOLID/DDD improvement plan. Major items:

- **MessageHandlers** (`presentation/handlers/messages.py`, 784+ lines): God class handling multiple concerns
  - Should be split into: `ClaudeCodeMessageHandler`, `DockerMessageHandler`, `FileMessageHandler`, `SettingsMessageHandler`
- **CallbackHandlers** (`presentation/handlers/callbacks.py`, 1194+ lines): God class with too many responsibilities
  - Should be split by domain: `DockerCallbackHandler`, `GitLabCallbackHandler`, `SystemCallbackHandler`, `SettingsCallbackHandler`
- **State management**: 14+ state dictionaries scattered across handlers
  - Need unified `UserStateManager` service
  - Current state dicts: `waiting_for_docker_command`, `waiting_for_project_name`, `waiting_for_gitlab_token`, etc.
- **Dependency injection**: Services are passed as constructor params but main.py has ~300 lines of setup
  - Consider dependency injection container (e.g., `dependency-injector` library)

## Proxy Configuration

The project uses a Squid proxy for external HTTP/HTTPS requests. Local network access requires `NO_PROXY`:

```bash
export NO_PROXY="localhost,127.0.0.1,192.168.0.0/16"
```

Git commands to local GitLab server may fail without proper proxy bypass. The bot automatically configures this on startup.

## Debugging

### Enabling Debug Mode

Set `DEBUG=true` in environment to enable verbose logging:
```bash
DEBUG=true python main.py
```

### Checking Claude Code Diagnostics

The bot runs diagnostics on startup (`infrastructure/claude_code/diagnostics.py`):
- Checks if `claude` CLI is available
- Verifies SDK installation
- Tests plugin loading
- Validates working directory permissions

### Common Issues

**SDK not available**: Install with `pip install claude-agent-sdk` or bot will fallback to CLI mode

**Permission errors in Docker**: Ensure volumes are mounted with correct permissions
```bash
chmod -R 755 ./data ./logs ./projects
```

**Claude Code sessions not persisting**: Verify `./claude_sessions` volume is mounted to `/root/.claude`

**MCP tools not working**: Rebuild telegram-mcp after changes
```bash
cd telegram-mcp && npm run build
```

**Account switching fails**: Check that `ANTHROPIC_API_KEY` is removed from environment when using Claude Account mode

### Log Locations

- **Application logs**: `./logs/bot.log` (or `/app/logs/bot.log` in container)
- **Docker logs**: `docker logs -f claude_agent`
- **Claude Code logs**: Check `~/.claude/logs` or environment-specific log path
