from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Optional, Dict


class Keyboards:
    """Factory class for creating keyboard layouts"""

    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """Main menu keyboard"""
        buttons = [
            [KeyboardButton(text="💬 Чат"), KeyboardButton(text="📊 Метрики")],
            [KeyboardButton(text="🐳 Docker"), KeyboardButton(text="📝 Команды")],
            [KeyboardButton(text="🗑️ Очистить"), KeyboardButton(text="ℹ️ Справка")]
        ]
        return ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
            input_field_placeholder="Выберите действие..."
        )

    @staticmethod
    def command_approval(command_id: str, command: str, is_dangerous: bool = False) -> InlineKeyboardMarkup:
        """Keyboard for command approval"""
        warning = "⚠️ " if is_dangerous else ""
        buttons = [
            [
                InlineKeyboardButton(text=f"{warning}✅ Выполнить", callback_data=f"exec:{command_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel:{command_id}")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def container_actions(container_id: str, status: str) -> InlineKeyboardMarkup:
        """Keyboard for container actions"""
        buttons = []

        row = []
        if status == "running":
            row.append(InlineKeyboardButton(text="⏸️ Стоп", callback_data=f"docker:stop:{container_id}"))
            row.append(InlineKeyboardButton(text="🔄 Рестарт", callback_data=f"docker:restart:{container_id}"))
        else:
            row.append(InlineKeyboardButton(text="▶️ Старт", callback_data=f"docker:start:{container_id}"))

        if row:
            buttons.append(row)

        buttons.append([
            InlineKeyboardButton(text="📋 Логи", callback_data=f"docker:logs:{container_id}"),
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"docker:rm:{container_id}")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def session_actions(session_id: str) -> InlineKeyboardMarkup:
        """Keyboard for session actions"""
        buttons = [
            [
                InlineKeyboardButton(text="📤 Экспорт MD", callback_data=f"session:export:md:{session_id}"),
                InlineKeyboardButton(text="📤 Экспорт JSON", callback_data=f"session:export:json:{session_id}")
            ],
            [
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"session:delete:{session_id}")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def user_actions(user_id: int) -> InlineKeyboardMarkup:
        """Keyboard for user management"""
        buttons = [
            [
                InlineKeyboardButton(text="✅ Активировать", callback_data=f"user:activate:{user_id}"),
                InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"user:deactivate:{user_id}")
            ],
            [
                InlineKeyboardButton(text="👤 Назначить роль", callback_data=f"user:role:{user_id}")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def role_selection(user_id: int) -> InlineKeyboardMarkup:
        """Keyboard for role selection"""
        buttons = [
            [
                InlineKeyboardButton(text="👑 Админ", callback_data=f"role:set:{user_id}:admin"),
                InlineKeyboardButton(text="🔧 DevOps", callback_data=f"role:set:{user_id}:devops")
            ],
            [
                InlineKeyboardButton(text="👤 Пользователь", callback_data=f"role:set:{user_id}:user"),
                InlineKeyboardButton(text="👁️ Только чтение", callback_data=f"role:set:{user_id}:readonly")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def system_metrics() -> InlineKeyboardMarkup:
        """Keyboard for system metrics"""
        buttons = [
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="metrics:refresh"),
                InlineKeyboardButton(text="📈 Топ процессов", callback_data="metrics:top")
            ],
            [
                InlineKeyboardButton(text="🐳 Контейнеры", callback_data="docker:list"),
                InlineKeyboardButton(text="📝 История", callback_data="commands:history")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def back(button: str = "main") -> InlineKeyboardMarkup:
        """Back button"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back:{button}")]
        ])

    @staticmethod
    def docker_list(containers: List[Dict]) -> InlineKeyboardMarkup:
        """Keyboard with list of containers and their action buttons"""
        buttons = []
        for c in containers[:10]:  # Max 10 containers
            container_id = c.get("id", "")
            name = c.get("name", "unknown")[:15]
            status = c.get("status", "unknown")

            # Status indicator
            status_emoji = "🟢" if status == "running" else "🔴"

            # Action based on status
            if status == "running":
                action_text = "⏸️"
                action_callback = f"docker:stop:{container_id}"
            else:
                action_text = "▶️"
                action_callback = f"docker:start:{container_id}"

            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_emoji} {name}",
                    callback_data=f"docker:info:{container_id}"
                ),
                InlineKeyboardButton(text=action_text, callback_data=action_callback),
                InlineKeyboardButton(text="📋", callback_data=f"docker:logs:{container_id}"),
            ])

        # Refresh button
        buttons.append([
            InlineKeyboardButton(text="🔄 Обновить", callback_data="docker:list")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    # ============== Claude Code HITL Keyboards ==============

    @staticmethod
    def claude_permission(user_id: int, tool_name: str, request_id: str) -> InlineKeyboardMarkup:
        """Keyboard for Claude Code permission request (approve/reject tool execution)"""
        is_dangerous = tool_name.lower() in ["bash", "write", "edit", "notebookedit"]
        warning = "⚠️ " if is_dangerous else ""
        buttons = [
            [
                InlineKeyboardButton(
                    text=f"{warning}✅ Разрешить",
                    callback_data=f"claude:approve:{user_id}:{request_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
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
                text="✏️ Другое (ввести ответ)",
                callback_data=f"claude:other:{user_id}:{request_id}"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def claude_cancel(user_id: int) -> InlineKeyboardMarkup:
        """Keyboard to cancel running Claude Code task"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛑 Отменить", callback_data=f"claude:cancel:{user_id}")]
        ])

    @staticmethod
    def claude_continue(user_id: int, session_id: str) -> InlineKeyboardMarkup:
        """Keyboard to continue a Claude Code session"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Продолжить",
                    callback_data=f"claude:continue:{user_id}:{session_id}"
                ),
                InlineKeyboardButton(
                    text="🔄 Новая сессия",
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
            InlineKeyboardButton(text="📂 Указать путь...", callback_data="project:custom")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    # ============== Project Management Keyboards ==============

    @staticmethod
    def project_list(
        projects: List,
        current_project_id: Optional[str] = None,
        show_create: bool = True
    ) -> InlineKeyboardMarkup:
        """
        Keyboard with list of projects for /change command.

        Args:
            projects: List of Project entities
            current_project_id: ID of currently active project
            show_create: Whether to show create button
        """
        buttons = []

        for p in projects[:10]:  # Max 10 projects
            # Mark current project
            is_current = current_project_id and p.id == current_project_id
            emoji = "📂" if is_current else "📁"
            mark = " ✓" if is_current else ""

            buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} {p.name}{mark}",
                    callback_data=f"project:switch:{p.id}"
                )
            ])

        # Action buttons
        action_row = []
        if show_create:
            action_row.append(
                InlineKeyboardButton(text="➕ Создать", callback_data="project:create")
            )
        action_row.append(
            InlineKeyboardButton(text="📂 Обзор", callback_data="project:browse")
        )
        buttons.append(action_row)

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def context_menu(
        current_context_name: str = "",
        project_name: str = "",
        message_count: int = 0
    ) -> InlineKeyboardMarkup:
        """
        Main context menu with action buttons.

        Args:
            current_context_name: Name of current context
            project_name: Name of current project
            message_count: Number of messages in current context
        """
        buttons = [
            [
                InlineKeyboardButton(text="📋 Список", callback_data="ctx:list"),
                InlineKeyboardButton(text="✨ Новый", callback_data="ctx:new")
            ],
            [
                InlineKeyboardButton(text="🗑️ Очистить", callback_data="ctx:clear"),
                InlineKeyboardButton(text="❌ Закрыть", callback_data="ctx:close")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def context_clear_confirm() -> InlineKeyboardMarkup:
        """Confirmation keyboard for context clearing"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, очистить", callback_data="ctx:clear:confirm"),
                InlineKeyboardButton(text="⬅️ Отмена", callback_data="ctx:menu")
            ]
        ])

    @staticmethod
    def context_list(
        contexts: List,
        current_context_id: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """
        Keyboard with list of contexts for a project.

        Args:
            contexts: List of ProjectContext entities
            current_context_id: ID of currently active context
        """
        buttons = []

        for ctx in contexts[:10]:  # Max 10 contexts
            # Mark current context
            is_current = current_context_id and ctx.id == current_context_id
            emoji = "💬" if is_current else "📝"
            mark = " ✓" if is_current else ""

            # Show message count
            msg_count = f"({ctx.message_count})" if ctx.message_count > 0 else ""

            buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} {ctx.name} {msg_count}{mark}",
                    callback_data=f"ctx:switch:{ctx.id}"
                )
            ])

        # Action buttons at bottom
        buttons.append([
            InlineKeyboardButton(text="✨ Новый", callback_data="ctx:new"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ctx:menu")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def folder_browser(
        folders: List[str],
        current_path: str = "/root/projects"
    ) -> InlineKeyboardMarkup:
        """
        Keyboard for browsing folders in /root/projects.

        Args:
            folders: List of folder paths
            current_path: Current browsing path
        """
        import os
        buttons = []

        for folder in folders[:10]:
            name = os.path.basename(folder)
            buttons.append([
                InlineKeyboardButton(
                    text=f"📁 {name}",
                    callback_data=f"project:folder:{folder[:50]}"
                )
            ])

        # Back button if not at root
        if current_path != "/root/projects":
            parent = os.path.dirname(current_path)
            buttons.append([
                InlineKeyboardButton(text="⬆️ Наверх", callback_data=f"project:browse:{parent}")
            ])

        # Refresh
        buttons.append([
            InlineKeyboardButton(text="🔄 Обновить", callback_data="project:browse")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def project_confirm_create(path: str, name: str) -> InlineKeyboardMarkup:
        """Confirm project creation"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Создать",
                    callback_data=f"project:confirm:{path[:40]}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="project:browse"
                )
            ]
        ])

    # ============== File Browser Keyboard (/cd command) ==============

    @staticmethod
    def file_browser(
        content,  # DirectoryContent
        folders_per_row: int = 2
    ) -> InlineKeyboardMarkup:
        """
        Keyboard for /cd command - interactive folder navigation.

        Args:
            content: DirectoryContent object with entries
            folders_per_row: Number of folder buttons per row

        Features:
        - Folder buttons for navigation
        - Back, Root, Select buttons
        - Close button
        """
        buttons = []

        # Collect folder entries (only directories get buttons)
        folder_buttons = []
        for entry in content.entries:
            if entry.is_dir:
                # Truncate long names for button display
                name = entry.name
                if len(name) > 15:
                    name = name[:12] + "..."

                # Use hash-based callback to avoid path length issues
                # Format: cd:goto:<path>
                folder_buttons.append(
                    InlineKeyboardButton(
                        text=f"📁 {name}",
                        callback_data=f"cd:goto:{entry.path[:50]}"
                    )
                )

        # Group folders into rows
        for i in range(0, len(folder_buttons), folders_per_row):
            buttons.append(folder_buttons[i:i + folders_per_row])

        # Navigation buttons
        nav_row = []

        # Back button (if not at root)
        if content.parent_path:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬆️ Назад",
                    callback_data=f"cd:goto:{content.parent_path}"
                )
            )

        # Root button (if not already at root)
        if not content.is_root:
            nav_row.append(
                InlineKeyboardButton(
                    text="🏠 Корень",
                    callback_data="cd:root"
                )
            )

        # Select current folder
        nav_row.append(
            InlineKeyboardButton(
                text="✅ Выбрать",
                callback_data=f"cd:select:{content.path[:50]}"
            )
        )

        if nav_row:
            buttons.append(nav_row)

        # Close button
        buttons.append([
            InlineKeyboardButton(text="❌ Закрыть", callback_data="cd:close")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)


    # ============== Context Variables Keyboards ==============

    @staticmethod
    def variables_menu(
        variables: Dict,  # Dict[str, ContextVariable]
        project_name: str = "",
        context_name: str = ""
    ) -> InlineKeyboardMarkup:
        """
        Main variables menu with list of existing variables.

        Args:
            variables: Dict of name -> ContextVariable
            project_name: Current project name for display
            context_name: Current context name for display

        Returns:
            InlineKeyboardMarkup with:
            - List of variables with view/edit/delete buttons
            - "Add new" button
            - "Close" button
        """
        buttons = []

        # List variables (max 10)
        for name in sorted(variables.keys())[:10]:
            var = variables[name]

            # Mask value for display
            value = var.value if hasattr(var, 'value') else str(var)
            display_val = value[:8] + "***" if len(value) > 8 else value

            # Truncate name for callback (max 20 chars)
            callback_name = name[:20]

            # Variable row: name=value [edit] [delete]
            buttons.append([
                InlineKeyboardButton(
                    text=f"📝 {name}",
                    callback_data=f"var:show:{callback_name}"
                ),
                InlineKeyboardButton(text="✏️", callback_data=f"var:e:{callback_name}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"var:d:{callback_name}")
            ])

        # Add and Close buttons
        buttons.append([
            InlineKeyboardButton(text="➕ Добавить", callback_data="var:add"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="var:close")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def variable_delete_confirm(name: str) -> InlineKeyboardMarkup:
        """Confirmation keyboard for variable deletion"""
        callback_name = name[:20]
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"var:dc:{callback_name}"),
                InlineKeyboardButton(text="⬅️ Отмена", callback_data="var:list")
            ]
        ])

    @staticmethod
    def variable_cancel() -> InlineKeyboardMarkup:
        """Cancel button for variable input flows"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="var:list")]
        ])

    @staticmethod
    def variable_skip_description() -> InlineKeyboardMarkup:
        """Skip description button during variable creation"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⏭️ Пропустить описание", callback_data="var:skip_desc"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="var:list")
            ]
        ])


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
