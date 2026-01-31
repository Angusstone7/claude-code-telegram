"""
Variable Callback Handlers

Handles context and global variables management callbacks:
- Context variables (per-context)
- Global variables (user-wide, inherited by all contexts)
"""

import logging
from typing import Optional
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from presentation.handlers.callbacks.base import BaseCallbackHandler
from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)


class VariableCallbackHandler(BaseCallbackHandler):
    """Handles variable management callbacks (context + global)."""

    # State storage for global variable input flow
    _gvar_input_state: dict = {}  # {user_id: {"step": "name"|"value"|"desc", "name": str, "value": str}}

    async def _get_var_context(self, callback: CallbackQuery):
        """Helper to get project and context for variable operations."""
        user_id = callback.from_user.id

        if not self.project_service or not self.context_service:
            await callback.answer("⚠️ Сервисы недоступны")
            return None, None

        from domain.value_objects.user_id import UserId
        uid = UserId.from_int(user_id)

        project = await self.project_service.get_current(uid)
        if not project:
            await callback.answer("❌ Нет активного проекта")
            return None, None

        context = await self.context_service.get_current(project.id)
        if not context:
            await callback.answer("❌ Нет активного контекста")
            return None, None

        return project, context

    # ============== Context Variables ==============

    async def handle_vars_list(self, callback: CallbackQuery) -> None:
        """Show variables list menu."""
        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            variables = await self.context_service.get_variables(context.id)

            if variables:
                lines = [f"📋 Переменные контекста\n"]
                lines.append(f"📂 {project.name} / {context.name}\n")
                for name in sorted(variables.keys()):
                    var = variables[name]
                    # Mask value for security
                    display_val = var.value[:8] + "***" if len(var.value) > 8 else var.value
                    lines.append(f"• {name} = {display_val}")
                    if var.description:
                        lines.append(f"  ↳ {var.description[:50]}")
                text = "\n".join(lines)
            else:
                text = (
                    f"📋 Переменные контекста\n\n"
                    f"📂 {project.name} / {context.name}\n\n"
                    f"Переменных пока нет.\n"
                    f"Нажмите ➕ Добавить для создания."
                )

            keyboard = Keyboards.variables_menu(
                variables, project.name, context.name,
                show_back=True, back_to="menu:context"
            )
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing variables list: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_add(self, callback: CallbackQuery) -> None:
        """Start variable add flow - ask for name."""
        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            # Set state in message handlers to expect variable name
            user_id = callback.from_user.id
            if hasattr(self.message_handlers, 'start_var_input'):
                self.message_handlers.start_var_input(user_id, callback.message)

            text = (
                "📝 Добавление переменной\n\n"
                "Введите имя переменной:\n"
                "(например: GITLAB_TOKEN, API_KEY)"
            )
            keyboard = Keyboards.variable_cancel()
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer("Введите имя")

        except Exception as e:
            logger.error(f"Error starting var add: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_show(self, callback: CallbackQuery) -> None:
        """Show full variable info."""
        var_name = callback.data.split(":")[-1]

        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            var = await self.context_service.get_variable(context.id, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            text = (
                f"📋 Переменная: {var.name}\n\n"
                f"📂 {project.name} / {context.name}\n\n"
                f"Значение:\n{var.value}\n"
            )
            if var.description:
                text += f"\nОписание:\n{var.description}"

            # Back button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"var:e:{var_name[:20]}"),
                    InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"var:d:{var_name[:20]}")
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="var:list")]
            ])
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_edit(self, callback: CallbackQuery) -> None:
        """Start variable edit flow."""
        var_name = callback.data.split(":")[-1]

        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            var = await self.context_service.get_variable(context.id, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            # Set state in message handlers to expect new value
            user_id = callback.from_user.id
            if hasattr(self.message_handlers, 'start_var_edit'):
                self.message_handlers.start_var_edit(user_id, var_name, callback.message)

            text = (
                f"✏️ Редактирование: {var.name}\n\n"
                f"Текущее значение:\n{var.value}\n\n"
                f"Введите новое значение:"
            )
            keyboard = Keyboards.variable_cancel()
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer("Введите новое значение")

        except Exception as e:
            logger.error(f"Error starting var edit: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_delete(self, callback: CallbackQuery) -> None:
        """Show delete confirmation."""
        var_name = callback.data.split(":")[-1]

        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            var = await self.context_service.get_variable(context.id, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            text = (
                f"🗑️ Удалить переменную?\n\n"
                f"📋 {var.name}\n"
                f"📂 {project.name} / {context.name}\n\n"
                f"⚠️ Это действие нельзя отменить!"
            )
            keyboard = Keyboards.variable_delete_confirm(var_name)
            await callback.message.edit_text(text, parse_mode=None, reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing delete confirm: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_delete_confirm(self, callback: CallbackQuery) -> None:
        """Confirm and delete variable."""
        var_name = callback.data.split(":")[-1]

        try:
            project, context = await self._get_var_context(callback)
            if not project or not context:
                return

            deleted = await self.context_service.delete_variable(context.id, var_name)

            if deleted:
                await callback.answer(f"✅ {var_name} удалена")
                # Show updated list
                await self.handle_vars_list(callback)
            else:
                await callback.answer("❌ Переменная не найдена")

        except Exception as e:
            logger.error(f"Error deleting variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    async def handle_vars_close(self, callback: CallbackQuery) -> None:
        """Close variables menu."""
        try:
            await callback.message.delete()
            await callback.answer()
        except Exception as e:
            logger.debug(f"Error closing vars menu: {e}")
            await callback.answer()

    async def handle_vars_cancel(self, callback: CallbackQuery) -> None:
        """Cancel variable input and return to list."""
        user_id = callback.from_user.id

        # Clear input state
        if hasattr(self.message_handlers, 'cancel_var_input'):
            self.message_handlers.cancel_var_input(user_id)

        await callback.answer("Отменено")
        # Show list again
        await self.handle_vars_list(callback)

    async def handle_vars_skip_desc(self, callback: CallbackQuery) -> None:
        """Skip description input and save variable."""
        user_id = callback.from_user.id

        try:
            # Get pending variable data and save without description
            if hasattr(self.message_handlers, 'save_variable_skip_desc'):
                await self.message_handlers.save_variable_skip_desc(user_id, callback.message)
                await callback.answer("✅ Переменная сохранена")
                # Show updated list
                await self.handle_vars_list(callback)
            else:
                await callback.answer("❌ Нет данных для сохранения")

        except Exception as e:
            logger.error(f"Error saving variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}")

    # ============== Global Variables ==============

    async def handle_gvar_list(self, callback: CallbackQuery) -> None:
        """Show global variables list menu."""
        try:
            from domain.value_objects.user_id import UserId

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            variables = await self.context_service.get_global_variables(uid)

            if variables:
                lines = ["🌍 <b>Глобальные переменные</b>\n"]
                lines.append("<i>Наследуются всеми проектами</i>\n")
                for name in sorted(variables.keys()):
                    var =variables[name]
                    display_val = var.value[:8] + "***" if len(var.value) > 8 else var.value
                    lines.append(f"• <code>{name}</code> = {display_val}")
                    if var.description:
                        lines.append(f"  ↳ <i>{var.description[:50]}</i>")
                text = "\n".join(lines)
            else:
                text = (
                    "🌍 <b>Глобальные переменные</b>\n\n"
                    "<i>Наследуются всеми проектами</i>\n\n"
                    "Переменных пока нет.\n"
                    "Нажмите ➕ Добавить для создания."
                )

            keyboard = Keyboards.global_variables_menu(variables, show_back=True, back_to="menu:settings")
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing global variables list: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_add(self, callback: CallbackQuery) -> None:
        """Start global variable add flow."""
        try:
            user_id = callback.from_user.id

            # Set state to expect name input
            self._gvar_input_state[user_id] = {"step": "name", "name": None, "value": None}

            text = (
                "🌍 <b>Добавление глобальной переменной</b>\n\n"
                "Введите имя переменной:\n"
                "<i>(например: GITLAB_TOKEN, API_KEY)</i>"
            )
            keyboard = Keyboards.global_variable_cancel()
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer("Введите имя")

        except Exception as e:
            logger.error(f"Error starting gvar add: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_show(self, callback: CallbackQuery) -> None:
        """Show full global variable info."""
        var_name = callback.data.split(":")[-1]

        try:
            from domain.value_objects.user_id import UserId

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            var = await self.context_service.get_global_variable(uid, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            text = (
                f"🌍 <b>Глобальная переменная</b>\n\n"
                f"📋 <b>Имя:</b> <code>{var.name}</code>\n"
                f"📝 <b>Значение:</b> <code>{var.value}</code>\n"
            )
            if var.description:
                text += f"💬 <b>Описание:</b> {var.description}\n"

            text += "\n<i>Наследуется всеми проектами и контекстами</i>"

            buttons = [
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"gvar:e:{var_name[:20]}"),
                    InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"gvar:d:{var_name[:20]}")
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="gvar:list")]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing global variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_edit(self, callback: CallbackQuery) -> None:
        """Start global variable edit flow."""
        var_name = callback.data.split(":")[-1]

        try:
            from domain.value_objects.user_id import UserId

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            var = await self.context_service.get_global_variable(uid, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            # Set state to expect value input (editing existing var)
            self._gvar_input_state[user_id] = {
                "step": "value",
                "name": var_name,
                "value": None,
                "editing": True,
                "old_desc": var.description
            }

            text = (
                f"✏️ <b>Редактирование: {var_name}</b>\n\n"
                f"Текущее значение: <code>{var.value}</code>\n\n"
                f"Введите новое значение:"
            )
            keyboard = Keyboards.global_variable_cancel()
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer("Введите новое значение")

        except Exception as e:
            logger.error(f"Error starting gvar edit: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_delete(self, callback: CallbackQuery) -> None:
        """Show delete confirmation for global variable."""
        var_name = callback.data.split(":")[-1]

        try:
            from domain.value_objects.user_id import UserId

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            var = await self.context_service.get_global_variable(uid, var_name)
            if not var:
                await callback.answer("❌ Переменная не найдена")
                return

            text = (
                f"🗑️ <b>Удалить глобальную переменную?</b>\n\n"
                f"📋 <code>{var.name}</code>\n\n"
                f"⚠️ Это действие нельзя отменить!\n"
                f"Переменная перестанет наследоваться всеми проектами."
            )
            keyboard = Keyboards.global_variable_delete_confirm(var_name)
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()

        except Exception as e:
            logger.error(f"Error showing delete confirm: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_delete_confirm(self, callback: CallbackQuery) -> None:
        """Confirm and delete global variable."""
        var_name = callback.data.split(":")[-1]

        try:
            from domain.value_objects.user_id import UserId

            user_id = callback.from_user.id
            uid = UserId.from_int(user_id)

            deleted = await self.context_service.delete_global_variable(uid, var_name)

            if deleted:
                await callback.answer(f"✅ {var_name} удалена")
                await self.handle_gvar_list(callback)
            else:
                await callback.answer("❌ Переменная не найдена")

        except Exception as e:
            logger.error(f"Error deleting global variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    async def handle_gvar_cancel(self, callback: CallbackQuery) -> None:
        """Cancel global variable input and return to list."""
        user_id = callback.from_user.id

        # Clear input state
        if user_id in self._gvar_input_state:
            del self._gvar_input_state[user_id]

        await callback.answer("Отменено")
        await self.handle_gvar_list(callback)

    async def handle_gvar_skip_desc(self, callback: CallbackQuery) -> None:
        """Skip description input and save global variable."""
        user_id = callback.from_user.id

        try:
            from domain.value_objects.user_id import UserId

            state = self._gvar_input_state.get(user_id)
            if not state or not state.get("name") or not state.get("value"):
                await callback.answer("❌ Нет данных для сохранения")
                return

            uid = UserId.from_int(user_id)

            await self.context_service.set_global_variable(
                uid,
                state["name"],
                state["value"],
                ""  # No description
            )

            # Clear state
            del self._gvar_input_state[user_id]

            await callback.answer(f"✅ {state['name']} сохранена")
            await self.handle_gvar_list(callback)

        except Exception as e:
            logger.error(f"Error saving global variable: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    # ============== Global Variable Input Processing ==============

    def is_gvar_input_active(self, user_id: int) -> bool:
        """Check if user is in global variable input flow."""
        return user_id in self._gvar_input_state

    def get_gvar_input_step(self, user_id: int) -> Optional[str]:
        """Get current input step for user."""
        state = self._gvar_input_state.get(user_id)
        return state.get("step") if state else None

    async def process_gvar_input(self, user_id: int, text: str, message) -> bool:
        """Process text input for global variable flow. Returns True if handled."""
        state = self._gvar_input_state.get(user_id)
        if not state:
            return False

        from domain.value_objects.user_id import UserId

        step = state.get("step")
        uid = UserId.from_int(user_id)

        if step == "name":
            # Validate name
            var_name = text.strip().upper()
            if not var_name or not var_name.replace("_", "").isalnum():
                await message.answer(
                    "❌ Недопустимое имя переменной.\n"
                    "Используйте только буквы, цифры и подчёркивание.",
                    reply_markup=Keyboards.global_variable_cancel()
                )
                return True

            state["name"] = var_name
            state["step"] = "value"

            await message.answer(
                f"✅ Имя: <code>{var_name}</code>\n\n"
                f"Введите значение переменной:",
                parse_mode="HTML",
                reply_markup=Keyboards.global_variable_cancel()
            )
            return True

        elif step == "value":
            var_value = text.strip()
            if not var_value:
                await message.answer(
                    "❌ Значение не может быть пустым.",
                    reply_markup=Keyboards.global_variable_cancel()
                )
                return True

            state["value"] = var_value

            # If editing, use old description
            if state.get("editing"):
                old_desc = state.get("old_desc", "")
                await self.context_service.set_global_variable(
                    uid, state["name"], var_value, old_desc
                )
                del self._gvar_input_state[user_id]
                await message.answer(f"✅ Переменная {state['name']} обновлена!")

                # Show list
                variables = await self.context_service.get_global_variables(uid)
                await message.answer(
                    "🌍 <b>Глобальные переменные</b>",
                    parse_mode="HTML",
                    reply_markup=Keyboards.global_variables_menu(variables, show_back=True, back_to="menu:settings")
                )
                return True

            # Move to description step
            state["step"] = "desc"
            await message.answer(
                f"✅ Значение установлено\n\n"
                f"Введите описание (для Claude) или нажмите «Пропустить»:",
                reply_markup=Keyboards.global_variable_skip_description()
            )
            return True

        elif step == "desc":
            var_desc = text.strip()

            await self.context_service.set_global_variable(
                uid, state["name"], state["value"], var_desc
            )

            del self._gvar_input_state[user_id]
            await message.answer(f"✅ Глобальная переменная {state['name']} сохранена!")

            # Show list
            variables = await self.context_service.get_global_variables(uid)
            await message.answer(
                "🌍 <b>Глобальные переменные</b>",
                parse_mode="HTML",
                reply_markup=Keyboards.global_variables_menu(variables, show_back=True, back_to="menu:settings")
            )
            return True

        return False
