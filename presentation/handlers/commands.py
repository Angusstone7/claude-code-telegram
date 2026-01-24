import logging
import os
from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
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
        message_handlers=None  # Optional, set after initialization
    ):
        self.bot_service = bot_service
        self.claude_proxy = claude_proxy
        self.message_handlers = message_handlers

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

**Claude Code Commands:**
/project `<path>` - Set working directory
/cancel - Cancel running task
/status - Show Claude Code status
/clear - Clear session history

**Basic Commands:**
/start - Start the bot
/help - Show this help
/stats - Show your statistics

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
        """Handle docker menu button"""
        await message.answer(
            "🐳 **Docker Management**\n\n"
            "Use buttons below to manage containers:",
            parse_mode="Markdown",
            reply_markup=Keyboards.system_metrics()
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

    async def cancel(self, message: Message) -> None:
        """Handle /cancel command - cancel running Claude Code task"""
        user_id = message.from_user.id

        if self.claude_proxy.is_task_running(user_id):
            cancelled = await self.claude_proxy.cancel_task(user_id)
            if cancelled:
                await message.answer("🛑 **Task cancelled**")
            else:
                await message.answer("⚠️ Failed to cancel task")
        else:
            await message.answer("ℹ️ No task is currently running")

    async def status(self, message: Message) -> None:
        """Handle /status command - show Claude Code status"""
        user_id = message.from_user.id

        # Check if Claude Code is installed
        installed, version_info = await self.claude_proxy.check_claude_installed()

        # Check if task is running
        is_running = self.claude_proxy.is_task_running(user_id)

        # Get working directory
        working_dir = "/root"
        if self.message_handlers:
            working_dir = self.message_handlers.get_working_dir(user_id)

        status_emoji = "🟢" if installed else "🔴"
        task_status = "🔄 Running" if is_running else "⏸️ Idle"

        text = f"""
📊 **Claude Code Status**

**CLI:** {status_emoji} {version_info}
**Task:** {task_status}
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

    # Menu buttons
    router.message.register(handlers.menu_chat, F.text == "💬 Chat")
    router.message.register(handlers.menu_metrics, F.text == "📊 Metrics")
    router.message.register(handlers.menu_docker, F.text == "🐳 Docker")
    router.message.register(handlers.menu_commands, F.text == "📝 Commands")
    router.message.register(handlers.clear, F.text == "🗑️ Clear")
    router.message.register(handlers.help, F.text == "ℹ️ Help")
