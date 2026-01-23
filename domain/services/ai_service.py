from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from domain.entities.session import Session


class AIMessage(    """Message for AI service"""
    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class AIResponse:
    """Response from AI service"""
    def __init__(
        self,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.model = model
        self.tokens_used = tokens_used

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class IAIService(ABC):
    """Interface for AI service (Claude, etc.)"""

    @abstractmethod
    async def chat(
        self,
        messages: List[AIMessage],
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096
    ) -> AIResponse:
        """Send chat request to AI"""
        pass

    @abstractmethod
    async def chat_with_session(
        self,
        session: Session,
        user_message: str,
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None
    ) -> AIResponse:
        """Chat using session context"""
        pass

    @abstractmethod
    def set_api_key(self, api_key: str) -> None:
        """Set API key for the service"""
        pass
