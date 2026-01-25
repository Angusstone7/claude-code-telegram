"""
Menu Handlers

Handles the main inline menu navigation and all submenu interactions.
This replaces individual commands with a unified menu interface.
"""

import logging
import os
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)


class MenuHandlers:
    """
    Handlers for the main menu system.

    Provides:
    - Main menu display and navigation
    - Submenu navigation (projects, context, settings, system, help)
    - Integration with existing services
    """

    def __init__(
        self,
        bot_service,
        claude_proxy,
        sdk_service=None,
        project_service=None,
        context_service=None,
        file_browser_service=None,
        account_service=None,
        message_handlers=None,  # Reference to MessageHandlers for YOLO state
    ):
        self.bot_service = bot_service
        self.claude_proxy = claude_proxy
        self.sdk_service = sdk_service
        self.project_service = project_service
        self.context_service = context_service
        self.file_browser_service = file_browser_service
        self.account_service = account_service
        self.message_handlers = message_handlers
        self.router = Router(name="menu")
        self._register_handlers()

    def _register_handlers(self):
        """Register menu callback handlers"""
        # Main menu navigation
        self.router.callback_query.register(
            self.handle_menu_callback,
            F.data.startswith("menu:")
        )

    # ============== Helper Methods ==============

    def _get_yolo_enabled(self, user_id: int) -> bool:
        """Check if YOLO mode is enabled for user"""
        if self.message_handlers:
            return self.message_handlers.is_yolo_mode(user_id)
        return False

    def _get_working_dir(self, user_id: int) -> str:
        """Get user's working directory"""
        if self.message_handlers:
            return self.message_handlers.get_working_dir(user_id)
        return "/root"

    def _is_task_running(self, user_id: int) -> bool:
        """Check if a task is running for user"""
        if self.sdk_service and self.sdk_service.is_task_running(user_id):
            return True
        if self.claude_proxy and self.claude_proxy.is_task_running(user_id):
            return True
        return False

    async def _get_project_info(self, user_id: int) -> tuple[Optional[str], Optional[str]]:
        """Get current project name and working dir"""
        if not self.project_service:
            return None, self._get_working_dir(user_id)

        try:
            from domain.value_objects.user_id import UserId
            uid = UserId.from_int(user_id)
            project = await self.project_service.get_current(uid)
            if project:
                return project.name, project.working_dir
        except Exception as e:
            logger.warning(f"Error getting project info: {e}")

        return None, self._get_working_dir(user_id)

    async def _get_context_info(self, user_id: int) -> tuple[Optional[str], int, bool]:
        """Get current context info (name, message_count, has_session)"""
        if not self.project_service or not self.context_service:
            return None, 0, False

        try:
            from domain.value_objects.user_id import UserId
            uid = UserId.from_int(user_id)
            project = await self.project_service.get_current(uid)
            if project:
                context = await self.context_service.get_current(project.id)
                if context:
                    return context.name, context.message_count, context.has_session
        except Exception as e:
            logger.warning(f"Error getting context info: {e}")

        return None, 0, False

    async def _get_auth_info(self, user_id: int) -> tuple[str, bool]:
        """Get auth mode and credentials status"""
        if not self.account_service:
            return "zai_api", False

        try:
            settings = await self.account_service.get_settings(user_id)
            creds_info = self.account_service.get_credentials_info()
            return settings.auth_mode.value, creds_info.exists
        except Exception as e:
            logger.warning(f"Error getting auth info: {e}")

        return "zai_api", False

    # ============== Main Menu ==============

    async def show_main_menu(self, message: Message, edit: bool = False):
        """Show main menu"""
        user_id = message.from_user.id

        # Gather state info
        project_name, working_dir = await self._get_project_info(user_id)
        yolo_enabled = self._get_yolo_enabled(user_id)
        has_task = self._is_task_running(user_id)

        # Build status text
        project_info = f"📂 {project_name}" if project_name else "📂 Нет проекта"
        path_info = f"📁 `{working_dir}`"
        yolo_info = "⚡ YOLO: ON" if yolo_enabled else ""
        task_info = "🔄 Задача выполняется" if has_task else ""

        status_parts = [project_info, path_info]
        if yolo_info:
            status_parts.append(yolo_info)
        if task_info:
            status_parts.append(task_info)

        text = (
            f"🤖 <b>Claude Code Telegram</b>\n\n"
            f"{chr(10).join(status_parts)}\n\n"
            f"Выберите раздел:"
        )

        keyboard = Keyboards.main_menu_inline(
            working_dir=working_dir,
            project_name=project_name,
            yolo_enabled=yolo_enabled,
            has_active_task=has_task
        )

        if edit and hasattr(message, 'edit_text'):
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    # ============== Menu Callback Router ==============

    async def handle_menu_callback(self, callback: CallbackQuery, state: FSMContext):
        """Route menu callbacks to appropriate handlers"""
        user_id = callback.from_user.id
        data = callback.data

        logger.debug(f"[{user_id}] Menu callback: {data}")

        # Parse callback data: menu:section:action:param
        parts = data.split(":")
        section = parts[1] if len(parts) > 1 else ""
        action = parts[2] if len(parts) > 2 else ""
        param = parts[3] if len(parts) > 3 else ""

        # Route to appropriate handler
        if section == "main":
            await self._show_main(callback)

        elif section == "close":
            await callback.message.delete()
            await callback.answer()

        elif section == "projects":
            await self._handle_projects(callback, action, param, state)

        elif section == "context":
            await self._handle_context(callback, action, param, state)

        elif section == "settings":
            await self._handle_settings(callback, action, param, state)

        elif section == "plugins":
            await self._handle_plugins(callback, state)

        elif section == "system":
            await self._handle_system(callback, action, param, state)

        elif section == "help":
            await self._handle_help(callback, action, state)

        else:
            await callback.answer(f"Неизвестный раздел: {section}")

    # ============== Main Menu ==============

    async def _show_main(self, callback: CallbackQuery):
        """Show main menu via callback"""
        user_id = callback.from_user.id

        project_name, working_dir = await self._get_project_info(user_id)
        yolo_enabled = self._get_yolo_enabled(user_id)
        has_task = self._is_task_running(user_id)

        project_info = f"📂 {project_name}" if project_name else "📂 Нет проекта"
        path_info = f"📁 <code>{working_dir}</code>"

        status_parts = [project_info, path_info]
        if yolo_enabled:
            status_parts.append("⚡ YOLO: ON")
        if has_task:
            status_parts.append("🔄 Задача выполняется")

        text = (
            f"🤖 <b>Claude Code Telegram</b>\n\n"
            f"{chr(10).join(status_parts)}\n\n"
            f"Выберите раздел:"
        )

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.main_menu_inline(
                working_dir=working_dir,
                project_name=project_name,
                yolo_enabled=yolo_enabled,
                has_active_task=has_task
            ),
            parse_mode="HTML"
        )
        await callback.answer()

    # ============== Projects Section ==============

    async def _handle_projects(self, callback: CallbackQuery, action: str, param: str, state: FSMContext):
        """Handle projects submenu"""
        user_id = callback.from_user.id

        if not action:
            # Show projects submenu
            project_name, working_dir = await self._get_project_info(user_id)

            text = (
                f"📂 <b>Проекты</b>\n\n"
                f"Текущий проект: <b>{project_name or 'не выбран'}</b>\n"
                f"Путь: <code>{working_dir}</code>"
            )

            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.menu_projects(working_dir, project_name),
                parse_mode="HTML"
            )
            await callback.answer()

        elif action == "browse":
            # Show file browser
            await self._show_file_browser(callback, state)

        elif action == "change":
            # Show project list
            await self._show_project_list(callback, state)

    async def _show_file_browser(self, callback: CallbackQuery, state: FSMContext):
        """Show file browser interface"""
        user_id = callback.from_user.id

        if not self.file_browser_service:
            from application.services.file_browser_service import FileBrowserService
            self.file_browser_service = FileBrowserService()

        current_dir = self._get_working_dir(user_id)

        # Ensure within root
        if not self.file_browser_service.is_within_root(current_dir):
            current_dir = self.file_browser_service.ROOT_PATH

        content = await self.file_browser_service.list_directory(current_dir)
        tree_view = await self.file_browser_service.get_tree_view(current_dir)

        await callback.message.edit_text(
            tree_view,
            reply_markup=Keyboards.file_browser(content),
            parse_mode="HTML"
        )
        await callback.answer()

    async def _show_project_list(self, callback: CallbackQuery, state: FSMContext):
        """Show project list for switching"""
        user_id = callback.from_user.id

        if not self.project_service:
            await callback.answer("Сервис проектов не инициализирован")
            return

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        projects = await self.project_service.list_projects(uid)
        current = await self.project_service.get_current(uid)
        current_id = current.id if current else None

        if projects:
            text = (
                f"📂 <b>Сменить проект</b>\n\n"
                f"Текущий: <b>{current.name if current else 'Нет'}</b>\n\n"
                f"Выберите проект:"
            )
            keyboard = Keyboards.project_list(projects, current_id)
        else:
            text = (
                f"📂 <b>Нет проектов</b>\n\n"
                f"У вас пока нет проектов.\n"
                f"Создайте новый или откройте <code>/root/projects</code>"
            )
            keyboard = Keyboards.project_list([], None, show_create=True)

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    # ============== Context Section ==============

    async def _handle_context(self, callback: CallbackQuery, action: str, param: str, state: FSMContext):
        """Handle context submenu"""
        user_id = callback.from_user.id

        if not action:
            # Show context submenu
            ctx_name, msg_count, has_session = await self._get_context_info(user_id)
            project_name, _ = await self._get_project_info(user_id)

            session_status = "📜 Есть сессия" if has_session else "✨ Чистый"

            text = (
                f"💬 <b>Контекст</b>\n\n"
                f"📂 Проект: {project_name or 'не выбран'}\n"
                f"💬 Контекст: {ctx_name or 'не выбран'}\n"
                f"📝 Сообщений: {msg_count}\n"
                f"📌 Статус: {session_status}"
            )

            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.menu_context(ctx_name, msg_count, has_session),
                parse_mode="HTML"
            )
            await callback.answer()

        elif action == "fresh":
            await self._create_fresh_context(callback, state)

        elif action == "list":
            await self._show_context_list(callback, state)

        elif action == "vars":
            await self._show_variables(callback, state)

        elif action == "clear":
            await self._clear_history(callback, state)

    async def _create_fresh_context(self, callback: CallbackQuery, state: FSMContext):
        """Create new fresh context"""
        user_id = callback.from_user.id

        # Clear session cache
        if self.message_handlers:
            self.message_handlers.clear_session_cache(user_id)

        if self.project_service and self.context_service:
            from domain.value_objects.user_id import UserId
            uid = UserId.from_int(user_id)

            project = await self.project_service.get_current(uid)
            if project:
                new_context = await self.context_service.create_new(
                    project_id=project.id,
                    user_id=uid,
                    name=None,
                    set_as_current=True
                )

                text = (
                    f"✅ <b>Новый контекст создан!</b>\n\n"
                    f"📂 Проект: {project.name}\n"
                    f"💬 Контекст: {new_context.name}\n\n"
                    f"Начните новый диалог."
                )
            else:
                text = "❌ Нет активного проекта. Выберите проект."
        else:
            await self.bot_service.clear_session(user_id)
            text = "🧹 Сессия очищена! Следующее сообщение начнёт новый диалог."

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.menu_back_only("menu:context"),
            parse_mode="HTML"
        )
        await callback.answer("Контекст создан")

    async def _show_context_list(self, callback: CallbackQuery, state: FSMContext):
        """Show context management"""
        user_id = callback.from_user.id

        if not self.project_service or not self.context_service:
            await callback.answer("Сервисы не инициализированы")
            return

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        project = await self.project_service.get_current(uid)
        if not project:
            await callback.message.edit_text(
                "❌ Нет активного проекта\n\nВыберите проект в разделе Проекты.",
                reply_markup=Keyboards.menu_back_only("menu:context"),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        current_ctx = await self.context_service.get_current(project.id)
        ctx_name = current_ctx.name if current_ctx else "не выбран"
        msg_count = current_ctx.message_count if current_ctx else 0
        has_session = current_ctx.has_session if current_ctx else False

        session_status = "📜 Есть сессия" if has_session else "✨ Чистый"
        text = (
            f"💬 <b>Управление контекстами</b>\n\n"
            f"📂 Проект: {project.name}\n"
            f"💬 Контекст: {ctx_name}\n"
            f"📝 Сообщений: {msg_count}\n"
            f"📌 Статус: {session_status}"
        )

        keyboard = Keyboards.context_menu(ctx_name, project.name, msg_count)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    async def _show_variables(self, callback: CallbackQuery, state: FSMContext):
        """Show context variables"""
        user_id = callback.from_user.id

        if not self.project_service or not self.context_service:
            await callback.answer("Сервисы не инициализированы")
            return

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        project = await self.project_service.get_current(uid)
        if not project:
            await callback.message.edit_text(
                "❌ Нет активного проекта",
                reply_markup=Keyboards.menu_back_only("menu:context"),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        context = await self.context_service.get_current(project.id)
        if not context:
            await callback.message.edit_text(
                "❌ Нет активного контекста",
                reply_markup=Keyboards.menu_back_only("menu:context"),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        variables = await self.context_service.get_variables(context.id)

        if variables:
            lines = [f"📋 <b>Переменные контекста</b>\n"]
            lines.append(f"📂 {project.name} / {context.name}\n")
            for name in sorted(variables.keys()):
                var = variables[name]
                display = var.value[:8] + "***" if len(var.value) > 8 else var.value
                lines.append(f"• {name} = {display}")
                if var.description:
                    lines.append(f"  ↳ {var.description[:50]}")
            text = "\n".join(lines)
        else:
            text = (
                f"📋 <b>Переменные контекста</b>\n\n"
                f"📂 {project.name} / {context.name}\n\n"
                f"Переменных пока нет.\n"
                f"Нажмите ➕ Добавить для создания."
            )

        keyboard = Keyboards.variables_menu(variables, project.name, context.name)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    async def _clear_history(self, callback: CallbackQuery, state: FSMContext):
        """Clear chat history"""
        user_id = callback.from_user.id

        await self.bot_service.clear_session(user_id)
        if self.message_handlers:
            self.message_handlers.clear_session_cache(user_id)

        await callback.message.edit_text(
            "🧹 <b>История очищена!</b>\n\n"
            "Следующее сообщение начнёт новый диалог.",
            reply_markup=Keyboards.menu_back_only("menu:context"),
            parse_mode="HTML"
        )
        await callback.answer("История очищена")

    # ============== Settings Section ==============

    async def _handle_settings(self, callback: CallbackQuery, action: str, param: str, state: FSMContext):
        """Handle settings submenu"""
        user_id = callback.from_user.id

        if not action:
            # Show settings submenu
            yolo_enabled = self._get_yolo_enabled(user_id)
            auth_mode, has_creds = await self._get_auth_info(user_id)

            text = (
                f"⚙️ <b>Настройки</b>\n\n"
                f"⚡ YOLO режим: {'✅ Включён' if yolo_enabled else '❌ Выключен'}\n"
                f"👤 Авторизация: {'☁️ Claude Account' if auth_mode == 'claude_account' else '🌐 z.ai API'}"
            )

            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.menu_settings(yolo_enabled, auth_mode, has_creds),
                parse_mode="HTML"
            )
            await callback.answer()

        elif action == "account":
            # Redirect to account menu
            if self.account_service:
                settings = await self.account_service.get_settings(user_id)
                creds_info = self.account_service.get_credentials_info()

                mode_name = "z.ai API" if settings.auth_mode.value == "zai_api" else "Claude Account"
                text = (
                    f"🔧 <b>Настройки аккаунта</b>\n\n"
                    f"Текущий режим: <b>{mode_name}</b>\n\n"
                    f"Выберите режим авторизации:"
                )

                await callback.message.edit_text(
                    text,
                    reply_markup=Keyboards.account_menu(
                        current_mode=settings.auth_mode.value,
                        has_credentials=creds_info.exists,
                        subscription_type=creds_info.subscription_type,
                    ),
                    parse_mode="HTML"
                )
            await callback.answer()

        elif action == "yolo":
            # Toggle YOLO mode
            if self.message_handlers:
                current = self.message_handlers.is_yolo_mode(user_id)
                new_state = not current
                self.message_handlers.set_yolo_mode(user_id, new_state)

                if new_state:
                    text = (
                        "🚀 <b>YOLO Mode: ON</b>\n\n"
                        "⚡ Все операции выполняются автоматически!\n"
                        "⚠️ Будьте осторожны - нет подтверждений!"
                    )
                else:
                    text = (
                        "🛡️ <b>YOLO Mode: OFF</b>\n\n"
                        "Операции снова требуют подтверждения."
                    )

                auth_mode, has_creds = await self._get_auth_info(user_id)

                await callback.message.edit_text(
                    text,
                    reply_markup=Keyboards.menu_settings(new_state, auth_mode, has_creds),
                    parse_mode="HTML"
                )
                await callback.answer(f"YOLO режим {'включён' if new_state else 'выключен'}")

        elif action == "login":
            # Show login prompt
            if self.account_service:
                creds_info = self.account_service.get_credentials_info()
                if creds_info.exists:
                    sub = creds_info.subscription_type or "unknown"
                    text = (
                        f"✅ <b>Уже авторизованы!</b>\n\n"
                        f"Подписка: {sub}\n"
                        f"Rate limit: {creds_info.rate_limit_tier or 'default'}\n\n"
                        f"Используйте Аккаунт для переключения режима."
                    )
                    await callback.message.edit_text(
                        text,
                        reply_markup=Keyboards.menu_back_only("menu:settings"),
                        parse_mode="HTML"
                    )
                else:
                    text = (
                        "🔐 <b>Авторизация Claude Account</b>\n\n"
                        "Для использования Claude Account нужна авторизация.\n\n"
                        "<b>Выберите способ:</b>"
                    )
                    await callback.message.edit_text(
                        text,
                        reply_markup=Keyboards.account_auth_options(),
                        parse_mode="HTML"
                    )
            await callback.answer()

    # ============== Plugins Section ==============

    async def _handle_plugins(self, callback: CallbackQuery, state: FSMContext):
        """Handle plugins menu"""
        if not self.sdk_service:
            await callback.message.edit_text(
                "⚠️ SDK сервис не доступен",
                reply_markup=Keyboards.menu_back_only("menu:main"),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        plugins = self.sdk_service.get_enabled_plugins_info()

        if not plugins:
            text = (
                "🔌 <b>Плагины Claude Code</b>\n\n"
                "Нет активных плагинов."
            )
        else:
            text = "🔌 <b>Плагины Claude Code</b>\n\n"
            for p in plugins:
                name = p.get("name", "unknown")
                desc = p.get("description", "")
                available = p.get("available", True)
                status = "✅" if available else "⚠️"
                text += f"{status} <b>{name}</b>\n"
                if desc:
                    text += f"   <i>{desc}</i>\n"
            text += f"\n<i>Всего: {len(plugins)} плагинов</i>"

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.plugins_menu(plugins),
            parse_mode="HTML"
        )
        await callback.answer()

    # ============== System Section ==============

    async def _handle_system(self, callback: CallbackQuery, action: str, param: str, state: FSMContext):
        """Handle system submenu"""
        user_id = callback.from_user.id

        if not action:
            # Show system submenu
            has_task = self._is_task_running(user_id)

            text = "📊 <b>Система</b>\n\nМониторинг и управление"

            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.menu_system(has_task),
                parse_mode="HTML"
            )
            await callback.answer()

        elif action == "status":
            await self._show_status(callback)

        elif action == "metrics":
            await self._show_metrics(callback)

        elif action == "docker":
            await self._show_docker(callback)

        elif action == "diagnose":
            await self._run_diagnostics(callback)

        elif action == "cancel":
            await self._cancel_task(callback)

    async def _show_status(self, callback: CallbackQuery):
        """Show Claude Code status"""
        user_id = callback.from_user.id

        # Check CLI
        installed, version_info = await self.claude_proxy.check_claude_installed()
        cli_emoji = "🟢" if installed else "🔴"

        # Check SDK
        sdk_status = "❌ Недоступен"
        sdk_running = False
        if self.sdk_service:
            sdk_ok, sdk_msg = await self.sdk_service.check_sdk_available()
            sdk_status = "🟢 Доступен" if sdk_ok else f"🔴 {sdk_msg}"
            sdk_running = self.sdk_service.is_task_running(user_id)

        cli_running = self.claude_proxy.is_task_running(user_id)
        is_running = sdk_running or cli_running
        working_dir = self._get_working_dir(user_id)

        task_status = "🔄 Работает" if is_running else "⏸️ Ожидание"
        backend = "SDK" if sdk_running else ("CLI" if cli_running else "Ожидание")

        text = (
            f"📊 <b>Статус Claude Code</b>\n\n"
            f"<b>CLI:</b> {cli_emoji} {version_info}\n"
            f"<b>SDK:</b> {sdk_status}\n"
            f"<b>Задача:</b> {task_status} ({backend})\n"
            f"<b>Папка:</b> <code>{working_dir}</code>"
        )

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.menu_back_only("menu:system"),
            parse_mode="HTML"
        )
        await callback.answer()

    async def _show_metrics(self, callback: CallbackQuery):
        """Show system metrics"""
        info = await self.bot_service.get_system_info()
        metrics = info["metrics"]

        lines = [
            "💻 <b>Метрики системы</b>",
            "",
            f"💻 <b>CPU:</b> {metrics['cpu_percent']:.1f}%",
            f"🧠 <b>Память:</b> {metrics['memory_percent']:.1f}% ({metrics['memory_used_gb']}GB / {metrics['memory_total_gb']}GB)",
            f"💾 <b>Диск:</b> {metrics['disk_percent']:.1f}% ({metrics['disk_used_gb']}GB / {metrics['disk_total_gb']}GB)",
        ]

        if metrics.get('load_average', [0])[0] > 0:
            lines.append(f"📈 <b>Нагрузка:</b> {metrics['load_average'][0]:.2f}")

        if info.get("alerts"):
            lines.append("\n⚠️ <b>Предупреждения:</b>")
            lines.extend(info["alerts"])

        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=Keyboards.menu_back_only("menu:system"),
            parse_mode="HTML"
        )
        await callback.answer()

    async def _show_docker(self, callback: CallbackQuery):
        """Show Docker containers"""
        try:
            # Check if docker module is installed
            try:
                import docker
            except ImportError:
                await callback.message.edit_text(
                    "🐳 <b>Docker контейнеры</b>\n\n"
                    "❌ Библиотека docker не установлена\n\n"
                    "Установите: <code>pip install docker</code>",
                    reply_markup=Keyboards.menu_back_only("menu:system"),
                    parse_mode="HTML"
                )
                await callback.answer()
                return

            # Try to connect to Docker daemon
            try:
                client = docker.from_env()
                containers = client.containers.list(all=True)
            except docker.errors.DockerException as e:
                await callback.message.edit_text(
                    "🐳 <b>Docker контейнеры</b>\n\n"
                    f"❌ Не удалось подключиться к Docker daemon:\n"
                    f"<code>{str(e)[:200]}</code>\n\n"
                    "Проверьте что Docker запущен и доступен.",
                    reply_markup=Keyboards.menu_back_only("menu:system"),
                    parse_mode="HTML"
                )
                await callback.answer()
                return

            if not containers:
                await callback.message.edit_text(
                    "🐳 <b>Docker контейнеры</b>\n\n"
                    "📦 Контейнеры не найдены\n\n"
                    "Используйте <code>docker ps -a</code> для проверки.",
                    reply_markup=Keyboards.menu_back_only("menu:system"),
                    parse_mode="HTML"
                )
                await callback.answer()
                return

            # Format container list
            lines = ["🐳 <b>Docker контейнеры:</b>\n"]
            container_list = []
            for container in containers:
                status_emoji = "🟢" if container.status == "running" else "🔴"
                image_tag = container.image.tags[0] if container.image.tags else str(container.image.id)[:12]
                lines.append(f"\n{status_emoji} <b>{container.name}</b>")
                lines.append(f"   Статус: {container.status}")
                lines.append(f"   Образ: <code>{image_tag[:40]}</code>")

                container_list.append({
                    "id": container.short_id,
                    "name": container.name,
                    "status": container.status,
                    "image": image_tag,
                })

            text = "\n".join(lines)
            keyboard = Keyboards.docker_list(container_list)

            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error showing Docker containers: {e}", exc_info=True)
            await callback.message.edit_text(
                f"🐳 Docker\n\n❌ Ошибка: {str(e)[:300]}",
                reply_markup=Keyboards.menu_back_only("menu:system"),
                parse_mode="HTML"
            )

        await callback.answer()

    async def _run_diagnostics(self, callback: CallbackQuery):
        """Run Claude Code diagnostics"""
        await callback.answer("Запускаю диагностику...")

        try:
            from infrastructure.claude_code.diagnostics import run_diagnostics, format_diagnostics_for_telegram
            results = await run_diagnostics(self.claude_proxy.claude_path)
            text = format_diagnostics_for_telegram(results)

            # Truncate if too long
            if len(text) > 4000:
                text = text[:3900] + "\n\n... (обрезано)"

            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.menu_back_only("menu:system"),
                parse_mode=None
            )
        except Exception as e:
            await callback.message.edit_text(
                f"❌ Диагностика не удалась: {e}",
                reply_markup=Keyboards.menu_back_only("menu:system"),
                parse_mode="HTML"
            )

    async def _cancel_task(self, callback: CallbackQuery):
        """Cancel running task"""
        user_id = callback.from_user.id
        cancelled = False

        # Try SDK first
        if self.sdk_service:
            cancelled = await self.sdk_service.cancel_task(user_id)

        # Try CLI
        if not cancelled and self.claude_proxy:
            cancelled = await self.claude_proxy.cancel_task(user_id)

        if cancelled:
            text = "🛑 <b>Задача отменена</b>"
        else:
            text = "ℹ️ Нет запущенных задач"

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.menu_back_only("menu:system"),
            parse_mode="HTML"
        )
        await callback.answer("Задача отменена" if cancelled else "Нет задач")

    # ============== Help Section ==============

    async def _handle_help(self, callback: CallbackQuery, action: str, state: FSMContext):
        """Handle help submenu"""
        if not action:
            # Show help submenu
            text = "❓ <b>Справка</b>\n\nВыберите тему:"

            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.menu_help(),
                parse_mode="HTML"
            )
            await callback.answer()

        elif action == "usage":
            text = """
📖 <b>Как работать с ботом</b>

<b>Основы:</b>
• Просто напишите задачу текстом
• Claude Code выполнит её автоматически
• Вы увидите вывод в реальном времени

<b>HITL (Human-in-the-Loop):</b>
🔐 <b>Разрешения</b> - Claude спросит разрешение на опасные операции
❓ <b>Вопросы</b> - Claude задаст уточняющие вопросы
🛑 <b>Отмена</b> - Можно отменить задачу в любой момент

<b>Примеры задач:</b>
• "Создай Python скрипт для парсинга JSON"
• "Прочитай файл README.md"
• "Запусти тесты командой pytest"
• "Исправь баг в файле main.py"

<b>Слэш-команды плагинов:</b>
• /ralph-loop - непрерывная разработка
• /commit - создать коммит
• /code-review - ревью кода
"""
            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.menu_back_only("menu:help"),
                parse_mode="HTML"
            )
            await callback.answer()

        elif action == "plugins":
            text = """
🔌 <b>О плагинах</b>

Плагины расширяют возможности Claude Code.

<b>Доступные плагины:</b>

<b>ralph-loop</b> - Непрерывная разработка
• Запуск: /ralph-loop
• Отмена: /cancel-ralph

<b>commit-commands</b> - Git операции
• /commit - создать коммит
• /commit-push-pr - коммит + PR

<b>code-review</b> - Ревью кода
• /code-review - начать ревью

<b>feature-dev</b> - Разработка фич
• /feature-dev - guided разработка

<b>frontend-design</b> - UI разработка
• /frontend-design - создание интерфейсов
"""
            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.menu_back_only("menu:help"),
                parse_mode="HTML"
            )
            await callback.answer()

        elif action == "yolo":
            text = """
⚡ <b>О YOLO режиме</b>

YOLO = You Only Live Once (авто-подтверждение)

<b>Когда включён:</b>
✅ Все операции выполняются автоматически
✅ Не нужно подтверждать каждое действие
✅ Быстрее выполняются задачи

<b>Риски:</b>
⚠️ Опасные команды выполняются без подтверждения
⚠️ Нет возможности отменить операцию заранее
⚠️ Файлы могут быть изменены/удалены

<b>Рекомендация:</b>
Используйте YOLO только для безопасных задач:
• Чтение файлов
• Анализ кода
• Генерация без записи

Отключайте для:
• Записи/удаления файлов
• Git операций
• Системных команд
"""
            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.menu_back_only("menu:help"),
                parse_mode="HTML"
            )
            await callback.answer()


def register_menu_handlers(dp, menu_handlers: MenuHandlers):
    """Register menu handlers with dispatcher"""
    dp.include_router(menu_handlers.router)
