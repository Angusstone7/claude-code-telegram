import logging
from aiogram import Router, F
from aiogram.types import Message
from application.services.bot_service import BotService
from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)
router = Router()


class MessageHandlers:
    """Bot message handlers"""

    def __init__(self, bot_service: BotService):
        self.bot_service = bot_service
        self.pending_tools = {}  # Store pending tool approvals

    async def handle_text(self, message: Message) -> None:
        """Handle text messages - chat with AI"""
        user_id = message.from_user.id

        # Check authorization
        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await message.answer("❌ You are not authorized to use this bot.")
            return

        try:
            # Send typing action
            await message.bot.send_chat_action(user_id, "typing")

            # Get AI response
            response_text, tool_calls = await self.bot_service.chat(
                user_id=user_id,
                message=message.text,
                enable_tools=True
            )

            # Send response
            if response_text:
                # Handle long messages
                if len(response_text) > 4000:
                    for i in range(0, len(response_text), 4000):
                        await message.answer(response_text[i:i+4000], parse_mode="Markdown")
                else:
                    await message.answer(response_text, parse_mode="Markdown")

            # Handle tool calls (need approval)
            if tool_calls:
                for tool in tool_calls:
                    if tool["name"] == "bash":
                        command = tool["input"]["command"]
                        await self._request_command_approval(
                            message=message,
                            tool_id=tool["id"],
                            command=command
                        )
                    elif tool["name"] == "get_metrics":
                        await self._handle_metrics(message, tool["id"])
                    elif tool["name"] == "list_containers":
                        await self._handle_containers(message, tool["id"])

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await message.answer(f"❌ Error: {str(e)}")

    async def _request_command_approval(self, message: Message, tool_id: str, command: str) -> None:
        """Request user approval for command execution"""
        # Create pending command
        cmd = await self.bot_service.create_pending_command(
            user_id=message.from_user.id,
            command=command
        )

        # Store mapping for callback
        self.pending_tools[tool_id] = cmd.command_id

        # Check if dangerous
        is_dangerous = cmd.is_dangerous

        # Show command with approval buttons
        warning = "⚠️ **DANGEROUS COMMAND**\n\n" if is_dangerous else ""
        text = f"{warning}🔧 **Proposed Command:**\n```bash\n{command}\n```"

        if is_dangerous:
            text += "\n\n⚠️ This command may be dangerous. Are you sure?"

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=Keyboards.command_approval(cmd.command_id, command, is_dangerous)
        )

    async def _handle_metrics(self, message: Message, tool_id: str) -> None:
        """Handle get_metrics tool call"""
        try:
            info = await self.bot_service.get_system_info()
            metrics = info["metrics"]

            response = (
                f"📊 **System Metrics:**\n\n"
                f"💻 CPU: {metrics['cpu_percent']:.1f}%\n"
                f"🧠 Memory: {metrics['memory_percent']:.1f}% ({metrics['memory_used_gb']}GB / {metrics['memory_total_gb']}GB)\n"
                f"💾 Disk: {metrics['disk_percent']:.1f}% ({metrics['disk_used_gb']}GB / {metrics['disk_total_gb']}GB)\n"
            )

            # Send tool result to AI
            await self.bot_service.handle_tool_result(
                user_id=message.from_user.id,
                tool_id=tool_id,
                result=response
            )

            # Get follow-up from AI
            follow_up, _ = await self.bot_service.chat(
                user_id=message.from_user.id,
                message="",  # Empty since we sent tool result
                enable_tools=False
            )

            if follow_up:
                await message.answer(follow_up, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            await self.bot_service.handle_tool_result(
                user_id=message.from_user.id,
                tool_id=tool_id,
                result=f"Error getting metrics: {e}"
            )

    async def _handle_containers(self, message: Message, tool_id: str) -> None:
        """Handle list_containers tool call"""
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            containers = await monitor.get_docker_containers()

            if not containers:
                result = "No Docker containers found."
            else:
                lines = ["🐳 **Docker Containers:**\n"]
                for c in containers:
                    status_emoji = "✅" if c["status"] == "running" else "⏸️"
                    lines.append(f"{status_emoji} **{c['name']}** - {c['status']}")
                    lines.append(f"   Image: {c['image']}")

                result = "\n".join(lines)

            # Send tool result to AI
            await self.bot_service.handle_tool_result(
                user_id=message.from_user.id,
                tool_id=tool_id,
                result=result
            )

            # Get follow-up from AI
            follow_up, _ = await self.bot_service.chat(
                user_id=message.from_user.id,
                message="",
                enable_tools=False
            )

            if follow_up:
                await message.answer(follow_up, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error getting containers: {e}")
            await self.bot_service.handle_tool_result(
                user_id=message.from_user.id,
                tool_id=tool_id,
                result=f"Error getting containers: {e}"
            )


def register_handlers(router: Router, handlers: MessageHandlers) -> None:
    """Register message handlers"""
    router.message.register(handlers.handle_text, F.text)


def get_message_handlers(bot_service: BotService) -> MessageHandlers:
    """Factory function to create message handlers"""
    return MessageHandlers(bot_service)
