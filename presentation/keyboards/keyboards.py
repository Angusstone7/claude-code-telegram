from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Optional, Dict


class Keyboards:
    """Factory class for creating keyboard layouts"""

    # ============== Main Inline Menu System ==============

    @staticmethod
    def main_menu_inline(
        working_dir: str = "/root",
        project_name: str = None,
        yolo_enabled: bool = False,
        has_active_task: bool = False
    ) -> InlineKeyboardMarkup:
        """
        Main menu with inline buttons.

        This is the primary navigation interface, replacing individual commands.
        """
        yolo_indicator = " ⚡" if yolo_enabled else ""
        task_indicator = " 🔄" if has_active_task else ""

        buttons = [
            # Row 1: Projects and Context
            [
                InlineKeyboardButton(text="📂 Проекты", callback_data="menu:projects"),
                InlineKeyboardButton(text="💬 Контекст", callback_data="menu:context"),
            ],
            # Row 2: Settings and Plugins
            [
                InlineKeyboardButton(text=f"⚙️ Настройки{yolo_indicator}", callback_data="menu:settings"),
                InlineKeyboardButton(text="🔌 Плагины", callback_data="menu:plugins"),
            ],
            # Row 3: System and Help
            [
                InlineKeyboardButton(text=f"📊 Система{task_indicator}", callback_data="menu:system"),
                InlineKeyboardButton(text="❓ Справка", callback_data="menu:help"),
            ],
            # Row 4: Close
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data="menu:close"),
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def menu_projects(
        current_dir: str = "/root",
        project_name: str = None
    ) -> InlineKeyboardMarkup:
        """Projects submenu - navigation and project management"""
        buttons = [
            [
                InlineKeyboardButton(text="📁 Навигация", callback_data="menu:projects:browse"),
            ],
            [
                InlineKeyboardButton(text="🔄 Сменить проект", callback_data="menu:projects:change"),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"),
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def menu_context(
        context_name: str = None,
        message_count: int = 0,
        has_session: bool = False
    ) -> InlineKeyboardMarkup:
        """Context submenu - session and context management"""
        buttons = [
            [
                InlineKeyboardButton(text="✨ Новый контекст", callback_data="menu:context:fresh"),
            ],
            [
                InlineKeyboardButton(text="💬 Контексты", callback_data="menu:context:list"),
                InlineKeyboardButton(text="📋 Переменные", callback_data="menu:context:vars"),
            ],
            [
                InlineKeyboardButton(text="🗑 Очистить историю", callback_data="menu:context:clear"),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"),
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def menu_settings(
        yolo_enabled: bool = False,
        auth_mode: str = "zai_api",
        has_credentials: bool = False
    ) -> InlineKeyboardMarkup:
        """Settings submenu - account and preferences"""
        yolo_status = "✅" if yolo_enabled else "❌"
        auth_icon = "☁️" if auth_mode == "claude_account" else "🌐"

        buttons = [
            [
                InlineKeyboardButton(
                    text=f"👤 Аккаунт ({auth_icon})",
                    callback_data="menu:settings:account"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⚡ YOLO режим: {yolo_status}",
                    callback_data="menu:settings:yolo"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌍 Глобальные переменные",
                    callback_data="menu:settings:global_vars"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Лимиты Claude.ai",
                    callback_data="menu:settings:usage"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔐 Авторизация Claude",
                    callback_data="menu:settings:login"
                ),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"),
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def menu_system(has_active_task: bool = False) -> InlineKeyboardMarkup:
        """System submenu - monitoring and control"""
        buttons = [
            [
                InlineKeyboardButton(text="📊 Статус Claude", callback_data="menu:system:status"),
            ],
            [
                InlineKeyboardButton(text="💻 Метрики", callback_data="menu:system:metrics"),
                InlineKeyboardButton(text="🐳 Docker", callback_data="menu:system:docker"),
            ],
            [
                InlineKeyboardButton(text="🔍 Диагностика", callback_data="menu:system:diagnose"),
            ],
        ]

        if has_active_task:
            buttons.append([
                InlineKeyboardButton(text="🛑 Отменить задачу", callback_data="menu:system:cancel"),
            ])

        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"),
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def menu_help() -> InlineKeyboardMarkup:
        """Help submenu"""
        buttons = [
            [
                InlineKeyboardButton(text="📖 Как работать с ботом", callback_data="menu:help:usage"),
            ],
            [
                InlineKeyboardButton(text="🔌 О плагинах", callback_data="menu:help:plugins"),
            ],
            [
                InlineKeyboardButton(text="⚡ О YOLO режиме", callback_data="menu:help:yolo"),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"),
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def menu_back_only(back_to: str = "menu:main") -> InlineKeyboardMarkup:
        """Simple back button keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_to)]
        ])

    # ============== Legacy Reply Keyboard (kept for compatibility) ==============

    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """Legacy reply keyboard - kept for compatibility"""
        buttons = [
            [KeyboardButton(text="📊 Метрики"), KeyboardButton(text="🐳 Docker")],
            [KeyboardButton(text="📂 Проект"), KeyboardButton(text="⚡ YOLO")],
            [KeyboardButton(text="🗑️ Очистить"), KeyboardButton(text="ℹ️ Справка")]
        ]
        return ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
            input_field_placeholder="Напишите задачу..."
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
    def container_actions(
        container_id: str,
        status: str,
        show_back: bool = True,
        back_to: str = "docker:list"
    ) -> InlineKeyboardMarkup:
        """
        Keyboard for container actions

        Args:
            container_id: Docker container ID
            status: Container status (running, exited, etc.)
            show_back: Whether to show back button
            back_to: Callback data for back button
        """
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

        # Back button
        if show_back:
            buttons.append([
                InlineKeyboardButton(text="🔙 К списку", callback_data=back_to)
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
    def system_metrics(
        show_back: bool = True,
        back_to: str = "menu:system"
    ) -> InlineKeyboardMarkup:
        """
        Keyboard for system metrics

        Args:
            show_back: Whether to show back button
            back_to: Callback data for back button
        """
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

        # Back button
        if show_back:
            buttons.append([
                InlineKeyboardButton(text="🔙 Назад", callback_data=back_to)
            ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def back(button: str = "main") -> InlineKeyboardMarkup:
        """Back button"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back:{button}")]
        ])

    @staticmethod
    def docker_list(
        containers: List[Dict],
        show_back: bool = True,
        back_to: str = "menu:system"
    ) -> InlineKeyboardMarkup:
        """
        Keyboard with list of containers and their action buttons

        Args:
            containers: List of container dictionaries
            show_back: Whether to show back button
            back_to: Callback data for back button
        """
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

        # Refresh and back buttons
        action_buttons = [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="docker:list")
        ]
        if show_back:
            action_buttons.append(
                InlineKeyboardButton(text="🔙 Назад", callback_data=back_to)
            )
        buttons.append(action_buttons)

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
            ],
            [
                InlineKeyboardButton(
                    text="💬 Уточнить",
                    callback_data=f"claude:clarify:{user_id}:{request_id}"
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
    def plan_approval(user_id: int, request_id: str) -> InlineKeyboardMarkup:
        """Keyboard for plan approval (ExitPlanMode)"""
        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Одобрить план",
                    callback_data=f"plan:approve:{user_id}:{request_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"plan:reject:{user_id}:{request_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Уточнить план",
                    callback_data=f"plan:clarify:{user_id}:{request_id}"
                ),
                InlineKeyboardButton(
                    text="🛑 Отменить задачу",
                    callback_data=f"plan:cancel:{user_id}:{request_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

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
        show_create: bool = True,
        show_back: bool = True,
        back_to: str = "menu:projects"
    ) -> InlineKeyboardMarkup:
        """
        Keyboard with list of projects for /change command.

        Args:
            projects: List of Project entities
            current_project_id: ID of currently active project
            show_create: Whether to show create button
            show_back: Whether to show back button
            back_to: Callback data for back button
        """
        buttons = []

        for p in projects[:10]:  # Max 10 projects
            # Mark current project
            is_current = current_project_id and p.id == current_project_id
            emoji = "📂" if is_current else "📁"
            mark = " ✓" if is_current else ""

            row = [
                InlineKeyboardButton(
                    text=f"{emoji} {p.name}{mark}",
                    callback_data=f"project:switch:{p.id}"
                ),
                InlineKeyboardButton(
                    text="🗑️",
                    callback_data=f"project:delete:{p.id}"
                )
            ]
            buttons.append(row)

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

        # Back button
        if show_back:
            buttons.append([
                InlineKeyboardButton(text="🔙 Назад", callback_data=back_to)
            ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def context_menu(
        current_context_name: str = "",
        project_name: str = "",
        message_count: int = 0,
        show_back: bool = True,
        back_to: str = "menu:context"
    ) -> InlineKeyboardMarkup:
        """
        Main context menu with action buttons.

        Args:
            current_context_name: Name of current context
            project_name: Name of current project
            message_count: Number of messages in current context
            show_back: Whether to show back button
            back_to: Callback data for back button
        """
        buttons = [
            [
                InlineKeyboardButton(text="📋 Список", callback_data="ctx:list"),
                InlineKeyboardButton(text="✨ Новый", callback_data="ctx:new")
            ],
            [
                InlineKeyboardButton(text="🗑️ Очистить", callback_data="ctx:clear"),
            ]
        ]

        # Add back button
        if show_back:
            buttons.append([
                InlineKeyboardButton(text="🔙 Назад", callback_data=back_to)
            ])

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

        # Navigation row
        nav_row = []

        # Back/Up button
        if current_path != "/root/projects":
            parent = os.path.dirname(current_path)
            nav_row.append(
                InlineKeyboardButton(text="⬆️ Наверх", callback_data=f"project:browse:{parent}")
            )

        # Refresh button
        nav_row.append(
            InlineKeyboardButton(text="🔄 Обновить", callback_data="project:browse")
        )

        buttons.append(nav_row)

        # Create folder button (only at root level)
        if current_path == "/root/projects":
            buttons.append([
                InlineKeyboardButton(text="📁 Создать папку", callback_data="project:mkdir")
            ])

        # Back to menu button
        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="menu:projects")
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

    @staticmethod
    def project_delete_confirm(project_id: str, project_name: str, delete_files: bool = False) -> InlineKeyboardMarkup:
        """
        Confirmation keyboard for project deletion.

        Args:
            project_id: Project ID
            project_name: Project name for display
            delete_files: Whether to also delete files
        """
        buttons = [
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить только проект",
                    callback_data=f"project:delete_confirm:{project_id}:db"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚠️ Удалить проект И файлы",
                    callback_data=f"project:delete_confirm:{project_id}:all"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="project:back"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

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
        context_name: str = "",
        show_back: bool = True,
        back_to: str = "menu:context"
    ) -> InlineKeyboardMarkup:
        """
        Main variables menu with list of existing variables.

        Args:
            variables: Dict of name -> ContextVariable
            project_name: Current project name for display
            context_name: Current context name for display
            show_back: Whether to show back button
            back_to: Callback data for back button

        Returns:
            InlineKeyboardMarkup with:
            - List of variables with view/edit/delete buttons
            - "Add new" button
            - "Back" button
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

        # Add button
        buttons.append([
            InlineKeyboardButton(text="➕ Добавить", callback_data="var:add")
        ])

        # Back button
        if show_back:
            buttons.append([
                InlineKeyboardButton(text="🔙 Назад", callback_data=back_to)
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

    # ============== Global Variables Keyboards ==============

    @staticmethod
    def global_variables_menu(
        variables: Dict,  # Dict[str, ContextVariable]
        show_back: bool = True,
        back_to: str = "menu:settings"
    ) -> InlineKeyboardMarkup:
        """
        Global variables menu - variables inherited by all projects.

        Args:
            variables: Dict of name -> ContextVariable
            show_back: Whether to show back button
            back_to: Callback data for back button

        Returns:
            InlineKeyboardMarkup with:
            - List of global variables with edit/delete buttons
            - "Add new" button
            - "Back" button
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

            # Variable row: name [edit] [delete]
            buttons.append([
                InlineKeyboardButton(
                    text=f"🌍 {name}",
                    callback_data=f"gvar:show:{callback_name}"
                ),
                InlineKeyboardButton(text="✏️", callback_data=f"gvar:e:{callback_name}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"gvar:d:{callback_name}")
            ])

        # Add button
        buttons.append([
            InlineKeyboardButton(text="➕ Добавить", callback_data="gvar:add")
        ])

        # Back button
        if show_back:
            buttons.append([
                InlineKeyboardButton(text="🔙 Назад", callback_data=back_to)
            ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def global_variable_delete_confirm(name: str) -> InlineKeyboardMarkup:
        """Confirmation keyboard for global variable deletion"""
        callback_name = name[:20]
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"gvar:dc:{callback_name}"),
                InlineKeyboardButton(text="⬅️ Отмена", callback_data="gvar:list")
            ]
        ])

    @staticmethod
    def global_variable_cancel() -> InlineKeyboardMarkup:
        """Cancel button for global variable input flows"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="gvar:list")]
        ])

    @staticmethod
    def global_variable_skip_description() -> InlineKeyboardMarkup:
        """Skip description button during global variable creation"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⏭️ Пропустить описание", callback_data="gvar:skip_desc"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="gvar:list")
            ]
        ])

    # ============== Plugin Management Keyboards ==============

    @staticmethod
    def plugins_menu(
        plugins: List[Dict],
        show_marketplace: bool = True,
        show_back: bool = True,
        back_to: str = "menu:main"
    ) -> InlineKeyboardMarkup:
        """
        Main plugins menu with list of enabled plugins.

        Args:
            plugins: List of plugin info dicts with name, description, available, source
            show_marketplace: Whether to show marketplace button
            show_back: Show back button instead of close button
            back_to: Callback data for back button

        Returns:
            InlineKeyboardMarkup with:
            - List of plugins with toggle buttons
            - "Add from marketplace" button
            - "Back" or "Close" button
        """
        buttons = []

        # List plugins (max 10)
        for plugin in plugins[:10]:
            name = plugin.get("name", "unknown")
            source = plugin.get("source", "official")
            available = plugin.get("available", True)

            # Status indicator
            status_emoji = "✅" if available else "⚠️"
            source_emoji = "🌐" if source == "official" else "📁"

            # Plugin row: status + name [toggle off]
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_emoji} {source_emoji} {name}",
                    callback_data=f"plugin:info:{name[:20]}"
                ),
                InlineKeyboardButton(
                    text="❌",
                    callback_data=f"plugin:disable:{name[:20]}"
                )
            ])

        # Action buttons
        action_row = []
        if show_marketplace:
            action_row.append(
                InlineKeyboardButton(text="🛒 Магазин", callback_data="plugin:marketplace")
            )
        action_row.append(
            InlineKeyboardButton(text="🔄 Обновить", callback_data="plugin:refresh")
        )
        buttons.append(action_row)

        # Back or close button
        if show_back:
            buttons.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data=back_to)
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text="❌ Закрыть", callback_data="plugin:close")
            ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def plugins_marketplace(
        available_plugins: List[Dict],
        enabled_names: List[str]
    ) -> InlineKeyboardMarkup:
        """
        Marketplace view with available plugins to enable.

        Args:
            available_plugins: List of all available plugins from marketplace
            enabled_names: List of currently enabled plugin names
        """
        buttons = []

        for plugin in available_plugins[:12]:  # Max 12 in marketplace
            name = plugin.get("name", "unknown")
            is_enabled = name in enabled_names

            # Show enable button only for disabled plugins
            if is_enabled:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"✅ {name}",
                        callback_data=f"plugin:info:{name[:20]}"
                    )
                ])
            else:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"➕ {name}",
                        callback_data=f"plugin:enable:{name[:20]}"
                    ),
                    InlineKeyboardButton(
                        text="ℹ️",
                        callback_data=f"plugin:info:{name[:20]}"
                    )
                ])

        # Back button
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="plugin:list")
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def plugin_confirm_action(name: str, action: str) -> InlineKeyboardMarkup:
        """Confirmation for plugin enable/disable"""
        if action == "enable":
            confirm_text = "✅ Да, включить"
            callback = f"plugin:enable_confirm:{name[:20]}"
        else:
            confirm_text = "❌ Да, отключить"
            callback = f"plugin:disable_confirm:{name[:20]}"

        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=confirm_text, callback_data=callback),
                InlineKeyboardButton(text="⬅️ Отмена", callback_data="plugin:list")
            ]
        ])

    # ============== AskUserQuestion Keyboards ==============

    # ============== Account Settings Keyboards ==============

    @staticmethod
    def account_menu(
        current_mode: str = "zai_api",
        has_credentials: bool = False,
        subscription_type: str = None,
        current_model: str = None,
        show_back: bool = False,
        back_to: str = "menu:settings"
    ) -> InlineKeyboardMarkup:
        """
        Account settings menu keyboard.

        Args:
            current_mode: Current auth mode ("zai_api" or "claude_account")
            has_credentials: Whether credentials file exists
            subscription_type: Subscription type from credentials
            current_model: Currently selected model (e.g., "claude-sonnet-4-5")
            show_back: Show back button instead of close button
            back_to: Callback data for back button
        """
        buttons = []

        # z.ai API button
        zai_emoji = "✅" if current_mode == "zai_api" else "🌐"
        buttons.append([
            InlineKeyboardButton(
                text=f"{zai_emoji} z.ai API",
                callback_data="account:mode:zai_api"
            )
        ])

        # Claude Account button
        if current_mode == "claude_account":
            claude_emoji = "✅"
            sub_info = f" ({subscription_type})" if subscription_type else ""
        else:
            claude_emoji = "☁️" if has_credentials else "🔓"
            sub_info = ""

        buttons.append([
            InlineKeyboardButton(
                text=f"{claude_emoji} Claude Account{sub_info}",
                callback_data="account:mode:claude_account"
            )
        ])

        # Local Model button
        local_emoji = "✅" if current_mode == "local_model" else "🖥️"
        buttons.append([
            InlineKeyboardButton(
                text=f"{local_emoji} Локальная модель",
                callback_data="account:mode:local_model"
            )
        ])

        # Model selection button - only for non-Claude modes
        # (Claude mode has its own submenu with model selection)
        if current_mode != "claude_account":
            model_text = "🤖 Модель"
            if current_model:
                # Use a simple formatting for model name
                model_name = current_model.replace("-", " ").replace("_", " ").title()
                # Keep short for display
                if len(model_name) > 20:
                    model_name = model_name[:17] + "..."
                model_text = f"🤖 Модель: {model_name}"

            buttons.append([
                InlineKeyboardButton(
                    text=model_text,
                    callback_data="account:select_model"
                )
            ])

        # Back or close button
        if show_back:
            buttons.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data=back_to)
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text="❌ Закрыть", callback_data="account:close")
            ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def account_auth_options() -> InlineKeyboardMarkup:
        """Keyboard with options for Claude Account authorization"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔐 Войти через браузер",
                    callback_data="account:login"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📤 Загрузить credentials файл",
                    callback_data="account:upload"
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="account:menu"
                )
            ]
        ])

    @staticmethod
    def claude_account_submenu(
        has_credentials: bool = False,
        subscription_type: str = None,
        current_model: str = None
    ) -> InlineKeyboardMarkup:
        """
        Submenu for Claude Account with management options.

        Args:
            has_credentials: Whether credentials file exists
            subscription_type: Subscription type from credentials
            current_model: Currently selected model
        """
        buttons = []

        # Model selection button
        model_text = "🤖 Модель"
        if current_model:
            model_name = current_model.replace("-", " ").replace("_", " ").title()
            if len(model_name) > 20:
                model_name = model_name[:17] + "..."
            model_text = f"🤖 Модель: {model_name}"

        buttons.append([
            InlineKeyboardButton(
                text=model_text,
                callback_data="account:select_model"
            )
        ])

        # Status button with subscription info
        status_text = f"ℹ️ Статус ({subscription_type})" if subscription_type else "ℹ️ Статус авторизации"
        buttons.append([
            InlineKeyboardButton(
                text=status_text,
                callback_data="account:status"
            )
        ])

        # Delete account button (only if credentials exist)
        if has_credentials:
            buttons.append([
                InlineKeyboardButton(
                    text="🗑️ Удалить аккаунт Claude",
                    callback_data="account:delete_account"
                )
            ])

        # Back button
        buttons.append([
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="account:menu"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def account_upload_credentials() -> InlineKeyboardMarkup:
        """Keyboard shown when waiting for credentials file upload"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="account:cancel_upload"
                )
            ]
        ])

    @staticmethod
    def account_cancel_login() -> InlineKeyboardMarkup:
        """Keyboard shown during OAuth login flow"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="account:cancel_login"
                )
            ]
        ])

    @staticmethod
    def model_select(
        models: list = None,
        auth_mode: str = "zai_api",
        current_model: str = None
    ) -> InlineKeyboardMarkup:
        """
        Dynamic model selection keyboard based on auth mode.

        Args:
            models: List of model dicts with id, name, is_selected (from AccountService.get_available_models())
            auth_mode: Current auth mode
            current_model: Currently selected model
        """
        buttons = []

        if models:
            # Dynamic buttons from provided models list
            for m in models:
                emoji = "✅" if m.get("is_selected") else "🔘"
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{emoji} {m['name']}",
                        callback_data=f"account:model:{m['id']}"
                    )
                ])
        else:
            # Fallback to Claude models if no list provided (backwards compatibility)
            from application.services.account_service import ClaudeModel
            for model_enum in [ClaudeModel.OPUS, ClaudeModel.SONNET, ClaudeModel.HAIKU]:
                is_selected = current_model in (model_enum, model_enum.value, str(model_enum))
                emoji = "✅" if is_selected else "🔘"
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{emoji} {ClaudeModel.get_display_name(model_enum)}",
                        callback_data=f"account:model:{model_enum.value}"
                    )
                ])

        # Default (auto) button
        default_emoji = "✅" if not current_model else "🔄"
        buttons.append([
            InlineKeyboardButton(
                text=f"{default_emoji} По умолчанию (авто)",
                callback_data="account:model:default"
            )
        ])

        # For local model mode, add "Change settings" button
        if auth_mode == "local_model":
            buttons.append([
                InlineKeyboardButton(
                    text="⚙️ Изменить настройки",
                    callback_data="account:local_setup"
                )
            ])

        # Back button
        buttons.append([
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="account:menu"
            )
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def account_confirm_mode_switch(mode: str) -> InlineKeyboardMarkup:
        """Confirmation keyboard for mode switch"""
        if mode == "claude_account":
            text = "✅ Да, переключить на Claude Account"
        elif mode == "local_model":
            text = "✅ Да, настроить локальную модель"
        else:
            text = "✅ Да, переключить на z.ai API"

        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"account:confirm:{mode}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="account:menu"
                )
            ]
        ])

    @staticmethod
    def cancel_only(back_to: str = "account:menu") -> InlineKeyboardMarkup:
        """Simple cancel button keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=back_to)]
        ])

    @staticmethod
    def local_model_skip_name(default_name: str) -> InlineKeyboardMarkup:
        """Keyboard for skipping display name input"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Использовать '{default_name}'",
                    callback_data=f"account:local_use_default_name"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="account:menu")]
        ])

    @staticmethod
    def question_options(
        questions: List[Dict],
        question_id: str
    ) -> InlineKeyboardMarkup:
        """
        Build keyboard for AskUserQuestion response from Claude.

        Args:
            questions: List of question dicts with question, header, options
            question_id: Unique ID for callback matching (e.g., "q_1234567890")

        Returns:
            InlineKeyboardMarkup with option buttons and "Other" option
        """
        buttons = []

        # Support only first question for now (Claude usually sends one at a time)
        for q_idx, question in enumerate(questions[:1]):
            options = question.get("options", [])

            for opt_idx, opt in enumerate(options[:4]):  # Max 4 options
                label = opt.get("label", f"Вариант {opt_idx + 1}")
                # Format: question:{question_id}:{question_idx}:{option_idx}
                # Keep callback data under 64 bytes
                callback = f"q:{question_id}:{q_idx}:{opt_idx}"
                buttons.append([
                    InlineKeyboardButton(text=label, callback_data=callback)
                ])

        # Add "Other" option for custom text input
        buttons.append([
            InlineKeyboardButton(
                text="💬 Другой ответ",
                callback_data=f"q:{question_id}:other"
            )
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
    def is_claude_clarify(callback_data: str) -> bool:
        return callback_data.startswith("claude:clarify:")

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
        - action: approve/reject/answer/other/cancel/continue/clarify
        - user_id: User ID
        - request_id: Request ID (for approve/reject/answer/clarify)
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

    # ============== Account Callback Helpers ==============

    @staticmethod
    def is_account_callback(callback_data: str) -> bool:
        """Check if this is an account settings callback"""
        return callback_data.startswith("account:")

    @staticmethod
    def parse_account_callback(callback_data: str) -> Dict[str, str]:
        """Parse account callback data"""
        parts = callback_data.split(":")
        result = {"action": parts[1] if len(parts) > 1 else ""}
        if len(parts) > 2:
            result["value"] = ":".join(parts[2:])
        return result
