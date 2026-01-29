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
        file_browser_service=None
    ):
        self.bot_service = bot_service
        self.message_handlers = message_handlers
        self.claude_proxy = claude_proxy  # ClaudeCodeProxyService instance (fallback)
        self.sdk_service = sdk_service    # ClaudeAgentSDKService instance (preferred)
        self.project_service = project_service
        self.context_service = context_service
        self.file_browser_service = file_browser_service
        self._user_states = {}  # For tracking user input states (e.g., waiting for folder name)

        # Initialize specialized handlers
        handler_args = (
            bot_service, message_handlers, claude_proxy, sdk_service,
            project_service, context_service, file_browser_service
        )
        self._docker = DockerCallbackHandler(*handler_args)
        self._claude = ClaudeCallbackHandler(*handler_args)
        self._project = ProjectCallbackHandler(*handler_args)
        self._context = ContextCallbackHandler(*handler_args)
        self._variables = VariableCallbackHandler(*handler_args)

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
                f"<pre>{display_output}</pre>\n\n"
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
            except:
                pass  # Skip AI follow-up on error

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

    # ============== Context Management Callbacks ==============

    async def _get_context_data(self, callback: CallbackQuery):
        """Helper to get project, context and user data for context operations"""
        user_id = callback.from_user.id

        if not self.project_service or not self.context_service:
            await callback.answer("⚠️ Сервисы недоступны")
            return None, None, None, None

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        project = await self.project_service.get_current(uid)
        if not project:
            await callback.answer("❌ Нет активного проекта")
            return None, None, None, None

        current_ctx = await self.context_service.get_current(project.id)
        return uid, project, current_ctx, self.context_service

    async def handle_context_menu(self, callback: CallbackQuery) -> None:
        """Show context main menu"""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            ctx_name = current_ctx.name if current_ctx else "не выбран"
            msg_count = current_ctx.message_count if current_ctx else 0
            has_session = current_ctx.has_session if current_ctx else False

            session_status = "📜 Есть сессия" if has_session else "✨ Чистый"
            text = (
                f"💬 Управление контекстами\n\n"
                f"📂 Проект: {project.name}\n"
                f"💬 Контекст: {ctx_name}\n"
                f"📝 Сообщений: {msg_count}\n"
                f"📌 Статус: {session_status}"
            )

            keyboard = Keyboards.context_menu(ctx_name, project.name, msg_count, show_back=True, back_to="menu:context")
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing context menu: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_context_list(self, callback: CallbackQuery) -> None:
        """Show list of contexts"""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            contexts = await ctx_service.list_contexts(project.id)
            current_id = current_ctx.id if current_ctx else None

            if contexts:
                text = f"💬 Контексты проекта {project.name}\n\nВыберите контекст:"
                keyboard = Keyboards.context_list(contexts, current_id)
            else:
                # Create default context if none exist
                context = await ctx_service.create_new(project.id, uid, "main", set_as_current=True)
                text = f"✨ Создан контекст: {context.name}"
                keyboard = Keyboards.context_menu(context.name, project.name, 0, show_back=True, back_to="menu:context")

            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error listing contexts: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_context_switch(self, callback: CallbackQuery) -> None:
        """Handle context switch"""
        context_id = callback.data.split(":")[-1]

        try:
            uid, project, _, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            context = await ctx_service.switch_context(project.id, context_id)

            if context:
                session_status = "📜 Есть сессия" if context.has_session else "✨ Чистый"
                text = (
                    f"💬 Переключено на контекст:\n\n"
                    f"📝 {context.name}\n"
                    f"📊 Сообщений: {context.message_count}\n"
                    f"📂 Проект: {project.name}\n"
                    f"📌 Статус: {session_status}"
                )
                keyboard = Keyboards.context_menu(context.name, project.name, context.message_count, show_back=True, back_to="menu:context")
                await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
                await callback.answer(f"Контекст: {context.name}")
            else:
                await callback.answer("❌ Контекст не найден")

        except Exception as e:
            logger.error(f"Error switching context: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_context_new(self, callback: CallbackQuery) -> None:
        """Handle new context creation"""
        try:
            uid, project, _, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            context = await ctx_service.create_new(project.id, uid, set_as_current=True)

            text = (
                f"✨ Новый контекст создан\n\n"
                f"📝 {context.name}\n"
                f"📂 Проект: {project.name}\n\n"
                f"Чистый старт — без истории!\n"
                f"Отправьте первое сообщение."
            )
            keyboard = Keyboards.context_menu(context.name, project.name, 0, show_back=True, back_to="menu:context")
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer(f"Создан {context.name}")

        except Exception as e:
            logger.error(f"Error creating context: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_context_clear(self, callback: CallbackQuery) -> None:
        """Show clear confirmation"""
        try:
            uid, project, current_ctx, _ = await self._get_context_data(callback)
            if not project:
                return

            if not current_ctx:
                await callback.answer("❌ Нет активного контекста")
                return

            text = (
                f"🗑️ Очистить контекст?\n\n"
                f"📝 {current_ctx.name}\n"
                f"📊 Сообщений: {current_ctx.message_count}\n\n"
                f"⚠️ Вся история будет удалена!"
            )
            keyboard = Keyboards.context_clear_confirm()
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing clear confirm: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_context_clear_confirm(self, callback: CallbackQuery) -> None:
        """Confirm and clear context - creates NEW context for fresh start"""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            if not current_ctx:
                await callback.answer("❌ Нет активного контекста")
                return

            # 1. Create new context (auto-generated name, set as current)
            new_context = await ctx_service.create_new(
                project_id=project.id,
                user_id=uid,
                name=None,  # Auto-generate name
                set_as_current=True
            )

            # 2. Clear in-memory session cache to ensure fresh start
            user_id = callback.from_user.id
            if self.message_handlers:
                self.message_handlers.clear_session_cache(user_id)

            text = (
                f"✅ Новый контекст создан\n\n"
                f"📝 {new_context.name}\n"
                f"📂 Проект: {project.name}\n\n"
                f"Начните новый диалог."
            )
            keyboard = Keyboards.context_menu(new_context.name, project.name, 0, show_back=True, back_to="menu:context")
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer("Новый контекст создан")

        except Exception as e:
            logger.error(f"Error clearing context: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_context_close(self, callback: CallbackQuery) -> None:
        """Close context menu"""
        try:
            await callback.message.delete()
            await callback.answer()
        except Exception as e:
            logger.debug(f"Error closing context menu: {e}")
            await callback.answer()

    # ============== File Browser Callbacks (/cd command) ==============

    async def handle_cd_goto(self, callback: CallbackQuery) -> None:
        """Handle folder navigation in /cd command"""
        # Extract path from callback data (cd:goto:/path/to/folder)
        path = callback.data.split(":", 2)[-1] if callback.data.count(":") >= 2 else ""

        if not self.file_browser_service:
            from application.services.file_browser_service import FileBrowserService
            self.file_browser_service = FileBrowserService()

        # Validate path is within root
        if not self.file_browser_service.is_within_root(path):
            await callback.answer("❌ Доступ запрещен")
            return

        # Check if directory exists
        import os
        if not os.path.isdir(path):
            await callback.answer("❌ Папка не найдена")
            return

        try:
            from presentation.keyboards.keyboards import Keyboards

            # Get content and tree view
            content = await self.file_browser_service.list_directory(path)
            tree_view = await self.file_browser_service.get_tree_view(path)

            # Update message
            await callback.message.edit_text(
                tree_view,
                parse_mode=ParseMode.HTML,
                reply_markup=Keyboards.file_browser(content)
            )
            await callback.answer()

        except Exception as e:
            logger.error(f"Error navigating to {path}: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_cd_root(self, callback: CallbackQuery) -> None:
        """Handle going to root directory"""
        if not self.file_browser_service:
            from application.services.file_browser_service import FileBrowserService
            self.file_browser_service = FileBrowserService()

        try:
            from presentation.keyboards.keyboards import Keyboards

            root_path = self.file_browser_service.ROOT_PATH

            # Ensure root exists
            import os
            os.makedirs(root_path, exist_ok=True)

            # Get content and tree view
            content = await self.file_browser_service.list_directory(root_path)
            tree_view = await self.file_browser_service.get_tree_view(root_path)

            # Update message
            await callback.message.edit_text(
                tree_view,
                parse_mode=ParseMode.HTML,
                reply_markup=Keyboards.file_browser(content)
            )
            await callback.answer("🏠 Корень")

        except Exception as e:
            logger.error(f"Error going to root: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_cd_select(self, callback: CallbackQuery) -> None:
        """Handle selecting folder as working directory"""
        # Extract path from callback data (cd:select:/path/to/folder)
        path = callback.data.split(":", 2)[-1] if callback.data.count(":") >= 2 else ""
        user_id = callback.from_user.id

        if not self.file_browser_service:
            from application.services.file_browser_service import FileBrowserService
            self.file_browser_service = FileBrowserService()

        # Validate path
        if not self.file_browser_service.is_within_root(path):
            await callback.answer("❌ Доступ запрещен")
            return

        import os
        if not os.path.isdir(path):
            await callback.answer("❌ Папка не найдена")
            return

        try:
            # Set working directory
            if self.message_handlers:
                self.message_handlers.set_working_dir(user_id, path)

            # Create/switch project if project_service available
            project_name = os.path.basename(path) or "root"
            if self.project_service:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)

                # First check if project with exact path exists
                existing = await self.project_service.project_repository.find_by_path(uid, path)
                if existing:
                    # Use existing project
                    project = existing
                else:
                    # Create new project for this exact path (don't use parent)
                    project = await self.project_service.create_project(uid, project_name, path)

                await self.project_service.switch_project(uid, project.id)
                project_name = project.name

            # Update message with confirmation
            import html
            await callback.message.edit_text(
                f"✅ <b>Рабочая директория установлена</b>\n\n"
                f"<b>Путь:</b> <code>{html.escape(path)}</code>\n"
                f"<b>Проект:</b> {html.escape(project_name)}\n\n"
                f"Теперь все команды Claude будут выполняться здесь.\n"
                f"Отправьте сообщение, чтобы начать работу.",
                parse_mode=ParseMode.HTML
            )
            await callback.answer(f"✅ {project_name}")

        except Exception as e:
            logger.error(f"Error selecting folder {path}: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_cd_close(self, callback: CallbackQuery) -> None:
        """Handle closing the file browser"""
        try:
            await callback.message.delete()
            await callback.answer("Закрыто")
        except Exception as e:
            logger.error(f"Error closing file browser: {e}")
            await callback.answer("Закрыто")

    # ============== Variable Management Callbacks ==============

    async def _get_var_context(self, callback: CallbackQuery):
        """Helper to get project and context for variable operations"""
        user_id = callback.from_user.id

        if not self.project_service or not self.context_service:
            await callback.answer("⚠️ Сервисы недоступны")
            return None, None

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        project = await self.project_service.get_current(uid)
        if not project:
            await callback.answer("❌ Нет активного проекта")
            return None, None

        context = await self.context_service.get_current(project.id)
        if not context:
            await callback.answer("❌ Нет активного контекста")
            return None, None

        return project, context

    async def handle_vars_list(self, callback: CallbackQuery) -> None:
        """Show variables list menu"""
        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            from presentation.keyboards.keyboards import Keyboards

            variables = await self.context_service.get_variables(context.id)

            if variables:
                lines = [f"📋 Переменные контекста\n"]
                lines.append(f"📂 {project.name} / {context.name}\n")
                for name in sorted(variables.keys()):
                    var = variables[name]
                    # Mask value for security
                    display_val = var.value[:8] + "***" if len(var.value) > 8 else var.value
                    lines.append(f"• {name} = {display_val}")
                    if var.description:
                        lines.append(f"  ↳ {var.description[:50]}")
                text = "\n".join(lines)
            else:
                text = (
                    f"📋 Переменные контекста\n\n"
                    f"📂 {project.name} / {context.name}\n\n"
                    f"Переменных пока нет.\n"
                    f"Нажмите ➕ Добавить для создания."
                )

            keyboard = Keyboards.variables_menu(variables, project.name, context.name, show_back=True, back_to="menu:context")
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing variables list: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_add(self, callback: CallbackQuery) -> None:
        """Start variable add flow - ask for name"""
        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            from presentation.keyboards.keyboards import Keyboards

            # Set state in message handlers to expect variable name
            user_id = callback.from_user.id
            if hasattr(self.message_handlers, 'start_var_input'):
                self.message_handlers.start_var_input(user_id, callback.message)

            text = (
                "📝 Добавление переменной\n\n"
                "Введите имя переменной:\n"
                "(например: GITLAB_TOKEN, API_KEY)"
            )
            keyboard = Keyboards.variable_cancel()
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer("Введите имя")

        except Exception as e:
            logger.error(f"Error starting var add: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_show(self, callback: CallbackQuery) -> None:
        """Show full variable info"""
        var_name = callback.data.split(":")[-1]

        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            from presentation.keyboards.keyboards import Keyboards

            var = await self.context_service.get_variable(context.id, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            text = (
                f"📋 Переменная: {var.name}\n\n"
                f"📂 {project.name} / {context.name}\n\n"
                f"Значение:\n{var.value}\n"
            )
            if var.description:
                text += f"\nОписание:\n{var.description}"

            # Back button
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"var:e:{var_name[:20]}"),
                    InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"var:d:{var_name[:20]}")
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="var:list")]
            ])
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_edit(self, callback: CallbackQuery) -> None:
        """Start variable edit flow"""
        var_name = callback.data.split(":")[-1]

        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            from presentation.keyboards.keyboards import Keyboards

            var = await self.context_service.get_variable(context.id, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            # Set state in message handlers to expect new value
            user_id = callback.from_user.id
            if hasattr(self.message_handlers, 'start_var_edit'):
                self.message_handlers.start_var_edit(user_id, var_name, callback.message)

            text = (
                f"✏️ Редактирование: {var.name}\n\n"
                f"Текущее значение:\n{var.value}\n\n"
                f"Введите новое значение:"
            )
            keyboard = Keyboards.variable_cancel()
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer("Введите новое значение")

        except Exception as e:
            logger.error(f"Error starting var edit: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_delete(self, callback: CallbackQuery) -> None:
        """Show delete confirmation"""
        var_name = callback.data.split(":")[-1]

        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            from presentation.keyboards.keyboards import Keyboards

            var = await self.context_service.get_variable(context.id, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            text = (
                f"🗑️ Удалить переменную?\n\n"
                f"📋 {var.name}\n"
                f"📂 {project.name} / {context.name}\n\n"
                f"⚠️ Это действие нельзя отменить!"
            )
            keyboard = Keyboards.variable_delete_confirm(var_name)
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing delete confirm: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_delete_confirm(self, callback: CallbackQuery) -> None:
        """Confirm and delete variable"""
        var_name = callback.data.split(":")[-1]

        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            deleted = await self.context_service.delete_variable(context.id, var_name)

            if deleted:
                await callback.answer(f"✅ {var_name} удалена")
                # Show updated list
                await self.handle_vars_list(callback)
            else:
                await callback.answer("❌ Переменная не найдена")

        except Exception as e:
            logger.error(f"Error deleting variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_close(self, callback: CallbackQuery) -> None:
        """Close variables menu"""
        try:
            await callback.message.delete()
            await callback.answer()
        except Exception as e:
            logger.debug(f"Error closing vars menu: {e}")
            await callback.answer()

    async def handle_vars_cancel(self, callback: CallbackQuery) -> None:
        """Cancel variable input and return to list"""
        user_id = callback.from_user.id

        # Clear input state
        if hasattr(self.message_handlers, 'cancel_var_input'):
            self.message_handlers.cancel_var_input(user_id)

        await callback.answer("Отменено")
        # Show list again
        await self.handle_vars_list(callback)

    async def handle_vars_skip_desc(self, callback: CallbackQuery) -> None:
        """Skip description input and save variable"""
        user_id = callback.from_user.id

        try:
            # Get pending variable data and save without description
            if hasattr(self.message_handlers, 'save_variable_skip_desc'):
                await self.message_handlers.save_variable_skip_desc(user_id, callback.message)
                await callback.answer("✅ Переменная сохранена")
                # Show updated list
                await self.handle_vars_list(callback)
            else:
                await callback.answer("❌ Нет данных для сохранения")

        except Exception as e:
            logger.error(f"Error saving variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Global Variables Handlers ==============

    # State storage for global variable input flow
    _gvar_input_state = {}  # {user_id: {"step": "name"|"value"|"desc", "name": str, "value": str}}

    async def handle_gvar_list(self, callback: CallbackQuery) -> None:
        """Show global variables list menu"""
        try:
            from domain.value_objects.user_id import UserId
            from presentation.keyboards.keyboards import Keyboards

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            variables = await self.context_service.get_global_variables(uid)

            if variables:
                lines = ["🌍 <b>Глобальные переменные</b>\n"]
                lines.append("<i>Наследуются всеми проектами</i>\n")
                for name in sorted(variables.keys()):
                    var = variables[name]
                    display_val = var.value[:8] + "***" if len(var.value) > 8 else var.value
                    lines.append(f"• <code>{name}</code> = {display_val}")
                    if var.description:
                        lines.append(f"  ↳ <i>{var.description[:50]}</i>")
                text = "\n".join(lines)
            else:
                text = (
                    "🌍 <b>Глобальные переменные</b>\n\n"
                    "<i>Наследуются всеми проектами</i>\n\n"
                    "Переменных пока нет.\n"
                    "Нажмите ➕ Добавить для создания."
                )

            keyboard = Keyboards.global_variables_menu(variables, show_back=True, back_to="menu:settings")
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing global variables list: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_add(self, callback: CallbackQuery) -> None:
        """Start global variable add flow"""
        try:
            from presentation.keyboards.keyboards import Keyboards

            user_id = callback.from_user.id

            # Set state to expect name input
            self._gvar_input_state[user_id] = {"step": "name", "name": None, "value": None}

            text = (
                "🌍 <b>Добавление глобальной переменной</b>\n\n"
                "Введите имя переменной:\n"
                "<i>(например: GITLAB_TOKEN, API_KEY)</i>"
            )
            keyboard = Keyboards.global_variable_cancel()
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer("Введите имя")

        except Exception as e:
            logger.error(f"Error starting gvar add: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_show(self, callback: CallbackQuery) -> None:
        """Show full global variable info"""
        var_name = callback.data.split(":")[-1]

        try:
            from domain.value_objects.user_id import UserId
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            var = await self.context_service.get_global_variable(uid, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            text = (
                f"🌍 <b>Глобальная переменная</b>\n\n"
                f"📋 <b>Имя:</b> <code>{var.name}</code>\n"
                f"📝 <b>Значение:</b> <code>{var.value}</code>\n"
            )
            if var.description:
                text += f"💬 <b>Описание:</b> {var.description}\n"

            text += "\n<i>Наследуется всеми проектами и контекстами</i>"

            buttons = [
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"gvar:e:{var_name[:20]}"),
                    InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"gvar:d:{var_name[:20]}")
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="gvar:list")]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing global variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_edit(self, callback: CallbackQuery) -> None:
        """Start global variable edit flow"""
        var_name = callback.data.split(":")[-1]

        try:
            from domain.value_objects.user_id import UserId
            from presentation.keyboards.keyboards import Keyboards

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            var = await self.context_service.get_global_variable(uid, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            # Set state to expect value input (editing existing var)
            self._gvar_input_state[user_id] = {
                "step": "value",
                "name": var_name,
                "value": None,
                "editing": True,
                "old_desc": var.description
            }

            text = (
                f"✏️ <b>Редактирование: {var_name}</b>\n\n"
                f"Текущее значение: <code>{var.value}</code>\n\n"
                f"Введите новое значение:"
            )
            keyboard = Keyboards.global_variable_cancel()
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer("Введите новое значение")

        except Exception as e:
            logger.error(f"Error starting gvar edit: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_delete(self, callback: CallbackQuery) -> None:
        """Show delete confirmation for global variable"""
        var_name = callback.data.split(":")[-1]

        try:
            from domain.value_objects.user_id import UserId
            from presentation.keyboards.keyboards import Keyboards

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            var = await self.context_service.get_global_variable(uid, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            text = (
                f"🗑️ <b>Удалить глобальную переменную?</b>\n\n"
                f"📋 <code>{var.name}</code>\n\n"
                f"⚠️ Это действие нельзя отменить!\n"
                f"Переменная перестанет наследоваться всеми проектами."
            )
            keyboard = Keyboards.global_variable_delete_confirm(var_name)
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing delete confirm: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_delete_confirm(self, callback: CallbackQuery) -> None:
        """Confirm and delete global variable"""
        var_name = callback.data.split(":")[-1]

        try:
            from domain.value_objects.user_id import UserId

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            deleted = await self.context_service.delete_global_variable(uid, var_name)

            if deleted:
                await callback.answer(f"✅ {var_name} удалена")
                await self.handle_gvar_list(callback)
            else:
                await callback.answer("❌ Переменная не найдена")

        except Exception as e:
            logger.error(f"Error deleting global variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_cancel(self, callback: CallbackQuery) -> None:
        """Cancel global variable input and return to list"""
        user_id = callback.from_user.id

        # Clear input state
        if user_id in self._gvar_input_state:
            del self._gvar_input_state[user_id]

        await callback.answer("Отменено")
        await self.handle_gvar_list(callback)

    async def handle_gvar_skip_desc(self, callback: CallbackQuery) -> None:
        """Skip description input and save global variable"""
        user_id = callback.from_user.id

        try:
            from domain.value_objects.user_id import UserId

            state = self._gvar_input_state.get(user_id)
            if not state or not state.get("name") or not state.get("value"):
                await callback.answer("❌ Нет данных для сохранения")
                return

            uid = UserId.from_int(user_id)

            await self.context_service.set_global_variable(
                uid,
                state["name"],
                state["value"],
                ""  # No description
            )

            # Clear state
            del self._gvar_input_state[user_id]

            await callback.answer(f"✅ {state['name']} сохранена")
            await self.handle_gvar_list(callback)

        except Exception as e:
            logger.error(f"Error saving global variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    def is_gvar_input_active(self, user_id: int) -> bool:
        """Check if user is in global variable input flow"""
        return user_id in self._gvar_input_state

    def get_gvar_input_step(self, user_id: int) -> Optional[str]:
        """Get current input step for user"""
        state = self._gvar_input_state.get(user_id)
        return state.get("step") if state else None

    async def process_gvar_input(self, user_id: int, text: str, message) -> bool:
        """Process text input for global variable flow. Returns True if handled."""
        state = self._gvar_input_state.get(user_id)
        if not state:
            return False

        from domain.value_objects.user_id import UserId
        from presentation.keyboards.keyboards import Keyboards

        step = state.get("step")
        uid = UserId.from_int(user_id)

        if step == "name":
            # Validate name
            var_name = text.strip().upper()
            if not var_name or not var_name.replace("_", "").isalnum():
                await message.answer(
                    "❌ Недопустимое имя переменной.\n"
                    "Используйте только буквы, цифры и подчёркивание.",
                    reply_markup=Keyboards.global_variable_cancel()
                )
                return True

            state["name"] = var_name
            state["step"] = "value"

            await message.answer(
                f"✅ Имя: <code>{var_name}</code>\n\n"
                f"Введите значение переменной:",
                parse_mode="HTML",
                reply_markup=Keyboards.global_variable_cancel()
            )
            return True

        elif step == "value":
            var_value = text.strip()
            if not var_value:
                await message.answer(
                    "❌ Значение не может быть пустым.",
                    reply_markup=Keyboards.global_variable_cancel()
                )
                return True

            state["value"] = var_value

            # If editing, use old description
            if state.get("editing"):
                old_desc = state.get("old_desc", "")
                await self.context_service.set_global_variable(
                    uid, state["name"], var_value, old_desc
                )
                del self._gvar_input_state[user_id]
                await message.answer(f"✅ Переменная {state['name']} обновлена!")

                # Show list
                variables = await self.context_service.get_global_variables(uid)
                await message.answer(
                    "🌍 <b>Глобальные переменные</b>",
                    parse_mode="HTML",
                    reply_markup=Keyboards.global_variables_menu(variables, show_back=True, back_to="menu:settings")
                )
                return True

            # Move to description step
            state["step"] = "desc"
            await message.answer(
                f"✅ Значение установлено\n\n"
                f"Введите описание (для Claude) или нажмите «Пропустить»:",
                reply_markup=Keyboards.global_variable_skip_description()
            )
            return True

        elif step == "desc":
            var_desc = text.strip()

            await self.context_service.set_global_variable(
                uid, state["name"], state["value"], var_desc
            )

            del self._gvar_input_state[user_id]
            await message.answer(f"✅ Глобальная переменная {state['name']} сохранена!")

            # Show list
            variables = await self.context_service.get_global_variables(uid)
            await message.answer(
                "🌍 <b>Глобальные переменные</b>",
                parse_mode="HTML",
                reply_markup=Keyboards.global_variables_menu(variables, show_back=True, back_to="menu:settings")
            )
            return True

        return False

    # ============== Plugin Management Handlers ==============

    async def handle_plugin_list(self, callback: CallbackQuery) -> None:
        """Show list of enabled plugins"""
        from presentation.keyboards.keyboards import Keyboards

        if not self.sdk_service:
            await callback.answer("⚠️ SDK не доступен")
            return

        plugins = self.sdk_service.get_enabled_plugins_info()

        if not plugins:
            text = (
                "🔌 <b>Плагины Claude Code</b>\n\n"
                "Нет активных плагинов.\n\n"
                "Нажмите 🛒 <b>Магазин</b> чтобы добавить плагины."
            )
        else:
            text = "🔌 <b>Плагины Claude Code</b>\n\n"
            for p in plugins:
                name = p.get("name", "unknown")
                desc = p.get("description", "")
                source = p.get("source", "official")
                available = p.get("available", True)

                status = "✅" if available else "⚠️"
                source_icon = "🌐" if source == "official" else "📁"
                text += f"{status} {source_icon} <b>{name}</b>\n"
                if desc:
                    text += f"   <i>{desc}</i>\n"

            text += f"\n<i>Всего: {len(plugins)} плагинов</i>"

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.plugins_menu(plugins)
        )
        await callback.answer()

    async def handle_plugin_refresh(self, callback: CallbackQuery) -> None:
        """Refresh plugins list"""
        await callback.answer("🔄 Обновлено")
        await self.handle_plugin_list(callback)

    async def handle_plugin_marketplace(self, callback: CallbackQuery) -> None:
        """Show marketplace with available plugins"""
        from presentation.keyboards.keyboards import Keyboards

        if not self.sdk_service:
            await callback.answer("⚠️ SDK не доступен")
            return

        # All available plugins from official marketplace
        marketplace_plugins = [
            {"name": "commit-commands", "desc": "Git workflow: commit, push, PR"},
            {"name": "code-review", "desc": "Ревью кода и PR"},
            {"name": "feature-dev", "desc": "Разработка фичи с архитектурой"},
            {"name": "frontend-design", "desc": "Создание UI интерфейсов"},
            {"name": "ralph-loop", "desc": "RAFL: итеративное решение задач"},
            {"name": "security-guidance", "desc": "Проверка безопасности кода"},
            {"name": "pr-review-toolkit", "desc": "Инструменты ревью PR"},
            {"name": "claude-code-setup", "desc": "Настройка Claude Code"},
            {"name": "hookify", "desc": "Управление хуками"},
            {"name": "explanatory-output-style", "desc": "Объяснительный стиль вывода"},
            {"name": "learning-output-style", "desc": "Обучающий стиль вывода"},
        ]

        # Get currently enabled plugins
        enabled = self.sdk_service.get_enabled_plugins_info()
        enabled_names = [p.get("name") for p in enabled]

        text = (
            "🛒 <b>Магазин плагинов</b>\n\n"
            "Выберите плагин для включения:\n"
            "✅ - уже включен\n"
            "➕ - нажмите чтобы включить\n\n"
            "<i>Изменения вступят в силу после перезапуска бота</i>"
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.plugins_marketplace(marketplace_plugins, enabled_names)
        )
        await callback.answer()

    async def handle_plugin_info(self, callback: CallbackQuery) -> None:
        """Show plugin info"""
        parts = callback.data.split(":")
        plugin_name = parts[2] if len(parts) > 2 else "unknown"

        # Plugin descriptions
        descriptions = {
            "commit-commands": "Автоматизация Git workflow: создание коммитов, пуш, создание PR с правильным форматированием.",
            "code-review": "Профессиональный ревью кода: находит баги, проблемы безопасности, предлагает улучшения.",
            "feature-dev": "Пошаговая разработка фичи: анализ архитектуры, планирование, реализация.",
            "frontend-design": "Создание красивых UI компонентов и страниц с современным дизайном.",
            "ralph-loop": "RAFL (Reflect-Act-Fix-Loop): итеративное решение сложных задач с самопроверкой.",
            "security-guidance": "Анализ безопасности кода: уязвимости, best practices, рекомендации.",
            "pr-review-toolkit": "Инструменты для ревью Pull Request'ов на GitHub.",
            "claude-code-setup": "Настройка и конфигурирование Claude Code.",
            "hookify": "Создание и управление git хуками.",
        }

        desc = descriptions.get(plugin_name, "Официальный плагин Claude Code")

        await callback.answer(f"ℹ️ {plugin_name}: {desc[:150]}", show_alert=True)

    async def handle_plugin_enable(self, callback: CallbackQuery) -> None:
        """Enable a plugin"""
        parts = callback.data.split(":")
        plugin_name = parts[2] if len(parts) > 2 else "unknown"

        if not self.sdk_service:
            await callback.answer("⚠️ SDK не доступен")
            return

        # Add plugin to enabled list
        if hasattr(self.sdk_service, 'add_plugin'):
            self.sdk_service.add_plugin(plugin_name)
            await callback.answer(f"✅ Плагин {plugin_name} включен!")
            await self.handle_plugin_marketplace(callback)
        else:
            await callback.answer(
                f"ℹ️ Добавьте {plugin_name} в CLAUDE_PLUGINS и перезапустите бота",
                show_alert=True
            )

    async def handle_plugin_disable(self, callback: CallbackQuery) -> None:
        """Disable a plugin"""
        parts = callback.data.split(":")
        plugin_name = parts[2] if len(parts) > 2 else "unknown"

        if not self.sdk_service:
            await callback.answer("⚠️ SDK не доступен")
            return

        # Remove plugin from enabled list
        if hasattr(self.sdk_service, 'remove_plugin'):
            self.sdk_service.remove_plugin(plugin_name)
            await callback.answer(f"❌ Плагин {plugin_name} отключен!")
            await self.handle_plugin_list(callback)
        else:
            await callback.answer(
                f"ℹ️ Удалите {plugin_name} из CLAUDE_PLUGINS и перезапустите бота",
                show_alert=True
            )

    async def handle_plugin_close(self, callback: CallbackQuery) -> None:
        """Close plugins menu"""
        await callback.message.delete()
        await callback.answer()


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
