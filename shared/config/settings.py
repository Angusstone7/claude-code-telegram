from dataclasses import dataclass
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    token: str
    allowed_user_ids: List[int]

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_TOKEN is required")
        allowed_ids_str = os.getenv("ALLOWED_USER_ID", "")
        allowed_user_ids = [int(id.strip()) for id in allowed_ids_str.split(",") if id.strip()]
        return cls(token=token, allowed_user_ids=allowed_user_ids)


@dataclass
class AnthropicConfig:
    """Anthropic Claude API configuration"""
    api_key: str
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4096

    @classmethod
    def from_env(cls) -> "AnthropicConfig":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))
        return cls(api_key=api_key, model=model, max_tokens=max_tokens)


@dataclass
class SSHConfig:
    """SSH configuration for remote command execution"""
    host: str = "host.docker.internal"
    port: int = 22
    user: str = "root"
    key_path: str = "/app/bot_key"

    @classmethod
    def from_env(cls) -> "SSHConfig":
        return cls(
            host=os.getenv("SSH_HOST", "host.docker.internal"),
            port=int(os.getenv("SSH_PORT", "22")),
            user=os.getenv("HOST_USER", "root"),
            key_path=os.getenv("SSH_KEY_PATH", "/app/bot_key")
        )


@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = "sqlite:///./data/bot.db"
    echo: bool = False

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        return cls(
            url=os.getenv("DATABASE_URL", "sqlite:///./data/bot.db"),
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true"
        )


@dataclass
class GitLabConfig:
    """GitLab CI/CD configuration"""
    url: str = "https://gitlab.com"
    token: Optional[str] = None
    project_id: Optional[int] = None

    @classmethod
    def from_env(cls) -> "GitLabConfig":
        return cls(
            url=os.getenv("GITLAB_URL", "https://gitlab.com"),
            token=os.getenv("GITLAB_TOKEN"),
            project_id=int(os.getenv("GITLAB_PROJECT_ID")) if os.getenv("GITLAB_PROJECT_ID") else None
        )


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    enabled: bool = True
    metrics_port: int = 9090
    alert_threshold_cpu: float = 80.0
    alert_threshold_memory: float = 85.0
    alert_threshold_disk: float = 90.0

    @classmethod
    def from_env(cls) -> "MonitoringConfig":
        return cls(
            enabled=os.getenv("MONITORING_ENABLED", "true").lower() == "true",
            metrics_port=int(os.getenv("METRICS_PORT", "9090")),
            alert_threshold_cpu=float(os.getenv("ALERT_THRESHOLD_CPU", "80.0")),
            alert_threshold_memory=float(os.getenv("ALERT_THRESHOLD_MEMORY", "85.0")),
            alert_threshold_disk=float(os.getenv("ALERT_THRESHOLD_DISK", "90.0"))
        )


@dataclass
class Settings:
    """Application settings"""
    telegram: TelegramConfig
    anthropic: AnthropicConfig
    ssh: SSHConfig
    database: DatabaseConfig
    gitlab: GitLabConfig
    monitoring: MonitoringConfig
    debug: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            telegram=TelegramConfig.from_env(),
            anthropic=AnthropicConfig.from_env(),
            ssh=SSHConfig.from_env(),
            database=DatabaseConfig.from_env(),
            gitlab=GitLabConfig.from_env(),
            monitoring=MonitoringConfig.from_env(),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )


# Global settings instance
settings = Settings.from_env()
