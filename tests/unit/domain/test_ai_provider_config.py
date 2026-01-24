"""Unit tests for AIProviderConfig value object"""

import pytest
from domain.value_objects import AIProviderConfig, AIProviderType, AIModelConfig
from domain.services import AIMessage


class TestAIModelConfig:
    """Tests for AIModelConfig value object"""

    def test_create_model_config(self):
        """Test creating a model configuration"""
        config = AIModelConfig(
            haiku="claude-3-5-haiku-20241022",
            sonnet="claude-3-5-sonnet-20241022",
            opus="claude-3-5-sonnet-20241022",
            default="claude-3-5-sonnet-20241022",
        )
        assert config.haiku == "claude-3-5-haiku-20241022"
        assert config.sonnet == "claude-3-5-sonnet-20241022"
        assert config.opus == "claude-3-5-sonnet-20241022"
        assert config.default == "claude-3-5-sonnet-20241022"

    def test_get_model_by_tier(self):
        """Test getting model by tier"""
        config = AIModelConfig(
            haiku="model-haiku",
            sonnet="model-sonnet",
            opus="model-opus",
            default="model-default",
        )
        assert config.get_model("haiku") == "model-haiku"
        assert config.get_model("sonnet") == "model-sonnet"
        assert config.get_model("opus") == "model-opus"
        assert config.get_model("default") == "model-default"


class TestAIProviderConfig:
    """Tests for AIProviderConfig value object"""

    def test_create_anthropic_config(self):
        """Test creating Anthropic provider configuration"""
        config = AIProviderConfig(
            provider_type=AIProviderType.ANTHROPIC, api_key="sk-ant-test-key"
        )
        assert config.provider_type == AIProviderType.ANTHROPIC
        assert config.api_key == "sk-ant-test-key"
        assert config.base_url is None
        assert config.default_model == "claude-3-5-sonnet-20241022"

    def test_create_zhipu_config(self):
        """Test creating ZhipuAI provider configuration"""
        config = AIProviderConfig(
            provider_type=AIProviderType.ZHIPU_AI,
            api_key="test-zhipu-key",
            base_url="https://open.bigmodel.cn/api/anthropic",
        )
        assert config.provider_type == AIProviderType.ZHIPU_AI
        assert config.api_key == "test-zhipu-key"
        assert config.base_url == "https://open.bigmodel.cn/api/anthropic"
        assert config.default_model == "glm-4.7"

    def test_config_requires_api_key(self):
        """Test that configuration requires API key"""
        with pytest.raises(ValueError, match="api_key is required"):
            AIProviderConfig(provider_type=AIProviderType.ANTHROPIC, api_key="")

    def test_config_validates_url_format(self):
        """Test that configuration validates URL format"""
        with pytest.raises(ValueError, match="Invalid URL format"):
            AIProviderConfig(
                provider_type=AIProviderType.CUSTOM,
                api_key="test-key",
                base_url="not-a-valid-url",
            )

    def test_from_env_detects_zhipu(self):
        """Test that from_env detects ZhipuAI from base_url"""
        config = AIProviderConfig.from_env(
            api_key="test-key", base_url="https://open.bigmodel.cn/api/anthropic"
        )
        assert config.provider_type == AIProviderType.ZHIPU_AI

    def test_from_env_with_custom_models(self):
        """Test creating config with custom models from env"""
        config = AIProviderConfig.from_env(
            api_key="test-key",
            base_url="https://open.bigmodel.cn/api/anthropic",
            haiku_model="glm-4.5-air",
            sonnet_model="glm-4.7",
            opus_model="glm-4.7",
            default_model="glm-4.7",
        )
        assert config.model_config.haiku == "glm-4.5-air"
        assert config.model_config.sonnet == "glm-4.7"
        assert config.model_config.opus == "glm-4.7"
        assert config.default_model == "glm-4.7"

    def test_with_model_returns_new_config(self):
        """Test that with_model returns a new immutable config"""
        original = AIProviderConfig(
            provider_type=AIProviderType.ANTHROPIC, api_key="test-key"
        )
        modified = original.with_model("claude-3-5-haiku-20241022")

        # Original should be unchanged
        assert original.default_model == "claude-3-5-sonnet-20241022"
        # Modified should have new model
        assert modified.default_model == "claude-3-5-haiku-20241022"
        # They should be different objects
        assert original is not modified


class TestAIMessage:
    """Tests for AIMessage value object"""

    def test_create_message(self):
        """Test creating an AI message"""
        message = AIMessage(role="user", content="Hello")
        assert message.role == "user"
        assert message.content == "Hello"

    def test_message_to_dict(self):
        """Test converting message to dictionary"""
        message = AIMessage(role="user", content="Hello")
        result = message.to_dict()
        assert result == {"role": "user", "content": "Hello"}
