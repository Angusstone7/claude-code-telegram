"""
Session Entity (Rich Domain Model)

Chat session entity - maintains conversation context with Claude.

Refactored from anemic data container to rich domain model
with business logic and invariants.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from domain.value_objects.user_id import UserId
from domain.entities.message import Message


# Domain constants (extracted from magic numbers)
MAX_MESSAGES_PER_SESSION = 1000  # Maximum messages before requiring cleanup
SESSION_CONTINUITY_HOURS = 24  # Hours before session is considered stale
MAX_CONTEXT_SIZE_BYTES = 100_000  # Max context dict size


class SessionError(Exception):
    """Base exception for session errors"""
    pass


class SessionFullError(SessionError):
    """Raised when session has too many messages"""
    pass


class SessionClosedError(SessionError):
    """Raised when trying to modify a closed session"""
    pass


class DuplicateMessageError(SessionError):
    """Raised when trying to add a duplicate message"""
    pass


@dataclass
class Session:
    """
    Chat session entity - maintains conversation context with Claude.

    Rich domain model with:
    - Invariant validation
    - Business rules
    - Behavior methods

    Previously was an anemic data container with only getters/setters.
    """

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

    # === Business Rules ===

    def add_message(self, message: Message) -> None:
        """
        Add a message to the session with business rules validation.

        Business rules:
        1. Session must be active
        2. Cannot exceed max messages
        3. No duplicate messages (by content and role in last 5)

        Raises:
            SessionClosedError: If session is closed
            SessionFullError: If session has max messages
            DuplicateMessageError: If message is duplicate
        """
        if not self.is_active:
            raise SessionClosedError(
                f"Cannot add message to closed session {self.session_id}"
            )

        if len(self.messages) >= MAX_MESSAGES_PER_SESSION:
            raise SessionFullError(
                f"Session {self.session_id} has reached maximum of "
                f"{MAX_MESSAGES_PER_SESSION} messages"
            )

        if self._is_duplicate(message):
            # Silently ignore duplicates instead of raising
            return

        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def _is_duplicate(self, message: Message) -> bool:
        """
        Check if message is duplicate of recent messages.

        Business rule: Same role and content in last 5 messages = duplicate.
        """
        recent = self.messages[-5:] if len(self.messages) >= 5 else self.messages
        for existing in recent:
            if (existing.role == message.role and
                existing.content == message.content):
                return True
        return False

    def can_continue(self) -> bool:
        """
        Check if session can be continued (business rule).

        A session can be continued if:
        1. It's active
        2. Last message was within SESSION_CONTINUITY_HOURS

        Returns:
            True if session can be continued
        """
        if not self.is_active:
            return False

        if not self.messages:
            return True

        last_message = self.messages[-1]
        if last_message.timestamp:
            age = datetime.utcnow() - last_message.timestamp
            return age < timedelta(hours=SESSION_CONTINUITY_HOURS)

        return True

    def is_stale(self) -> bool:
        """
        Check if session is stale (hasn't been used recently).

        Returns:
            True if session is stale
        """
        if self.updated_at:
            age = datetime.utcnow() - self.updated_at
            return age > timedelta(hours=SESSION_CONTINUITY_HOURS)
        return False

    def get_conversation_summary(self) -> str:
        """
        Generate a summary of the conversation.

        Business logic: Summarizes last 10 messages for context.

        Returns:
            Summary string
        """
        if not self.messages:
            return "Empty conversation"

        recent = self.messages[-10:]
        summary_parts = []
        for msg in recent:
            role = msg.role.value.capitalize()
            content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            summary_parts.append(f"{role}: {content}")

        total = len(self.messages)
        if total > 10:
            summary_parts.insert(0, f"[{total - 10} earlier messages...]")

        return "\n".join(summary_parts)

    def get_token_estimate(self) -> int:
        """
        Estimate total tokens in session.

        Business logic: Rough estimate for context management.

        Returns:
            Estimated token count
        """
        total_chars = sum(len(msg.content) for msg in self.messages)
        # Rough estimate: 4 chars per token
        return total_chars // 4

    def needs_pruning(self) -> bool:
        """
        Check if session needs message pruning.

        Business rule: Prune if over 80% of max capacity.

        Returns:
            True if pruning is recommended
        """
        threshold = int(MAX_MESSAGES_PER_SESSION * 0.8)
        return len(self.messages) > threshold

    def prune_old_messages(self, keep_recent: int = 100) -> int:
        """
        Remove old messages, keeping most recent.

        Args:
            keep_recent: Number of recent messages to keep

        Returns:
            Number of messages removed
        """
        if len(self.messages) <= keep_recent:
            return 0

        removed = len(self.messages) - keep_recent
        self.messages = self.messages[-keep_recent:]
        self.updated_at = datetime.utcnow()
        return removed

    # === State Methods ===

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
        """
        Set context value with size validation.

        Raises:
            ValueError: If context would exceed max size
        """
        # Check size after adding
        test_context = {**self.context, key: value}
        import json
        size = len(json.dumps(test_context))
        if size > MAX_CONTEXT_SIZE_BYTES:
            raise ValueError(
                f"Context size ({size} bytes) would exceed maximum "
                f"({MAX_CONTEXT_SIZE_BYTES} bytes)"
            )

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
        """
        Reopen a closed session.

        Business rule: Can only reopen if not stale.

        Raises:
            SessionError: If session is too old to reopen
        """
        if self.is_stale():
            raise SessionError(
                f"Cannot reopen stale session {self.session_id}. "
                f"Create a new session instead."
            )
        self.is_active = True
        self.updated_at = datetime.utcnow()

    # === Properties ===

    @property
    def message_count(self) -> int:
        """Get number of messages in session"""
        return len(self.messages)

    @property
    def age(self) -> timedelta:
        """Get session age"""
        return datetime.utcnow() - self.created_at

    @property
    def last_activity(self) -> Optional[datetime]:
        """Get last activity time"""
        if self.messages:
            return self.messages[-1].timestamp or self.updated_at
        return self.updated_at

    # === Conversion ===

    def get_conversation_history(self) -> List[Dict]:
        """Get conversation history in Claude API format"""
        return [{"role": msg.role.value, "content": msg.content} for msg in self.messages]

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "session_id": self.session_id,
            "user_id": int(self.user_id),
            "message_count": self.message_count,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
        }
