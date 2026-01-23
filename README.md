# Claude DevOps Bot

> Advanced Telegram bot for server management using Claude AI with natural language processing.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![DDD](https://img.shields.io/badge/Architecture-DDD-green.svg)](https://martinfowler.com/tags/domain%20driven%20design.html)
[![SOLID](https://img.shields.io/badge/Principles-SOLID-brightgreen.svg)](https://en.wikipedia.org/wiki/SOLID)

## Features

- 🤖 **AI-Powered**: Natural language interface to Claude 3.5 Sonnet
- 🔧 **Command Execution**: Execute server commands via SSH with approval workflow
- 📊 **System Monitoring**: Real-time CPU, memory, disk metrics
- 🐳 **Docker Management**: List, start, stop, restart containers
- 💬 **Chat Sessions**: Persistent conversation history with context
- 👥 **Multi-User**: Role-based access control (Admin, DevOps, User, ReadOnly)
- 🛡️ **Safety Checks**: Dangerous command warnings and approval
- 📝 **Command History**: Track all executed commands
- 🔄 **Auto-Deploy**: GitLab CI/CD integration

## Architecture

This project follows **Domain-Driven Design (DDD)** and **SOLID** principles:

```
ubuntu_claude/
├── domain/               # Business logic (DDD)
│   ├── entities/        # User, Session, Command, Message
│   ├── value_objects/   # UserId, Role, Permission
│   ├── repositories/    # Repository interfaces
│   └── services/        # Domain service interfaces
├── application/          # Use cases
│   └── services/        # BotService (orchestration)
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
    └── config/         # Settings
```

### SOLID Principles

- **S**ingle Responsibility: Each class has one reason to change
- **O**pen/Closed: Extended through interfaces, not modification
- **L**iskov Substitution: Interfaces are properly implemented
- **I**nterface Segregation: Focused, minimal interfaces
- **D**ependency Inversion: Depends on abstractions, not concretions

### DDD Layers

| Layer | Responsibility |
|-------|----------------|
| **Domain** | Core business logic, entities, value objects |
| **Application** | Use case orchestration (BotService) |
| **Infrastructure** | External integrations (SSH, AI, DB) |
| **Presentation** | Telegram bot interface |

## Quick Start

### 1. Clone and Configure

```bash
git clone http://192.168.0.116:8088/root/ubuntu_claude.git
cd ubuntu_claude
cp .env.example .env
```

### 2. Edit `.env`

```ini
TELEGRAM_TOKEN=your_bot_token_from_botfather
ANTHROPIC_API_KEY=sk-ant-your-key
ALLOWED_USER_ID=664382290
HOST_USER=root
```

### 3. Generate SSH Keys

```bash
ssh-keygen -t ed25519 -f ./bot_key -N ""
cat ./bot_key.pub >> ~/.ssh/authorized_keys
```

### 4. Run with Docker

```bash
docker-compose up -d --build
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot |
| `/help` | Show help |
| `/clear` | Clear chat history |
| `/stats` | User statistics |

## Menu Buttons

| Button | Action |
|--------|--------|
| 💬 Chat | Talk with Claude AI |
| 📊 Metrics | System metrics |
| 🐳 Docker | Container list |
| 📝 Commands | Command history |
| 🗑️ Clear | Clear history |

## Usage Examples

### Natural Language Commands

```
User: Check disk usage
Bot: [Shows disk usage]
User: Restart nginx container
Bot: [Proposes docker restart command]
User: [Approves]
Bot: [Executes and shows result]
```

### Direct Commands

```
User: Install htop
Bot: [Proposes: apt install htop]
User: [Approves]
Bot: [Executes installation]
```

## Configuration

### Environment Variables

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

## CI/CD

The project includes GitLab CI/CD pipeline for automatic deployment:

```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy
```

Push to `main` branch triggers:
1. Build Docker image
2. Transfer to server via SSH
3. Deploy with docker-compose

## Development

### Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run Locally

```bash
python main.py
```

### Run Tests

```bash
pytest tests/
```

### Code Style

```bash
black application/ domain/ infrastructure/ presentation/ shared/
mypy application/ domain/ infrastructure/ presentation/ shared/
```

## API Reference

### BotService

Main application service orchestrating all operations.

```python
async def chat(user_id: int, message: str) -> tuple[str, List[Dict]]
async def execute_command(command_id: str) -> CommandExecutionResult
async def get_system_info() -> Dict
async def get_user_stats(user_id: int) -> Dict
```

### Repositories

```python
class UserRepository(ABC):
    async def find_by_id(self, user_id: UserId) -> Optional[User]
    async def save(self, user: User) -> None

class SessionRepository(ABC):
    async def find_active_by_user(self, user_id: UserId) -> Optional[Session]
    async def save(self, session: Session) -> None

class CommandRepository(ABC):
    async def save(self, command: Command) -> None
    async def find_by_user(self, user_id: int) -> List[Command]
```

## Security

- ✅ SSH key-based authentication
- ✅ User authorization via ALLOWED_USER_ID
- ✅ Dangerous command warnings
- ✅ Command approval workflow
- ✅ Role-based access control
- ✅ Audit logging

## Troubleshooting

### Bot doesn't respond

1. Check `logs/bot.log`
2. Verify environment variables
3. Ensure SSH key is valid

### SSH connection fails

1. Verify host accessibility
2. Check SSH key permissions
3. Ensure public key is in `authorized_keys`

### Database errors

1. Check `data/` directory permissions
2. Ensure SQLite is available

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

Built with:
- [Aiogram](https://aiogram.dev/) - Telegram bot framework
- [Anthropic](https://www.anthropic.com/) - Claude AI API
- [psutil](https://psutil.readthedocs.io/) - System monitoring

---

**Made with ❤️ for DevOps automation**
