from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Optional, Dict


class Keyboards:
    """Factory class for creating keyboard layouts"""

    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """Main menu keyboard"""
        buttons = [
            [KeyboardButton(text="💬 Chat"), KeyboardButton(text="📊 Metrics")],
            [KeyboardButton(text="🐳 Docker"), KeyboardButton(text="📝 Commands")],
            [KeyboardButton(text="🗑️ Clear"), KeyboardButton(text="ℹ️ Help")]
        ]
        return ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
            input_field_placeholder="Choose an action..."
        )

    @staticmethod
    def command_approval(command_id: str, command: str, is_dangerous: bool = False) -> InlineKeyboardMarkup:
        """Keyboard for command approval"""
        warning = "⚠️ " if is_dangerous else ""
        buttons = [
            [
                InlineKeyboardButton(text=f"{warning}✅ Execute", callback_data=f"exec:{command_id}"),
                InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel:{command_id}")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def container_actions(container_id: str, status: str) -> InlineKeyboardMarkup:
        """Keyboard for container actions"""
        buttons = []

        row = []
        if status == "running":
            row.append(InlineKeyboardButton(text="⏸️ Stop", callback_data=f"docker:stop:{container_id}"))
            row.append(InlineKeyboardButton(text="🔄 Restart", callback_data=f"docker:restart:{container_id}"))
        else:
            row.append(InlineKeyboardButton(text="▶️ Start", callback_data=f"docker:start:{container_id}"))

        if row:
            buttons.append(row)

        buttons.append([
            InlineKeyboardButton(text="📋 Logs", callback_data=f"docker:logs:{container_id}"),
            InlineKeyboardButton(text="🗑️ Remove", callback_data=f"docker:rm:{container_id}")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def session_actions(session_id: str) -> InlineKeyboardMarkup:
        """Keyboard for session actions"""
        buttons = [
            [
                InlineKeyboardButton(text="📤 Export MD", callback_data=f"session:export:md:{session_id}"),
                InlineKeyboardButton(text="📤 Export JSON", callback_data=f"session:export:json:{session_id}")
            ],
            [
                InlineKeyboardButton(text="🗑️ Delete", callback_data=f"session:delete:{session_id}")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def user_actions(user_id: int) -> InlineKeyboardMarkup:
        """Keyboard for user management"""
        buttons = [
            [
                InlineKeyboardButton(text="✅ Activate", callback_data=f"user:activate:{user_id}"),
                InlineKeyboardButton(text="❌ Deactivate", callback_data=f"user:deactivate:{user_id}")
            ],
            [
                InlineKeyboardButton(text="👤 Set Role", callback_data=f"user:role:{user_id}")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def role_selection(user_id: int) -> InlineKeyboardMarkup:
        """Keyboard for role selection"""
        buttons = [
            [
                InlineKeyboardButton(text="👑 Admin", callback_data=f"role:set:{user_id}:admin"),
                InlineKeyboardButton(text="🔧 DevOps", callback_data=f"role:set:{user_id}:devops")
            ],
            [
                InlineKeyboardButton(text="👤 User", callback_data=f"role:set:{user_id}:user"),
                InlineKeyboardButton(text="👁️ ReadOnly", callback_data=f"role:set:{user_id}:readonly")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def system_metrics() -> InlineKeyboardMarkup:
        """Keyboard for system metrics"""
        buttons = [
            [
                InlineKeyboardButton(text="🔄 Refresh", callback_data="metrics:refresh"),
                InlineKeyboardButton(text="📈 Top Processes", callback_data="metrics:top")
            ],
            [
                InlineKeyboardButton(text="🐳 Containers", callback_data="docker:list"),
                InlineKeyboardButton(text="📝 History", callback_data="commands:history")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def back(button: str = "main") -> InlineKeyboardMarkup:
        """Back button"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data=f"back:{button}")]
        ])

    # ============== Claude Code HITL Keyboards ==============

    @staticmethod
    def claude_permission(user_id: int, tool_name: str, request_id: str) -> InlineKeyboardMarkup:
        """Keyboard for Claude Code permission request (approve/reject tool execution)"""
        is_dangerous = tool_name.lower() in ["bash", "write", "edit", "notebookedit"]
        warning = "⚠️ " if is_dangerous else ""
        buttons = [
            [
                InlineKeyboardButton(
                    text=f"{warning}✅ Approve",
                    callback_data=f"claude:approve:{user_id}:{request_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Reject",
                    callback_data=f"claude:reject:{user_id}:{request_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def claude_question(user_id: int, options: List[str], request_id: str) -> InlineKeyboardMarkup:
        """Keyboard for Claude Code question with options"""
        buttons = []

        # Add option buttons (max 4 per row)
        row = []
        for i, option in enumerate(options[:8]):  # Max 8 options
            # Truncate long options
            display = option if len(option) <= 30 else option[:27] + "..."
            row.append(InlineKeyboardButton(
                text=display,
                callback_data=f"claude:answer:{user_id}:{request_id}:{i}"
            ))
            if len(row) >= 2:  # 2 buttons per row
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        # Add "Other" button for custom input
        buttons.append([
            InlineKeyboardButton(
                text="✏️ Other (type answer)",
                callback_data=f"claude:other:{user_id}:{request_id}"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def claude_cancel(user_id: int) -> InlineKeyboardMarkup:
        """Keyboard to cancel running Claude Code task"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛑 Cancel Task", callback_data=f"claude:cancel:{user_id}")]
        ])

    @staticmethod
    def claude_continue(user_id: int, session_id: str) -> InlineKeyboardMarkup:
        """Keyboard to continue a Claude Code session"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Continue",
                    callback_data=f"claude:continue:{user_id}:{session_id}"
                ),
                InlineKeyboardButton(
                    text="🔄 New Session",
                    callback_data=f"claude:new:{user_id}"
                )
            ]
        ])

    @staticmethod
    def project_selection(projects: List[Dict[str, str]]) -> InlineKeyboardMarkup:
        """Keyboard for project selection"""
        buttons = []
        for proj in projects[:10]:  # Max 10 projects
            name = proj.get("name", "Unknown")
            path = proj.get("path", "")
            buttons.append([
                InlineKeyboardButton(
                    text=f"📁 {name}",
                    callback_data=f"project:select:{path[:50]}"  # Truncate path for callback
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="📂 Custom path...", callback_data="project:custom")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)


class CallbackData:
    """Helper for parsing callback data"""

    @staticmethod
    def parse(callback_data: str) -> List[str]:
        """Parse callback data into parts"""
        return callback_data.split(":")

    @staticmethod
    def is_command_exec(callback_data: str) -> bool:
        return callback_data.startswith("exec:")

    @staticmethod
    def is_command_cancel(callback_data: str) -> bool:
        return callback_data.startswith("cancel:")

    @staticmethod
    def get_command_id(callback_data: str) -> str:
        parts = callback_data.split(":")
        return parts[1] if len(parts) > 1 else None

    # ============== Claude Code Callback Helpers ==============

    @staticmethod
    def is_claude_callback(callback_data: str) -> bool:
        """Check if this is a Claude Code callback"""
        return callback_data.startswith("claude:")

    @staticmethod
    def is_claude_approve(callback_data: str) -> bool:
        return callback_data.startswith("claude:approve:")

    @staticmethod
    def is_claude_reject(callback_data: str) -> bool:
        return callback_data.startswith("claude:reject:")

    @staticmethod
    def is_claude_answer(callback_data: str) -> bool:
        return callback_data.startswith("claude:answer:")

    @staticmethod
    def is_claude_other(callback_data: str) -> bool:
        return callback_data.startswith("claude:other:")

    @staticmethod
    def is_claude_cancel(callback_data: str) -> bool:
        return callback_data.startswith("claude:cancel:")

    @staticmethod
    def is_claude_continue(callback_data: str) -> bool:
        return callback_data.startswith("claude:continue:")

    @staticmethod
    def parse_claude_callback(callback_data: str) -> Dict[str, str]:
        """
        Parse Claude Code callback data.

        Returns dict with:
        - action: approve/reject/answer/other/cancel/continue
        - user_id: User ID
        - request_id: Request ID (for approve/reject/answer)
        - option_index: Option index (for answer)
        - session_id: Session ID (for continue)
        """
        parts = callback_data.split(":")
        result = {"action": parts[1] if len(parts) > 1 else ""}

        if len(parts) > 2:
            result["user_id"] = parts[2]
        if len(parts) > 3:
            if result["action"] == "answer":
                result["request_id"] = parts[3]
                if len(parts) > 4:
                    result["option_index"] = parts[4]
            elif result["action"] == "continue":
                result["session_id"] = parts[3]
            else:
                result["request_id"] = parts[3]

        return result

    @staticmethod
    def is_project_callback(callback_data: str) -> bool:
        return callback_data.startswith("project:")

    @staticmethod
    def parse_project_callback(callback_data: str) -> Dict[str, str]:
        """Parse project selection callback"""
        parts = callback_data.split(":")
        result = {"action": parts[1] if len(parts) > 1 else ""}
        if len(parts) > 2:
            result["path"] = ":".join(parts[2:])  # Rejoin in case path has colons
        return result
