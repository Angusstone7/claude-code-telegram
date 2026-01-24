# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Claude DevOps Bot** - a Telegram bot for server management using Claude AI with natural language processing. The project follows Domain-Driven Design (DDD) and SOLID principles.

## Development Commands

```bash
# Local development
python main.py

# Testing
pytest tests/

# Code formatting
black application/ domain/ infrastructure/ presentation/ shared/

# Type checking
mypy application/ domain/ infrastructure/ presentation/ shared/

# Docker deployment
docker-compose up -d --build
```

## Architecture: DDD + SOLID

The codebase is organized into four distinct layers:

```
ubuntu_claude/
├── domain/               # Business logic (core entities)
│   ├── entities/        # User, Session, Command, Message
│   ├── value_objects/   # UserId, Role, Permission
│   ├── repositories/    # Repository interfaces
│   └── services/        # Domain service interfaces
├── application/          # Use cases & orchestration
│   └── services/        # BotService (main coordinator)
├── infrastructure/       # External dependencies
│   ├── persistence/     # SQLite repositories
│   ├── ssh/            # SSH command executor
│   ├── messaging/      # Claude AI service
│   └── monitoring/     # System metrics
├── presentation/         # Telegram interface
│   ├── handlers/       # Commands, messages, callbacks
│   ├── keyboards/      # Inline keyboards
│   └── middleware/     # Auth middleware
└── shared/              # Common utilities
    └── config/         # Settings management
```

### Layer Responsibilities

| Layer | Responsibility |
|-------|----------------|
| **Domain** | Core business logic, entities, value objects, repository interfaces |
| **Application** | Use case orchestration via `BotService` |
| **Infrastructure** | External integrations (SSH, Claude AI, SQLite) |
| **Presentation** | Telegram bot interface (handlers, keyboards, middleware) |

## Key Components

### Main Entry Point
- **`main.py`**: Contains the `Application` class with initialization, setup, and lifecycle management
- Entry point: `asyncio.run(main())` starts the bot polling

### Core Application Service
- **`BotService`** (`application/services/bot_service.py`): Central orchestrator coordinating all operations
  - User management and authorization
  - Session management with persistent history
  - AI chat integration with Claude
  - Command execution workflow
  - Multi-user support with role-based access

### Domain Entities
- **User**: Core entity with role-based permissions (Admin, DevOps, User, ReadOnly)
- **Session**: Persistent conversation history with context
- **Command**: Commands with approval workflow and execution tracking
- **Message**: Chat message with roles (user/assistant)

### Infrastructure Layer
- **ClaudeAIService** (`infrastructure/messaging/`): Integration with Anthropic API (claude-3-5-sonnet-20241022)
- **SSHCommandExecutor** (`infrastructure/ssh/`): Secure command execution via AsyncSSH
- **SQLite repositories** (`infrastructure/persistence/`): Data persistence for all entities
- **System monitoring** (`infrastructure/monitoring/`): CPU, memory, disk metrics via psutil

## Technology Stack

- **Python**: 3.11+
- **Bot Framework**: Aiogram 3.10.0
- **AI Integration**: Anthropic Claude API (anthropic>=0.40.0)
- **Database**: SQLite with aiosqlite (async SQLite driver)
- **SSH**: AsyncSSH 2.17.0
- **System Monitoring**: psutil 6.0.0+
- **Deployment**: Docker with docker-compose

## Configuration

Configuration is managed through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_TOKEN` | Bot token from @BotFather | *required* |
| `ANTHROPIC_API_KEY` | Claude API key | *required* |
| `ALLOWED_USER_ID` | Allowed Telegram user ID | *required* |
| `HOST_USER` | SSH user | `root` |
| `SSH_HOST` | SSH host | `host.docker.internal` |
| `SSH_PORT` | SSH port | `22` |
| `DATABASE_URL` | Database path | `sqlite:///./data/bot.db` |
| `LOG_LEVEL` | Logging level | `INFO` |

### User Roles

| Role | Permissions |
|------|-------------|
| **admin** | All permissions |
| **devops** | Execute commands, Docker, GitLab, Metrics, Schedule tasks |
| **user** | Execute commands, View logs, Manage sessions, View metrics |
| **readonly** | View logs, View metrics |

## Key Workflows

### Natural Language Command Flow
1. User sends natural language command
2. Bot parses with Claude AI
3. Proposes command for approval
4. User approves or rejects
5. Command executes via SSH
6. Results returned to user

### Multi-User Session Management
1. User initiates session
2. Session created with UUID
3. Chat history persists in SQLite
4. Context maintained across interactions
5. Sessions can be cleared on request

## Deployment

### Docker Setup
- **Dockerfile**: Python 3.11-slim with openssh-client
- **docker-compose.yml**: Main container with SSH key volume mount
- **docker-compose.prod.yml**: Production deployment configuration
- Uses `host.docker.internal` for host access from container

### CI/CD Pipeline
- **GitLab CI/CD**: Automated deployment on main/master push
- Stages: Build → Deploy
- Features: Docker image building, SSH deployment, automatic SSH key generation, backup and rollback capability

## Security Features

- SSH key-based authentication for command execution
- User authorization via ALLOWED_USER_ID
- Role-based access control (4 tiers)
- Dangerous command warnings with approval workflow
- Audit logging of all executed commands

## Important Design Decisions

1. **DDD Architecture**: Clear separation of concerns with domain logic isolated from infrastructure
2. **Async-first**: Full async/await implementation for performance
3. **Repository Pattern**: Abstracted data access for testability
4. **Dependency Injection**: Services injected for loose coupling
5. **Event-driven**: Telegram callbacks and message handlers
6. **Stateful**: Persistent sessions and command history
7. **Security-first**: SSH key auth, approval workflows, RBAC
