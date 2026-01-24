"""AI Provider configuration value objects"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re


class AIProviderType(Enum):
    """Supported AI provider types"""

    ANTHROPIC = "anthropic"
    ZHIPU_AI = "zhipu_ai"
    CUSTOM = "custom"


@dataclass
class AIModelConfig:
    """AI model configuration"""

    haiku: str
    sonnet: str
    opus: str
    default: str

    def get_model(self, tier: str) -> str:
        """Get model by tier (haiku/sonnet/opus/default)"""
        return getattr(self, tier, self.default)


@dataclass
class AIProviderConfig:
    """AI Provider configuration value object

    Immutable configuration for AI providers following DDD principles.
    Supports multiple providers with proper validation.
    """

    provider_type: AIProviderType
    api_key: str
    base_url: Optional[str] = None
    model_config: Optional[AIModelConfig] = None
    max_tokens: int = 4096

    def __post_init__(self):
        """Validate configuration after initialization"""
        if not self.api_key:
            raise ValueError("api_key is required")

        if self.base_url:
            self._validate_url(self.base_url)

        # Set provider-specific defaults
        if self.model_config is None:
            self.model_config = self._get_default_model_config()

    @staticmethod
    def _validate_url(url: str) -> None:
        """Validate URL format"""
        if not re.match(r"^https?://", url):
            raise ValueError(f"Invalid URL format: {url}")

    def _get_default_model_config(self) -> AIModelConfig:
        """Get default model configuration based on provider type"""
        if self.provider_type == AIProviderType.ZHIPU_AI:
            return AIModelConfig(
                haiku="glm-4.5-air", sonnet="glm-4.7", opus="glm-4.7", default="glm-4.7"
            )
        # Default to Anthropic
        return AIModelConfig(
            haiku="claude-3-5-haiku-20241022",
            sonnet="claude-3-5-sonnet-20241022",
            opus="claude-3-5-sonnet-20241022",
            default="claude-3-5-sonnet-20241022",
        )

    @classmethod
    def from_env(
        cls,
        api_key: str,
        base_url: Optional[str] = None,
        haiku_model: Optional[str] = None,
        sonnet_model: Optional[str] = None,
        opus_model: Optional[str] = None,
        default_model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> "AIProviderConfig":
        """Create configuration from environment variables

        Factory method that determines provider type based on base_url.
        """
        # Detect provider type from base_url
        if base_url:
            if "zhipu" in base_url.lower() or "bigmodel" in base_url.lower():
                provider_type = AIProviderType.ZHIPU_AI
            else:
                provider_type = AIProviderType.CUSTOM
        else:
            provider_type = AIProviderType.ANTHROPIC

        # Create model config
        model_config = None
        if any([haiku_model, sonnet_model, opus_model, default_model]):
            model_config = AIModelConfig(
                haiku=haiku_model or "claude-3-5-haiku-20241022",
                sonnet=sonnet_model or "claude-3-5-sonnet-20241022",
                opus=opus_model or "claude-3-5-sonnet-20241022",
                default=default_model or "claude-3-5-sonnet-20241022",
            )

        return cls(
            provider_type=provider_type,
            api_key=api_key,
            base_url=base_url,
            model_config=model_config,
            max_tokens=max_tokens,
        )

    @property
    def default_model(self) -> str:
        """Get the default model for this provider"""
        return (
            self.model_config.default
            if self.model_config
            else "claude-3-5-sonnet-20241022"
        )

    def with_model(self, model: str) -> "AIProviderConfig":
        """Return a new config with a different default model (immutable)"""
        if self.model_config is None:
            self.model_config = self._get_default_model_config()
        new_config = AIModelConfig(
            haiku=self.model_config.haiku,
            sonnet=self.model_config.sonnet,
            opus=self.model_config.opus,
            default=model,
        )
        return AIProviderConfig(
            provider_type=self.provider_type,
            api_key=self.api_key,
            base_url=self.base_url,
            model_config=new_config,
            max_tokens=self.max_tokens,
        )
