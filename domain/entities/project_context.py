"""
Project Context Entity

Represents a conversation context within a project (like Cursor's sessions).
Each project can have multiple contexts for different conversations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
import uuid

from domain.value_objects.user_id import UserId


@dataclass
class ContextVariable:
    """
    Context variable with description for AI understanding.

    The description helps Claude understand:
    - What the variable is for
    - How and when to use it
    - Any special considerations
    """
    name: str
    value: str
    description: str = ""


@dataclass
class ContextMessage:
    """A message within a project context"""
    id: int
    context_id: str
    role: str  # 'user' or 'assistant'
    content: str
    tool_name: Optional[str] = None
    tool_result: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProjectContext:
    """
    Project context entity - a conversation session within a project.

    Like Cursor IDE, each project can have multiple contexts:
    - Main context (default)
    - Feature-specific contexts
    - New contexts without history

    Each context maintains:
    - Claude Code session ID for continuation
    - Message count
    - Current/active status
    """

    id: str
    project_id: str
    user_id: UserId
    name: str
    claude_session_id: Optional[str] = None
    is_current: bool = False
    message_count: int = 0
    variables: Dict[str, ContextVariable] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        project_id: str,
        user_id: UserId,
        name: Optional[str] = None
    ) -> "ProjectContext":
        """
        Factory method to create a new context.

        Args:
            project_id: Parent project ID
            user_id: Owner's user ID
            name: Context name (auto-generated if not provided)

        Returns:
            New ProjectContext instance
        """
        context_id = str(uuid.uuid4())

        # Generate name if not provided
        if not name:
            name = f"context-{context_id[:8]}"

        return cls(
            id=context_id,
            project_id=project_id,
            user_id=user_id,
            name=name,
            claude_session_id=None,
            is_current=False,
            message_count=0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    @classmethod
    def create_main(cls, project_id: str, user_id: UserId) -> "ProjectContext":
        """
        Create the main/default context for a project.

        Args:
            project_id: Parent project ID
            user_id: Owner's user ID

        Returns:
            New main ProjectContext
        """
        context = cls.create(project_id, user_id, "main")
        context.is_current = True
        return context

    def set_claude_session(self, session_id: str) -> None:
        """
        Set the Claude Code session ID for continuation.

        Args:
            session_id: Claude Code session ID
        """
        self.claude_session_id = session_id
        self.updated_at = datetime.now()

    def clear_claude_session(self) -> None:
        """Clear the Claude session (start fresh)"""
        self.claude_session_id = None
        self.updated_at = datetime.now()

    def mark_as_current(self) -> None:
        """Mark this context as the current/active one"""
        self.is_current = True
        self.updated_at = datetime.now()

    def unmark_as_current(self) -> None:
        """Unmark this context as current"""
        self.is_current = False
        self.updated_at = datetime.now()

    def increment_message_count(self, count: int = 1) -> None:
        """Increment the message count"""
        self.message_count += count
        self.updated_at = datetime.now()

    def rename(self, new_name: str) -> None:
        """Rename the context"""
        self.name = new_name
        self.updated_at = datetime.now()

    @property
    def has_session(self) -> bool:
        """Check if context has an active Claude session"""
        return self.claude_session_id is not None

    @property
    def is_empty(self) -> bool:
        """Check if context has no messages"""
        return self.message_count == 0

    # ==================== Context Variables ====================

    def set_variable(self, name: str, value: str, description: str = "") -> None:
        """Set a context variable that will be included in Claude's context.

        Args:
            name: Variable name (e.g., GITLAB_TOKEN)
            value: Variable value
            description: Description for AI to understand how to use this variable
        """
        self.variables[name] = ContextVariable(name=name, value=value, description=description)
        self.updated_at = datetime.now()

    def delete_variable(self, name: str) -> bool:
        """Delete a context variable. Returns True if deleted, False if not found."""
        if name in self.variables:
            del self.variables[name]
            self.updated_at = datetime.now()
            return True
        return False

    def get_variable(self, name: str) -> Optional[ContextVariable]:
        """Get a context variable"""
        return self.variables.get(name)

    def get_variable_value(self, name: str) -> Optional[str]:
        """Get just the value of a context variable"""
        var = self.variables.get(name)
        return var.value if var else None

    def build_variables_prompt(self) -> str:
        """Build a prompt block with all context variables for Claude.

        Includes descriptions to help Claude understand how to use each variable.

        Returns:
            Formatted string with variables and descriptions, or empty string if no variables set.
        """
        if not self.variables:
            return ""

        lines = ["📋 Context Variables (use these in your responses when relevant):"]
        for var in sorted(self.variables.values(), key=lambda v: v.name):
            lines.append(f"  {var.name}={var.value}")
            if var.description:
                lines.append(f"    ↳ {var.description}")

        return "\n".join(lines)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ProjectContext):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        return hash(self.id)
