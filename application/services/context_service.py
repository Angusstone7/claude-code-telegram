"""
Context Service

Application service for managing project contexts (sessions).
Like Cursor IDE's context/conversation management.
"""

import logging
from typing import List, Optional, Dict

from domain.entities.project_context import ProjectContext, ContextMessage, ContextVariable
from domain.value_objects.user_id import UserId
from domain.repositories.project_context_repository import IProjectContextRepository

logger = logging.getLogger(__name__)


class ContextService:
    """
    Service for managing project contexts.

    Like Cursor IDE, handles:
    - Multiple contexts per project
    - Context switching
    - Message history
    - Claude Code session continuation
    """

    def __init__(self, context_repository: IProjectContextRepository):
        self.context_repository = context_repository

    async def get_current(self, project_id: str) -> Optional[ProjectContext]:
        """
        Get the current context for a project.

        Args:
            project_id: Project ID

        Returns:
            Current context or None
        """
        return await self.context_repository.get_current(project_id)

    async def get_by_id(self, context_id: str) -> Optional[ProjectContext]:
        """
        Get context by ID.

        Args:
            context_id: Context ID

        Returns:
            Context or None
        """
        return await self.context_repository.find_by_id(context_id)

    async def list_contexts(self, project_id: str) -> List[ProjectContext]:
        """
        List all contexts for a project.

        Args:
            project_id: Project ID

        Returns:
            List of contexts
        """
        return await self.context_repository.find_by_project(project_id)

    async def create_new(
        self,
        project_id: str,
        user_id: UserId,
        name: Optional[str] = None,
        set_as_current: bool = True
    ) -> ProjectContext:
        """
        Create a new context (fresh conversation, no history).

        Args:
            project_id: Parent project ID
            user_id: Owner's user ID
            name: Optional context name
            set_as_current: Whether to set as current context

        Returns:
            Newly created context
        """
        # Create context
        context = await self.context_repository.create_new(project_id, user_id, name)
        logger.info(f"Created new context '{context.name}' for project {project_id}")

        # Set as current if requested
        if set_as_current:
            await self.switch_context(project_id, context.id)

        return context

    async def ensure_context(self, project_id: str, user_id: UserId) -> ProjectContext:
        """
        Ensure a current context exists for project.

        Args:
            project_id: Project ID
            user_id: User ID

        Returns:
            Current context (existing or created)
        """
        context = await self.context_repository.get_current(project_id)
        if context:
            return context

        # Create main context
        return await self.create_new(project_id, user_id, "main", set_as_current=True)

    async def switch_context(self, project_id: str, context_id: str) -> Optional[ProjectContext]:
        """
        Switch to a different context.

        Args:
            project_id: Project ID
            context_id: Context ID to switch to

        Returns:
            The switched-to context or None
        """
        # Verify context exists and belongs to project
        context = await self.context_repository.find_by_id(context_id)
        if not context or context.project_id != project_id:
            logger.warning(f"Context {context_id} not found or belongs to different project")
            return None

        # Set as current
        await self.context_repository.set_current(project_id, context_id)
        logger.info(f"Switched to context '{context.name}'")

        return context

    async def delete_context(self, context_id: str) -> bool:
        """
        Delete a context and its messages.

        Args:
            context_id: Context ID

        Returns:
            True if deleted
        """
        result = await self.context_repository.delete(context_id)
        if result:
            logger.info(f"Deleted context {context_id}")
        return result

    # ==================== Message Operations ====================

    async def save_message(
        self,
        context_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        tool_result: Optional[str] = None
    ) -> None:
        """
        Save a message to context history.

        Args:
            context_id: Context ID
            role: Message role ('user' or 'assistant')
            content: Message content
            tool_name: Optional tool name
            tool_result: Optional tool result
        """
        await self.context_repository.add_message(
            context_id,
            role,
            content,
            tool_name,
            tool_result
        )

    async def get_messages(
        self,
        context_id: str,
        limit: int = 50
    ) -> List[ContextMessage]:
        """
        Get message history for a context.

        Args:
            context_id: Context ID
            limit: Max messages to return

        Returns:
            List of messages
        """
        return await self.context_repository.get_messages(context_id, limit)

    async def clear_messages(self, context_id: str) -> None:
        """
        Clear all messages in a context.

        Args:
            context_id: Context ID
        """
        await self.context_repository.clear_messages(context_id)
        logger.info(f"Cleared messages for context {context_id}")

    # ==================== Claude Session ====================

    async def get_claude_session_id(self, context_id: str) -> Optional[str]:
        """
        Get Claude Code session ID for continuation.

        Args:
            context_id: Context ID

        Returns:
            Session ID or None
        """
        return await self.context_repository.get_claude_session_id(context_id)

    async def set_claude_session_id(self, context_id: str, session_id: str) -> None:
        """
        Save Claude Code session ID for continuation.

        Args:
            context_id: Context ID
            session_id: Claude Code session ID
        """
        await self.context_repository.set_claude_session_id(context_id, session_id)
        logger.debug(f"Saved Claude session {session_id} for context {context_id}")

    async def clear_claude_session(self, context_id: str) -> None:
        """
        Clear Claude session (start fresh conversation).

        Args:
            context_id: Context ID
        """
        await self.context_repository.clear_claude_session_id(context_id)
        logger.info(f"Cleared Claude session for context {context_id}")

    async def start_fresh(self, context_id: str) -> None:
        """
        Start fresh - clear both messages and Claude session.

        Args:
            context_id: Context ID
        """
        await self.clear_messages(context_id)
        await self.clear_claude_session(context_id)
        logger.info(f"Started fresh for context {context_id}")

    # ==================== Context Variables ====================

    async def set_variable(
        self,
        context_id: str,
        name: str,
        value: str,
        description: str = ""
    ) -> None:
        """
        Set a context variable that will be included in Claude's context.

        Args:
            context_id: Context ID
            name: Variable name (e.g., 'GITLAB_TOKEN')
            value: Variable value
            description: Description for AI to understand how to use this variable
        """
        await self.context_repository.set_variable(context_id, name, value, description)
        logger.info(f"Set variable '{name}' for context {context_id}")

    async def delete_variable(self, context_id: str, name: str) -> bool:
        """
        Delete a context variable.

        Args:
            context_id: Context ID
            name: Variable name to delete

        Returns:
            True if deleted, False if not found
        """
        result = await self.context_repository.delete_variable(context_id, name)
        if result:
            logger.info(f"Deleted variable '{name}' from context {context_id}")
        return result

    async def get_variables(self, context_id: str) -> Dict[str, ContextVariable]:
        """
        Get all context variables.

        Args:
            context_id: Context ID

        Returns:
            Dict of variable name -> ContextVariable
        """
        return await self.context_repository.get_variables(context_id)

    async def get_variable(self, context_id: str, name: str) -> Optional[ContextVariable]:
        """
        Get a single context variable.

        Args:
            context_id: Context ID
            name: Variable name

        Returns:
            ContextVariable or None if not found
        """
        return await self.context_repository.get_variable(context_id, name)

    async def get_enriched_prompt(
        self,
        context_id: str,
        user_prompt: str,
        user_id: UserId = None
    ) -> str:
        """
        Enrich a user prompt with context variables.

        This builds a prompt that includes all context variables
        so Claude can use them automatically. Global variables are
        inherited and can be overridden by context-specific variables.

        Args:
            context_id: Context ID
            user_prompt: Original user prompt
            user_id: User ID for loading global variables

        Returns:
            Enriched prompt with context variables prepended
        """
        context = await self.context_repository.find_by_id(context_id)
        if not context:
            return user_prompt

        # Get merged variables (global + context-specific)
        if user_id:
            merged_variables = await self.get_merged_variables(context_id, user_id)
            # Temporarily set merged variables for building prompt
            original_variables = context.variables
            context.variables = merged_variables
            variables_block = context.build_variables_prompt()
            context.variables = original_variables
        else:
            variables_block = context.build_variables_prompt()

        if variables_block:
            return f"{variables_block}\n\n---\n\n{user_prompt}"

        return user_prompt

    # ==================== Global Variables ====================

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
        await self.context_repository.set_global_variable(user_id, name, value, description)
        logger.info(f"Set global variable '{name}' for user {user_id}")

    async def delete_global_variable(self, user_id: UserId, name: str) -> bool:
        """
        Delete a global variable.

        Args:
            user_id: User ID
            name: Variable name

        Returns:
            True if deleted, False if not found
        """
        result = await self.context_repository.delete_global_variable(user_id, name)
        if result:
            logger.info(f"Deleted global variable '{name}' for user {user_id}")
        return result

    async def get_global_variables(self, user_id: UserId) -> Dict[str, ContextVariable]:
        """
        Get all global variables for a user.

        Args:
            user_id: User ID

        Returns:
            Dict of variable name -> ContextVariable
        """
        return await self.context_repository.get_global_variables(user_id)

    async def get_global_variable(self, user_id: UserId, name: str) -> Optional[ContextVariable]:
        """
        Get a single global variable.

        Args:
            user_id: User ID
            name: Variable name

        Returns:
            ContextVariable or None
        """
        return await self.context_repository.get_global_variable(user_id, name)

    async def get_merged_variables(
        self,
        context_id: str,
        user_id: UserId
    ) -> Dict[str, ContextVariable]:
        """
        Get merged variables: global variables + context-specific variables.

        Context-specific variables override global variables with the same name.

        Args:
            context_id: Context ID
            user_id: User ID

        Returns:
            Dict of merged variables
        """
        # Start with global variables
        merged = await self.get_global_variables(user_id)

        # Override with context-specific variables
        context_vars = await self.get_variables(context_id)
        merged.update(context_vars)

        return merged
