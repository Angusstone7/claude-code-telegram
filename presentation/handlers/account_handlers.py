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

    def __init__(self, user_id: int, proxy_url: Optional[str] = None):
        self.user_id = user_id
        self.proxy_url = proxy_url
        self.process: Optional[asyncio.subprocess.Process] = None
        self.oauth_url: Optional[str] = None
        self.status: str = "pending"  # pending, waiting_code, completed, failed
        self._output_lines: list[str] = []

    def _get_env(self) -> dict:
        """Build environment for OAuth login (proxy, no API keys, headless)"""
        env = os.environ.copy()

        # Set proxy for accessing claude.ai (if configured)
        if self.proxy_url:
            env["HTTP_PROXY"] = self.proxy_url
            env["HTTPS_PROXY"] = self.proxy_url
            env["http_proxy"] = self.proxy_url
            env["https_proxy"] = self.proxy_url

        # Bypass proxy for local network addresses
        env["NO_PROXY"] = "localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,host.docker.internal,.local"
        env["no_proxy"] = "localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,host.docker.internal,.local"

        # Headless environment - prevent CLI from trying to open browser
        env["BROWSER"] = "/bin/true"  # No-op browser command
        env["CI"] = "true"  # Signal CI/headless environment
        env["TERM"] = "dumb"  # Simple terminal
        env.pop("DISPLAY", None)  # No display

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
            # Use "claude login" - CLI outputs URL when no browser available
            self.process = await asyncio.create_subprocess_exec(
                "claude", "login",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # Merge stderr to stdout
                env=self._get_env(),
            )

            logger.info(f"[{self.user_id}] Started 'claude login' process (PID: {self.process.pid})")

            # Read output until we find the OAuth URL
            # Typical output: "Browser didn't open? Use the url below..."
            # followed by "https://claude.ai/oauth/authorize?..."
            timeout_seconds = 30

            async def read_until_url():
                while True:
                    line = await self.process.stdout.readline()
                    if not line:
                        logger.info(f"[{self.user_id}] claude /login: EOF reached, output_lines={len(self._output_lines)}")
                        break

                    decoded = line.decode('utf-8', errors='ignore').strip()
                    self._output_lines.append(decoded)
                    # Log at INFO level for debugging
                    logger.info(f"[{self.user_id}] claude /login output: {decoded[:200]}")

                    # Look for OAuth URL in line
                    url_match = re.search(r'https://claude\.ai/oauth/authorize[^\s]+', decoded)
                    if url_match:
                        return url_match.group(0)

                return None

            try:
                self.oauth_url = await asyncio.wait_for(read_until_url(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning(f"[{self.user_id}] Timeout waiting for OAuth URL. Got {len(self._output_lines)} lines: {self._output_lines}")
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
    # z.ai API key setup states
    waiting_zai_api_key = State()


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
        project_service=None,  # Optional: needed to get project_id for context reset
    ):
        self.account_service = account_service
        self.context_service = context_service
        self.project_service = project_service
        self.message_handlers = None  # Set from main.py for session cache clear
        self.router = Router(name="account")
        # Active OAuth login sessions per user
        self._oauth_sessions: dict[int, OAuthLoginSession] = {}
        self._register_handlers()

    async def _get_user_lang(self, user_id: int) -> str:
        """Get user's language preference"""
        if self.account_service:
            lang = await self.account_service.get_user_language(user_id)
            if lang:
                return lang
        return "ru"

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

        # z.ai API key setup handlers
        self.router.message.register(
            self.handle_zai_api_key_input,
            AccountStates.waiting_zai_api_key,
            F.text
        )

    async def handle_account_command(self, message: Message, state: FSMContext):
        """Handle /account command - show settings menu"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Get current settings
        settings = await self.account_service.get_settings(user_id)
        creds_info = self.account_service.get_credentials_info()
        has_zai_key = bool(settings.zai_api_key)

        # Build info message
        mode_names = {
            AuthMode.ZAI_API: "z.ai API",
            AuthMode.CLAUDE_ACCOUNT: "Claude Account",
            AuthMode.LOCAL_MODEL: t("account.local_model"),
        }
        current_mode_name = mode_names.get(settings.auth_mode, "Unknown")

        text = (
            f"{t('account.title')}\n\n"
            f"{t('account.current_mode', mode=current_mode_name)}\n\n"
        )

        if settings.auth_mode == AuthMode.ZAI_API:
            key_status = "✅" if has_zai_key else "❌"
            text += f"🔑 API key: {key_status}\n"
        elif settings.auth_mode == AuthMode.CLAUDE_ACCOUNT:
            if creds_info.exists:
                sub = creds_info.subscription_type or "unknown"
                tier = creds_info.rate_limit_tier or "default"
                text += f"{t('account.status_subscription', sub=sub)}\n"
                text += f"{t('account.status_rate_limit', tier=tier)}\n"
                if creds_info.expires_at:
                    text += f"{t('account.status_expires', date=creds_info.expires_at.strftime('%d.%m.%Y %H:%M'))}\n"
            else:
                text += f"{t('account.status_creds_not_found')}\n"

        text += f"\n{t('account.select_mode')}"

        # Send menu
        await message.answer(
            text,
            reply_markup=Keyboards.account_menu(
                current_mode=settings.auth_mode.value,
                has_credentials=creds_info.exists,
                subscription_type=creds_info.subscription_type,
                current_model=settings.model,
                has_zai_key=has_zai_key,
                show_back=True,
                back_to="menu:main",
                lang=lang
            )
        )

    async def handle_account_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle account settings callbacks"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

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
            await callback.answer(t("account.upload_cancelled"))

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

        elif action == "zai_setup":
            # Start z.ai API key setup
            await self._start_zai_api_key_setup(callback, state)

        elif action == "zai_delete":
            # Delete z.ai API key
            await self._handle_zai_delete_key(callback, state)

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

        # If already in this mode, show submenu for Claude Account or z.ai API
        if settings.auth_mode == mode:
            if mode == AuthMode.CLAUDE_ACCOUNT:
                # Show Claude Account submenu with options
                await self._show_claude_submenu(callback, state)
                return
            elif mode == AuthMode.ZAI_API:
                # Show z.ai API submenu with key management
                await self._show_zai_submenu(callback, state)
                return
            else:
                await callback.answer("Этот режим уже выбран")
                return

        # Get user language
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # For Claude Account, check if credentials exist
        if mode == AuthMode.CLAUDE_ACCOUNT:
            creds_info = self.account_service.get_credentials_info()
            if not creds_info.exists:
                # No credentials - offer login or upload options
                text = (
                    f"{t('account.claude_auth_title')}\n\n"
                    f"{t('account.claude_auth_desc')}\n\n"
                    f"{t('account.claude_auth_select')}\n\n"
                    f"{t('account.claude_auth_browser')}\n"
                    f"{t('account.claude_auth_browser_desc')}\n\n"
                    f"{t('account.claude_auth_upload')}\n"
                    f"{t('account.claude_auth_upload_desc')}"
                )

                await callback.message.edit_text(
                    text,
                    reply_markup=Keyboards.account_auth_options(lang=lang)
                )
                await callback.answer()
                return

        # For Local Model, start setup flow directly
        if mode == AuthMode.LOCAL_MODEL:
            await self._start_local_model_setup(callback, state)
            return

        # For z.ai API, check if user has API key
        if mode == AuthMode.ZAI_API:
            has_zai_key = await self.account_service.has_zai_api_key(user_id)
            if not has_zai_key:
                # No API key - ask user to add one
                text = (
                    f"{t('account.zai_auth_title')}\n\n"
                    f"{t('account.zai_auth_desc')}\n\n"
                    f"{t('account.zai_auth_options')}\n"
                    f"{t('account.zai_auth_add_key')}\n\n"
                    f"{t('account.zai_auth_note')}"
                )

                await callback.message.edit_text(
                    text,
                    reply_markup=Keyboards.zai_auth_options(lang=lang),
                    parse_mode="HTML"
                )
                await callback.answer()
                return

        # Show confirmation
        if mode == AuthMode.CLAUDE_ACCOUNT:
            creds_info = self.account_service.get_credentials_info()
            sub = creds_info.subscription_type or "unknown"
            text = (
                f"{t('account.confirm_switch_claude')}\n\n"
                f"{t('account.confirm_switch_claude_sub', sub=sub)}\n"
                f"{t('account.confirm_switch_claude_proxy')}\n\n"
                f"{t('account.confirm_switch_claude_note')}"
            )
        else:
            # z.ai with key
            text = (
                f"{t('account.confirm_switch_zai')}\n\n"
                f"{t('account.confirm_switch_zai_note')}"
            )

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.account_confirm_mode_switch(mode.value, lang=lang)
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
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        try:
            mode = AuthMode(mode_str)
        except ValueError:
            await callback.answer(t("account.unknown_mode", mode=mode_str))
            return

        # Switch mode
        success, settings, error_msg = await self.account_service.set_auth_mode(user_id, mode)

        if not success:
            # Failed to switch - show error
            await callback.answer(t("account.switch_error", error=error_msg), show_alert=True)
            # Show menu with current (unchanged) mode
            await self._show_menu(callback, state)
            return

        mode_name = "z.ai API" if mode == AuthMode.ZAI_API else "Claude Account"
        await callback.answer(t("account.switch_success", mode=mode_name))

        # Show updated menu
        await self._show_menu(callback, state)

    async def _handle_status(self, callback: CallbackQuery):
        """Show detailed auth status"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        settings = await self.account_service.get_settings(user_id)
        creds_info = self.account_service.get_credentials_info()

        text = f"{t('account.status_title')}\n\n"

        # Current mode
        mode_name = "z.ai API" if settings.auth_mode == AuthMode.ZAI_API else "Claude Account"
        text += f"{t('account.status_mode', mode=mode_name)}\n\n"

        # z.ai API info
        import os
        zai_base = os.environ.get("ANTHROPIC_BASE_URL", t("account.status_not_set"))
        zai_token = t("account.status_token_set") if os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY") else t("account.status_token_not_set")
        text += f"{t('account.status_zai')}\n"
        url_display = f"{zai_base[:40]}..." if len(zai_base) > 40 else zai_base
        text += f"{t('account.status_base_url', url=url_display)}\n"
        text += f"{zai_token}\n\n"

        # Claude Account info
        text += f"{t('account.status_claude')}\n"
        if creds_info.exists:
            text += f"{t('account.status_creds_found')}\n"
            text += f"{t('account.status_subscription', sub=creds_info.subscription_type or 'unknown')}\n"
            text += f"{t('account.status_rate_limit', tier=creds_info.rate_limit_tier or 'default')}\n"
            if creds_info.expires_at:
                text += f"{t('account.status_expires', date=creds_info.expires_at.strftime('%d.%m.%Y %H:%M'))}\n"
            if creds_info.scopes:
                text += f"{t('account.status_scopes', scopes=', '.join(creds_info.scopes[:3]))}\n"
        else:
            text += f"{t('account.status_creds_not_found')}\n"
            text += f"{t('account.status_path', path=CREDENTIALS_PATH)}\n"

        text += f"\n{t('account.status_proxy')}"

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=Keyboards.menu_back_only("account:menu", lang=lang)
        )
        await callback.answer()

    async def _show_menu(self, callback: CallbackQuery, state: FSMContext):
        """Show account menu"""
        await state.clear()

        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        settings = await self.account_service.get_settings(user_id)
        creds_info = self.account_service.get_credentials_info()
        has_zai_key = bool(settings.zai_api_key)

        mode_names = {
            AuthMode.ZAI_API: "z.ai API",
            AuthMode.CLAUDE_ACCOUNT: "Claude Account",
            AuthMode.LOCAL_MODEL: "Local Model",
        }
        current_mode_name = mode_names.get(settings.auth_mode, "Unknown")

        # Add key status for z.ai mode
        key_status = ""
        if settings.auth_mode == AuthMode.ZAI_API:
            key_status = "\n🔑 API Key: " + ("✅" if has_zai_key else "❌")

        text = (
            f"{t('account.title')}\n\n"
            f"{t('account.current_mode', mode=current_mode_name)}{key_status}\n\n"
            f"{t('account.select_mode')}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.account_menu(
                current_mode=settings.auth_mode.value,
                has_credentials=creds_info.exists,
                subscription_type=creds_info.subscription_type,
                current_model=settings.model,
                has_zai_key=has_zai_key,
                show_back=True,
                back_to="menu:main",
                lang=lang
            ),
            parse_mode="HTML"
        )

    async def _show_claude_submenu(self, callback: CallbackQuery, state: FSMContext):
        """Show Claude Account submenu with options"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)

        settings = await self.account_service.get_settings(user_id)
        creds_info = self.account_service.get_credentials_info()

        text = "☁️ <b>Claude Account</b>\n\n"

        if creds_info.exists:
            text += f"Status: ✅ Authorized\n"
            if creds_info.subscription_type:
                text += f"Subscription: {creds_info.subscription_type}\n"
            if creds_info.rate_limit_tier:
                text += f"Rate limit: {creds_info.rate_limit_tier}\n"
        else:
            text += "Status: ❌ Not authorized\n"

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.claude_account_submenu(
                has_credentials=creds_info.exists,
                subscription_type=creds_info.subscription_type,
                current_model=settings.model if settings.auth_mode == AuthMode.CLAUDE_ACCOUNT else None,
                lang=lang
            ),
            parse_mode="HTML"
        )
        await callback.answer()

    async def _show_zai_submenu(self, callback: CallbackQuery, state: FSMContext):
        """Show z.ai API submenu with key management options"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)

        settings = await self.account_service.get_settings(user_id)
        has_key = bool(settings.zai_api_key)

        text = "🌐 <b>z.ai API</b>\n\n"

        if has_key:
            # Mask the key for display (show first 8 and last 4 chars)
            key = settings.zai_api_key
            if len(key) > 16:
                masked = f"{key[:8]}...{key[-4:]}"
            else:
                masked = f"{key[:4]}***"
            text += f"Status: ✅ API key configured\n"
            text += f"Key: <code>{masked}</code>\n"
        else:
            text += "Status: ❌ API key not configured\n"

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.zai_api_submenu(
                has_key=has_key,
                current_model=settings.model,
                lang=lang
            ),
            parse_mode="HTML"
        )
        await callback.answer()

    async def _show_upload_prompt(self, callback: CallbackQuery, state: FSMContext):
        """Show credentials file upload prompt"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        await state.set_state(AccountStates.waiting_credentials_file)

        text = (
            f"{t('account.upload_title')}\n\n"
            f"{t('account.upload_send_file')}\n\n"
            f"{t('account.upload_where')}\n"
            f"{t('account.upload_path_linux')}\n"
            f"{t('account.upload_path_win')}\n\n"
            f"{t('account.upload_note')}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.account_upload_credentials(lang=lang)
        )
        await callback.answer()

    async def _show_model_selection(self, callback: CallbackQuery, state: FSMContext):
        """Show model selection menu based on current auth mode"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Get settings and available models for current auth mode
        settings = await self.account_service.get_settings(user_id)
        models = await self.account_service.get_available_models(user_id)

        # Build title based on auth mode
        titles = {
            AuthMode.CLAUDE_ACCOUNT: ("Claude", t("account.model_subtitle_claude")),
            AuthMode.ZAI_API: ("z.ai API", t("account.model_subtitle_zai")),
            AuthMode.LOCAL_MODEL: (t("account.local_model"), t("account.model_subtitle_local")),
        }
        title, subtitle = titles.get(settings.auth_mode, (t("account.model"), ""))

        text = f"{t('account.model_title', title=title)}\n"
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
                text += f"\n<i>{t('account.model_no_local')}</i>"
            else:
                text += f"\n<i>{t('account.model_empty')}</i>"

        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.model_select(
                models=models,
                auth_mode=settings.auth_mode.value,
                current_model=settings.model,
                lang=lang
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
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Get old model before changing
        old_model = await self.account_service.get_model(user_id)

        # Parse model value
        new_model = None if model_value == "default" else model_value

        if model_value == "default":
            await self.account_service.set_model(user_id, None)
            model_name = t("account.model_default")
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
            if self.context_service and self.project_service:
                try:
                    from domain.value_objects.user_id import UserId
                    uid = UserId.from_int(user_id)
                    project = await self.project_service.get_current(uid)
                    if project:
                        current_context = await self.context_service.get_current(project.id)
                        if current_context:
                            await self.context_service.start_fresh(current_context.id)
                            logger.info(f"[{user_id}] Session reset on model change: {old_model} -> {new_model}")
                except Exception as e:
                    logger.warning(f"[{user_id}] Failed to clear context on model change: {e}")

        # Return to menu with success message
        await self._show_menu(callback, state)
        msg = t("account.model_changed", model=model_name)
        if session_reset:
            msg += f"\n{t('account.session_reset')}"
        await callback.answer(msg, show_alert=session_reset)

    async def _handle_delete_account(self, callback: CallbackQuery, state: FSMContext):
        """Handle Claude Account deletion (credentials file)"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

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
                await callback.answer(t("account.logged_out"))
            else:
                await callback.answer(message, show_alert=True)

        except Exception as e:
            logger.error(f"[{user_id}] Error deleting account: {e}", exc_info=True)
            await callback.answer(t("account.upload_error", error=str(e)), show_alert=True)

    async def handle_credentials_upload(self, message: Message, state: FSMContext):
        """Handle credentials file upload"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Download file
        document = message.document

        # Check filename
        if document.file_name and not document.file_name.endswith(".json"):
            await message.answer(
                f"{t('account.upload_must_json')}\n"
                f"{t('account.upload_retry')}",
                reply_markup=Keyboards.account_upload_credentials(lang=lang)
            )
            return

        # Check file size (credentials should be small)
        if document.file_size > 50 * 1024:  # 50 KB max
            await message.answer(
                f"{t('account.upload_too_large')}\n"
                f"{t('account.upload_retry_size')}",
                reply_markup=Keyboards.account_upload_credentials(lang=lang)
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
                        f"⚠️ {t('account.creds_saved')}\n{t('account.switch_error', error=mode_error)}",
                        reply_markup=Keyboards.account_menu(
                            current_mode=AuthMode.ZAI_API.value,
                            has_credentials=True,
                            current_model=settings.model,
                            show_back=True,
                            back_to="menu:main",
                            lang=lang
                        )
                    )
                    await state.clear()
                    return

                creds_info = self.account_service.get_credentials_info()
                settings = await self.account_service.get_settings(user_id)

                await message.answer(
                    f"{t('account.upload_success')}\n\n"
                    f"{t('account.current_mode', mode='Claude Account')}\n"
                    f"{t('account.status_subscription', sub=creds_info.subscription_type or 'unknown')}\n"
                    f"{t('account.status_rate_limit', tier=creds_info.rate_limit_tier or 'default')}\n\n"
                    f"{t('account.confirm_switch_claude_note')}",
                    reply_markup=Keyboards.account_menu(
                        current_mode=AuthMode.CLAUDE_ACCOUNT.value,
                        has_credentials=True,
                        subscription_type=creds_info.subscription_type,
                        current_model=settings.model,
                        show_back=True,
                        back_to="menu:main",
                        lang=lang
                    )
                )
                await state.clear()
                logger.info(f"[{user_id}] Credentials uploaded, switched to Claude Account")

            else:
                await message.answer(
                    f"{t('account.upload_error', error=msg)}\n\n"
                    f"{t('account.upload_send_or_cancel')}",
                    reply_markup=Keyboards.account_upload_credentials(lang=lang)
                )

        except Exception as e:
            logger.error(f"[{user_id}] Error uploading credentials: {e}")
            await message.answer(
                f"{t('account.upload_error', error=str(e))}\n\n"
                f"{t('account.upload_send_or_cancel')}",
                reply_markup=Keyboards.account_upload_credentials(lang=lang)
            )

    async def handle_cancel_upload_text(self, message: Message, state: FSMContext):
        """Handle text input during credentials upload state"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        if message.text and message.text.lower() in ("отмена", "cancel", "/cancel"):
            await state.clear()
            await message.answer(t("account.upload_cancelled_use"))
        else:
            await message.answer(
                f"{t('account.upload_send_file')}\n"
                f"{t('account.upload_send_or_cancel')}",
                reply_markup=Keyboards.account_upload_credentials(lang=lang)
            )

    # ============== OAuth Login Handlers ==============

    async def handle_login_command(self, message: Message, state: FSMContext):
        """Handle /login command - start OAuth login flow"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Check if credentials already exist
        creds_info = self.account_service.get_credentials_info()
        if creds_info.exists:
            sub = creds_info.subscription_type or "unknown"
            await message.answer(
                f"{t('account.oauth_success')}\n\n"
                f"{t('account.status_subscription', sub=sub)}\n"
                f"{t('account.status_rate_limit', tier=creds_info.rate_limit_tier or 'default')}\n\n"
                f"/account",
                parse_mode="HTML"
            )
            return

        # Start OAuth login
        await self._start_oauth_login(message, state)

    async def _handle_login(self, callback: CallbackQuery, state: FSMContext):
        """Handle login button callback - start OAuth login"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)
        await callback.answer(t("status.loading"))
        await self._start_oauth_login_callback(callback, state)

    async def _start_oauth_login(self, message: Message, state: FSMContext):
        """Start OAuth login flow (from message)"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Show loading message
        loading_msg = await message.answer(
            f"{t('account.login_step1')}\n\n"
            f"{t('account.login_wait')}",
            parse_mode="HTML"
        )

        # Create and start OAuth session
        session = OAuthLoginSession(user_id)
        self._oauth_sessions[user_id] = session

        oauth_url = await session.start()

        if oauth_url:
            await state.set_state(AccountStates.waiting_oauth_code)

            await loading_msg.edit_text(
                f"{t('account.oauth_title')}\n\n"
                f"{t('account.oauth_step1', button=t('account.oauth_open_btn'))}\n"
                f"<a href=\"{oauth_url}\">{t('account.oauth_open_btn')}</a>\n\n"
                f"{t('account.oauth_step2')}\n"
                f"{t('account.oauth_step3')}\n"
                f"{t('account.oauth_step4')}\n\n"
                f"<i>⏱️ 5 min</i>",
                parse_mode="HTML",
                reply_markup=Keyboards.account_cancel_login(lang=lang),
                disable_web_page_preview=True
            )
        else:
            # Failed to get URL
            output = "\n".join(session._output_lines[-3:]) if session._output_lines else "No output"
            await loading_msg.edit_text(
                f"{t('account.oauth_failed')}\n\n"
                f"Claude CLI:\n<pre>{output[:200]}</pre>",
                parse_mode="HTML",
                reply_markup=Keyboards.menu_back_only("account:menu", lang=lang)
            )
            self._oauth_sessions.pop(user_id, None)

    async def _start_oauth_login_callback(self, callback: CallbackQuery, state: FSMContext):
        """Start OAuth login flow (from callback)"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Edit message to show loading
        await callback.message.edit_text(
            f"{t('account.login_step1')}\n\n"
            f"{t('account.login_wait')}",
            parse_mode="HTML"
        )

        # Create and start OAuth session
        session = OAuthLoginSession(user_id)
        self._oauth_sessions[user_id] = session

        oauth_url = await session.start()

        if oauth_url:
            await state.set_state(AccountStates.waiting_oauth_code)

            await callback.message.edit_text(
                f"{t('account.oauth_title')}\n\n"
                f"{t('account.oauth_step1', button=t('account.oauth_open_btn'))}\n"
                f"<a href=\"{oauth_url}\">{t('account.oauth_open_btn')}</a>\n\n"
                f"{t('account.oauth_step2')}\n"
                f"{t('account.oauth_step3')}\n"
                f"{t('account.oauth_step4')}\n\n"
                f"<i>⏱️ 5 min</i>",
                parse_mode="HTML",
                reply_markup=Keyboards.account_cancel_login(lang=lang),
                disable_web_page_preview=True
            )
        else:
            # Failed to get URL
            output = "\n".join(session._output_lines[-3:]) if session._output_lines else "No output"
            await callback.message.edit_text(
                f"{t('account.oauth_failed')}\n\n"
                f"Claude CLI:\n<pre>{output[:200]}</pre>",
                parse_mode="HTML",
                reply_markup=Keyboards.menu_back_only("account:menu", lang=lang)
            )
            self._oauth_sessions.pop(user_id, None)

    async def handle_oauth_code_input(self, message: Message, state: FSMContext):
        """Handle OAuth code input from user"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        code = message.text.strip()

        # Check for cancel commands
        if code.lower() in ("отмена", "cancel", "/cancel"):
            await self._cancel_oauth_login_message(message, state)
            return

        # Get active session
        session = self._oauth_sessions.get(user_id)
        if not session or session.status != "waiting_code":
            await state.clear()
            await message.answer(t("error.session_expired"))
            return

        # Show processing message
        processing_msg = await message.answer(t("status.processing"))

        # Submit code
        success, result_msg = await session.submit_code(code)

        if success:
            # Switch to Claude Account mode
            mode_success, _, mode_error = await self.account_service.set_auth_mode(user_id, AuthMode.CLAUDE_ACCOUNT)

            if not mode_success:
                # This shouldn't happen since OAuth just saved credentials, but handle it
                settings = await self.account_service.get_settings(user_id)
                await processing_msg.edit_text(
                    f"⚠️ {t('account.creds_saved')}\n{t('account.switch_error', error=mode_error)}",
                    parse_mode="HTML",
                    reply_markup=Keyboards.account_menu(
                        current_mode=AuthMode.ZAI_API.value,
                        has_credentials=True,
                        current_model=settings.model,
                        show_back=True,
                        back_to="menu:main",
                        lang=lang
                    )
                )
                await state.clear()
                return

            creds_info = self.account_service.get_credentials_info()
            settings = await self.account_service.get_settings(user_id)

            await processing_msg.edit_text(
                f"{t('account.oauth_success')}\n\n"
                f"{t('account.current_mode', mode='Claude Account')}\n"
                f"{t('account.status_subscription', sub=creds_info.subscription_type or 'unknown')}\n"
                f"{t('account.status_rate_limit', tier=creds_info.rate_limit_tier or 'default')}\n\n"
                f"{t('account.confirm_switch_claude_note')}",
                parse_mode="HTML",
                reply_markup=Keyboards.account_menu(
                    current_mode=AuthMode.CLAUDE_ACCOUNT.value,
                    has_credentials=True,
                    subscription_type=creds_info.subscription_type,
                    current_model=settings.model,
                    show_back=True,
                    back_to="menu:main",
                    lang=lang
                )
            )
            await state.clear()
            logger.info(f"[{user_id}] OAuth login completed successfully")
        else:
            await processing_msg.edit_text(
                f"{t('account.oauth_failed')}\n\n"
                f"{result_msg}\n\n"
                f"{t('account.upload_send_or_cancel')}",
                parse_mode="HTML",
                reply_markup=Keyboards.account_cancel_login(lang=lang)
            )

        # Cleanup session
        self._oauth_sessions.pop(user_id, None)

    async def _cancel_oauth_login(self, callback: CallbackQuery, state: FSMContext):
        """Cancel OAuth login from callback"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Cancel active session
        session = self._oauth_sessions.pop(user_id, None)
        if session:
            await session.cancel()

        await state.clear()
        await self._show_menu(callback, state)
        await callback.answer(t("account.oauth_cancelled"))

    async def _cancel_oauth_login_message(self, message: Message, state: FSMContext):
        """Cancel OAuth login from message"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Cancel active session
        session = self._oauth_sessions.pop(user_id, None)
        if session:
            await session.cancel()

        await state.clear()
        await message.answer(t("account.oauth_cancelled_use"))

    # ============== Local Model Setup Handlers ==============

    async def _start_local_model_setup(self, callback: CallbackQuery, state: FSMContext):
        """Start local model setup flow - ask for URL"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        text = (
            f"{t('account.local_title')}\n\n"
            f"{t('account.local_enter_url')}\n\n"
            f"{t('account.local_examples')}\n"
            f"{t('account.local_example1')}\n"
            f"{t('account.local_example2')}\n"
            "• vLLM: <code>http://localhost:8000/v1</code>\n\n"
            "<i>OpenAI API compatible</i>"
        )

        await state.set_state(AccountStates.waiting_local_url)
        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.cancel_only(lang=lang),
            parse_mode="HTML"
        )
        await callback.answer()

    async def handle_local_url_input(self, message: Message, state: FSMContext):
        """Handle local model URL input"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        url = message.text.strip()

        # Validate URL
        if not url.startswith(("http://", "https://")):
            await message.answer(
                f"{t('account.local_url_invalid')}\n\n"
                f"URL: http:// or https://",
                reply_markup=Keyboards.cancel_only(lang=lang),
                parse_mode="HTML"
            )
            return

        # Store URL and ask for model name
        await state.update_data(local_url=url)
        await state.set_state(AccountStates.waiting_local_model_name)

        await message.answer(
            f"{t('account.local_model_name')}\n\n"
            f"{t('account.local_enter_model')}\n\n"
            "<b>Examples:</b>\n"
            "• <code>llama-3.2-8b</code>\n"
            "• <code>mistral-7b-instruct</code>\n"
            "• <code>codestral-22b</code>\n"
            "• <code>qwen2.5-coder-32b</code>",
            reply_markup=Keyboards.cancel_only(lang=lang),
            parse_mode="HTML"
        )

    async def handle_local_model_name_input(self, message: Message, state: FSMContext):
        """Handle local model name input"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        model_name = message.text.strip()

        if not model_name:
            await message.answer(
                f"{t('error.invalid_input')}\n\n"
                f"{t('account.local_enter_name_prompt')}",
                reply_markup=Keyboards.cancel_only(lang=lang)
            )
            return

        # Store model name and ask for display name
        await state.update_data(local_model_name=model_name)
        await state.set_state(AccountStates.waiting_local_display_name)

        await message.answer(
            f"🏷️ <b>{t('account.local_enter_display')}</b>\n\n"
            f"{t('account.local_display_example')}\n\n"
            f"{t('account.local_skip_name', name=model_name)}:",
            reply_markup=Keyboards.local_model_skip_name(model_name, lang=lang),
            parse_mode="HTML"
        )

    async def handle_local_display_name_input(self, message: Message, state: FSMContext):
        """Handle local model display name input"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        display_name = message.text.strip()

        if not display_name:
            await message.answer(
                f"{t('error.invalid_input')}\n\n"
                f"{t('account.local_enter_display_prompt')}",
                reply_markup=Keyboards.cancel_only(lang=lang)
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
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Get stored data
        data = await state.get_data()
        url = data.get("local_url")
        model_name = data.get("local_model_name")

        if not url or not model_name:
            # Something went wrong, start over
            if isinstance(event, CallbackQuery):
                await event.message.edit_text(
                    t("account.local_error_data"),
                    reply_markup=Keyboards.cancel_only(lang=lang)
                )
            else:
                await event.answer(
                    t("account.local_error_data"),
                    reply_markup=Keyboards.cancel_only(lang=lang)
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
            f"{t('account.local_success')}\n\n"
            f"Name: {display_name}\n"
            f"{t('account.local_url', url=url)}\n"
            f"{t('account.local_model', model=model_name)}\n\n"
            f"{t('account.confirm_switch_claude_note')}"
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
                    back_to="menu:main",
                    lang=lang
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
                    back_to="menu:main",
                    lang=lang
                ),
                parse_mode="HTML"
            )

        logger.info(f"[{user_id}] Local model configured: {display_name} at {url}")

    # ============== z.ai API Key Setup Handlers ==============

    async def _start_zai_api_key_setup(self, callback: CallbackQuery, state: FSMContext):
        """Start z.ai API key setup flow - ask for API key"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        # Check if user already has a key
        has_key = await self.account_service.has_zai_api_key(user_id)

        text = f"{t('account.zai_setup_title')}\n\n"

        if has_key:
            text += f"✅ <i>{t('account.zai_key_saved')}</i>\n\n"

        text += (
            f"{t('account.zai_enter_key')}\n\n"
            f"<b>Get key:</b>\n"
            f"1. <a href=\"https://open.bigmodel.cn\">open.bigmodel.cn</a>\n"
            f"2. API Keys\n"
            f"3. Create key\n\n"
            f"{t('account.zai_auth_note')}"
        )

        await state.set_state(AccountStates.waiting_zai_api_key)
        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.zai_api_key_input(has_existing_key=has_key, lang=lang),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await callback.answer()

    async def handle_zai_api_key_input(self, message: Message, state: FSMContext):
        """Handle z.ai API key input from user"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        api_key = message.text.strip()

        # Check for cancel commands
        if api_key.lower() in ("отмена", "cancel", "/cancel"):
            await state.clear()
            await message.answer(t("account.zai_cancelled"))
            return

        # Delete the user's message containing the API key for security
        try:
            await message.delete()
        except Exception:
            pass  # May not have permission

        # Show processing message
        processing_msg = await message.answer(t("status.processing"))

        # Validate and save the key
        success, result_msg, settings = await self.account_service.set_zai_api_key(user_id, api_key)

        if success:
            # Key is valid and saved
            await state.clear()

            creds_info = self.account_service.get_credentials_info()
            settings = await self.account_service.get_settings(user_id)

            await processing_msg.edit_text(
                f"{result_msg}\n\n"
                f"{t('account.confirm_switch_zai_note')}",
                reply_markup=Keyboards.account_menu(
                    current_mode=settings.auth_mode.value,
                    has_credentials=creds_info.exists,
                    subscription_type=creds_info.subscription_type,
                    current_model=settings.model,
                    has_zai_key=True,
                    show_back=True,
                    back_to="menu:main",
                    lang=lang
                ),
                parse_mode="HTML"
            )
            logger.info(f"[{user_id}] z.ai API key saved successfully")
        else:
            # Key is invalid
            await processing_msg.edit_text(
                f"{t('account.zai_key_error', error=result_msg)}\n\n"
                f"{t('account.zai_key_retry')}",
                reply_markup=Keyboards.zai_api_key_input(has_existing_key=False, lang=lang),
                parse_mode="HTML"
            )

    async def _handle_zai_delete_key(self, callback: CallbackQuery, state: FSMContext):
        """Delete z.ai API key"""
        user_id = callback.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        success, message = await self.account_service.delete_zai_api_key(user_id)

        if success:
            await self._show_menu(callback, state)
            await callback.answer(t("account.zai_key_deleted"))
        else:
            await callback.answer(message, show_alert=True)

    async def handle_local_cancel_text(self, message: Message, state: FSMContext):
        """Handle cancel text during local model setup"""
        user_id = message.from_user.id
        lang = await self._get_user_lang(user_id)
        from shared.i18n import get_translator
        t = get_translator(lang)

        if message.text and message.text.lower() in ("отмена", "cancel", "/cancel"):
            await state.clear()
            await message.answer(t("account.zai_cancelled"))
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
