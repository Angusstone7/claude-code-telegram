from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from domain.value_objects.user_id import UserId
from domain.entities.message import Message


@dataclass
class Session:
    """Chat session entity - maintains conversation context with Claude"""

    session_id: str
    user_id: UserId
    messages: List[Message] = field(default_factory=list)
    context: Dict = field(default_factory=dict)
    created_at: datetime = None
    updated_at: datetime = None
    is_active: bool = True

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()

    def add_message(self, message: Message) -> None:
        """Add a message to the session"""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        """Get messages from session"""
        if limit:
            return self.messages[-limit:]
        return self.messages

    def clear_messages(self) -> None:
        """Clear all messages from session"""
        self.messages.clear()
        self.updated_at = datetime.utcnow()

    def set_context(self, key: str, value: any) -> None:
        """Set context value"""
        self.context[key] = value
        self.updated_at = datetime.utcnow()

    def get_context(self, key: str, default: any = None) -> any:
        """Get context value"""
        return self.context.get(key, default)

    def close(self) -> None:
        """Close the session"""
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def reopen(self) -> None:
        """Reopen a closed session"""
        self.is_active = True
        self.updated_at = datetime.utcnow()

    @property
    def message_count(self) -> int:
        """Get number of messages in session"""
        return len(self.messages)

    def get_conversation_history(self) -> List[Dict]:
        """Get conversation history in Claude API format"""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]
