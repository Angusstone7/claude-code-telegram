"""
Account Handlers

Handles /account command and account settings callbacks.
Manages switching between z.ai API and Claude Account authorization modes.
"""

import logging
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from application.services.account_service import (
    AccountService,
    AuthMode,
    CredentialsInfo,
    CREDENTIALS_PATH,
    CLAUDE_PROXY,
)
from presentation.keyboards.keyboards import Keyboards, CallbackData

logger = logging.getLogger(__name__)


class AccountStates(StatesGroup):
    """FSM states for account operations"""
    waiting_credentials_file = State()


class AccountHandlers:
    """
    Handlers for account settings.

    Provides:
    - /account command - show account settings menu
    - Mode switching callbacks
    - Credentials file upload handling
    """

    def __init__(self, account_service: AccountService):
        self.account_service = account_service
        self.router = Router(name="account")
        self._register_handlers()

    def _register_handlers(self):
        """Register all handlers"""
        # Command handler
        self.router.message.register(
            self.handle_account_command,
            Command("account")
        )

        # Callback handlers
        self.router.callback_query.register(
            self.handle_account_callback,
            F.data.startswith("account:")
        )

        # Credentials file upload handler
        self.router.message.register(
            self.handle_credentials_upload,
            AccountStates.waiting_credentials_file,
            F.document
        )

        # Cancel text during upload state
        self.router.message.register(
            self.handle_cancel_upload_text,
            AccountStates.waiting_credentials_file,
            F.text
        )

    async def handle_account_command(self, message: Message, state: FSMContext):
        """Handle /account command - show settings menu"""
        user_id = message.from_user.id

        # Get current settings
        settings = await self.account_service.get_settings(user_id)
        creds_info = self.account_service.get_credentials_info()

        # Build info message
        current_mode_name = (
            "z.ai API" if settings.auth_mode == AuthMode.ZAI_API
            else "Claude Account"
        )

        text = (
            f"🔧 <b>Настройки аккаунта</b>\n\n"
            f"Текущий режим: <b>{current_mode_name}</b>\n\n"
        )

        if settings.auth_mode == AuthMode.CLAUDE_ACCOUNT:
            if creds_info.exists:
                sub = creds_info.subscription_type or "unknown"
                tier = creds_info.rate_limit_tier or "default"
                text += f"📊 Подписка: {sub}\n"
                text += f"⚡ Rate limit: {tier}\n"
                if creds_info.expires_at:
                    text += f"⏰ Истекает: {creds_info.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
            else:
                text += "⚠️ Credentials файл не найден\n"

        text += "\nВыберите режим авторизации:"

        # Send menu
        await message.answer(
            text,
            reply_markup=Keyboards.account_menu(
                current_mode=settings.auth_mode.value,
                has_credentials=creds_info.exists,
                subscription_type=creds_info.subscription_type,
            )
        )

    async def handle_account_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle account settings callbacks"""
        user_id = callback.from_user.id
        data = CallbackData.parse_account_callback(callback.data)
        action = data.get("action", "")

        logger.debug(f"[{user_id}] Account callback: {action}")

        if action == "mode":
            # Mode selection
            mode_str = data.get("value", "")
            await self._handle_mode_selection(callback, state, mode_str)

        elif action == "confirm":
            # Confirm mode switch
            mode_str = data.get("value", "")
            await self._handle_mode_confirm(callback, state, mode_str)

        elif action == "status":
            # Show detailed status
            await self._handle_status(callback)

        elif action == "menu":
            # Return to menu
            await self._show_menu(callback, state)

        elif action == "close":
            # Close menu
            await callback.message.delete()
            await callback.answer()

        elif action == "cancel_upload":
            # Cancel credentials upload
            await state.clear()
            await self._show_menu(callback, state)
            await callback.answer("Загрузка отменена")

        else:
            await callback.answer(f"Неизвестное действие: {action}")

    async def _handle_mode_selection(
        self,
        callback: CallbackQuery,
        state: FSMContext,
        mode_str: str
    ):
        """Handle mode selection button"""
        user_id = callback.from_user.id

        try:
            mode = AuthMode(mode_str)
        except ValueError:
            await callback.answer(f"Неизвестный режим: {mode_str}")
            return

        settings = await self.account_service.get_settings(user_id)

        # If already in this mode, do nothing
        if settings.auth_mode == mode:
            await callback.answer("Этот режим уже выбран")
            return

        # For Claude Account, check if credentials exist
        if mode == AuthMode.CLAUDE_ACCOUNT:
            creds_info = self.account_service.get_credentials_info()
            if not creds_info.exists:
                # Need to upload credentials file
                await state.set_state(AccountStates.waiting_credentials_file)

                text = (
                    "📤 <b>Загрузите credentials файл</b>\n\n"
                    "Для использования Claude Account необходимо загрузить "
                    "файл <code>.credentials.json</code>.\n\n"
                    "<b>Как получить файл:</b>\n"
                    "1. На компьютере с браузером выполните <code>claude /login</code>\n"
                    "2. Авторизуйтесь в claude.ai\n"
                    "3. Найдите файл <code>~/.claude/.credentials.json</code>\n"
                    "4. Отправьте этот файл сюда\n\n"
                    f"<i>Путь на Windows: C:\\Users\\[user]\\.claude\\.credentials.json</i>"
                )

                await callback.message.edit_text(
                    text,
                    reply_markup=Keyboards.account_upload_credentials()
                )
                await callback.answer()
                return

        # Show confirmation
        if mode == AuthMode.CLAUDE_ACCOUNT:
            creds_info = self.account_service.get_credentials_info()
            sub = creds_info.subscription_type or "unknown"
            text = (
                f"☁️ <b>Переключить на Claude Account?</b>\n\n"
                f"Подписка: {sub}\n"
                f"Прокси: {CLAUDE_PROXY[:30]}...\n\n"
                f"Все запросы будут идти через вашу подписку Claude."
            )
        else:
            text = (
                "🌐 <b>Переключить на z.ai API?</b>\n\n"
                "Запросы будут идти через z.ai API с оплатой по токенам."
            )

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.account_confirm_mode_switch(mode.value)
        )
        await callback.answer()

    async def _handle_mode_confirm(
        self,
        callback: CallbackQuery,
        state: FSMContext,
        mode_str: str
    ):
        """Handle confirmed mode switch"""
        user_id = callback.from_user.id

        try:
            mode = AuthMode(mode_str)
        except ValueError:
            await callback.answer(f"Неизвестный режим: {mode_str}")
            return

        # Switch mode
        await self.account_service.set_auth_mode(user_id, mode)

        mode_name = "z.ai API" if mode == AuthMode.ZAI_API else "Claude Account"
        await callback.answer(f"✅ Режим: {mode_name}")

        # Show updated menu
        await self._show_menu(callback, state)

    async def _handle_status(self, callback: CallbackQuery):
        """Show detailed auth status"""
        user_id = callback.from_user.id
        settings = await self.account_service.get_settings(user_id)
        creds_info = self.account_service.get_credentials_info()

        text = "📊 <b>Статус авторизации</b>\n\n"

        # Current mode
        mode_name = "z.ai API" if settings.auth_mode == AuthMode.ZAI_API else "Claude Account"
        text += f"<b>Текущий режим:</b> {mode_name}\n\n"

        # z.ai API info
        import os
        zai_base = os.environ.get("ANTHROPIC_BASE_URL", "не задан")
        zai_token = "✅ задан" if os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY") else "❌ не задан"
        text += f"<b>z.ai API:</b>\n"
        text += f"  Base URL: <code>{zai_base[:40]}...</code>\n" if len(zai_base) > 40 else f"  Base URL: <code>{zai_base}</code>\n"
        text += f"  Token: {zai_token}\n\n"

        # Claude Account info
        text += f"<b>Claude Account:</b>\n"
        if creds_info.exists:
            text += f"  Статус: ✅ credentials найден\n"
            text += f"  Подписка: {creds_info.subscription_type or 'unknown'}\n"
            text += f"  Rate limit: {creds_info.rate_limit_tier or 'default'}\n"
            if creds_info.expires_at:
                text += f"  Истекает: {creds_info.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
            if creds_info.scopes:
                text += f"  Scopes: {', '.join(creds_info.scopes[:3])}\n"
        else:
            text += f"  Статус: ❌ credentials не найден\n"
            text += f"  Путь: <code>{CREDENTIALS_PATH}</code>\n"

        text += f"\n<b>Прокси:</b> <code>{CLAUDE_PROXY[:40]}...</code>"

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.back("account:menu")
        )
        await callback.answer()

    async def _show_menu(self, callback: CallbackQuery, state: FSMContext):
        """Show account menu"""
        await state.clear()

        user_id = callback.from_user.id
        settings = await self.account_service.get_settings(user_id)
        creds_info = self.account_service.get_credentials_info()

        current_mode_name = (
            "z.ai API" if settings.auth_mode == AuthMode.ZAI_API
            else "Claude Account"
        )

        text = (
            f"🔧 <b>Настройки аккаунта</b>\n\n"
            f"Текущий режим: <b>{current_mode_name}</b>\n\n"
            f"Выберите режим авторизации:"
        )

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.account_menu(
                current_mode=settings.auth_mode.value,
                has_credentials=creds_info.exists,
                subscription_type=creds_info.subscription_type,
            )
        )

    async def handle_credentials_upload(self, message: Message, state: FSMContext):
        """Handle credentials file upload"""
        user_id = message.from_user.id

        # Download file
        document = message.document

        # Check filename
        if document.file_name and not document.file_name.endswith(".json"):
            await message.answer(
                "❌ Файл должен быть .json\n"
                "Ожидается файл <code>.credentials.json</code>",
                reply_markup=Keyboards.account_upload_credentials()
            )
            return

        # Check file size (credentials should be small)
        if document.file_size > 50 * 1024:  # 50 KB max
            await message.answer(
                "❌ Файл слишком большой (макс 50 KB)\n"
                "Убедитесь что это правильный файл credentials",
                reply_markup=Keyboards.account_upload_credentials()
            )
            return

        try:
            # Download file content
            file = await message.bot.get_file(document.file_id)
            file_content = await message.bot.download_file(file.file_path)
            credentials_json = file_content.read().decode("utf-8")

            # Save credentials
            success, msg = self.account_service.save_credentials(credentials_json)

            if success:
                # Switch to Claude Account mode
                await self.account_service.set_auth_mode(user_id, AuthMode.CLAUDE_ACCOUNT)

                creds_info = self.account_service.get_credentials_info()

                await message.answer(
                    f"✅ <b>Авторизация успешна!</b>\n\n"
                    f"Режим: Claude Account\n"
                    f"Подписка: {creds_info.subscription_type or 'unknown'}\n"
                    f"Rate limit: {creds_info.rate_limit_tier or 'default'}\n\n"
                    f"Теперь все запросы идут через вашу подписку Claude.",
                    reply_markup=Keyboards.account_menu(
                        current_mode=AuthMode.CLAUDE_ACCOUNT.value,
                        has_credentials=True,
                        subscription_type=creds_info.subscription_type,
                    )
                )
                await state.clear()
                logger.info(f"[{user_id}] Credentials uploaded, switched to Claude Account")

            else:
                await message.answer(
                    f"❌ {msg}\n\n"
                    "Попробуйте ещё раз или отмените.",
                    reply_markup=Keyboards.account_upload_credentials()
                )

        except Exception as e:
            logger.error(f"[{user_id}] Error uploading credentials: {e}")
            await message.answer(
                f"❌ Ошибка: {e}\n\n"
                "Попробуйте ещё раз или отмените.",
                reply_markup=Keyboards.account_upload_credentials()
            )

    async def handle_cancel_upload_text(self, message: Message, state: FSMContext):
        """Handle text input during credentials upload state"""
        if message.text and message.text.lower() in ("отмена", "cancel", "/cancel"):
            await state.clear()
            await message.answer("Загрузка отменена. Используйте /account для настроек.")
        else:
            await message.answer(
                "Ожидается файл <code>.credentials.json</code>\n"
                "Отправьте файл или нажмите Отмена.",
                reply_markup=Keyboards.account_upload_credentials()
            )


def register_account_handlers(dp, account_handlers: AccountHandlers):
    """Register account handlers with dispatcher"""
    dp.include_router(account_handlers.router)
