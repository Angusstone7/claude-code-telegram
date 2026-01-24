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
            f"Welcome, {user.first_name}!\n"
            f"Your role: **{user.role.name}**\n\n"
            f"**Claude Code:** {status}\n"
            f"**Working dir:** `{working_dir}`\n\n"
            f"Just send me a task and Claude Code will handle it!\n"
            f"I'll forward all outputs, permissions, and questions to you.\n\n"
            f"Use /help to see available commands.",
            parse_mode="Markdown",
            reply_markup=Keyboards.main_menu()
        )

    async def help(self, message: Message) -> None:
        """Handle /help command"""
        help_text = """
🤖 **Claude Code Telegram Proxy - Help**

**Navigation & Projects:**
/cd - Browse and navigate folders
/change - Switch between projects
/fresh - Clear context, start fresh

**Context Management:**
/context new - Create new context
/context list - List all contexts
/context clear - Clear current context

**Claude Code:**
/cancel - Cancel running task
/status - Show Claude Code status

**Basic Commands:**
/start - Start the bot
/help - Show this help
/stats - Show your statistics
/clear - Clear chat history

**How it works:**
1. Send any task as a message
2. Claude Code will work on it
3. You'll see real-time output
4. Approve/reject tool executions
5. Answer questions when asked

**HITL (Human-in-the-Loop):**
🔐 **Permissions** - Approve dangerous operations
❓ **Questions** - Answer Claude's questions
🛑 **Cancel** - Stop running tasks anytime

**Examples:**
• "Create a Python script that prints hello"
• "Read the README.md file"
• "Run npm install in the project"
• "Fix the bug in main.py"

Just describe what you want!
        """
        await message.answer(help_text, parse_mode="Markdown")

    async def clear(self, message: Message) -> None:
        """Handle /clear command"""
        await self.bot_service.clear_session(message.from_user.id)
        await message.answer("🧹 Chat history cleared!")

    async def stats(self, message: Message) -> None:
        """Handle /stats command"""
        stats = await self.bot_service.get_user_stats(message.from_user.id)

        text = f"""
📊 **Your Statistics**

**User:** {stats.get('user', {}).get('username', 'Unknown')}
**Role:** {stats.get('user', {}).get('role', 'user')}
**Status:** {'✅ Active' if stats.get('user', {}).get('is_active') else '❌ Inactive'}

**Commands:**
• Total: {stats.get('commands', {}).get('total', 0)}
{chr(10).join(f"  • {k}: {v}" for k, v in stats.get('commands', {}).get('by_status', {}).items() if k != 'total')}

**Sessions:**
• Total: {stats.get('sessions', {}).get('total', 0)}
• Active: {stats.get('sessions', {}).get('active', 0)}
        """
        await message.answer(text, parse_mode="Markdown")

    async def menu_chat(self, message: Message) -> None:
        """Handle chat menu button"""
        await message.answer(
            "💬 **Chat Mode**\n\n"
            "Just describe what you want to do!\n\n"
            "Examples:\n"
            "• 'Check disk usage'\n"
            "• 'Restart nginx container'\n"
            "• 'Show running processes'\n"
            "• 'Install htop package'",
            parse_mode="Markdown"
        )

    async def menu_metrics(self, message: Message) -> None:
        """Handle metrics menu button"""
        info = await self.bot_service.get_system_info()

        metrics = info["metrics"]
        lines = [
            "📊 **System Metrics**",
            "",
            f"💻 **CPU:** {metrics['cpu_percent']:.1f}%",
            f"🧠 **Memory:** {metrics['memory_percent']:.1f}% ({metrics['memory_used_gb']}GB / {metrics['memory_total_gb']}GB)",
            f"💾 **Disk:** {metrics['disk_percent']:.1f}% ({metrics['disk_used_gb']}GB / {metrics['disk_total_gb']}GB)",
        ]

        if metrics.get('load_average', [0])[0] > 0:
            lines.append(f"📈 **Load:** {metrics['load_average'][0]:.2f}")

        # Show alerts
        if info.get("alerts"):
            lines.append("\n⚠️ **Alerts:**")
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
                    "🐳 **Docker Containers**\n\n"
                    "No containers found.\n\n"
                    "Use Claude Code to manage Docker:\n"
                    "• 'docker ps -a'\n"
                    "• 'docker run ...'",
                    parse_mode="Markdown"
                )
                return

            # Build container list with action buttons
            lines = ["🐳 **Docker Containers:**\n"]
            for c in containers:
                status_emoji = "🟢" if c["status"] == "running" else "🔴"
                lines.append(f"\n{status_emoji} **{c['name']}**")
                lines.append(f"   Status: {c['status']}")
                lines.append(f"   Image: `{c['image'][:30]}`")

            text = "\n".join(lines)
            await message.answer(
                text,
                parse_mode="Markdown",
                reply_markup=Keyboards.docker_list(containers)
            )

        except Exception as e:
            logger.error(f"Error getting docker containers: {e}")
            await message.answer(
                f"🐳 **Docker**\n\n❌ Error: {e}",
                parse_mode="Markdown"
            )

    async def menu_commands(self, message: Message) -> None:
        """Handle commands menu button"""
        await message.answer(
            "📝 **Commands**\n\n"
            "Just type any task in natural language!\n\n"
            "**Examples:**\n"
            "• 'List files in current directory'\n"
            "• 'Show system memory usage'\n"
            "• 'Create a Python script'\n"
            "• 'Read the README.md file'\n\n"
            "Claude Code will handle it!",
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
                    f"📁 **Working directory set:**\n`{path}`",
                    parse_mode="Markdown"
                )
            else:
                await message.answer(
                    "⚠️ Message handlers not initialized",
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
                f"📁 **Current working directory:**\n`{current_dir}`\n\n"
                f"Use `/project <path>` to change it.\n\n"
                f"Example:\n`/project /home/myproject`",
                parse_mode="Markdown",
                reply_markup=Keyboards.project_selection(projects) if projects else None
            )

    async def change(self, message: Message) -> None:
        """Handle /change command - show project list for switching"""
        user_id = message.from_user.id

        if not self.project_service:
            await message.answer("⚠️ Project service not initialized")
            return

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        # Get user's projects
        projects = await self.project_service.list_projects(uid)
        current = await self.project_service.get_current(uid)

        current_name = current.name if current else "None"
        current_id = current.id if current else None

        if projects:
            text = (
                f"📂 **Switch Project**\n\n"
                f"Current: **{current_name}**\n\n"
                f"Select a project:"
            )
            keyboard = Keyboards.project_list(projects, current_id)
        else:
            text = (
                f"📂 **No Projects**\n\n"
                f"You don't have any projects yet.\n"
                f"Create one or browse `/root/projects`"
            )
            keyboard = Keyboards.project_list([], None, show_create=True)

        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

    async def context(self, message: Message, command: CommandObject) -> None:
        """Handle /context command - manage contexts within project"""
        user_id = message.from_user.id

        if not self.project_service or not self.context_service:
            await message.answer("⚠️ Services not initialized")
            return

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        # Get current project
        project = await self.project_service.get_current(uid)
        if not project:
            await message.answer(
                "❌ **No active project**\n\n"
                "Use `/change` to select a project first.",
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
                f"✨ **New Context Created**\n\n"
                f"Context: **{context.name}**\n"
                f"Project: {project.name}\n\n"
                f"Fresh start - no history!",
                parse_mode="Markdown"
            )

        elif subcommand == "list":
            # List contexts
            contexts = await self.context_service.list_contexts(project.id)
            current_ctx = await self.context_service.get_current(project.id)
            current_id = current_ctx.id if current_ctx else None

            if contexts:
                text = (
                    f"💬 **Contexts for {project.name}**\n\n"
                    f"Select a context:"
                )
                keyboard = Keyboards.context_list(contexts, current_id)
            else:
                text = "No contexts found. Creating main context..."
                context = await self.context_service.create_new(
                    project.id, uid, "main", set_as_current=True
                )
                text = f"✨ Created context: **{context.name}**"
                keyboard = None

            await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

        elif subcommand == "clear":
            # Clear current context messages
            current_ctx = await self.context_service.get_current(project.id)
            if current_ctx:
                await self.context_service.start_fresh(current_ctx.id)
                await message.answer(
                    f"🗑️ **Context Cleared**\n\n"
                    f"Context: {current_ctx.name}\n"
                    f"Messages and session cleared.",
                    parse_mode="Markdown"
                )
            else:
                await message.answer("No active context to clear.")

        else:
            # Show help
            current_ctx = await self.context_service.get_current(project.id)
            ctx_name = current_ctx.name if current_ctx else "none"

            await message.answer(
                f"💬 **Context Management**\n\n"
                f"Project: **{project.name}**\n"
                f"Context: **{ctx_name}**\n\n"
                f"**Commands:**\n"
                f"`/context new` - Create fresh context\n"
                f"`/context list` - List all contexts\n"
                f"`/context clear` - Clear current context\n\n"
                f"Contexts let you have multiple conversations\n"
                f"within the same project (like Cursor IDE).",
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
                        f"🧹 **Context Cleared!**\n\n"
                        f"📂 Project: **{project.name}**\n"
                        f"💬 Context: **{context.name}**\n\n"
                        f"Session history cleared. Next message starts fresh conversation.",
                        parse_mode="Markdown"
                    )
                    return

        # No project/context - just clear bot service session
        await self.bot_service.clear_session(user_id)
        await message.answer(
            "🧹 **Session Cleared!**\n\n"
            "Next message starts a fresh conversation.",
            parse_mode="Markdown"
        )

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

        # Check both SDK and CLI backends
        cancelled = False

        # Try SDK first (if message handlers have SDK service)
        if self.message_handlers and hasattr(self.message_handlers, 'sdk_service'):
            sdk_service = self.message_handlers.sdk_service
            if sdk_service and sdk_service.is_task_running(user_id):
                cancelled = await sdk_service.cancel_task(user_id)
                if cancelled:
                    await message.answer("🛑 **Task cancelled**")
                    return

        # Try CLI fallback
        if self.claude_proxy.is_task_running(user_id):
            cancelled = await self.claude_proxy.cancel_task(user_id)
            if cancelled:
                await message.answer("🛑 **Task cancelled**")
            else:
                await message.answer("⚠️ Failed to cancel task")
        elif not cancelled:
            await message.answer("ℹ️ No task is currently running")

    async def status(self, message: Message) -> None:
        """Handle /status command - show Claude Code status"""
        user_id = message.from_user.id

        # Check if Claude Code CLI is installed
        installed, version_info = await self.claude_proxy.check_claude_installed()

        # Check SDK availability
        sdk_status = "❌ Not available"
        sdk_running = False
        if self.message_handlers and hasattr(self.message_handlers, 'sdk_service'):
            sdk_service = self.message_handlers.sdk_service
            if sdk_service:
                sdk_ok, sdk_msg = await sdk_service.check_sdk_available()
                sdk_status = "🟢 Available (HITL enabled)" if sdk_ok else f"🔴 {sdk_msg}"
                sdk_running = sdk_service.is_task_running(user_id)

        # Check if task is running (either backend)
        cli_running = self.claude_proxy.is_task_running(user_id)
        is_running = sdk_running or cli_running

        # Get working directory
        working_dir = "/root"
        if self.message_handlers:
            working_dir = self.message_handlers.get_working_dir(user_id)

        cli_emoji = "🟢" if installed else "🔴"
        task_status = "🔄 Running" if is_running else "⏸️ Idle"

        # Determine backend in use
        backend = "SDK" if sdk_running else ("CLI" if cli_running else "Idle")

        text = f"""
📊 **Claude Code Status**

**CLI:** {cli_emoji} {version_info}
**SDK:** {sdk_status}
**Task:** {task_status} ({backend})
**Working dir:** `{working_dir}`
"""

        if is_running:
            text += "\n\nUse /cancel to stop the current task."

        text += "\n\nUse /diagnose to run full diagnostics."

        await message.answer(text, parse_mode="Markdown")

    async def diagnose(self, message: Message) -> None:
        """Handle /diagnose command - run full Claude Code diagnostics"""
        await message.answer("🔍 Running diagnostics... (this may take up to 30 seconds)")

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
    router.message.register(handlers.cd, Command("cd"))

    # Menu buttons
    router.message.register(handlers.menu_chat, F.text == "💬 Chat")
    router.message.register(handlers.menu_metrics, F.text == "📊 Metrics")
    router.message.register(handlers.menu_docker, F.text == "🐳 Docker")
    router.message.register(handlers.menu_commands, F.text == "📝 Commands")
    router.message.register(handlers.clear, F.text == "🗑️ Clear")
    router.message.register(handlers.help, F.text == "ℹ️ Help")
