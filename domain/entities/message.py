from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from enum import Enum


class MessageRole(Enum):
    """Role of the message sender"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Message entity - represents a single message in the conversation"""
    role: MessageRole
    content: str
    timestamp: datetime = None
    tool_use_id: Optional[str] = None
    tool_result: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert message to dictionary format"""
        result = {
            "role": self.role.value,
            "content": self.content
        }
        if self.tool_use_id:
            result["tool_use_id"] = self.tool_use_id
        if self.tool_result is not None:
            result["tool_result"] = self.tool_result
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create message from dictionary"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            tool_use_id=data.get("tool_use_id"),
            tool_result=data.get("tool_result")
        )
