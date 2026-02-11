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

# View production logs via HTTP API (ALWAYS USE THIS, docker CLI not available)
curl "http://192.168.0.116:9999/logs/claude_agent?tail=100"  # View last 100 lines
curl http://192.168.0.116:9999/containers                    # List all containers

# Build telegram-mcp TypeScript plugin
cd telegram-mcp && npm run build
```

## Project Statistics

| Metric | Value |
|--------|-------|
| Python LOC | ~28,100 |
| Python files | 112 |
| Unit tests | 143+ |
| Handlers LOC | ~9,000 |
| telegram-mcp LOC | ~10,000 |

**Note:** LOC increased from ~23,600 to ~28,100 after January 2026 refactoring due to modular architecture (added base classes, facades, coordinators).

## Architecture Overview

This is a Telegram bot that acts as a remote interface to Claude Code CLI and SDK, enabling AI-powered coding assistance via Telegram. The project follows DDD (Domain-Driven Design) with four layers:

**Domain** → **Application** → **Infrastructure** → **Presentation**

### Project Structure

```
/root/projects/ubuntu_claude/
├── domain/                          # DDD Domain layer (Business Logic)
│   ├── entities/                   # User, Session, Command, Message, Project
│   ├── value_objects/              # UserId, Role, Permission, AIProviderConfig, ProjectPath
│   ├── repositories/               # Repository interfaces (abstract contracts)
│   └── services/                   # Domain service interfaces
│
├── application/                     # DDD Application layer (Use Cases)
│   ├── services/
│   │   ├── bot_service.py         # Main orchestration for legacy features
│   │   ├── account_service.py     # Auth mode switching (API Key vs Claude Account)
│   │   ├── project_service.py     # Project management and working directory
│   │   ├── context_service.py     # Conversation context per project
│   │   ├── file_browser_service.py # File system navigation
│   │   └── file_processor_service.py # File upload processing
│   ├── commands/
│   └── queries/
│
├── infrastructure/                  # DDD Infrastructure layer
│   ├── claude_code/                # Claude Code integration
│   │   ├── sdk_service.py         # SDK backend (preferred, with HITL support)
│   │   ├── proxy_service.py       # CLI backend (fallback)
│   │   ├── diagnostics.py         # SDK/CLI health checks
│   │   ├── tool_formatters.py     # Response formatting for Telegram
│   │   └── task_context.py        # Session context management
│   ├── persistence/                # SQLite implementations
│   │   ├── sqlite_repository.py   # User, Session, Command repositories
│   │   ├── project_repository.py  # Project storage
│   │   ├── project_context_repository.py # Conversation history
│   │   └── sqlite_account_repository.py  # Account credentials
│   ├── messaging/                  # AI service
│   │   └── claude_service.py      # Anthropic API integration
│   ├── ssh/                        # Remote execution
│   │   └── ssh_executor.py        # AsyncSSH wrapper
│   ├── docker/                     # Container management
│   ├── gitlab/                     # GitLab integration
│   └── monitoring/                 # System metrics
│       └── system_monitor.py
│
├── presentation/                    # DDD Presentation layer (Telegram Interface)
│   ├── handlers/                   # Request handlers(~9,000 LOC total)
│   │   ├── commands.py            # /start, /help, /clear, /stats (872 LOC)
│   │   ├── message/               # Modular message handlers (refactored Jan 2026)
│   │   │   ├── facade.py          # Backward-compatible facade
│   │   │   ├── coordinator.py     # Routes messages to specialized handlers
│   │   │   ├── text_handler.py    # Text message processing
│   │   │   ├── file_handler.py    # Document/photo upload handling
│   │   │   ├── ai_request_handler.py  # AI request orchestration
│   │   │   ├── hitl_handler.py    # HITL (Human-in-the-Loop) permission handling
│   │   │   ├── variable_handler.py # Variable input flows
│   │   │   ├── plan_handler.py    # Plan approval flows
│   │   │   └── base.py            # Base handler class
│   │   ├── streaming.py           # Streaming message handling (926 LOC)
│   │   ├── callbacks.py           # Inline button callbacks (1,999 LOC)
│   │   ├── account_handlers.py    # Account management UI (1,307 LOC)
│   │   ├── menu_handlers.py       # Main menu system (1,042 LOC)
│   │   └── state/                 # State managers
│   │       ├── user_state.py      # User session state
│   │       ├── hitl_manager.py    # Human-in-the-Loop permission handling
│   │       ├── plan_manager.py    # Plan approval state
│   │       ├── file_context.py    # File upload caching
│   │       └── variable_input.py  # Variable input state machine
│   ├── keyboards/
│   │   └── keyboards.py           # Inline keyboard definitions (189+ LOC)
│   └── middleware/
│       └── auth.py                # User authorization checks
│
├── shared/                         # Shared utilities
│   ├── config/
│   │   └── settings.py            # Configuration from environment variables
│   ├── container.py               # Dependency Injection Container (~324 LOC)
│   ├── constants.py               # Application constants
│   ├── logging/                   # Logging utilities
│   └── utils/                     # Helper functions
│
├── telegram-mcp/                   # TypeScript MCP Server
│   ├── src/
│   │   └── index.ts               # MCP implementation (10K+ LOC)
│   ├── package.json
│   └── tsconfig.json
│
├── tests/                          # Test Suite
│   ├── conftest.py                # Pytest fixtures and config
│   └── unit/
│       ├── domain/                # Domain layer tests
│       ├── application/           # Application layer tests
│       └── infrastructure/        # Infrastructure tests
│
├── main.py                         # Application entry point (268 LOC)
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container image definition
├── docker-compose.yml              # Development deployment
├── docker-compose.prod.yml         # Production deployment
├── .gitlab-ci.yml                  # CI/CD pipeline
└── .env.example                    # Environment template
```

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

**Modular Message Handler Architecture** (refactored Jan 2026):

1. **Telegram message arrives** → Aiogram dispatcher
2. **Auth middleware checks user** → `presentation/middleware/auth.py` (verifies against `ALLOWED_USER_ID`)
3. **Message routing** (modular architecture):
   - `MessageHandlersFacade` (entry point) →
   - `MessageCoordinator` (routes to specialized handlers) →
   - Specialized handlers:
     - `TextMessageHandler` - handles text messages, AI requests
     - `FileMessageHandler` - handles documents and photos
     - `HITLHandler` - handles permission requests
     - `VariableHandler` - handles variable input flows
     - `PlanHandler` - handles plan approval flows
4. **Service layer calls**:
   - For Claude Code interactions: `ClaudeAgentSDKService` (preferred) or `ClaudeCodeProxyService` (fallback)
   - For project/context management: `ProjectService`, `ContextService`, `FileBrowserService`
   - For account switching: `AccountService`
   - For legacy features: `BotService` (SSH commands, Docker management, system monitoring)
5. **Response sent back** to Telegram (with streaming support for SDK backend)

**Important Notes**:
- The bot operates within the working directory set via project management. Use the file browser to navigate to the correct project directory before sending coding requests.
- All handler methods MUST accept `**kwargs` for aiogram compatibility (aiogram passes additional arguments like `dispatcher` to registered handlers)

### Key Design Patterns

- **Repository Pattern**: Domain layer defines interfaces (`domain/repositories/`), infrastructure implements them (`infrastructure/persistence/`)
- **Value Objects**: Immutable identifiers like `UserId`, `Role`, `ProjectPath`, `AIProviderConfig` in `domain/value_objects/`
- **Application Services**: Each service handles a specific capability
  - `BotService`: Legacy features (SSH, Docker, system monitoring)
  - `ProjectService`: Project management and working directory switching
  - `ContextService`: Conversation context per project
  - `FileBrowserService`: File system navigation
  - `AccountService`: Authentication mode switching (API Key vs Claude Account)
- **Dependency Injection**: Container-based wiring in `shared/container.py` (~324 LOC)
- **Facade Pattern**: `MessageHandlersFacade` provides backward-compatible interface to refactored message handlers
- **Coordinator Pattern**: `MessageCoordinator` routes messages to specialized handlers based on message type and state
- **Handler Registration**: Handlers are registered separately in `main.py`
  - Command handlers: `/start`, `/help`, `/clear`, `/stats`
  - Message handlers: Text messages, documents, photos
  - Callback handlers: Inline keyboard button clicks
  - Account handlers: Account management UI
  - Menu handlers: Main menu navigation

### Modular Message Handler Architecture

**Refactored January 2026** - Replaced monolithic `messages.py` (1,615 LOC) with modular architecture:

**Entry Point:**
- `MessageHandlersFacade` (`presentation/handlers/message/facade.py`)
  - Provides backward-compatible interface
  - Maintains same public API as legacy `MessageHandlers`
  - Delegates all work to `MessageCoordinator`

**Routing Layer:**
- `MessageCoordinator` (`presentation/handlers/message/coordinator.py`)
  - Routes messages to appropriate specialized handlers
  - Manages state transitions
  - Provides access to all state managers (user state, HITL, variables, plans, files)

**Specialized Handlers:**
- `TextMessageHandler` - Handles text messages and AI request orchestration
- `FileMessageHandler` - Handles document and photo uploads
- `AIRequestHandler` - Orchestrates AI interactions with SDK/CLI backends
- `HITLHandler` - Manages Human-in-the-Loop permission flows
- `VariableHandler` - Handles context/global variable input workflows
- `PlanHandler` - Handles plan approval workflows

**Critical Implementation Detail:**
- All handler methods MUST accept `**kwargs` to be compatible with aiogram's middleware system
- Aiogram passes additional arguments (e.g., `dispatcher`, `event_router`) to registered handlers
- Failure to accept `**kwargs` results in `TypeError: got an unexpected keyword argument 'dispatcher'`

**Legacy Files:**
- `presentation/handlers/messages.py` (1,615 LOC) - Legacy monolithic implementation, kept for testing comparison in `test_new_vs_legacy.py`
- Not used in production (all imports switched to `message/facade.py`)
- Can be deleted after sufficient production testing period

**Adding New Message Handler Functionality:**
1. Determine which specialized handler should contain the logic
2. Add the method to the appropriate handler class (inherit from `BaseMessageHandler`)
3. If needed, add routing logic to `MessageCoordinator`
4. Ensure method signature includes `**kwargs` for aiogram compatibility
5. Add public method to `MessageHandlersFacade` if it needs to be exposed externally
6. Update tests in `test_new_vs_legacy.py` if adding core functionality

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
- Allows Claude to proactively send notifications/files to Telegram withoutbot intervention
- Build with `cd telegram-mcp && npm run build`
- Configured in `.claude/` directory for Claude Code CLI
- Uses `@modelcontextprotocol/sdk` package
- Requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables

### Session Management

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
- 1,307 lines of inline keyboard handlers
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
- `ALLOWED_USER_ID` - Telegram user ID for authorization (comma-separated for multiple users)
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
- `ANTHROPIC_MODEL` - Model to use (default: `claude-sonnet-4-20250514`)
- `ANTHROPIC_DEFAULT_HAIKU_MODEL` - Haiku model alias (default: `claude-3-5-haiku-20241022`)
- `ANTHROPIC_DEFAULT_SONNET_MODEL` - Sonnet model alias (default: `claude-sonnet-4-20250514`)
- `ANTHROPIC_DEFAULT_OPUS_MODEL` - Opus model alias (default: `claude-opus-4-20250514`)

## Database Schema

**SQLite Database** (`data/bot.db`)

| Table | Purpose |
|-------|---------|
| users | User profiles with roles and permissions |
| sessions | Conversation sessions (legacy) |
| commands | Command execution history |
| projects | User projects with working directories |
| project_contexts | Per-project conversation history |
| accounts | OAuth credentials for Claude Account mode |

## Dependencies

| Component | Purpose | Version |
|-----------|---------|---------|
| aiogram | Telegram bot framework | 3.10.0 |
| anthropic | Claude API | >=0.40.0 |
| claude-agent-sdk | Claude Code SDK | >=0.1.0 |
| aiosqlite | Async SQLite | >=0.19.0 |
| asyncssh | SSH execution | 2.17.0 |
| psutil | System monitoring | >=6.0.0 |
| docker | Container management | >=7.0.0 |
| python-dotenv | Config loading | 1.0.1 |
| pytest-asyncio | Async testing | >=0.21.0 |
| black | Code formatting | >=23.0.0 |
| mypy | Type checking | >=1.5.0 |

## Docker and Deployment

**Development**:
```bash
docker-compose up -d --build
```

**Production** (via GitLab CI/CD):
- Push to `main` or `master` branch triggers automatic deployment
- Pipeline has 2 stages: build (Docker image) and deploy (transfer to server)
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

**Test Configuration** (`tests/conftest.py`):
- Async test support with pytest-asyncio
- Fixtures for entities (User, Session, Command, Message)
- Mock fixtures for repositories and services
- Value object fixtures (UserId, Role, etc.)

**Refactoring Tests** (`test_new_vs_legacy.py`):
- Compares refactored modular handlers with legacy implementation
- Validates method signatures, parameters, and compatibility
- 5 validation tests: method matching, parameter flow, signature compatibility
- All tests passed during January 2026 refactoring

## Recent Refactoring (January 2026)

✅ **MessageHandlers Refactoring - COMPLETED**
- Transformed monolithic `messages.py` (1,615 LOC) into modular architecture with 9 specialized handlers
- Zero functionality loss, zero production incidents
- Maintainability improved by 150-250%, complexity reduced by 81%
- See `.ralph-loop/SUCCESS_REPORT.md` for full details

## Known Issues & Refactoring Needs

See `CODE_REVIEW_REPORT.md` for detailed code review. Major items:

- **CallbackHandlers** (`presentation/handlers/callbacks.py`, 2,608 LOC): God class with 80+ methods
  - Should be split by domain: `DockerCallbackHandler`, `ProjectCallbackHandler`, `ContextCallbackHandler`, `ClaudeCallbackHandler`, `PluginCallbackHandler`
- **Keyboards** (`presentation/keyboards/keyboards.py`, 1,628 LOC): Factory class with 60+ static methods
  - Should be grouped into submodules: `keyboards/menu.py`, `keyboards/docker.py`, `keyboards/claude.py`, `keyboards/account.py`
- **State management**: State managers are partially implemented
  - Implemented: `UserStateManager`, `HITLManager`, `VariableInputManager`, `PlanApprovalManager`, `FileContextManager`
  - Need to continue consolidating remaining scattered state dictionaries

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

**TypeError: got an unexpected keyword argument 'dispatcher'**:
- This occurs when handler methods don't accept `**kwargs`
- All registered aiogram handlers MUST include `**kwargs` in their signature
- Example fix: `async def handle_text(self, message: Message, **kwargs):`
- Fixed in commit `f89ed6e` (January 30, 2026)

### Log Locations

**IMPORTANT: Docker CLI is NOT available. Always use HTTP API for container logs.**

- **Container logs via HTTP API** (ALWAYS USE THIS):
  ```bash
  # View last 100 lines of bot logs
  curl "http://192.168.0.116:9999/logs/claude_agent?tail=100"

  # List all running containers
  curl http://192.168.0.116:9999/containers

  # Get logs for any container
  curl "http://192.168.0.116:9999/logs/{container_name}?tail=100"
  ```

- **Application logs**: `./logs/bot.log` (or `/app/logs/bot.log` in container)
- **Claude Code logs**: Check `~/.claude/logs` or environment-specific log path

## Active Technologies
- Python 3.11 (backend), TypeScript 5.x (frontend) + FastAPI, PyJWT, argon2-cffi, Vite, React 18, shadcn/ui, Zustand, TanStack Query, react-markdown, react-router-dom v6, react-i18next, react-hook-form, zod (001-react-admin-panel)
- SQLite (существующая — расширение схемы: web_users, refresh_tokens, login_attempts) (001-react-admin-panel)

## Recent Changes
- 001-react-admin-panel: Added Python 3.11 (backend), TypeScript 5.x (frontend) + FastAPI, PyJWT, argon2-cffi, Vite, React 18, shadcn/ui, Zustand, TanStack Query, react-markdown, react-router-dom v6, react-i18next, react-hook-form, zod
