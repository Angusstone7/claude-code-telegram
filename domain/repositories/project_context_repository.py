"""
Project Context Repository Interface

Defines the contract for project context persistence operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from domain.entities.project_context import ProjectContext, ContextMessage
from domain.value_objects.user_id import UserId


class IProjectContextRepository(ABC):
    """
    Repository interface for ProjectContext entity.

    Handles both context CRUD and message persistence.
    """

    # ==================== Context CRUD ====================

    @abstractmethod
    async def save(self, context: ProjectContext) -> None:
        """
        Save or update a context.

        Args:
            context: ProjectContext entity to save
        """
        pass

    @abstractmethod
    async def find_by_id(self, context_id: str) -> Optional[ProjectContext]:
        """
        Find context by ID.

        Args:
            context_id: Context UUID

        Returns:
            ProjectContext if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_project(self, project_id: str) -> List[ProjectContext]:
        """
        Find all contexts for a project.

        Args:
            project_id: Project ID

        Returns:
            List of project's contexts
        """
        pass

    @abstractmethod
    async def get_current(self, project_id: str) -> Optional[ProjectContext]:
        """
        Get the current context for a project.

        Args:
            project_id: Project ID

        Returns:
            Current context if exists, None otherwise
        """
        pass

    @abstractmethod
    async def set_current(self, project_id: str, context_id: str) -> None:
        """
        Set the current context for a project.

        Args:
            project_id: Project ID
            context_id: Context ID to set as current
        """
        pass

    @abstractmethod
    async def create_new(
        self,
        project_id: str,
        user_id: UserId,
        name: Optional[str] = None
    ) -> ProjectContext:
        """
        Create a new context for a project.

        Args:
            project_id: Parent project ID
            user_id: Owner's user ID
            name: Optional context name

        Returns:
            Newly created ProjectContext
        """
        pass

    @abstractmethod
    async def delete(self, context_id: str) -> bool:
        """
        Delete a context and all its messages.

        Args:
            context_id: Context ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    # ==================== Message Operations ====================

    @abstractmethod
    async def add_message(
        self,
        context_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        tool_result: Optional[str] = None
    ) -> None:
        """
        Add a message to a context.

        Args:
            context_id: Context ID
            role: Message role ('user' or 'assistant')
            content: Message content
            tool_name: Optional tool name if tool was used
            tool_result: Optional tool result
        """
        pass

    @abstractmethod
    async def get_messages(
        self,
        context_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[ContextMessage]:
        """
        Get messages for a context.

        Args:
            context_id: Context ID
            limit: Maximum number of messages
            offset: Offset for pagination

        Returns:
            List of ContextMessage
        """
        pass

    @abstractmethod
    async def clear_messages(self, context_id: str) -> None:
        """
        Clear all messages in a context.

        Args:
            context_id: Context ID
        """
        pass

    # ==================== Claude Session ====================

    @abstractmethod
    async def set_claude_session_id(
        self,
        context_id: str,
        session_id: str
    ) -> None:
        """
        Set Claude Code session ID for a context.

        Args:
            context_id: Context ID
            session_id: Claude Code session ID
        """
        pass

    @abstractmethod
    async def get_claude_session_id(self, context_id: str) -> Optional[str]:
        """
        Get Claude Code session ID for a context.

        Args:
            context_id: Context ID

        Returns:
            Session ID if exists, None otherwise
        """
        pass

    @abstractmethod
    async def clear_claude_session_id(self, context_id: str) -> None:
        """
        Clear Claude Code session ID (start fresh).

        Args:
            context_id: Context ID
        """
        pass

    # ==================== Global Variables ====================

    @abstractmethod
    async def set_global_variable(
        self,
        user_id: UserId,
        name: str,
        value: str,
        description: str = ""
    ) -> None:
        """
        Set a global variable that applies to all projects.

        Args:
            user_id: User ID
            name: Variable name
            value: Variable value
            description: Description for AI
        """
        pass

    @abstractmethod
    async def delete_global_variable(self, user_id: UserId, name: str) -> bool:
        """
        Delete a global variable.

        Args:
            user_id: User ID
            name: Variable name

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def get_global_variables(self, user_id: UserId) -> dict:
        """
        Get all global variables for a user.

        Args:
            user_id: User ID

        Returns:
            Dict of variable name -> ContextVariable
        """
        pass

    @abstractmethod
    async def get_global_variable(self, user_id: UserId, name: str):
        """
        Get a single global variable.

        Args:
            user_id: User ID
            name: Variable name

        Returns:
            ContextVariable or None
        """
        pass
