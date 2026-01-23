import logging
from typing import List, Optional
from anthropic import AsyncAnthropic
from domain.services.ai_service import IAIService, AIMessage, AIResponse
from domain.entities.session import Session
from shared.config.settings import settings

logger = logging.getLogger(__name__)


class ClaudeAIService(IAIService):
    """Anthropic Claude AI service implementation"""

    def __init__(self, api_key: str = None):
        self._api_key = api_key or settings.anthropic.api_key
        self._client: Optional[AsyncAnthropic] = None
        self.model = settings.anthropic.model
        self.max_tokens = settings.anthropic.max_tokens

    @property
    def client(self) -> AsyncAnthropic:
        """Lazy initialization of Anthropic client"""
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

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

    def set_api_key(self, api_key: str) -> None:
        """Set API key for the service"""
        self._api_key = api_key
        self._client = None  # Reset client to use new key


class SystemPrompts:
    """Predefined system prompts for different use cases"""

    DEVOPS = """You are an intelligent DevOps assistant with access to a Linux server via SSH.
You can help with:
- Server administration and troubleshooting
- Docker container management
- Git operations and CI/CD pipelines
- Log analysis and monitoring
- System resource monitoring

When executing commands:
1. Always explain what the command does before suggesting it
2. For dangerous operations (rm -rf, formatting, etc.), always ask for confirmation
3. Provide clear explanations of command output
4. Suggest safer alternatives when possible

You have access to bash command execution tool. Use it to help the user.
"""

    CODE_ASSISTANT = """You are an expert programmer and code assistant.
You can help with:
- Writing and reviewing code
- Debugging and troubleshooting
- Code optimization and refactoring
- Explaining code and concepts

Provide clear, concise explanations and well-structured code examples."""

    SECURITY_AUDITOR = """You are a security specialist focused on identifying and explaining security issues.
When analyzing systems or code:
1. Identify potential vulnerabilities
2. Explain the risks clearly
3. Suggest remediation steps
4. Prioritize issues by severity"""

    @classmethod
    def custom(cls, prompt: str) -> str:
        """Get custom system prompt"""
        return prompt
