import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message
from application.services.bot_service import BotService
from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)
router = Router()


class CommandHandlers:
    """Bot command handlers"""

    def __init__(self, bot_service: BotService):
        self.bot_service = bot_service

    async def start(self, message: Message) -> None:
        """Handle /start command"""
        user = await self.bot_service.get_or_create_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        await message.answer(
            f"🤖 **Claude DevOps Bot**\n\n"
            f"Welcome, {user.first_name}!\n"
            f"Your role: **{user.role.name}**\n\n"
            f"I can help you manage servers via SSH using natural language.\n"
            f"Just ask me to do something, and I'll figure out the commands!\n\n"
            f"Use /help to see available commands.",
            parse_mode="Markdown",
            reply_markup=Keyboards.main_menu()
        )

    async def help(self, message: Message) -> None:
        """Handle /help command"""
        help_text = """
🤖 **Claude DevOps Bot - Help**

**Basic Commands:**
/start - Start the bot
/help - Show this help
/clear - Clear chat history
/stats - Show your statistics

**Main Menu:**
💬 **Chat** - Talk with Claude AI
📊 **Metrics** - System metrics
🐳 **Docker** - Container management
📝 **Commands** - Command history

**Features:**
• Execute server commands via natural language
• Monitor system resources
• Manage Docker containers
• View command history
• AI-powered assistance

Just describe what you want to do, and I'll help you!
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


def register_handlers(router: Router, handlers: CommandHandlers) -> None:
    """Register command handlers"""
    router.message.register(handlers.start, Command("start"))
    router.message.register(handlers.help, Command("help"))
    router.message.register(handlers.clear, Command("clear"))
    router.message.register(handlers.stats, Command("stats"))

    # Menu buttons
    router.message.register(handlers.menu_chat, F.text == "💬 Chat")
    router.message.register(handlers.menu_metrics, F.text == "📊 Metrics")
    router.message.register(handlers.menu_docker, F.text == "🐳 Docker")
    router.message.register(handlers.clear, F.text == "🗑️ Clear")
    router.message.register(handlers.help, F.text == "ℹ️ Help")
