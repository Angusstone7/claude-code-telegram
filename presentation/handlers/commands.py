import logging
import os
from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.enums import ParseMode
from application.services.bot_service import BotService
from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService
from infrastructure.claude_code.diagnostics import run_diagnostics, format_diagnostics_for_telegram
from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)
router = Router()


class CommandHandlers:
    """Bot command handlers for Claude Code proxy"""

    def __init__(
        self,
        bot_service: BotService,
        claude_proxy: ClaudeCodeProxyService,
        message_handlers=None,  # Optional, set after initialization
        project_service=None,   # ProjectService for /change
        context_service=None,   # ContextService for /context
        file_browser_service=None  # FileBrowserService for /cd
    ):
        self.bot_service = bot_service
        self.claude_proxy = claude_proxy
        self.message_handlers = message_handlers
        self.project_service = project_service
        self.context_service = context_service
        self.file_browser_service = file_browser_service

    async def start(self, message: Message) -> None:
        """Handle /start command"""
        user = await self.bot_service.get_or_create_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # Get working directory
        working_dir = "/root"
        if self.message_handlers:
            working_dir = self.message_handlers.get_working_dir(message.from_user.id)

        # Check Claude Code status
        installed, version_info = await self.claude_proxy.check_claude_installed()
        status = f"✅ {version_info}" if installed else f"⚠️ {version_info}"

        await message.answer(
            f"🤖 **Claude Code Telegram Proxy**\n\n"
            f"Привет, {user.first_name}!\n"
            f"Ваша роль: **{user.role.name}**\n\n"
            f"**Claude Code:** {status}\n"
            f"**Рабочая папка:** `{working_dir}`\n\n"
            f"Просто отправьте задачу — Claude Code её выполнит!\n"
            f"Я буду показывать вывод, запрашивать разрешения и передавать вопросы.\n\n"
            f"Используйте /help для списка команд.",
            parse_mode="Markdown",
            reply_markup=Keyboards.main_menu()
        )

    async def help(self, message: Message) -> None:
        """Handle /help command"""
        help_text = """
🤖 **Claude Code Telegram Proxy - Справка**

**Навигация и проекты:**
/cd - Навигация по папкам
/change - Сменить проект
/fresh - Очистить контекст

**Управление контекстом:**
/context new - Создать новый контекст
/context list - Список контекстов
/context clear - Очистить текущий контекст

**Claude Code:**
/yolo - YOLO режим (авто-подтверждение)
/plugins - Показать плагины
/cancel - Отменить задачу
/status - Статус Claude Code

**Основные команды:**
/start - Запустить бота
/help - Показать справку
/stats - Ваша статистика
/clear - Очистить историю чата

**Как это работает:**
1. Отправьте задачу сообщением
2. Claude Code начнёт работу
3. Вы увидите вывод в реальном времени
4. Подтверждайте/отклоняйте операции
5. Отвечайте на вопросы Claude

**HITL (Human-in-the-Loop):**
🔐 **Разрешения** - Подтверждение опасных операций
❓ **Вопросы** - Ответы на вопросы Claude
🛑 **Отмена** - Остановить задачу в любой момент

**Примеры:**
• "Создай Python скрипт, который выводит hello"
• "Прочитай файл README.md"
• "Запусти npm install в проекте"
• "Исправь баг в main.py"

Просто опишите что нужно сделать!
        """
        await message.answer(help_text, parse_mode="Markdown")

    async def clear(self, message: Message) -> None:
        """Handle /clear command"""
        await self.bot_service.clear_session(message.from_user.id)
        await message.answer("🧹 История чата очищена!")

    async def stats(self, message: Message) -> None:
        """Handle /stats command"""
        stats = await self.bot_service.get_user_stats(message.from_user.id)

        text = f"""
📊 **Ваша статистика**

**Пользователь:** {stats.get('user', {}).get('username', 'Неизвестно')}
**Роль:** {stats.get('user', {}).get('role', 'user')}
**Статус:** {'✅ Активен' if stats.get('user', {}).get('is_active') else '❌ Неактивен'}

**Команды:**
• Всего: {stats.get('commands', {}).get('total', 0)}
{chr(10).join(f"  • {k}: {v}" for k, v in stats.get('commands', {}).get('by_status', {}).items() if k != 'total')}

**Сессии:**
• Всего: {stats.get('sessions', {}).get('total', 0)}
• Активных: {stats.get('sessions', {}).get('active', 0)}
        """
        await message.answer(text, parse_mode="Markdown")

    async def menu_chat(self, message: Message) -> None:
        """Handle chat menu button"""
        await message.answer(
            "💬 **Режим чата**\n\n"
            "Просто опишите что нужно сделать!\n\n"
            "Примеры:\n"
            "• 'Проверь использование диска'\n"
            "• 'Перезапусти контейнер nginx'\n"
            "• 'Покажи запущенные процессы'\n"
            "• 'Установи пакет htop'",
            parse_mode="Markdown"
        )

    async def menu_metrics(self, message: Message) -> None:
        """Handle metrics menu button"""
        info = await self.bot_service.get_system_info()

        metrics = info["metrics"]
        lines = [
            "📊 **Метрики системы**",
            "",
            f"💻 **CPU:** {metrics['cpu_percent']:.1f}%",
            f"🧠 **Память:** {metrics['memory_percent']:.1f}% ({metrics['memory_used_gb']}GB / {metrics['memory_total_gb']}GB)",
            f"💾 **Диск:** {metrics['disk_percent']:.1f}% ({metrics['disk_used_gb']}GB / {metrics['disk_total_gb']}GB)",
        ]

        if metrics.get('load_average', [0])[0] > 0:
            lines.append(f"📈 **Нагрузка:** {metrics['load_average'][0]:.2f}")

        # Show alerts
        if info.get("alerts"):
            lines.append("\n⚠️ **Предупреждения:**")
            lines.extend(info["alerts"])

        await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=Keyboards.system_metrics())

    async def menu_docker(self, message: Message) -> None:
        """Handle docker menu button - show list of containers"""
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            containers = await monitor.get_docker_containers()

            if not containers:
                await message.answer(
                    "🐳 **Docker контейнеры**\n\n"
                    "Контейнеры не найдены.\n\n"
                    "Используйте Claude Code для управления Docker:\n"
                    "• 'docker ps -a'\n"
                    "• 'docker run ...'",
                    parse_mode="Markdown"
                )
                return

            # Build container list with action buttons
            lines = ["🐳 **Docker контейнеры:**\n"]
            for c in containers:
                status_emoji = "🟢" if c["status"] == "running" else "🔴"
                lines.append(f"\n{status_emoji} **{c['name']}**")
                lines.append(f"   Статус: {c['status']}")
                lines.append(f"   Образ: `{c['image'][:30]}`")

            text = "\n".join(lines)
            await message.answer(
                text,
                parse_mode="Markdown",
                reply_markup=Keyboards.docker_list(containers)
            )

        except Exception as e:
            logger.error(f"Error getting docker containers: {e}")
            await message.answer(
                f"🐳 **Docker**\n\n❌ Ошибка: {e}",
                parse_mode="Markdown"
            )

    async def menu_commands(self, message: Message) -> None:
        """Handle commands menu button"""
        await message.answer(
            "📝 **Команды**\n\n"
            "Просто напишите задачу на естественном языке!\n\n"
            "**Примеры:**\n"
            "• 'Покажи файлы в текущей папке'\n"
            "• 'Покажи использование памяти'\n"
            "• 'Создай Python скрипт'\n"
            "• 'Прочитай файл README.md'\n\n"
            "Claude Code всё сделает!",
            parse_mode="Markdown"
        )

    async def project(self, message: Message, command: CommandObject) -> None:
        """Handle /project command - set working directory"""
        user_id = message.from_user.id

        if command.args:
            # Set working directory directly
            path = command.args.strip()

            # Validate path exists (basic check)
            if not os.path.isabs(path):
                path = os.path.abspath(path)

            if self.message_handlers:
                self.message_handlers.set_working_dir(user_id, path)
                await message.answer(
                    f"📁 **Рабочая папка установлена:**\n`{path}`",
                    parse_mode="Markdown"
                )
            else:
                await message.answer(
                    "⚠️ Обработчики сообщений не инициализированы",
                    parse_mode="Markdown"
                )
        else:
            # Show current working directory and prompt for input
            current_dir = "/root"
            if self.message_handlers:
                current_dir = self.message_handlers.get_working_dir(user_id)

            # List some common project directories
            projects = []
            for dir_path in ["/root", "/home", "/var/www", "/opt"]:
                if os.path.exists(dir_path):
                    projects.append({"name": os.path.basename(dir_path) or dir_path, "path": dir_path})

            await message.answer(
                f"📁 **Текущая рабочая папка:**\n`{current_dir}`\n\n"
                f"Используйте `/project <путь>` для смены.\n\n"
                f"Пример:\n`/project /home/myproject`",
                parse_mode="Markdown",
                reply_markup=Keyboards.project_selection(projects) if projects else None
            )

    async def change(self, message: Message) -> None:
        """Handle /change command - show project list for switching"""
        user_id = message.from_user.id

        if not self.project_service:
            await message.answer("⚠️ Сервис проектов не инициализирован")
            return

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        # Get user's projects
        projects = await self.project_service.list_projects(uid)
        current = await self.project_service.get_current(uid)

        current_name = current.name if current else "Нет"
        current_id = current.id if current else None

        if projects:
            text = (
                f"📂 **Сменить проект**\n\n"
                f"Текущий: **{current_name}**\n\n"
                f"Выберите проект:"
            )
            keyboard = Keyboards.project_list(projects, current_id)
        else:
            text = (
                f"📂 **Нет проектов**\n\n"
                f"У вас пока нет проектов.\n"
                f"Создайте новый или откройте `/root/projects`"
            )
            keyboard = Keyboards.project_list([], None, show_create=True)

        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

    async def context(self, message: Message, command: CommandObject) -> None:
        """Handle /context command - manage contexts within project"""
        user_id = message.from_user.id

        if not self.project_service or not self.context_service:
            await message.answer("⚠️ Сервисы не инициализированы")
            return

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        # Get current project
        project = await self.project_service.get_current(uid)
        if not project:
            await message.answer(
                "❌ **Нет активного проекта**\n\n"
                "Используйте `/change` для выбора проекта.",
                parse_mode="Markdown"
            )
            return

        subcommand = command.args.strip().lower() if command.args else ""

        if subcommand == "new":
            # Create new context
            context = await self.context_service.create_new(
                project.id, uid, set_as_current=True
            )
            await message.answer(
                f"✨ **Новый контекст создан**\n\n"
                f"Контекст: **{context.name}**\n"
                f"Проект: {project.name}\n\n"
                f"Чистый старт — без истории!",
                parse_mode="Markdown"
            )

        elif subcommand == "list":
            # List contexts
            contexts = await self.context_service.list_contexts(project.id)
            current_ctx = await self.context_service.get_current(project.id)
            current_id = current_ctx.id if current_ctx else None

            if contexts:
                text = (
                    f"💬 **Контексты проекта {project.name}**\n\n"
                    f"Выберите контекст:"
                )
                keyboard = Keyboards.context_list(contexts, current_id)
            else:
                text = "Контексты не найдены. Создаю основной контекст..."
                context = await self.context_service.create_new(
                    project.id, uid, "main", set_as_current=True
                )
                text = f"✨ Создан контекст: **{context.name}**"
                keyboard = None

            await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

        elif subcommand == "clear":
            # Clear current context messages
            current_ctx = await self.context_service.get_current(project.id)
            if current_ctx:
                await self.context_service.start_fresh(current_ctx.id)
                await message.answer(
                    f"🗑️ **Контекст очищен**\n\n"
                    f"Контекст: {current_ctx.name}\n"
                    f"Сообщения и сессия очищены.",
                    parse_mode="Markdown"
                )
            else:
                await message.answer("Нет активного контекста для очистки.")

        else:
            # Show help
            current_ctx = await self.context_service.get_current(project.id)
            ctx_name = current_ctx.name if current_ctx else "нет"

            await message.answer(
                f"💬 **Управление контекстами**\n\n"
                f"Проект: **{project.name}**\n"
                f"Контекст: **{ctx_name}**\n\n"
                f"**Команды:**\n"
                f"`/context new` - Создать новый контекст\n"
                f"`/context list` - Список контекстов\n"
                f"`/context clear` - Очистить текущий контекст\n\n"
                f"Контексты позволяют вести несколько диалогов\n"
                f"в рамках одного проекта (как в Cursor IDE).",
                parse_mode="Markdown"
            )

    async def fresh(self, message: Message) -> None:
        """
        Handle /fresh command - clear context and start fresh conversation.

        Clears:
        - Claude session ID (stops auto-continue)
        - Context messages
        - Internal session state
        """
        user_id = message.from_user.id

        # Clear internal session state
        if self.message_handlers:
            self.message_handlers._continue_sessions.pop(user_id, None)

        # Clear context in project
        if self.project_service and self.context_service:
            from domain.value_objects.user_id import UserId
            uid = UserId.from_int(user_id)

            project = await self.project_service.get_current(uid)
            if project:
                context = await self.context_service.get_current(project.id)
                if context:
                    await self.context_service.start_fresh(context.id)

                    await message.answer(
                        f"🧹 **Контекст очищен!**\n\n"
                        f"📂 Проект: **{project.name}**\n"
                        f"💬 Контекст: **{context.name}**\n\n"
                        f"История сессии очищена. Следующее сообщение начнёт новый диалог.",
                        parse_mode="Markdown"
                    )
                    return

        # No project/context - just clear bot service session
        await self.bot_service.clear_session(user_id)
        await message.answer(
            "🧹 **Сессия очищена!**\n\n"
            "Следующее сообщение начнёт новый диалог.",
            parse_mode="Markdown"
        )

    async def yolo(self, message: Message) -> None:
        """
        Handle /yolo command - toggle YOLO mode.

        YOLO mode auto-approves all operations without waiting for confirmation.
        Use with caution!
        """
        user_id = message.from_user.id

        if not self.message_handlers:
            await message.answer("⚠️ Обработчики сообщений не инициализированы")
            return

        current = self.message_handlers.is_yolo_mode(user_id)
        new_state = not current
        self.message_handlers.set_yolo_mode(user_id, new_state)

        if new_state:
            await message.answer(
                "🚀 **YOLO Mode: ON**\n\n"
                "⚡ Все операции будут выполняться автоматически!\n"
                "⚠️ Будьте осторожны - нет подтверждений!\n\n"
                "Используйте `/yolo` снова чтобы выключить.",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "🛡️ **YOLO Mode: OFF**\n\n"
                "Операции снова требуют подтверждения.",
                parse_mode="Markdown"
            )

    async def plugins(self, message: Message) -> None:
        """
        Handle /plugins command - show available Claude Code plugins.

        Shows plugins from the official anthropic/claude-plugins-official repo.
        """
        if not self.message_handlers or not hasattr(self.message_handlers, 'sdk_service'):
            await message.answer(
                "🔌 **Плагины Claude Code**\n\n"
                "⚠️ SDK сервис недоступен.\n"
                "Плагины требуют Claude Agent SDK.",
                parse_mode="Markdown"
            )
            return

        sdk_service = self.message_handlers.sdk_service
        if not sdk_service:
            await message.answer(
                "🔌 **Плагины Claude Code**\n\n"
                "⚠️ SDK сервис не инициализирован.",
                parse_mode="Markdown"
            )
            return

        plugins_info = sdk_service.get_enabled_plugins_info()

        if not plugins_info:
            await message.answer(
                "🔌 **Плагины Claude Code**\n\n"
                "Плагины не настроены.",
                parse_mode="Markdown"
            )
            return

        lines = ["🔌 **Плагины Claude Code:**\n"]
        available_count = 0
        for plugin in plugins_info:
            if plugin.get("available"):
                lines.append(f"✅ `/{plugin['name']}` — {plugin['description']}")
                available_count += 1
            else:
                lines.append(f"❌ `/{plugin['name']}` — не найден")

        if available_count > 0:
            lines.append("\n**Как использовать:**")
            lines.append("Просто скажите Claude что нужно сделать:")
            lines.append("• _'сделай коммит'_")
            lines.append("• _'запусти /commit'_")
            lines.append("• _'создай PR'_")
            lines.append("• _'проведи код ревью'_")
            lines.append("\nClaude сам определит какой плагин использовать!")
        else:
            lines.append("\n⚠️ Плагины не найдены в директории.")
            lines.append(f"Путь: `{sdk_service.plugins_dir}`")

        await message.answer("\n".join(lines), parse_mode="Markdown")

    async def cd(self, message: Message, command: CommandObject) -> None:
        """
        Handle /cd command - interactive folder navigation.

        Usage:
            /cd           - Show current directory with navigation
            /cd ..        - Go to parent directory
            /cd <folder>  - Navigate to folder
            /cd ~         - Go to root (/root/projects)
        """
        user_id = message.from_user.id

        if not self.file_browser_service:
            # Fallback: create service on demand
            from application.services.file_browser_service import FileBrowserService
            self.file_browser_service = FileBrowserService()

        # Get current working directory
        current_dir = "/root/projects"
        if self.message_handlers:
            current_dir = self.message_handlers.get_working_dir(user_id)

        # Ensure current_dir is within root
        if not self.file_browser_service.is_within_root(current_dir):
            current_dir = self.file_browser_service.ROOT_PATH

        # Resolve target path
        if command.args:
            target = command.args.strip()
            target_path = self.file_browser_service.resolve_path(current_dir, target)
        else:
            target_path = current_dir

        # Ensure directory exists
        if not os.path.isdir(target_path):
            # Try creating if it's a subdir of root
            if self.file_browser_service.is_within_root(target_path):
                try:
                    os.makedirs(target_path, exist_ok=True)
                except OSError:
                    target_path = self.file_browser_service.ROOT_PATH
            else:
                target_path = self.file_browser_service.ROOT_PATH

        # Get directory content and tree view
        content = await self.file_browser_service.list_directory(target_path)
        tree_view = await self.file_browser_service.get_tree_view(target_path)

        # Send with HTML formatting
        await message.answer(
            tree_view,
            parse_mode=ParseMode.HTML,
            reply_markup=Keyboards.file_browser(content)
        )

    async def cancel(self, message: Message) -> None:
        """Handle /cancel command - cancel running Claude Code task"""
        user_id = message.from_user.id
        cancelled = False

        # Try SDK first (preferred) - it handles full cleanup including status reset
        if self.message_handlers and hasattr(self.message_handlers, 'sdk_service'):
            sdk_service = self.message_handlers.sdk_service
            if sdk_service:
                cancelled = await sdk_service.cancel_task(user_id)
                if cancelled:
                    await message.answer("🛑 **Задача отменена** (SDK)")
                    return

        # Try CLI fallback
        if self.claude_proxy:
            cli_cancelled = await self.claude_proxy.cancel_task(user_id)
            if cli_cancelled:
                await message.answer("🛑 **Задача отменена** (CLI)")
                return

        if not cancelled:
            await message.answer("ℹ️ Сейчас нет запущенных задач")

    async def status(self, message: Message) -> None:
        """Handle /status command - show Claude Code status"""
        user_id = message.from_user.id

        # Check if Claude Code CLI is installed
        installed, version_info = await self.claude_proxy.check_claude_installed()

        # Check SDK availability
        sdk_status = "❌ Недоступен"
        sdk_running = False
        if self.message_handlers and hasattr(self.message_handlers, 'sdk_service'):
            sdk_service = self.message_handlers.sdk_service
            if sdk_service:
                sdk_ok, sdk_msg = await sdk_service.check_sdk_available()
                sdk_status = "🟢 Доступен (HITL включён)" if sdk_ok else f"🔴 {sdk_msg}"
                sdk_running = sdk_service.is_task_running(user_id)

        # Check if task is running (either backend)
        cli_running = self.claude_proxy.is_task_running(user_id)
        is_running = sdk_running or cli_running

        # Get working directory
        working_dir = "/root"
        if self.message_handlers:
            working_dir = self.message_handlers.get_working_dir(user_id)

        cli_emoji = "🟢" if installed else "🔴"
        task_status = "🔄 Работает" if is_running else "⏸️ Ожидание"

        # Determine backend in use
        backend = "SDK" if sdk_running else ("CLI" if cli_running else "Ожидание")

        text = f"""
📊 **Статус Claude Code**

**CLI:** {cli_emoji} {version_info}
**SDK:** {sdk_status}
**Задача:** {task_status} ({backend})
**Рабочая папка:** `{working_dir}`
"""

        if is_running:
            text += "\n\nИспользуйте /cancel чтобы остановить текущую задачу."

        text += "\n\nИспользуйте /diagnose для полной диагностики."

        await message.answer(text, parse_mode="Markdown")

    async def diagnose(self, message: Message) -> None:
        """Handle /diagnose command - run full Claude Code diagnostics"""
        await message.answer("🔍 Запуск диагностики... (может занять до 30 секунд)")

        try:
            results = await run_diagnostics(self.claude_proxy.claude_path)
            text = format_diagnostics_for_telegram(results)
            await message.answer(text, parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ Diagnostics failed: {e}")


def register_handlers(router: Router, handlers: CommandHandlers) -> None:
    """Register command handlers"""
    # Basic commands
    router.message.register(handlers.start, Command("start"))
    router.message.register(handlers.help, Command("help"))
    router.message.register(handlers.clear, Command("clear"))
    router.message.register(handlers.stats, Command("stats"))

    # Claude Code commands
    router.message.register(handlers.project, Command("project"))
    router.message.register(handlers.cancel, Command("cancel"))
    router.message.register(handlers.status, Command("status"))
    router.message.register(handlers.diagnose, Command("diagnose"))

    # Project/Context management commands
    router.message.register(handlers.change, Command("change"))
    router.message.register(handlers.context, Command("context"))
    router.message.register(handlers.fresh, Command("fresh"))
    router.message.register(handlers.yolo, Command("yolo"))
    router.message.register(handlers.plugins, Command("plugins"))
    router.message.register(handlers.cd, Command("cd"))

    # Menu buttons
    router.message.register(handlers.menu_chat, F.text == "💬 Чат")
    router.message.register(handlers.menu_metrics, F.text == "📊 Метрики")
    router.message.register(handlers.menu_docker, F.text == "🐳 Docker")
    router.message.register(handlers.menu_commands, F.text == "📝 Команды")
    router.message.register(handlers.clear, F.text == "🗑️ Очистить")
    router.message.register(handlers.help, F.text == "ℹ️ Справка")
