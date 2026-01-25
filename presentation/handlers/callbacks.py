import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from presentation.keyboards.keyboards import CallbackData
from typing import Optional

logger = logging.getLogger(__name__)
router = Router()


class CallbackHandlers:
    """Bot callback query handlers"""

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
                f"🚀 **Command executed**\n\n"
                f"```bash\n{display_output}\n```\n\n"
                f"⏱️ Time: {result.execution_time:.2f}s | Exit code: {result.exit_code}",
                parse_mode=None
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

    async def handle_metrics_refresh(self, callback: CallbackQuery) -> None:
        """Handle metrics refresh callback"""
        try:
            info = await self.bot_service.get_system_info()
            metrics = info["metrics"]

            text = (
                f"📊 **Метрики системы**\n\n"
                f"💻 **CPU:** {metrics['cpu_percent']:.1f}%\n"
                f"🧠 **Память:** {metrics['memory_percent']:.1f}% ({metrics['memory_used_gb']}GB / {metrics['memory_total_gb']}GB)\n"
                f"💾 **Диск:** {metrics['disk_percent']:.1f}% ({metrics['disk_used_gb']}GB / {metrics['disk_total_gb']}GB)\n"
            )

            if metrics.get('load_average', [0])[0] > 0:
                text += f"📈 **Нагрузка:** {metrics['load_average'][0]:.2f}\n"

            # Alerts
            if info.get("alerts"):
                text += "\n⚠️ **Предупреждения:**\n"
                text += "\n".join(info["alerts"])

            await callback.message.edit_text(text, parse_mode=None)

        except Exception as e:
            logger.error(f"Error refreshing metrics: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

        await callback.answer()

    async def handle_docker_list(self, callback: CallbackQuery) -> None:
        """Handle docker list callback"""
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            from presentation.keyboards.keyboards import Keyboards
            monitor = SystemMonitor()
            containers = await monitor.get_docker_containers()

            if not containers:
                text = "🐳 Контейнеры не найдены"
                await callback.message.edit_text(text, parse_mode=None)
            else:
                lines = ["🐳 **Docker контейнеры:**\n"]
                for c in containers:
                    status_emoji = "🟢" if c["status"] == "running" else "🔴"
                    lines.append(f"\n{status_emoji} **{c['name']}**")
                    lines.append(f"   Статус: {c['status']}")
                    lines.append(f"   Образ: `{c['image'][:30]}`")

                text = "\n".join(lines)
                await callback.message.edit_text(
                    text,
                    parse_mode=None,
                    reply_markup=Keyboards.docker_list(containers)
                )

        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

        await callback.answer()

    async def handle_docker_stop(self, callback: CallbackQuery) -> None:
        """Handle docker stop container"""
        container_id = callback.data.split(":")[-1]
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            success, message = await monitor.docker_stop(container_id)

            if success:
                await callback.answer(f"✅ {message}")
                await self.handle_docker_list(callback)
            else:
                await callback.answer(f"❌ {message}")

        except Exception as e:
            logger.error(f"Error stopping container: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_docker_start(self, callback: CallbackQuery) -> None:
        """Handle docker start container"""
        container_id = callback.data.split(":")[-1]
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            success, message = await monitor.docker_start(container_id)

            if success:
                await callback.answer(f"✅ {message}")
                await self.handle_docker_list(callback)
            else:
                await callback.answer(f"❌ {message}")

        except Exception as e:
            logger.error(f"Error starting container: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_docker_restart(self, callback: CallbackQuery) -> None:
        """Handle docker restart container"""
        container_id = callback.data.split(":")[-1]
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            success, message = await monitor.docker_restart(container_id)

            if success:
                await callback.answer(f"✅ {message}")
                await self.handle_docker_list(callback)
            else:
                await callback.answer(f"❌ {message}")

        except Exception as e:
            logger.error(f"Error restarting container: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_docker_logs(self, callback: CallbackQuery) -> None:
        """Handle docker logs"""
        container_id = callback.data.split(":")[-1]
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            success, logs = await monitor.docker_logs(container_id, lines=30)

            if success:
                if len(logs) > 3500:
                    logs = logs[-3500:]
                text = f"📋 Логи ({container_id})\n\n{logs}"
                await callback.message.edit_text(text, parse_mode=None)
            else:
                await callback.answer(f"❌ {logs}")

        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

        await callback.answer()

    async def handle_docker_rm(self, callback: CallbackQuery) -> None:
        """Handle docker remove container"""
        container_id = callback.data.split(":")[-1]
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            success, message = await monitor.docker_remove(container_id, force=True)

            if success:
                await callback.answer(f"✅ {message}")
                await self.handle_docker_list(callback)
            else:
                await callback.answer(f"❌ {message}")

        except Exception as e:
            logger.error(f"Error removing container: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_docker_info(self, callback: CallbackQuery) -> None:
        """Handle docker container info - show detailed view with actions"""
        container_id = callback.data.split(":")[-1]
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            from presentation.keyboards.keyboards import Keyboards
            monitor = SystemMonitor()
            containers = await monitor.get_docker_containers()

            container = next((c for c in containers if c["id"] == container_id), None)
            if container:
                text = (
                    f"🐳 **Контейнер: {container['name']}**\n\n"
                    f"**ID:** `{container['id']}`\n"
                    f"**Статус:** {container['status']}\n"
                    f"**Образ:** `{container['image']}`\n"
                )
                if container.get("ports"):
                    text += f"**Порты:** {', '.join(str(p) for p in container['ports'])}\n"

                await callback.message.edit_text(
                    text,
                    parse_mode=None,
                    reply_markup=Keyboards.container_actions(container_id, container["status"])
                )
            else:
                await callback.answer("Контейнер не найден")

        except Exception as e:
            logger.error(f"Error getting container info: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

        await callback.answer()

    async def handle_metrics_top(self, callback: CallbackQuery) -> None:
        """Handle top processes request"""
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            processes = await monitor.get_top_processes(limit=10)

            lines = ["📈 **Топ процессов:**\n"]
            for p in processes:
                lines.append(
                    f"`{p.pid:>6}` | CPU: {p.cpu_percent:>5.1f}% | MEM: {p.memory_percent:>5.1f}% | {p.name[:20]}"
                )

            text = "\n".join(lines)
            await callback.message.edit_text(text, parse_mode=None)

        except Exception as e:
            logger.error(f"Error getting top processes: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

        await callback.answer()

    async def handle_commands_history(self, callback: CallbackQuery) -> None:
        """Handle commands history request"""
        try:
            from domain.value_objects.user_id import UserId
            user_id = UserId.from_int(callback.from_user.id)

            commands = await self.bot_service.command_repository.find_by_user(user_id, limit=10)

            if not commands:
                text = "📝 **История команд**\n\nКоманд пока нет."
            else:
                lines = ["📝 **История команд:**\n"]
                for cmd in commands[:10]:
                    status_emoji = "✅" if cmd.status.value == "completed" else "⏳"
                    cmd_preview = cmd.command[:30] + "..." if len(cmd.command) > 30 else cmd.command
                    lines.append(f"{status_emoji} `{cmd_preview}`")

                text = "\n".join(lines)

            await callback.message.edit_text(text, parse_mode=None)

        except Exception as e:
            logger.error(f"Error getting command history: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

        await callback.answer()

    # ============== Claude Code HITL Callbacks ==============

    async def handle_claude_approve(self, callback: CallbackQuery) -> None:
        """Handle Claude Code permission approval"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            # Update message to show approved (without parse_mode to avoid markdown issues)
            original_text = callback.message.text or ""
            await callback.message.edit_text(
                original_text + "\n\n✅ Approved",
                parse_mode=None  # Don't parse - original text may have special chars
            )

            # Send approval to Claude Code proxy
            if self.claude_proxy:
                await self.claude_proxy.respond_to_permission(user_id, True)

            # Notify message handler to continue
            if hasattr(self.message_handlers, 'handle_permission_response'):
                await self.message_handlers.handle_permission_response(user_id, True)

            await callback.answer("✅ Одобрено")

        except Exception as e:
            logger.error(f"Error handling claude approve: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_claude_reject(self, callback: CallbackQuery) -> None:
        """Handle Claude Code permission rejection"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            # Update message to show rejected (without parse_mode to avoid markdown issues)
            original_text = callback.message.text or ""
            await callback.message.edit_text(
                original_text + "\n\n❌ Rejected",
                parse_mode=None
            )

            # Send rejection to Claude Code proxy
            if self.claude_proxy:
                await self.claude_proxy.respond_to_permission(user_id, False)

            # Notify message handler
            if hasattr(self.message_handlers, 'handle_permission_response'):
                await self.message_handlers.handle_permission_response(user_id, False)

            await callback.answer("❌ Отклонено")

        except Exception as e:
            logger.error(f"Error handling claude reject: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_claude_answer(self, callback: CallbackQuery) -> None:
        """Handle Claude Code question answer (selected option)"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))
        option_index = int(data.get("option_index", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            # Get the answer text from message handler's pending question
            answer = str(option_index)  # Default to index
            if hasattr(self.message_handlers, 'get_pending_question_option'):
                answer = self.message_handlers.get_pending_question_option(user_id, option_index)

            # Update message to show answer (without parse_mode to avoid markdown issues)
            original_text = callback.message.text or ""
            await callback.message.edit_text(
                original_text + f"\n\n📝 Ответ: {answer}",
                parse_mode=None
            )

            # Send answer to Claude Code proxy
            if self.claude_proxy:
                await self.claude_proxy.respond_to_question(user_id, answer)

            # Notify message handler
            if hasattr(self.message_handlers, 'handle_question_response'):
                await self.message_handlers.handle_question_response(user_id, answer)

            await callback.answer(f"Ответ: {answer[:20]}...")

        except Exception as e:
            logger.error(f"Error handling claude answer: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_claude_other(self, callback: CallbackQuery) -> None:
        """Handle Claude Code question - user wants to type custom answer"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            # Update message to prompt for text input (without parse_mode to avoid markdown issues)
            original_text = callback.message.text or ""
            await callback.message.edit_text(
                original_text + "\n\n✏️ Type your answer below:",
                parse_mode=None
            )

            # Set message handler to expect text answer
            if hasattr(self.message_handlers, 'set_expecting_answer'):
                self.message_handlers.set_expecting_answer(user_id, True)

            await callback.answer("Введите ответ в чат")

        except Exception as e:
            logger.error(f"Error handling claude other: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_claude_cancel(self, callback: CallbackQuery) -> None:
        """Handle Claude Code task cancellation"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            cancelled = False

            # Try SDK service first (preferred) - it handles full cleanup
            if self.sdk_service:
                cancelled = await self.sdk_service.cancel_task(user_id)
                logger.info(f"SDK cancel_task for user {user_id}: {cancelled}")

            # Fall back to CLI proxy if SDK didn't cancel
            if not cancelled and self.claude_proxy:
                cancelled = await self.claude_proxy.cancel_task(user_id)
                logger.info(f"Proxy cancel_task for user {user_id}: {cancelled}")

            if cancelled:
                await callback.message.edit_text(
                    "🛑 Задача отменена",
                    parse_mode=None
                )
                await callback.answer("Задача отменена")
            else:
                await callback.answer("Нет активной задачи для отмены")

        except Exception as e:
            logger.error(f"Error cancelling task: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_claude_continue(self, callback: CallbackQuery) -> None:
        """Handle continue Claude Code session"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))
        session_id = data.get("session_id")

        if user_id != callback.from_user.id:
            await callback.answer("❌ Это действие не для вас")
            return

        try:
            await callback.message.edit_text(
                "▶️ Продолжение сессии...\n\nОтправьте следующее сообщение для продолжения.",
                parse_mode=None
            )

            # Store session_id for next message
            if hasattr(self.message_handlers, 'set_continue_session'):
                self.message_handlers.set_continue_session(user_id, session_id)

            await callback.answer("Отправьте следующее сообщение")

        except Exception as e:
            logger.error(f"Error continuing session: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_project_select(self, callback: CallbackQuery) -> None:
        """Handle project selection"""
        data = CallbackData.parse_project_callback(callback.data)
        action = data.get("action")
        path = data.get("path", "")

        user_id = callback.from_user.id

        try:
            if action == "select" and path:
                # Set working directory
                if hasattr(self.message_handlers, 'set_working_dir'):
                    self.message_handlers.set_working_dir(user_id, path)

                await callback.message.edit_text(
                    f"📁 Рабочая папка установлена:\n{path}",
                    parse_mode=None
                )
                await callback.answer(f"Проект: {path}")

            elif action == "custom":
                # Prompt for custom path input
                if hasattr(self.message_handlers, 'set_expecting_path'):
                    self.message_handlers.set_expecting_path(user_id, True)

                await callback.message.edit_text(
                    "📂 Введите путь к проекту:\n\nВведите полный путь к папке проекта.",
                    parse_mode=None
                )
                await callback.answer("Введите путь в чат")

        except Exception as e:
            logger.error(f"Error handling project select: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Project Management Callbacks ==============

    async def handle_project_switch(self, callback: CallbackQuery) -> None:
        """Handle project switch (from /change command)"""
        project_id = callback.data.split(":")[-1]
        user_id = callback.from_user.id

        if not self.project_service:
            await callback.answer("⚠️ Project service not available")
            return

        try:
            from domain.value_objects.user_id import UserId
            from presentation.keyboards.keyboards import Keyboards

            uid = UserId.from_int(user_id)
            project = await self.project_service.switch_project(uid, project_id)

            if project:
                # Also update working directory in message handlers
                if hasattr(self.message_handlers, 'set_working_dir'):
                    self.message_handlers.set_working_dir(user_id, project.working_dir)

                await callback.message.edit_text(
                    f"✅ Переключено на проект:\n\n"
                    f"{project.name}\n"
                    f"Путь: {project.working_dir}\n\n"
                    f"Используйте /context list для просмотра контекстов.",
                    parse_mode=None
                )
                await callback.answer(f"Выбран {project.name}")
            else:
                await callback.answer("❌ Проект не найден")

        except Exception as e:
            logger.error(f"Error switching project: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_project_create(self, callback: CallbackQuery) -> None:
        """Handle project create - show folder browser"""
        await self.handle_project_browse(callback)

    async def handle_project_browse(self, callback: CallbackQuery) -> None:
        """Handle project browse - show folders in /root/projects"""
        import os
        from presentation.keyboards.keyboards import Keyboards

        try:
            root_path = "/root/projects"

            # Check if path specified in callback
            if ":" in callback.data and callback.data.count(":") > 1:
                path = ":".join(callback.data.split(":")[2:])
                if path and os.path.isdir(path):
                    root_path = path

            # Ensure directory exists
            if not os.path.exists(root_path):
                os.makedirs(root_path, exist_ok=True)

            # Get folders
            folders = []
            try:
                for entry in os.scandir(root_path):
                    if entry.is_dir() and not entry.name.startswith('.'):
                        folders.append(entry.path)
            except OSError:
                pass

            folders.sort()

            if folders:
                text = (
                    f"📂 **Обзор проектов**\n\n"
                    f"Путь: `{root_path}`\n\n"
                    f"Выберите папку для создания проекта:"
                )
            else:
                text = (
                    f"📂 **Папки не найдены**\n\n"
                    f"Путь: `{root_path}`\n\n"
                    f"Сначала создайте папку с помощью Claude Code."
                )

            try:
                await callback.message.edit_text(
                    text,
                    parse_mode=None,
                    reply_markup=Keyboards.folder_browser(folders, root_path)
                )
            except Exception as edit_err:
                # Ignore "message is not modified" error
                if "message is not modified" not in str(edit_err):
                    raise edit_err
            await callback.answer()

        except Exception as e:
            logger.error(f"Error browsing projects: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_project_folder(self, callback: CallbackQuery) -> None:
        """Handle folder selection - create project from folder"""
        import os
        from presentation.keyboards.keyboards import Keyboards

        folder_path = ":".join(callback.data.split(":")[2:])
        user_id = callback.from_user.id

        if not folder_path or not os.path.isdir(folder_path):
            await callback.answer("❌ Неверная папка")
            return

        if not self.project_service:
            await callback.answer("⚠️ Сервис проектов недоступен")
            return

        try:
            from domain.value_objects.user_id import UserId

            uid = UserId.from_int(user_id)
            name = os.path.basename(folder_path)

            # Create or get project
            project = await self.project_service.get_or_create(uid, folder_path, name)

            # Switch to it
            await self.project_service.switch_project(uid, project.id)

            # Update working directory
            if hasattr(self.message_handlers, 'set_working_dir'):
                self.message_handlers.set_working_dir(user_id, folder_path)

            await callback.message.edit_text(
                f"✅ Проект создан:\n\n"
                f"{project.name}\n"
                f"Путь: {project.working_dir}\n\n"
                f"Готово к работе! Отправьте первое сообщение.",
                parse_mode=None
            )
            await callback.answer(f"Создан {project.name}")

        except Exception as e:
            logger.error(f"Error creating project from folder: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_project_delete(self, callback: CallbackQuery) -> None:
        """Handle project delete - show confirmation dialog"""
        project_id = callback.data.split(":")[-1]
        user_id = callback.from_user.id

        if not self.project_service:
            await callback.answer("⚠️ Project service not available")
            return

        try:
            from domain.value_objects.user_id import UserId
            from presentation.keyboards.keyboards import Keyboards

            uid = UserId.from_int(user_id)
            project = await self.project_service.get_by_id(project_id)

            if not project:
                await callback.answer("❌ Проект не найден")
                return

            if int(project.user_id) != user_id:
                await callback.answer("❌ Это не ваш проект")
                return

            text = (
                f"⚠️ Удаление проекта\n\n"
                f"Проект: {project.name}\n"
                f"Путь: {project.working_dir}\n\n"
                f"Выберите действие:"
            )

            await callback.message.edit_text(
                text,
                parse_mode=None,
                reply_markup=Keyboards.project_delete_confirm(project_id, project.name)
            )
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing delete confirmation: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_project_delete_confirm(self, callback: CallbackQuery) -> None:
        """Handle confirmed project deletion"""
        import shutil

        # Parse callback: project:delete_confirm:<id>:<mode>
        parts = callback.data.split(":")
        project_id = parts[2] if len(parts) > 2 else ""
        delete_mode = parts[3] if len(parts) > 3 else "db"
        user_id = callback.from_user.id

        if not self.project_service:
            await callback.answer("⚠️ Project service not available")
            return

        try:
            from domain.value_objects.user_id import UserId
            from presentation.keyboards.keyboards import Keyboards

            uid = UserId.from_int(user_id)
            project = await self.project_service.get_by_id(project_id)

            if not project:
                await callback.answer("❌ Проект не найден")
                return

            if int(project.user_id) != user_id:
                await callback.answer("❌ Это не ваш проект")
                return

            project_name = project.name
            project_path = project.working_dir

            # Delete from database
            deleted = await self.project_service.delete_project(uid, project_id)

            if not deleted:
                await callback.answer("❌ Не удалось удалить проект")
                return

            # Delete files if requested
            files_deleted = False
            if delete_mode == "all":
                try:
                    import os
                    if os.path.exists(project_path) and project_path.startswith("/root/projects"):
                        shutil.rmtree(project_path)
                        files_deleted = True
                except Exception as e:
                    logger.error(f"Error deleting project files: {e}")

            # Show result
            if files_deleted:
                result_text = (
                    f"✅ Проект удален полностью\n\n"
                    f"Проект: {project_name}\n"
                    f"Файлы удалены: {project_path}"
                )
            else:
                result_text = (
                    f"✅ Проект удален из базы\n\n"
                    f"Проект: {project_name}\n"
                    f"Файлы сохранены: {project_path}"
                )

            # Show updated project list
            projects = await self.project_service.list_projects(uid)
            current = await self.project_service.get_current(uid)
            current_id = current.id if current else None

            await callback.message.edit_text(
                result_text + "\n\n📁 Ваши проекты:",
                parse_mode=None,
                reply_markup=Keyboards.project_list(projects, current_id)
            )
            await callback.answer(f"✅ Проект {project_name} удален")

        except Exception as e:
            logger.error(f"Error deleting project: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_project_back(self, callback: CallbackQuery) -> None:
        """Handle back to project list"""
        user_id = callback.from_user.id

        if not self.project_service:
            await callback.answer("⚠️ Project service not available")
            return

        try:
            from domain.value_objects.user_id import UserId
            from presentation.keyboards.keyboards import Keyboards

            uid = UserId.from_int(user_id)
            projects = await self.project_service.list_projects(uid)
            current = await self.project_service.get_current(uid)
            current_id = current.id if current else None

            if projects:
                text = "📁 Ваши проекты:\n\nВыберите проект или создайте новый:"
            else:
                text = "📁 Проекты не найдены\n\nСоздайте первый проект:"

            await callback.message.edit_text(
                text,
                parse_mode=None,
                reply_markup=Keyboards.project_list(projects, current_id)
            )
            await callback.answer()

        except Exception as e:
            logger.error(f"Error going back to project list: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

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

            keyboard = Keyboards.context_menu(ctx_name, project.name, msg_count)
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
                keyboard = Keyboards.context_menu(context.name, project.name, 0)

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
                keyboard = Keyboards.context_menu(context.name, project.name, context.message_count)
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
            keyboard = Keyboards.context_menu(context.name, project.name, 0)
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
        """Confirm and clear context"""
        try:
            uid, project, current_ctx, ctx_service = await self._get_context_data(callback)
            if not project:
                return

            if not current_ctx:
                await callback.answer("❌ Нет активного контекста")
                return

            await ctx_service.start_fresh(current_ctx.id)

            text = (
                f"✅ Контекст очищен\n\n"
                f"📝 {current_ctx.name}\n"
                f"📂 Проект: {project.name}\n\n"
                f"История удалена. Начните новый диалог."
            )
            keyboard = Keyboards.context_menu(current_ctx.name, project.name, 0)
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer("Контекст очищен")

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
                project = await self.project_service.get_or_create(uid, path, project_name)
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

            keyboard = Keyboards.variables_menu(variables, project.name, context.name)
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
