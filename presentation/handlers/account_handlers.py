"""
Account Handlers

Handles /account command and account settings callbacks.
Manages switching between z.ai API and Claude Account authorization modes.
Includes OAuth login flow via `claude /login`.
"""

import asyncio
import logging
import os
import re
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
    LocalModelConfig,
    CREDENTIALS_PATH,
    CLAUDE_PROXY,
)
from presentation.keyboards.keyboards import Keyboards, CallbackData

logger = logging.getLogger(__name__)


class OAuthLoginSession:
    """
    Manages OAuth login process via claude CLI.

    Flow:
    1. Start `claude /login` subprocess with proxy env
    2. Read stdout until OAuth URL appears
    3. Return URL for user to click
    4. Wait for user to submit code
    5. Pass code to stdin
    6. Wait for completion
    """

    def __init__(self, user_id: int, proxy_url: str = CLAUDE_PROXY):
        self.user_id = user_id
        self.proxy_url = proxy_url
        self.process: Optional[asyncio.subprocess.Process] = None
        self.oauth_url: Optional[str] = None
        self.status: str = "pending"  # pending, waiting_code, completed, failed
        self._output_lines: list[str] = []

    def _get_env(self) -> dict:
        """Build environment for OAuth login (proxy, no API keys)"""
        env = os.environ.copy()

        # Set proxy for accessing claude.ai
        env["HTTP_PROXY"] = self.proxy_url
        env["HTTPS_PROXY"] = self.proxy_url
        env["http_proxy"] = self.proxy_url
        env["https_proxy"] = self.proxy_url

        # Bypass proxy for local network addresses
        env["NO_PROXY"] = "localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,host.docker.internal,.local"
        env["no_proxy"] = "localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,host.docker.internal,.local"

        # Remove API keys to force OAuth login
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        env.pop("ANTHROPIC_BASE_URL", None)

        return env

    async def start(self) -> Optional[str]:
        """
        Start claude /login and return OAuth URL.

        Returns:
            OAuth URL if found, None if failed
        """
        try:
            self.process = await asyncio.create_subprocess_exec(
                "claude", "/login",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # Merge stderr to stdout
                env=self._get_env(),
            )

            logger.info(f"[{self.user_id}] Started claude /login process (PID: {self.process.pid})")

            # Read output until we find the OAuth URL
            # Typical output: "Browser didn't open? Use the url below..."
            # followed by "https://claude.ai/oauth/authorize?..."
            timeout_seconds = 30

            async def read_until_url():
                while True:
                    line = await self.process.stdout.readline()
                    if not line:
                        break

                    decoded = line.decode('utf-8', errors='ignore').strip()
                    self._output_lines.append(decoded)
                    logger.debug(f"[{self.user_id}] claude /login: {decoded}")

                    # Look for OAuth URL in line
                    url_match = re.search(r'https://claude\.ai/oauth/authorize[^\s]+', decoded)
                    if url_match:
                        return url_match.group(0)

                return None

            try:
                self.oauth_url = await asyncio.wait_for(read_until_url(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning(f"[{self.user_id}] Timeout waiting for OAuth URL")
                await self.cancel()
                return None

            if self.oauth_url:
                self.status = "waiting_code"
                logger.info(f"[{self.user_id}] Got OAuth URL: {self.oauth_url[:50]}...")
                return self.oauth_url
            else:
                self.status = "failed"
                logger.warning(f"[{self.user_id}] No OAuth URL found in output")
                return None

        except FileNotFoundError:
            logger.error(f"[{self.user_id}] claude CLI not found")
            self.status = "failed"
            return None
        except Exception as e:
            logger.error(f"[{self.user_id}] Error starting OAuth login: {e}")
            self.status = "failed"
            return None

    async def submit_code(self, code: str) -> tuple[bool, str]:
        """
        Submit OAuth code to complete login.

        Args:
            code: OAuth code from user

        Returns:
            Tuple of (success, message)
        """
        if not self.process or self.status != "waiting_code":
            return False, "Login session not active"

        try:
            # Send code to stdin
            self.process.stdin.write(f"{code}\n".encode())
            await self.process.stdin.drain()

            logger.info(f"[{self.user_id}] Submitted OAuth code")

            # Read remaining output
            async def read_remaining():
                while True:
                    line = await self.process.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode('utf-8', errors='ignore').strip()
                    self._output_lines.append(decoded)
                    logger.debug(f"[{self.user_id}] claude /login: {decoded}")

            try:
                await asyncio.wait_for(read_remaining(), timeout=30)
            except asyncio.TimeoutError:
                pass

            # Wait for process to complete
            try:
                await asyncio.wait_for(self.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                self.process.terminate()
                await self.process.wait()

            # Check if credentials were saved
            if os.path.exists(CREDENTIALS_PATH):
                self.status = "completed"
                logger.info(f"[{self.user_id}] OAuth login completed, credentials saved")
                return True, "Авторизация успешна!"
            else:
                # Check output for errors
                output = "\n".join(self._output_lines[-5:])
                self.status = "failed"
                logger.warning(f"[{self.user_id}] OAuth login failed, no credentials")
                return False, f"Credentials не сохранены. Вывод:\n{output[:200]}"

        except Exception as e:
            logger.error(f"[{self.user_id}] Error submitting OAuth code: {e}")
            self.status = "failed"
            return False, f"Ошибка: {e}"

    async def cancel(self):
        """Cancel the login process"""
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            except Exception:
                pass

        self.status = "cancelled"


class AccountStates(StatesGroup):
    """FSM states for account operations"""
    waiting_credentials_file = State()
    waiting_oauth_code = State()
    # Local model setup states
    waiting_local_url = State()
    waiting_local_model_name = State()
    waiting_local_display_name = State()


class AccountHandlers:
    """
    Handlers for account settings.

    Provides:
    - /account command - show account settings menu
    - Mode switching callbacks
    - Credentials file upload handling
    - OAuth login via claude /login
    """

    def __init__(
        self,
        account_service: AccountService,
        context_service=None,  # Optional: for session reset on model change
    ):
        self.account_service = account_service
        self.context_service = context_service
        self.message_handlers = None  # Set from main.py for session cache clear
        self.router = Router(name="account")
        # Active OAuth login sessions per user
        self._oauth_sessions: dict[int, OAuthLoginSession] = {}
        self._register_handlers()

    def _register_handlers(self):
        """Register all handlers"""
        # Command handler
        self.router.message.register(
            self.handle_account_command,
            Command("account")
        )
        # Also register /login command as shortcut
        self.router.message.register(
            self.handle_login_command,
            Command("login")
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

        # OAuth code input handler
        self.router.message.register(
            self.handle_oauth_code_input,
            AccountStates.waiting_oauth_code,
            F.text
        )

        # Local model setup handlers
        self.router.message.register(
            self.handle_local_url_input,
            AccountStates.waiting_local_url,
            F.text
        )
        self.router.message.register(
            self.handle_local_model_name_input,
            AccountStates.waiting_local_model_name,
            F.text
        )
        self.router.message.register(
            self.handle_local_display_name_input,
            AccountStates.waiting_local_display_name,
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
                current_model=settings.model,
                show_back=True,
                back_to="menu:main"
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

        elif action == "login":
            # Start OAuth login flow
            await self._handle_login(callback, state)

        elif action == "cancel_login":
            # Cancel OAuth login
            await self._cancel_oauth_login(callback, state)

        elif action == "upload":
            # Show credentials file upload prompt
            await self._show_upload_prompt(callback, state)

        elif action == "select_model":
            # Show model selection menu
            await self._show_model_selection(callback, state)

        elif action == "model":
            # Handle model selection
            model_value = data.get("value", "")
            await self._handle_model_selection(callback, state, model_value)

        elif action == "delete_account":
            # Delete Claude Account credentials
            await self._handle_delete_account(callback, state)

        elif action == "local_setup":
            # Start local model setup
            await self._start_local_model_setup(callback, state)

        elif action == "local_use_default_name":
            # Use model name as display name
            await self._handle_local_use_default_name(callback, state)

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

        # If already in this mode, show submenu for Claude Account
        if settings.auth_mode == mode:
            if mode == AuthMode.CLAUDE_ACCOUNT:
                # Show Claude Account submenu with options
                await self._show_claude_submenu(callback, state)
                return
            else:
                await callback.answer("Этот режим уже выбран")
                return

        # For Claude Account, check if credentials exist
        if mode == AuthMode.CLAUDE_ACCOUNT:
            creds_info = self.account_service.get_credentials_info()
            if not creds_info.exists:
                # No credentials - offer login or upload options
                text = (
                    "🔐 <b>Авторизация Claude Account</b>\n\n"
                    "Для использования Claude Account нужна авторизация.\n\n"
                    "<b>Выберите способ:</b>\n\n"
                    "🔐 <b>Войти через браузер</b>\n"
                    "Вы получите ссылку, авторизуетесь и введёте код\n\n"
                    "📤 <b>Загрузить credentials файл</b>\n"
                    "Если уже есть <code>.credentials.json</code>"
                )

                await callback.message.edit_text(
                    text,
                    reply_markup=Keyboards.account_auth_options()
                )
                await callback.answer()
                return

        # For Local Model, start setup flow directly
        if mode == AuthMode.LOCAL_MODEL:
            await self._start_local_model_setup(callback, state)
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
        success, settings, error_msg = await self.account_service.set_auth_mode(user_id, mode)

        if not success:
            # Failed to switch - show error
            await callback.answer(error_msg, show_alert=True)
            # Show menu with current (unchanged) mode
            await self._show_menu(callback, state)
            return

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
            parse_mode="HTML",
            reply_markup=Keyboards.menu_back_only("account:menu")
        )
        await callback.answer()

    async def _show_menu(self, callback: CallbackQuery, state: FSMContext):
        """Show account menu"""
        await state.clear()

        user_id = callback.from_user.id
        settings = await self.account_service.get_settings(user_id)
        creds_info = self.account_service.get_credentials_info()

        mode_names = {
            AuthMode.ZAI_API: "z.ai API",
            AuthMode.CLAUDE_ACCOUNT: "Claude Account",
            AuthMode.LOCAL_MODEL: "Локальная модель",
        }
        current_mode_name = mode_names.get(settings.auth_mode, "Неизвестно")

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
                current_model=settings.model,
                show_back=True,
                back_to="menu:main"
            ),
            parse_mode="HTML"
        )

    async def _show_claude_submenu(self, callback: CallbackQuery, state: FSMContext):
        """Show Claude Account submenu with options"""
        user_id = callback.from_user.id
        settings = await self.account_service.get_settings(user_id)
        creds_info = self.account_service.get_credentials_info()

        text = "☁️ <b>Claude Account</b>\n\n"

        if creds_info.exists:
            text += f"Статус: ✅ Авторизован\n"
            if creds_info.subscription_type:
                text += f"Подписка: {creds_info.subscription_type}\n"
            if creds_info.rate_limit_tier:
                text += f"Rate limit: {creds_info.rate_limit_tier}\n"
        else:
            text += "Статус: ❌ Не авторизован\n"

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.claude_account_submenu(
                has_credentials=creds_info.exists,
                subscription_type=creds_info.subscription_type,
                current_model=settings.model if settings.auth_mode == AuthMode.CLAUDE_ACCOUNT else None
            ),
            parse_mode="HTML"
        )
        await callback.answer()

    async def _show_upload_prompt(self, callback: CallbackQuery, state: FSMContext):
        """Show credentials file upload prompt"""
        await state.set_state(AccountStates.waiting_credentials_file)

        text = (
            "📤 <b>Загрузите credentials файл</b>\n\n"
            "Отправьте файл <code>.credentials.json</code>.\n\n"
            "<b>Где найти файл:</b>\n"
            "• Linux/Mac: <code>~/.claude/.credentials.json</code>\n"
            "• Windows: <code>C:\\Users\\[user]\\.claude\\.credentials.json</code>\n\n"
            "<i>Файл создаётся после выполнения <code>claude /login</code></i>"
        )

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.account_upload_credentials()
        )
        await callback.answer()

    async def _show_model_selection(self, callback: CallbackQuery, state: FSMContext):
        """Show model selection menu based on current auth mode"""
        user_id = callback.from_user.id

        # Get settings and available models for current auth mode
        settings = await self.account_service.get_settings(user_id)
        models = await self.account_service.get_available_models(user_id)

        # Build title based on auth mode
        titles = {
            AuthMode.CLAUDE_ACCOUNT: ("Claude", "Официальные модели Anthropic"),
            AuthMode.ZAI_API: ("z.ai API", "Модели ZhipuAI"),
            AuthMode.LOCAL_MODEL: ("Локальная модель", "LMStudio / Ollama / LLama"),
        }
        title, subtitle = titles.get(settings.auth_mode, ("Модели", ""))

        text = f"🤖 <b>Выбор модели - {title}</b>\n"
        if subtitle:
            text += f"<i>{subtitle}</i>\n\n"

        # Add model descriptions
        for m in models:
            emoji = "✅" if m.get("is_selected") else "  "
            text += f"{emoji} <b>{m['name']}</b>\n"
            if m.get("desc"):
                text += f"   <i>{m['desc']}</i>\n\n"

        if not models:
            if settings.auth_mode == AuthMode.LOCAL_MODEL:
                text += "\n<i>Локальная модель не настроена. Нажмите '⚙️ Изменить настройки' чтобы добавить.</i>"
            else:
                text += "\n<i>Нет доступных моделей</i>"

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.model_select(
                models=models,
                auth_mode=settings.auth_mode.value,
                current_model=settings.model
            ),
            parse_mode="HTML"
        )
        await callback.answer()

    async def _handle_model_selection(
        self,
        callback: CallbackQuery,
        state: FSMContext,
        model_value: str
    ):
        """Handle model selection with session reset"""
        user_id = callback.from_user.id

        # Get old model before changing
        old_model = await self.account_service.get_model(user_id)

        # Parse model value
        new_model = None if model_value == "default" else model_value

        if model_value == "default":
            await self.account_service.set_model(user_id, None)
            model_name = "По умолчанию (авто)"
        else:
            await self.account_service.set_model(user_id, model_value)
            from application.services.account_service import ClaudeModel
            model_name = ClaudeModel.get_display_name(model_value)

        # Reset session if model changed
        session_reset = False
        if old_model != new_model:
            # Clear in-memory session cache
            if self.message_handlers:
                self.message_handlers.clear_session_cache(user_id)
                session_reset = True

            # Clear project context (start fresh conversation)
            if self.context_service:
                try:
                    current_context = await self.context_service.get_current_context(user_id)
                    if current_context:
                        await self.context_service.start_fresh(current_context.id)
                        logger.info(f"[{user_id}] Session reset on model change: {old_model} -> {new_model}")
                except Exception as e:
                    logger.warning(f"[{user_id}] Failed to clear context on model change: {e}")

        # Return to menu with success message
        await self._show_menu(callback, state)
        msg = f"✅ Модель: {model_name}"
        if session_reset:
            msg += "\n🔄 Сессия сброшена"
        await callback.answer(msg, show_alert=session_reset)

    async def _handle_delete_account(self, callback: CallbackQuery, state: FSMContext):
        """Handle Claude Account deletion (credentials file)"""
        user_id = callback.from_user.id

        try:
            # Delete credentials file
            success, message = self.account_service.delete_credentials()

            if success:
                # If was in Claude Account mode, switch to z.ai API
                settings = await self.account_service.get_settings(user_id)
                if settings.auth_mode == AuthMode.CLAUDE_ACCOUNT:
                    await self.account_service.set_auth_mode(user_id, AuthMode.ZAI_API)

                # Return to menu
                await self._show_menu(callback, state)
                await callback.answer("✅ Аккаунт Claude удалён")
            else:
                await callback.answer(message, show_alert=True)

        except Exception as e:
            logger.error(f"[{user_id}] Error deleting account: {e}", exc_info=True)
            await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

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
                mode_success, _, mode_error = await self.account_service.set_auth_mode(user_id, AuthMode.CLAUDE_ACCOUNT)

                if not mode_success:
                    # This shouldn't happen since we just saved credentials, but handle it
                    settings = await self.account_service.get_settings(user_id)
                    await message.answer(
                        f"⚠️ Credentials сохранены, но не удалось переключить режим:\n{mode_error}",
                        reply_markup=Keyboards.account_menu(
                            current_mode=AuthMode.ZAI_API.value,
                            has_credentials=True,
                            current_model=settings.model,
                            show_back=True,
                            back_to="menu:main"
                        )
                    )
                    await state.clear()
                    return

                creds_info = self.account_service.get_credentials_info()
                settings = await self.account_service.get_settings(user_id)

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
                        current_model=settings.model,
                        show_back=True,
                        back_to="menu:main"
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

    # ============== OAuth Login Handlers ==============

    async def handle_login_command(self, message: Message, state: FSMContext):
        """Handle /login command - start OAuth login flow"""
        user_id = message.from_user.id

        # Check if credentials already exist
        creds_info = self.account_service.get_credentials_info()
        if creds_info.exists:
            sub = creds_info.subscription_type or "unknown"
            await message.answer(
                f"✅ <b>Уже авторизованы!</b>\n\n"
                f"Подписка: {sub}\n"
                f"Rate limit: {creds_info.rate_limit_tier or 'default'}\n\n"
                f"Используйте /account для переключения режима.",
                parse_mode="HTML"
            )
            return

        # Start OAuth login
        await self._start_oauth_login(message, state)

    async def _handle_login(self, callback: CallbackQuery, state: FSMContext):
        """Handle login button callback - start OAuth login"""
        await callback.answer("Запускаю авторизацию...")
        await self._start_oauth_login_callback(callback, state)

    async def _start_oauth_login(self, message: Message, state: FSMContext):
        """Start OAuth login flow (from message)"""
        user_id = message.from_user.id

        # Show loading message
        loading_msg = await message.answer(
            "⏳ <b>Запускаю авторизацию...</b>\n\n"
            "Получаю ссылку для входа...",
            parse_mode="HTML"
        )

        # Create and start OAuth session
        session = OAuthLoginSession(user_id)
        self._oauth_sessions[user_id] = session

        oauth_url = await session.start()

        if oauth_url:
            await state.set_state(AccountStates.waiting_oauth_code)

            await loading_msg.edit_text(
                f"🔐 <b>Авторизация Claude Account</b>\n\n"
                f"1️⃣ Перейдите по ссылке:\n"
                f"<a href=\"{oauth_url}\">Открыть страницу авторизации</a>\n\n"
                f"2️⃣ Войдите в свой аккаунт Claude\n"
                f"3️⃣ Скопируйте код авторизации\n"
                f"4️⃣ Отправьте код сюда\n\n"
                f"<i>Ссылка действительна 5 минут</i>",
                parse_mode="HTML",
                reply_markup=Keyboards.account_cancel_login(),
                disable_web_page_preview=True
            )
        else:
            # Failed to get URL
            output = "\n".join(session._output_lines[-3:]) if session._output_lines else "Нет вывода"
            await loading_msg.edit_text(
                f"❌ <b>Не удалось запустить авторизацию</b>\n\n"
                f"Claude CLI вернул:\n<pre>{output[:200]}</pre>\n\n"
                f"Убедитесь что claude установлен и доступен.",
                parse_mode="HTML",
                reply_markup=Keyboards.menu_back_only("account:menu")
            )
            self._oauth_sessions.pop(user_id, None)

    async def _start_oauth_login_callback(self, callback: CallbackQuery, state: FSMContext):
        """Start OAuth login flow (from callback)"""
        user_id = callback.from_user.id

        # Edit message to show loading
        await callback.message.edit_text(
            "⏳ <b>Запускаю авторизацию...</b>\n\n"
            "Получаю ссылку для входа...",
            parse_mode="HTML"
        )

        # Create and start OAuth session
        session = OAuthLoginSession(user_id)
        self._oauth_sessions[user_id] = session

        oauth_url = await session.start()

        if oauth_url:
            await state.set_state(AccountStates.waiting_oauth_code)

            await callback.message.edit_text(
                f"🔐 <b>Авторизация Claude Account</b>\n\n"
                f"1️⃣ Перейдите по ссылке:\n"
                f"<a href=\"{oauth_url}\">Открыть страницу авторизации</a>\n\n"
                f"2️⃣ Войдите в свой аккаунт Claude\n"
                f"3️⃣ Скопируйте код авторизации\n"
                f"4️⃣ Отправьте код сюда\n\n"
                f"<i>Ссылка действительна 5 минут</i>",
                parse_mode="HTML",
                reply_markup=Keyboards.account_cancel_login(),
                disable_web_page_preview=True
            )
        else:
            # Failed to get URL
            output = "\n".join(session._output_lines[-3:]) if session._output_lines else "Нет вывода"
            await callback.message.edit_text(
                f"❌ <b>Не удалось запустить авторизацию</b>\n\n"
                f"Claude CLI вернул:\n<pre>{output[:200]}</pre>\n\n"
                f"Убедитесь что claude установлен и доступен.",
                parse_mode="HTML",
                reply_markup=Keyboards.menu_back_only("account:menu")
            )
            self._oauth_sessions.pop(user_id, None)

    async def handle_oauth_code_input(self, message: Message, state: FSMContext):
        """Handle OAuth code input from user"""
        user_id = message.from_user.id
        code = message.text.strip()

        # Check for cancel commands
        if code.lower() in ("отмена", "cancel", "/cancel"):
            await self._cancel_oauth_login_message(message, state)
            return

        # Get active session
        session = self._oauth_sessions.get(user_id)
        if not session or session.status != "waiting_code":
            await state.clear()
            await message.answer(
                "❌ Сессия авторизации не найдена или истекла.\n"
                "Используйте /login чтобы начать заново."
            )
            return

        # Show processing message
        processing_msg = await message.answer("⏳ Проверяю код...")

        # Submit code
        success, result_msg = await session.submit_code(code)

        if success:
            # Switch to Claude Account mode
            mode_success, _, mode_error = await self.account_service.set_auth_mode(user_id, AuthMode.CLAUDE_ACCOUNT)

            if not mode_success:
                # This shouldn't happen since OAuth just saved credentials, but handle it
                settings = await self.account_service.get_settings(user_id)
                await processing_msg.edit_text(
                    f"⚠️ OAuth успешен, но не удалось переключить режим:\n{mode_error}",
                    parse_mode="HTML",
                    reply_markup=Keyboards.account_menu(
                        current_mode=AuthMode.ZAI_API.value,
                        has_credentials=True,
                        current_model=settings.model,
                        show_back=True,
                        back_to="menu:main"
                    )
                )
                await state.clear()
                return

            creds_info = self.account_service.get_credentials_info()
            settings = await self.account_service.get_settings(user_id)

            await processing_msg.edit_text(
                f"✅ <b>Авторизация успешна!</b>\n\n"
                f"Режим: Claude Account\n"
                f"Подписка: {creds_info.subscription_type or 'unknown'}\n"
                f"Rate limit: {creds_info.rate_limit_tier or 'default'}\n\n"
                f"Теперь все запросы идут через вашу подписку Claude.",
                parse_mode="HTML",
                reply_markup=Keyboards.account_menu(
                    current_mode=AuthMode.CLAUDE_ACCOUNT.value,
                    has_credentials=True,
                    subscription_type=creds_info.subscription_type,
                    current_model=settings.model,
                    show_back=True,
                    back_to="menu:main"
                )
            )
            await state.clear()
            logger.info(f"[{user_id}] OAuth login completed successfully")
        else:
            await processing_msg.edit_text(
                f"❌ <b>Ошибка авторизации</b>\n\n"
                f"{result_msg}\n\n"
                f"Попробуйте ещё раз или нажмите Отмена.",
                parse_mode="HTML",
                reply_markup=Keyboards.account_cancel_login()
            )

        # Cleanup session
        self._oauth_sessions.pop(user_id, None)

    async def _cancel_oauth_login(self, callback: CallbackQuery, state: FSMContext):
        """Cancel OAuth login from callback"""
        user_id = callback.from_user.id

        # Cancel active session
        session = self._oauth_sessions.pop(user_id, None)
        if session:
            await session.cancel()

        await state.clear()
        await self._show_menu(callback, state)
        await callback.answer("Авторизация отменена")

    async def _cancel_oauth_login_message(self, message: Message, state: FSMContext):
        """Cancel OAuth login from message"""
        user_id = message.from_user.id

        # Cancel active session
        session = self._oauth_sessions.pop(user_id, None)
        if session:
            await session.cancel()

        await state.clear()
        await message.answer(
            "Авторизация отменена.\n"
            "Используйте /account для настроек."
        )

    # ============== Local Model Setup Handlers ==============

    async def _start_local_model_setup(self, callback: CallbackQuery, state: FSMContext):
        """Start local model setup flow - ask for URL"""
        text = (
            "🖥️ <b>Настройка локальной модели</b>\n\n"
            "Введите URL вашего локального сервера.\n\n"
            "<b>Примеры:</b>\n"
            "• LMStudio: <code>http://localhost:1234/v1</code>\n"
            "• Ollama: <code>http://localhost:11434/v1</code>\n"
            "• vLLM: <code>http://localhost:8000/v1</code>\n\n"
            "<i>Сервер должен быть совместим с OpenAI API</i>"
        )

        await state.set_state(AccountStates.waiting_local_url)
        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.cancel_only(),
            parse_mode="HTML"
        )
        await callback.answer()

    async def handle_local_url_input(self, message: Message, state: FSMContext):
        """Handle local model URL input"""
        url = message.text.strip()

        # Validate URL
        if not url.startswith(("http://", "https://")):
            await message.answer(
                "❌ URL должен начинаться с http:// или https://\n\n"
                "Попробуйте ещё раз:",
                reply_markup=Keyboards.cancel_only(),
                parse_mode="HTML"
            )
            return

        # Store URL and ask for model name
        await state.update_data(local_url=url)
        await state.set_state(AccountStates.waiting_local_model_name)

        await message.answer(
            "📝 <b>Название модели</b>\n\n"
            "Введите название модели на вашем сервере.\n\n"
            "<b>Примеры:</b>\n"
            "• <code>llama-3.2-8b</code>\n"
            "• <code>mistral-7b-instruct</code>\n"
            "• <code>codestral-22b</code>\n"
            "• <code>qwen2.5-coder-32b</code>\n\n"
            "<i>Проверьте список моделей на вашем сервере</i>",
            reply_markup=Keyboards.cancel_only(),
            parse_mode="HTML"
        )

    async def handle_local_model_name_input(self, message: Message, state: FSMContext):
        """Handle local model name input"""
        model_name = message.text.strip()

        if not model_name:
            await message.answer(
                "❌ Название модели не может быть пустым.\n\n"
                "Введите название модели:",
                reply_markup=Keyboards.cancel_only()
            )
            return

        # Store model name and ask for display name
        await state.update_data(local_model_name=model_name)
        await state.set_state(AccountStates.waiting_local_display_name)

        await message.answer(
            "🏷️ <b>Имя для отображения</b>\n\n"
            f"Введите понятное имя для этой модели\n"
            f"(например: 'Мой LMStudio' или 'Локальная Llama').\n\n"
            f"Или нажмите кнопку чтобы использовать '{model_name}':",
            reply_markup=Keyboards.local_model_skip_name(model_name),
            parse_mode="HTML"
        )

    async def handle_local_display_name_input(self, message: Message, state: FSMContext):
        """Handle local model display name input"""
        user_id = message.from_user.id
        display_name = message.text.strip()

        if not display_name:
            await message.answer(
                "❌ Имя не может быть пустым.\n\n"
                "Введите имя для отображения:",
                reply_markup=Keyboards.cancel_only()
            )
            return

        await self._complete_local_model_setup(message, state, display_name)

    async def _handle_local_use_default_name(self, callback: CallbackQuery, state: FSMContext):
        """Handle using model name as display name"""
        data = await state.get_data()
        model_name = data.get("local_model_name", "Local Model")

        await callback.answer()
        # Create a fake message to reuse the completion logic
        await self._complete_local_model_setup(callback, state, model_name)

    async def _complete_local_model_setup(
        self,
        event,  # Message or CallbackQuery
        state: FSMContext,
        display_name: str
    ):
        """Complete local model setup"""
        user_id = event.from_user.id

        # Get stored data
        data = await state.get_data()
        url = data.get("local_url")
        model_name = data.get("local_model_name")

        if not url or not model_name:
            # Something went wrong, start over
            if isinstance(event, CallbackQuery):
                await event.message.edit_text(
                    "❌ Ошибка: данные настройки потеряны. Начните заново.",
                    reply_markup=Keyboards.cancel_only()
                )
            else:
                await event.answer(
                    "❌ Ошибка: данные настройки потеряны. Начните заново.",
                    reply_markup=Keyboards.cancel_only()
                )
            await state.clear()
            return

        # Create config and save
        config = LocalModelConfig(
            name=display_name,
            base_url=url,
            model_name=model_name,
        )

        settings = await self.account_service.set_local_model_config(user_id, config)

        await state.clear()

        text = (
            f"✅ <b>Локальная модель настроена!</b>\n\n"
            f"Имя: {display_name}\n"
            f"URL: <code>{url}</code>\n"
            f"Модель: <code>{model_name}</code>\n\n"
            f"Теперь все запросы идут на локальный сервер."
        )

        creds_info = self.account_service.get_credentials_info()

        if isinstance(event, CallbackQuery):
            await event.message.edit_text(
                text,
                reply_markup=Keyboards.account_menu(
                    current_mode=AuthMode.LOCAL_MODEL.value,
                    has_credentials=creds_info.exists,
                    current_model=model_name,
                    show_back=True,
                    back_to="menu:main"
                ),
                parse_mode="HTML"
            )
        else:
            await event.answer(
                text,
                reply_markup=Keyboards.account_menu(
                    current_mode=AuthMode.LOCAL_MODEL.value,
                    has_credentials=creds_info.exists,
                    current_model=model_name,
                    show_back=True,
                    back_to="menu:main"
                ),
                parse_mode="HTML"
            )

        logger.info(f"[{user_id}] Local model configured: {display_name} at {url}")

    async def handle_local_cancel_text(self, message: Message, state: FSMContext):
        """Handle cancel text during local model setup"""
        if message.text and message.text.lower() in ("отмена", "cancel", "/cancel"):
            await state.clear()
            await message.answer("Настройка отменена. Используйте /account для настроек.")
        else:
            current_state = await state.get_state()
            if current_state == AccountStates.waiting_local_url:
                await self.handle_local_url_input(message, state)
            elif current_state == AccountStates.waiting_local_model_name:
                await self.handle_local_model_name_input(message, state)
            elif current_state == AccountStates.waiting_local_display_name:
                await self.handle_local_display_name_input(message, state)


def register_account_handlers(dp, account_handlers: AccountHandlers):
    """Register account handlers with dispatcher"""
    dp.include_router(account_handlers.router)
