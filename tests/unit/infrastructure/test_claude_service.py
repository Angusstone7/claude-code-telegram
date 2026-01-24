"""Unit tests for ClaudeAIService"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from domain.value_objects import AIProviderConfig, AIProviderType
from infrastructure.messaging.claude_service import ClaudeAIService
from domain.services import AIMessage, AIResponse


class TestClaudeAIService:
    """Tests for ClaudeAIService"""

    @pytest.fixture
    def anthropic_config(self):
        """Create Anthropic provider configuration"""
        return AIProviderConfig(
            provider_type=AIProviderType.ANTHROPIC,
            api_key="sk-ant-test-key",
            max_tokens=4096
        )

    @pytest.fixture
    def zhipu_config(self):
        """Create ZhipuAI provider configuration"""
        return AIProviderConfig(
            provider_type=AIProviderType.ZHIPU_AI,
            api_key="test-zhipu-key",
            base_url="https://open.bigmodel.cn/api/anthropic",
            max_tokens=4096
        )

    @pytest.fixture
    def service_anthropic(self, anthropic_config):
        """Create service with Anthropic config"""
        return ClaudeAIService(anthropic_config)

    @pytest.fixture
    def service_zhipu(self, zhipu_config):
        """Create service with ZhipuAI config"""
        return ClaudeAIService(zhipu_config)

    def test_service_injection(self, anthropic_config):
        """Test that service properly receives config via constructor"""
        service = ClaudeAIService(anthropic_config)
        assert service._config == anthropic_config
        assert service.model == "claude-3-5-sonnet-20241022"
        assert service.max_tokens == 4096

    def test_service_with_zhipu_config(self, service_zhipu):
        """Test service with ZhipuAI configuration"""
        assert service_zhipu.model == "glm-4.7"
        assert service_zhipu._config.base_url == "https://open.bigmodel.cn/api/anthropic"

    @pytest.mark.asyncio
    async def test_chat_uses_correct_model(self, service_anthropic):
        """Test that chat uses the correct model from config"""
        mock_response = Mock()
        mock_response.content = [Mock(type="text", text="Hello!")]
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.usage = Mock(input_tokens=10, output_tokens=20)

        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch('infrastructure.messaging.claude_service.AsyncAnthropic', return_value=mock_client):
            messages = [AIMessage(role="user", content="Hello")]
            response = await service_anthropic.chat(messages)

            # Verify correct model was used
            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs['model'] == "claude-3-5-sonnet-20241022"
            assert call_args.kwargs['max_tokens'] == 4096

    @pytest.mark.asyncio
    async def test_chat_with_zhipu_model(self, service_zhipu):
        """Test that chat uses ZhipuAI model when configured"""
        mock_response = Mock()
        mock_response.content = [Mock(type="text", text="Response")]
        mock_response.model = "glm-4.7"
        mock_response.usage = Mock(input_tokens=10, output_tokens=20)

        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch('infrastructure.messaging.claude_service.AsyncAnthropic', return_value=mock_client):
            messages = [AIMessage(role="user", content="Hello")]
            await service_zhipu.chat(messages)

            # Verify ZhipuAI model was used
            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs['model'] == "glm-4.7"

    def test_client_lazy_initialization_anthropic(self, service_anthropic):
        """Test that Anthropic client is lazily initialized without base_url"""
        assert service_anthropic._client is None

        with patch('infrastructure.messaging.claude_service.AsyncAnthropic') as mock_anthropic:
            _ = service_anthropic.client
            mock_anthropic.assert_called_once_with(api_key="sk-ant-test-key")

    def test_client_lazy_initialization_zhipu(self, service_zhipu):
        """Test that client is lazily initialized with base_url for ZhipuAI"""
        assert service_zhipu._client is None

        with patch('infrastructure.messaging.claude_service.AsyncAnthropic') as mock_anthropic:
            _ = service_zhipu.client
            mock_anthropic.assert_called_once_with(
                api_key="test-zhipu-key",
                base_url="https://open.bigmodel.cn/api/anthropic"
            )

    @pytest.mark.asyncio
    async def test_set_api_key_updates_config(self, service_anthropic):
        """Test that set_api_key creates new config and resets client"""
        # Initialize client
        with patch('anthropic.AsyncAnthropic'):
            _ = service_anthropic.client
            assert service_anthropic._client is not None

        # Set new API key
        service_anthropic.set_api_key("new-key")

        # Client should be reset
        assert service_anthropic._client is None
        assert service_anthropic._config.api_key == "new-key"

    @pytest.mark.asyncio
    async def test_set_api_key_with_base_url(self, service_zhipu):
        """Test that set_api_key can update both key and base_url"""
        service_zhipu.set_api_key("new-key", "https://new-url.com")

        assert service_zhipu._config.api_key == "new-key"
        assert service_zhipu._config.base_url == "https://new-url.com"
        assert service_zhipu._client is None


class TestSystemPrompts:
    """Tests for SystemPrompts"""

    def test_devops_prompt(self):
        """Test DevOps system prompt"""
        from domain.services.system_prompts import SystemPrompts

        prompt = SystemPrompts.DEVOPS
        assert "DevOps assistant" in prompt
        assert "SSH" in prompt
        assert "Docker" in prompt

    def test_code_assistant_prompt(self):
        """Test code assistant system prompt"""
        from domain.services.system_prompts import SystemPrompts

        prompt = SystemPrompts.CODE_ASSISTANT
        assert "programmer" in prompt
        assert "code" in prompt

    def test_security_auditor_prompt(self):
        """Test security auditor system prompt"""
        from domain.services.system_prompts import SystemPrompts

        prompt = SystemPrompts.SECURITY_AUDITOR
        assert "security" in prompt
        assert "vulnerabilities" in prompt

    def test_custom_prompt(self):
        """Test custom system prompt"""
        from domain.services.system_prompts import SystemPrompts

        custom = "You are a custom assistant"
        assert SystemPrompts.custom(custom) == custom

    def test_for_role(self):
        """Test getting prompt by role"""
        from domain.services.system_prompts import SystemPrompts

        assert SystemPrompts.for_role("devops") == SystemPrompts.DEVOPS
        assert SystemPrompts.for_role("developer") == SystemPrompts.CODE_ASSISTANT
        assert SystemPrompts.for_role("security") == SystemPrompts.SECURITY_AUDITOR
        # Unknown role defaults to DevOps
        assert SystemPrompts.for_role("unknown") == SystemPrompts.DEVOPS
