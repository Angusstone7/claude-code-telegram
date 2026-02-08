import asyncio
import html
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from presentation.keyboards.keyboards import CallbackData, Keyboards
from typing import Optional

# Import specialized handlers
from presentation.handlers.callbacks.docker import DockerCallbackHandler
from presentation.handlers.callbacks.claude import ClaudeCallbackHandler
from presentation.handlers.callbacks.project import ProjectCallbackHandler
from presentation.handlers.callbacks.context import ContextCallbackHandler
from presentation.handlers.callbacks.variables import VariableCallbackHandler

logger = logging.getLogger(__name__)
router = Router()


class CallbackHandlers:
    """
    Bot callback query handlers.

    Delegates to specialized handlers:
    - DockerCallbackHandler: docker_*, metrics_*
    - ClaudeCallbackHandler: claude_*, plan_*
    - ProjectCallbackHandler: project_*, cd_*
    - ContextCallbackHandler: context_*
    - VariableCallbackHandler: vars_*, gvar_*
    """

    def __init__(
        self,
        bot_service,
        message_handlers,
        claude_proxy=None,
        sdk_service=None,
        project_service=None,
        context_service=None,
        file_browser_service=None,
        system_monitor=None,
    ):
        self.bot_service = bot_service
        self.message_handlers = message_handlers
        self.claude_proxy = claude_proxy  # ClaudeCodeProxyService instance (fallback)
        self.sdk_service = sdk_service    # ClaudeAgentSDKService instance (preferred)
        self.project_service = project_service
        self.context_service = context_service
        self.file_browser_service = file_browser_service
        self.system_monitor = system_monitor
        self._user_states = {}  # For tracking user input states (e.g., waiting for folder name)

        # Initialize specialized handlers (use keyword args for clarity)
        handler_kwargs = dict(
            bot_service=bot_service,
            message_handlers=message_handlers,
            claude_proxy=claude_proxy,
            sdk_service=sdk_service,
            project_service=project_service,
            context_service=context_service,
            file_browser_service=file_browser_service,
            system_monitor=system_monitor,
        )
        self._docker = DockerCallbackHandler(**handler_kwargs)
        self._claude = ClaudeCallbackHandler(**handler_kwargs)
        self._project = ProjectCallbackHandler(**handler_kwargs)
        self._context = ContextCallbackHandler(**handler_kwargs)
        self._variables = VariableCallbackHandler(**handler_kwargs)

        from presentation.handlers.callbacks.plugins import PluginCallbackHandler
        self._plugins = PluginCallbackHandler(**handler_kwargs)

    def get_user_state(self, user_id: int) -> dict | None:
        """Get current user state if any."""
        # Check project handler state first
        project_state = self._project.get_user_state(user_id)
        if project_state:
            return project_state
        return self._user_states.get(user_id)

    async def process_user_input(self, message) -> bool:
        """
        Process user input based on current state.
        Returns True if input was consumed, False otherwise.
        """
        user_id = message.from_user.id

        # Try project handler first
        if await self._project.process_user_input(message):
            return True

        # Try global variable input
        if self._variables.is_gvar_input_active(user_id):
            return await self._variables.process_gvar_input(user_id, message.text, message)

        # Legacy state handling
        state = self._user_states.get(user_id)
        if not state:
            return False

        return False

    async def handle_command_approve(self, callback: CallbackQuery) -> None:
        """Handle command approval callback"""
        command_id = CallbackData.get_command_id(callback.data)
        if not command_id:
            await callback.answer("❌ Неверная команда")
            return

        try:
            # Execute command
            result = await self.bot_service.execute_command(command_id)

            # Format output
            display_output = result.full_output
            if len(display_output) > 3000:
                display_output = display_output[:1000] + "\n... [OUTPUT TRUNCATED] ...\n" + display_output[-500:]

            # Update message with result
            await callback.message.edit_text(
                f"🚀 <b>Command executed</b>\n\n"
                f"<pre><code>{html.escape(display_output)}</code></pre>\n\n"
                f"⏱️ Time: {result.execution_time:.2f}s | Exit code: {result.exit_code}",
                parse_mode="HTML"
            )

            # Send result to AI for follow-up
            from domain.value_objects.user_id import UserId
            session = await self.bot_service.session_repository.find_active_by_user(
                UserId.from_int(callback.from_user.id)
            )

            # Get AI commentary on result
            try:
                response, _ = await self.bot_service.chat(
                    user_id=callback.from_user.id,
                    message="",
                    enable_tools=False
                )
                if response:
                    await callback.message.answer(response, parse_mode=None)
            except (asyncio.TimeoutError, ConnectionError) as e:
                # Network-related errors - skip AI follow-up gracefully
                logger.warning(f"AI follow-up failed due to network error: {e}")
            except Exception as e:
                # Other errors - log but don't break the flow
                logger.error(f"Unexpected error in AI follow-up: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            await callback.message.edit_text(f"❌ Ошибка: {str(e)}", parse_mode=None)

        await callback.answer()

    async def handle_command_cancel(self, callback: CallbackQuery) -> None:
        """Handle command cancellation callback"""
        command_id = CallbackData.get_command_id(callback.data)
        if not command_id:
            await callback.answer("❌ Неверная команда")
            return

        try:
            await self.bot_service.reject_command(command_id, "Отменено пользователем")
            await callback.message.edit_text("❌ Command cancelled")
        except Exception as e:
            logger.error(f"Error cancelling command: {e}")
            await callback.message.edit_text(f"❌ Ошибка: {str(e)}")

        await callback.answer()

    # ============== Docker Handlers (delegated to _docker) ==============

    async def handle_metrics_refresh(self, callback: CallbackQuery) -> None:
        """Delegate to DockerCallbackHandler."""
        await self._docker.handle_metrics_refresh(callback)

    async def handle_docker_list(self, callback: CallbackQuery) -> None:
        """Delegate to DockerCallbackHandler."""
        await self._docker.handle_docker_list(callback)

    async def handle_docker_stop(self, callback: CallbackQuery) -> None:
        """Delegate to DockerCallbackHandler."""
        await self._docker.handle_docker_stop(callback)

    async def handle_docker_start(self, callback: CallbackQuery) -> None:
        """Delegate to DockerCallbackHandler."""
        await self._docker.handle_docker_start(callback)

    async def handle_docker_restart(self, callback: CallbackQuery) -> None:
        """Delegate to DockerCallbackHandler."""
        await self._docker.handle_docker_restart(callback)

    async def handle_docker_logs(self, callback: CallbackQuery) -> None:
        """Delegate to DockerCallbackHandler."""
        await self._docker.handle_docker_logs(callback)

    async def handle_docker_rm(self, callback: CallbackQuery) -> None:
        """Delegate to DockerCallbackHandler."""
        await self._docker.handle_docker_rm(callback)

    async def handle_docker_info(self, callback: CallbackQuery) -> None:
        """Delegate to DockerCallbackHandler."""
        await self._docker.handle_docker_info(callback)

    async def handle_metrics_top(self, callback: CallbackQuery) -> None:
        """Delegate to DockerCallbackHandler."""
        await self._docker.handle_metrics_top(callback)

    async def handle_commands_history(self, callback: CallbackQuery) -> None:
        """Handle commands history request"""
        try:
            from domain.value_objects.user_id import UserId
            user_id = UserId.from_int(callback.from_user.id)

            commands = await self.bot_service.command_repository.find_by_user(user_id, limit=10)

            if not commands:
                text = "📝 <b>История команд</b>\n\nКоманд пока нет."
            else:
                lines = ["📝 <b>История команд:</b>\n"]
                for cmd in commands[:10]:
                    status_emoji = "✅" if cmd.status.value == "completed" else "⏳"
                    cmd_preview = cmd.command[:30] + "..." if len(cmd.command) > 30 else cmd.command
                    lines.append(f"{status_emoji} <code>{cmd_preview}</code>")

                text = "\n".join(lines)

            await callback.message.edit_text(text, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error getting command history: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

        await callback.answer()

    # ============== Claude Code HITL Callbacks (delegated to _claude) ==============

    async def handle_claude_approve(self, callback: CallbackQuery) -> None:
        await self._claude.handle_claude_approve(callback)

    async def handle_claude_reject(self, callback: CallbackQuery) -> None:
        await self._claude.handle_claude_reject(callback)

    async def handle_claude_clarify(self, callback: CallbackQuery) -> None:
        await self._claude.handle_claude_clarify(callback)

    async def handle_claude_answer(self, callback: CallbackQuery) -> None:
        await self._claude.handle_claude_answer(callback)

    async def handle_claude_other(self, callback: CallbackQuery) -> None:
        await self._claude.handle_claude_other(callback)

    async def handle_claude_cancel(self, callback: CallbackQuery) -> None:
        await self._claude.handle_claude_cancel(callback)

    async def handle_claude_continue(self, callback: CallbackQuery) -> None:
        await self._claude.handle_claude_continue(callback)

    # ============== Plan Approval Callbacks (delegated to _claude) ==============

    async def handle_plan_approve(self, callback: CallbackQuery) -> None:
        await self._claude.handle_plan_approve(callback)

    async def handle_plan_reject(self, callback: CallbackQuery) -> None:
        await self._claude.handle_plan_reject(callback)

    async def handle_plan_clarify(self, callback: CallbackQuery) -> None:
        await self._claude.handle_plan_clarify(callback)

    async def handle_plan_cancel(self, callback: CallbackQuery) -> None:
        await self._claude.handle_plan_cancel(callback)

    # ============== Project Management Callbacks (delegated to _project) ==============

    async def handle_project_select(self, callback: CallbackQuery) -> None:
        await self._project.handle_project_select(callback)

    async def handle_project_switch(self, callback: CallbackQuery) -> None:
        await self._project.handle_project_switch(callback)

    async def handle_project_create(self, callback: CallbackQuery) -> None:
        await self._project.handle_project_create(callback)

    async def handle_project_browse(self, callback: CallbackQuery) -> None:
        await self._project.handle_project_browse(callback)

    async def handle_project_folder(self, callback: CallbackQuery) -> None:
        await self._project.handle_project_folder(callback)

    async def handle_project_mkdir(self, callback: CallbackQuery) -> None:
        await self._project.handle_project_mkdir(callback)

    async def handle_project_mkdir_input(self, message, folder_name: str) -> bool:
        return await self._project.handle_project_mkdir_input(message, folder_name)

    async def handle_project_delete(self, callback: CallbackQuery) -> None:
        await self._project.handle_project_delete(callback)

    async def handle_project_delete_confirm(self, callback: CallbackQuery) -> None:
        await self._project.handle_project_delete_confirm(callback)

    async def handle_project_back(self, callback: CallbackQuery) -> None:
        await self._project.handle_project_back(callback)

    # ============== Context Management Callbacks (delegated to _context) ==============

    async def handle_context_menu(self, callback: CallbackQuery) -> None:
        await self._context.handle_context_menu(callback)

    async def handle_context_list(self, callback: CallbackQuery) -> None:
        await self._context.handle_context_list(callback)

    async def handle_context_switch(self, callback: CallbackQuery) -> None:
        await self._context.handle_context_switch(callback)

    async def handle_context_new(self, callback: CallbackQuery) -> None:
        await self._context.handle_context_new(callback)

    async def handle_context_clear(self, callback: CallbackQuery) -> None:
        await self._context.handle_context_clear(callback)

    async def handle_context_clear_confirm(self, callback: CallbackQuery) -> None:
        await self._context.handle_context_clear_confirm(callback)

    async def handle_context_close(self, callback: CallbackQuery) -> None:
        await self._context.handle_context_close(callback)

    # ============== File Browser Callbacks (/cd command) - delegated to _project ==============

    async def handle_cd_goto(self, callback: CallbackQuery) -> None:
        await self._project.handle_cd_goto(callback)

    async def handle_cd_root(self, callback: CallbackQuery) -> None:
        await self._project.handle_cd_root(callback)

    async def handle_cd_select(self, callback: CallbackQuery) -> None:
        await self._project.handle_cd_select(callback)

    async def handle_cd_close(self, callback: CallbackQuery) -> None:
        await self._project.handle_cd_close(callback)

    # ============== Variable Management Callbacks (delegated to _variables) ==============

    async def handle_vars_list(self, callback: CallbackQuery) -> None:
        await self._variables.handle_vars_list(callback)

    async def handle_vars_add(self, callback: CallbackQuery) -> None:
        await self._variables.handle_vars_add(callback)

    async def handle_vars_show(self, callback: CallbackQuery) -> None:
        await self._variables.handle_vars_show(callback)

    async def handle_vars_edit(self, callback: CallbackQuery) -> None:
        await self._variables.handle_vars_edit(callback)

    async def handle_vars_delete(self, callback: CallbackQuery) -> None:
        await self._variables.handle_vars_delete(callback)

    async def handle_vars_delete_confirm(self, callback: CallbackQuery) -> None:
        await self._variables.handle_vars_delete_confirm(callback)

    async def handle_vars_close(self, callback: CallbackQuery) -> None:
        await self._variables.handle_vars_close(callback)

    async def handle_vars_cancel(self, callback: CallbackQuery) -> None:
        await self._variables.handle_vars_cancel(callback)

    async def handle_vars_skip_desc(self, callback: CallbackQuery) -> None:
        await self._variables.handle_vars_skip_desc(callback)

    # ============== Global Variables Handlers (delegated to _variables) ==============

    async def handle_gvar_list(self, callback: CallbackQuery) -> None:
        await self._variables.handle_gvar_list(callback)

    async def handle_gvar_add(self, callback: CallbackQuery) -> None:
        await self._variables.handle_gvar_add(callback)

    async def handle_gvar_show(self, callback: CallbackQuery) -> None:
        await self._variables.handle_gvar_show(callback)

    async def handle_gvar_edit(self, callback: CallbackQuery) -> None:
        await self._variables.handle_gvar_edit(callback)

    async def handle_gvar_delete(self, callback: CallbackQuery) -> None:
        await self._variables.handle_gvar_delete(callback)

    async def handle_gvar_delete_confirm(self, callback: CallbackQuery) -> None:
        await self._variables.handle_gvar_delete_confirm(callback)

    async def handle_gvar_cancel(self, callback: CallbackQuery) -> None:
        await self._variables.handle_gvar_cancel(callback)

    async def handle_gvar_skip_desc(self, callback: CallbackQuery) -> None:
        await self._variables.handle_gvar_skip_desc(callback)

    def is_gvar_input_active(self, user_id: int) -> bool:
        return self._variables.is_gvar_input_active(user_id)

    def get_gvar_input_step(self, user_id: int) -> Optional[str]:
        return self._variables.get_gvar_input_step(user_id)

    async def process_gvar_input(self, user_id: int, text: str, message) -> bool:
        return await self._variables.process_gvar_input(user_id, text, message)

    # ============== Plugin Management Handlers (delegated to _plugins) ==============

    async def handle_plugin_list(self, callback: CallbackQuery) -> None:
        await self._plugins.handle_plugin_list(callback)

    async def handle_plugin_refresh(self, callback: CallbackQuery) -> None:
        await self._plugins.handle_plugin_refresh(callback)

    async def handle_plugin_marketplace(self, callback: CallbackQuery) -> None:
        await self._plugins.handle_plugin_marketplace(callback)

    async def handle_plugin_info(self, callback: CallbackQuery) -> None:
        await self._plugins.handle_plugin_info(callback)

    async def handle_plugin_enable(self, callback: CallbackQuery) -> None:
        await self._plugins.handle_plugin_enable(callback)

    async def handle_plugin_disable(self, callback: CallbackQuery) -> None:
        await self._plugins.handle_plugin_disable(callback)

    async def handle_plugin_close(self, callback: CallbackQuery) -> None:
        await self._plugins.handle_plugin_close(callback)


def register_handlers(router: Router, handlers: CallbackHandlers) -> None:
    """Register callback handlers"""
    # Legacy command handlers
    router.callback_query.register(
        handlers.handle_command_approve,
        F.data.startswith("exec:")
    )
    router.callback_query.register(
        handlers.handle_command_cancel,
        F.data.startswith("cancel:")
    )
    router.callback_query.register(
        handlers.handle_metrics_refresh,
        F.data == "metrics:refresh"
    )
    router.callback_query.register(
        handlers.handle_docker_list,
        F.data == "docker:list"
    )

    # Claude Code HITL handlers
    router.callback_query.register(
        handlers.handle_claude_approve,
        F.data.startswith("claude:approve:")
    )
    router.callback_query.register(
        handlers.handle_claude_reject,
        F.data.startswith("claude:reject:")
    )
    router.callback_query.register(
        handlers.handle_claude_clarify,
        F.data.startswith("claude:clarify:")
    )
    router.callback_query.register(
        handlers.handle_claude_answer,
        F.data.startswith("claude:answer:")
    )
    router.callback_query.register(
        handlers.handle_claude_other,
        F.data.startswith("claude:other:")
    )
    router.callback_query.register(
        handlers.handle_claude_cancel,
        F.data.startswith("claude:cancel:")
    )
    router.callback_query.register(
        handlers.handle_claude_continue,
        F.data.startswith("claude:continue:")
    )

    # Plan approval handlers (ExitPlanMode)
    router.callback_query.register(
        handlers.handle_plan_approve,
        F.data.startswith("plan:approve:")
    )
    router.callback_query.register(
        handlers.handle_plan_reject,
        F.data.startswith("plan:reject:")
    )
    router.callback_query.register(
        handlers.handle_plan_clarify,
        F.data.startswith("plan:clarify:")
    )
    router.callback_query.register(
        handlers.handle_plan_cancel,
        F.data.startswith("plan:cancel:")
    )

    # Project management handlers (specific first, then generic)
    router.callback_query.register(
        handlers.handle_project_switch,
        F.data.startswith("project:switch:")
    )
    router.callback_query.register(
        handlers.handle_project_delete_confirm,
        F.data.startswith("project:delete_confirm:")
    )
    router.callback_query.register(
        handlers.handle_project_delete,
        F.data.startswith("project:delete:")
    )
    router.callback_query.register(
        handlers.handle_project_back,
        F.data == "project:back"
    )
    router.callback_query.register(
        handlers.handle_project_create,
        F.data == "project:create"
    )
    router.callback_query.register(
        handlers.handle_project_mkdir,
        F.data == "project:mkdir"
    )
    router.callback_query.register(
        handlers.handle_project_browse,
        F.data.startswith("project:browse")
    )
    router.callback_query.register(
        handlers.handle_project_folder,
        F.data.startswith("project:folder:")
    )
    # Legacy project selection (fallback)
    router.callback_query.register(
        handlers.handle_project_select,
        F.data.startswith("project:")
    )

    # Context management handlers (ctx: prefix for shorter callback data)
    router.callback_query.register(
        handlers.handle_context_menu,
        F.data == "ctx:menu"
    )
    router.callback_query.register(
        handlers.handle_context_list,
        F.data == "ctx:list"
    )
    router.callback_query.register(
        handlers.handle_context_new,
        F.data == "ctx:new"
    )
    router.callback_query.register(
        handlers.handle_context_clear,
        F.data == "ctx:clear"
    )
    router.callback_query.register(
        handlers.handle_context_clear_confirm,
        F.data == "ctx:clear:confirm"
    )
    router.callback_query.register(
        handlers.handle_context_switch,
        F.data.startswith("ctx:switch:")
    )
    router.callback_query.register(
        handlers.handle_context_close,
        F.data == "ctx:close"
    )

    # Variable management handlers (var: prefix)
    router.callback_query.register(
        handlers.handle_vars_list,
        F.data == "var:list"
    )
    router.callback_query.register(
        handlers.handle_vars_add,
        F.data == "var:add"
    )
    router.callback_query.register(
        handlers.handle_vars_close,
        F.data == "var:close"
    )
    router.callback_query.register(
        handlers.handle_vars_cancel,
        F.data == "var:cancel"
    )
    router.callback_query.register(
        handlers.handle_vars_skip_desc,
        F.data == "var:skip_desc"
    )
    router.callback_query.register(
        handlers.handle_vars_show,
        F.data.startswith("var:show:")
    )
    router.callback_query.register(
        handlers.handle_vars_edit,
        F.data.startswith("var:e:")
    )
    router.callback_query.register(
        handlers.handle_vars_delete,
        F.data.startswith("var:d:")
    )
    router.callback_query.register(
        handlers.handle_vars_delete_confirm,
        F.data.startswith("var:dc:")
    )

    # Global variable management handlers (gvar: prefix)
    router.callback_query.register(
        handlers.handle_gvar_list,
        F.data == "gvar:list"
    )
    router.callback_query.register(
        handlers.handle_gvar_add,
        F.data == "gvar:add"
    )
    router.callback_query.register(
        handlers.handle_gvar_cancel,
        F.data == "gvar:cancel"
    )
    router.callback_query.register(
        handlers.handle_gvar_skip_desc,
        F.data == "gvar:skip_desc"
    )
    router.callback_query.register(
        handlers.handle_gvar_show,
        F.data.startswith("gvar:show:")
    )
    router.callback_query.register(
        handlers.handle_gvar_edit,
        F.data.startswith("gvar:e:")
    )
    router.callback_query.register(
        handlers.handle_gvar_delete,
        F.data.startswith("gvar:d:")
    )
    router.callback_query.register(
        handlers.handle_gvar_delete_confirm,
        F.data.startswith("gvar:dc:")
    )

    # File browser handlers (/cd command)
    router.callback_query.register(
        handlers.handle_cd_goto,
        F.data.startswith("cd:goto:")
    )
    router.callback_query.register(
        handlers.handle_cd_root,
        F.data == "cd:root"
    )
    router.callback_query.register(
        handlers.handle_cd_select,
        F.data.startswith("cd:select:")
    )
    router.callback_query.register(
        handlers.handle_cd_close,
        F.data == "cd:close"
    )

    # Docker action handlers
    router.callback_query.register(
        handlers.handle_docker_stop,
        F.data.startswith("docker:stop:")
    )
    router.callback_query.register(
        handlers.handle_docker_start,
        F.data.startswith("docker:start:")
    )
    router.callback_query.register(
        handlers.handle_docker_restart,
        F.data.startswith("docker:restart:")
    )
    router.callback_query.register(
        handlers.handle_docker_logs,
        F.data.startswith("docker:logs:")
    )
    router.callback_query.register(
        handlers.handle_docker_rm,
        F.data.startswith("docker:rm:")
    )
    router.callback_query.register(
        handlers.handle_docker_info,
        F.data.startswith("docker:info:")
    )

    # Metrics handlers
    router.callback_query.register(
        handlers.handle_metrics_top,
        F.data == "metrics:top"
    )

    # Commands history handler
    router.callback_query.register(
        handlers.handle_commands_history,
        F.data == "commands:history"
    )

    # Plugin management handlers
    router.callback_query.register(
        handlers.handle_plugin_list,
        F.data == "plugin:list"
    )
    router.callback_query.register(
        handlers.handle_plugin_refresh,
        F.data == "plugin:refresh"
    )
    router.callback_query.register(
        handlers.handle_plugin_marketplace,
        F.data == "plugin:marketplace"
    )
    router.callback_query.register(
        handlers.handle_plugin_info,
        F.data.startswith("plugin:info:")
    )
    router.callback_query.register(
        handlers.handle_plugin_enable,
        F.data.startswith("plugin:enable:")
    )
    router.callback_query.register(
        handlers.handle_plugin_disable,
        F.data.startswith("plugin:disable:")
    )
    router.callback_query.register(
        handlers.handle_plugin_close,
        F.data == "plugin:close"
    )


def get_callback_handlers(
    bot_service,
    message_handlers,
    claude_proxy=None,
    project_service=None,
    context_service=None,
    file_browser_service=None
) -> CallbackHandlers:
    """Factory function to create callback handlers"""
    return CallbackHandlers(
        bot_service,
        message_handlers,
        claude_proxy,
        project_service,
        context_service,
        file_browser_service
    )
