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

    def __init__(self, bot_service, message_handlers, claude_proxy=None):
        self.bot_service = bot_service
        self.message_handlers = message_handlers
        self.claude_proxy = claude_proxy  # ClaudeCodeProxyService instance

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
            from presentation.keyboards.keyboards import Keyboards
            monitor = SystemMonitor()
            containers = await monitor.get_docker_containers()

            if not containers:
                text = "🐳 **No containers found**"
                await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
            else:
                lines = ["🐳 **Docker Containers:**\n"]
                for c in containers:
                    status_emoji = "🟢" if c["status"] == "running" else "🔴"
                    lines.append(f"\n{status_emoji} **{c['name']}**")
                    lines.append(f"   Status: {c['status']}")
                    lines.append(f"   Image: `{c['image'][:30]}`")

                text = "\n".join(lines)
                await callback.message.edit_text(
                    text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=Keyboards.docker_list(containers)
                )

        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            await callback.answer(f"❌ Error: {e}")

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
            await callback.answer(f"❌ Error: {e}")

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
            await callback.answer(f"❌ Error: {e}")

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
            await callback.answer(f"❌ Error: {e}")

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
                text = f"📋 **Logs** (`{container_id}`)\n\n```\n{logs}\n```"
                await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
            else:
                await callback.answer(f"❌ {logs}")

        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            await callback.answer(f"❌ Error: {e}")

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
            await callback.answer(f"❌ Error: {e}")

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
                    f"🐳 **Container: {container['name']}**\n\n"
                    f"**ID:** `{container['id']}`\n"
                    f"**Status:** {container['status']}\n"
                    f"**Image:** `{container['image']}`\n"
                )
                if container.get("ports"):
                    text += f"**Ports:** {', '.join(str(p) for p in container['ports'])}\n"

                await callback.message.edit_text(
                    text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=Keyboards.container_actions(container_id, container["status"])
                )
            else:
                await callback.answer("Container not found")

        except Exception as e:
            logger.error(f"Error getting container info: {e}")
            await callback.answer(f"❌ Error: {e}")

        await callback.answer()

    async def handle_metrics_top(self, callback: CallbackQuery) -> None:
        """Handle top processes request"""
        try:
            from infrastructure.monitoring.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            processes = await monitor.get_top_processes(limit=10)

            lines = ["📈 **Top Processes:**\n"]
            for p in processes:
                lines.append(
                    f"`{p.pid:>6}` | CPU: {p.cpu_percent:>5.1f}% | MEM: {p.memory_percent:>5.1f}% | {p.name[:20]}"
                )

            text = "\n".join(lines)
            await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Error getting top processes: {e}")
            await callback.answer(f"❌ Error: {e}")

        await callback.answer()

    async def handle_commands_history(self, callback: CallbackQuery) -> None:
        """Handle commands history request"""
        try:
            from domain.value_objects.user_id import UserId
            user_id = UserId.from_int(callback.from_user.id)

            commands = await self.bot_service.command_repository.find_by_user(user_id, limit=10)

            if not commands:
                text = "📝 **Command History**\n\nNo commands yet."
            else:
                lines = ["📝 **Command History:**\n"]
                for cmd in commands[:10]:
                    status_emoji = "✅" if cmd.status.value == "completed" else "⏳"
                    cmd_preview = cmd.command[:30] + "..." if len(cmd.command) > 30 else cmd.command
                    lines.append(f"{status_emoji} `{cmd_preview}`")

                text = "\n".join(lines)

            await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Error getting command history: {e}")
            await callback.answer(f"❌ Error: {e}")

        await callback.answer()

    # ============== Claude Code HITL Callbacks ==============

    async def handle_claude_approve(self, callback: CallbackQuery) -> None:
        """Handle Claude Code permission approval"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ This action is not for you")
            return

        try:
            # Update message to show approved
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ **Approved**",
                parse_mode=ParseMode.MARKDOWN
            )

            # Send approval to Claude Code proxy
            if self.claude_proxy:
                await self.claude_proxy.respond_to_permission(user_id, True)

            # Notify message handler to continue
            if hasattr(self.message_handlers, 'handle_permission_response'):
                await self.message_handlers.handle_permission_response(user_id, True)

            await callback.answer("✅ Approved")

        except Exception as e:
            logger.error(f"Error handling claude approve: {e}")
            await callback.answer(f"❌ Error: {e}")

    async def handle_claude_reject(self, callback: CallbackQuery) -> None:
        """Handle Claude Code permission rejection"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ This action is not for you")
            return

        try:
            # Update message to show rejected
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ **Rejected**",
                parse_mode=ParseMode.MARKDOWN
            )

            # Send rejection to Claude Code proxy
            if self.claude_proxy:
                await self.claude_proxy.respond_to_permission(user_id, False)

            # Notify message handler
            if hasattr(self.message_handlers, 'handle_permission_response'):
                await self.message_handlers.handle_permission_response(user_id, False)

            await callback.answer("❌ Rejected")

        except Exception as e:
            logger.error(f"Error handling claude reject: {e}")
            await callback.answer(f"❌ Error: {e}")

    async def handle_claude_answer(self, callback: CallbackQuery) -> None:
        """Handle Claude Code question answer (selected option)"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))
        option_index = int(data.get("option_index", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ This action is not for you")
            return

        try:
            # Get the answer text from message handler's pending question
            answer = str(option_index)  # Default to index
            if hasattr(self.message_handlers, 'get_pending_question_option'):
                answer = self.message_handlers.get_pending_question_option(user_id, option_index)

            # Update message to show answer
            await callback.message.edit_text(
                callback.message.text + f"\n\n📝 **Answer:** {answer}",
                parse_mode=ParseMode.MARKDOWN
            )

            # Send answer to Claude Code proxy
            if self.claude_proxy:
                await self.claude_proxy.respond_to_question(user_id, answer)

            # Notify message handler
            if hasattr(self.message_handlers, 'handle_question_response'):
                await self.message_handlers.handle_question_response(user_id, answer)

            await callback.answer(f"Answered: {answer[:20]}...")

        except Exception as e:
            logger.error(f"Error handling claude answer: {e}")
            await callback.answer(f"❌ Error: {e}")

    async def handle_claude_other(self, callback: CallbackQuery) -> None:
        """Handle Claude Code question - user wants to type custom answer"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ This action is not for you")
            return

        try:
            # Update message to prompt for text input
            await callback.message.edit_text(
                callback.message.text + "\n\n✏️ **Type your answer below:**",
                parse_mode=ParseMode.MARKDOWN
            )

            # Set message handler to expect text answer
            if hasattr(self.message_handlers, 'set_expecting_answer'):
                self.message_handlers.set_expecting_answer(user_id, True)

            await callback.answer("Type your answer in chat")

        except Exception as e:
            logger.error(f"Error handling claude other: {e}")
            await callback.answer(f"❌ Error: {e}")

    async def handle_claude_cancel(self, callback: CallbackQuery) -> None:
        """Handle Claude Code task cancellation"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))

        if user_id != callback.from_user.id:
            await callback.answer("❌ This action is not for you")
            return

        try:
            # Cancel the task
            if self.claude_proxy:
                cancelled = await self.claude_proxy.cancel_task(user_id)
                if cancelled:
                    await callback.message.edit_text(
                        "🛑 **Task cancelled**",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    await callback.answer("Task cancelled")
                else:
                    await callback.answer("No active task to cancel")
            else:
                await callback.answer("❌ Proxy not available")

        except Exception as e:
            logger.error(f"Error cancelling task: {e}")
            await callback.answer(f"❌ Error: {e}")

    async def handle_claude_continue(self, callback: CallbackQuery) -> None:
        """Handle continue Claude Code session"""
        data = CallbackData.parse_claude_callback(callback.data)
        user_id = int(data.get("user_id", 0))
        session_id = data.get("session_id")

        if user_id != callback.from_user.id:
            await callback.answer("❌ This action is not for you")
            return

        try:
            await callback.message.edit_text(
                "▶️ **Continuing session...**\n\nSend your next message to continue.",
                parse_mode=ParseMode.MARKDOWN
            )

            # Store session_id for next message
            if hasattr(self.message_handlers, 'set_continue_session'):
                self.message_handlers.set_continue_session(user_id, session_id)

            await callback.answer("Send your next message")

        except Exception as e:
            logger.error(f"Error continuing session: {e}")
            await callback.answer(f"❌ Error: {e}")

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
                    f"📁 **Working directory set:**\n`{path}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                await callback.answer(f"Project: {path}")

            elif action == "custom":
                # Prompt for custom path input
                if hasattr(self.message_handlers, 'set_expecting_path'):
                    self.message_handlers.set_expecting_path(user_id, True)

                await callback.message.edit_text(
                    "📂 **Enter project path:**\n\nType the full path to your project directory.",
                    parse_mode=ParseMode.MARKDOWN
                )
                await callback.answer("Type path in chat")

        except Exception as e:
            logger.error(f"Error handling project select: {e}")
            await callback.answer(f"❌ Error: {e}")


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

    # Project selection handlers
    router.callback_query.register(
        handlers.handle_project_select,
        F.data.startswith("project:")
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


def get_callback_handlers(bot_service, message_handlers, claude_proxy=None) -> CallbackHandlers:
    """Factory function to create callback handlers"""
    return CallbackHandlers(bot_service, message_handlers, claude_proxy)
