from dataclasses import dataclass
from typing import List, Optional
import os
from dotenv import load_dotenv
from domain.value_objects import AIProviderConfig

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
        allowed_user_ids = [
            int(id.strip()) for id in allowed_ids_str.split(",") if id.strip()
        ]
        return cls(token=token, allowed_user_ids=allowed_user_ids)


@dataclass
class AnthropicConfig:
    """Anthropic Claude API configuration

    Supports both Anthropic's official API and compatible APIs like ZhipuAI.
    For ZhipuAI, set ANTHROPIC_BASE_URL to https://open.bigmodel.cn/api/anthropic
    and use ANTHROPIC_AUTH_TOKEN instead of ANTHROPIC_API_KEY.

    This is a facade over AIProviderConfig for backward compatibility.
    """

    _provider_config: AIProviderConfig

    @classmethod
    def from_env(cls) -> "AnthropicConfig":
        # Support both ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN
        # For ZhipuAI, use ANTHROPIC_AUTH_TOKEN
        api_key = os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY is required")

        base_url = os.getenv("ANTHROPIC_BASE_URL")
        haiku_model = os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL")
        sonnet_model = os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL")
        opus_model = os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL")
        default_model = os.getenv("ANTHROPIC_MODEL")
        max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))

        provider_config = AIProviderConfig.from_env(
            api_key=api_key,
            base_url=base_url,
            haiku_model=haiku_model,
            sonnet_model=sonnet_model,
            opus_model=opus_model,
            default_model=default_model,
            max_tokens=max_tokens,
        )

        return cls(_provider_config=provider_config)

    @property
    def api_key(self) -> str:
        return self._provider_config.api_key

    @property
    def base_url(self) -> Optional[str]:
        return self._provider_config.base_url

    @property
    def auth_token(self) -> Optional[str]:
        return self._provider_config.api_key

    @property
    def model(self) -> str:
        return self._provider_config.default_model

    @property
    def haiku_model(self) -> str:
        return self._provider_config.model_config.haiku

    @property
    def sonnet_model(self) -> str:
        return self._provider_config.model_config.sonnet

    @property
    def opus_model(self) -> str:
        return self._provider_config.model_config.opus

    @property
    def max_tokens(self) -> int:
        return self._provider_config.max_tokens

    @property
    def provider_config(self) -> AIProviderConfig:
        """Get the underlying provider configuration"""
        return self._provider_config


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
            key_path=os.getenv("SSH_KEY_PATH", "/app/bot_key"),
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
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
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
            project_id=(
                int(os.getenv("GITLAB_PROJECT_ID"))
                if os.getenv("GITLAB_PROJECT_ID")
                else None
            ),
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
            alert_threshold_disk=float(os.getenv("ALERT_THRESHOLD_DISK", "90.0")),
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
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# Global settings instance
settings = Settings.from_env()
