import logging
from typing import List, Optional
from anthropic import AsyncAnthropic
from domain.services.ai_service import IAIService, AIMessage, AIResponse
from domain.entities.session import Session
from domain.value_objects import AIProviderConfig

logger = logging.getLogger(__name__)


class ClaudeAIService(IAIService):
    """Anthropic Claude AI service implementation

    Implements IAIService interface using Anthropic's AsyncAnthropic client.
    Supports both official Anthropic API and compatible APIs like ZhipuAI.
    Follows Dependency Inversion Principle by accepting config via constructor.
    """

    def __init__(self, provider_config: AIProviderConfig):
        """Initialize the service with provider configuration

        Args:
            provider_config: AI provider configuration value object
        """
        self._config = provider_config
        self._client: Optional[AsyncAnthropic] = None

    @property
    def client(self) -> AsyncAnthropic:
        """Lazy initialization of Anthropic client"""
        if self._client is None:
            client_kwargs = {"api_key": self._config.api_key}
            if self._config.base_url:
                client_kwargs["base_url"] = self._config.base_url
            self._client = AsyncAnthropic(**client_kwargs)
        return self._client

    @property
    def model(self) -> str:
        """Get the current default model"""
        return self._config.default_model

    @property
    def max_tokens(self) -> int:
        """Get the max tokens setting"""
        return self._config.max_tokens

    async def chat(
        self,
        messages: List[AIMessage],
        tools: Optional[List[dict]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = None
    ) -> AIResponse:
        """Send chat request to Claude"""
        try:
            api_messages = [msg.to_dict() for msg in messages]

            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens or self.max_tokens,
                "messages": api_messages
            }

            if system_prompt:
                kwargs["system"] = system_prompt
            if tools:
                kwargs["tools"] = tools

            response = await self.client.messages.create(**kwargs)

            content = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

            return AIResponse(
                content=content,
                tool_calls=tool_calls,
                model=response.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens
            )

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def chat_with_session(
        self,
        session: Session,
        user_message: str,
        tools: Optional[List[dict]] = None,
        system_prompt: Optional[str] = None
    ) -> AIResponse:
        """Chat using session context"""
        # Add user message to session
        from domain.entities.message import Message, MessageRole
        session.add_message(Message(role=MessageRole.USER, content=user_message))

        # Get conversation history
        messages = [
            AIMessage(role=m.role.value, content=m.content)
            for m in session.get_messages(limit=50)  # Limit context window
        ]

        response = await self.chat(messages, tools, system_prompt)

        # Add assistant response to session
        if response.content:
            session.add_message(Message(role=MessageRole.ASSISTANT, content=response.content))

        return response

    def set_api_key(self, api_key: str, base_url: str = None) -> None:
        """Set API key and optionally base URL for the service

        Creates a new configuration with the updated values.
        """
        if base_url:
            # Create new config with both updated values
            self._config = AIProviderConfig.from_env(
                api_key=api_key,
                base_url=base_url,
                max_tokens=self._config.max_tokens
            )
        else:
            # Keep existing base_url, just update api_key
            self._config = AIProviderConfig.from_env(
                api_key=api_key,
                base_url=self._config.base_url,
                max_tokens=self._config.max_tokens
            )
        self._client = None  # Reset client to use new configuration


# Re-export SystemPrompts from domain layer for backward compatibility
from domain.services.system_prompts import SystemPrompts
