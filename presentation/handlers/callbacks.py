import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from presentation.keyboards.keyboards import CallbackData

logger = logging.getLogger(__name__)
router = Router()


class CallbackHandlers:
    """Bot callback query handlers"""

    def __init__(self, bot_service, message_handlers):
        self.bot_service = bot_service
        self.message_handlers = message_handlers

    async def handle_command_approve(self, callback: CallbackQuery) -> None:
        """Handle command approval callback"""
        command_id = CallbackData.get_command_id(callback.data)
        if not command_id:
            await callback.answer("❌ Invalid command")
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
                parse_mode=ParseMode.MARKDOWN
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
                    await callback.message.answer(response, parse_mode=ParseMode.MARKDOWN)
            except:
                pass  # Skip AI follow-up on error

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            await callback.message.edit_text(f"❌ **Error:** {str(e)}", parse_mode=ParseMode.MARKDOWN)

        await callback.answer()

    async def handle_command_cancel(self, callback: CallbackQuery) -> None:
        """Handle command cancellation callback"""
        command_id = CallbackData.get_command_id(callback.data)
        if not command_id:
            await callback.answer("❌ Invalid command")
            return

        try:
            await self.bot_service.reject_command(command_id, "Cancelled by user")
            await callback.message.edit_text("❌ Command cancelled")
        except Exception as e:
            logger.error(f"Error cancelling command: {e}")
            await callback.message.edit_text(f"❌ Error: {str(e)}")

        await callback.answer()

    async def handle_metrics_refresh(self, callback: CallbackQuery) -> None:
        """Handle metrics refresh callback"""
        try:
            info = await self.bot_service.get_system_info()
            metrics = info["metrics"]

            text = (
                f"📊 **System Metrics**\n\n"
                f"💻 **CPU:** {metrics['cpu_percent']:.1f}%\n"
                f"🧠 **Memory:** {metrics['memory_percent']:.1f}% ({metrics['memory_used_gb']}GB / {metrics['memory_total_gb']}GB)\n"
                f"💾 **Disk:** {metrics['disk_percent']:.1f}% ({metrics['disk_used_gb']}GB / {metrics['disk_total_gb']}GB)\n"
            )

            if metrics.get('load_average', [0])[0] > 0:
                text += f"📈 **Load:** {metrics['load_average'][0]:.2f}\n"

            # Alerts
            if info.get("alerts"):
                text += "\n⚠️ **Alerts:**\n"
                text += "\n".join(info["alerts"])

            await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Error refreshing metrics: {e}")
            await callback.answer(f"❌ Error: {e}")

        await callback.answer()

    async def handle_docker_list(self, callback: CallbackQuery) -> None:
        """Handle docker list callback"""
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            containers = await monitor.get_docker_containers()

            if not containers:
                text = "🐳 **No containers found**"
            else:
                lines = ["🐳 **Docker Containers:**\n"]
                for c in containers:
                    status_emoji = "✅" if c["status"] == "running" else "⏸️"
                    lines.append(f"\n{status_emoji} **{c['name']}**")
                    lines.append(f"   ID: `{c['id']}`")
                    lines.append(f"   Image: {c['image']}")
                    lines.append(f"   Status: {c['status']}")

                text = "\n".join(lines)

            await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            await callback.answer(f"❌ Error: {e}")

        await callback.answer()


def register_handlers(router: Router, handlers: CallbackHandlers) -> None:
    """Register callback handlers"""
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


def get_callback_handlers(bot_service, message_handlers) -> CallbackHandlers:
    """Factory function to create callback handlers"""
    return CallbackHandlers(bot_service, message_handlers)
