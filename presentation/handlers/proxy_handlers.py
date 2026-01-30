"""Proxy settings handlers for Telegram bot"""

import logging
from typing import Dict, Optional
from aiogram.types import CallbackQuery, Message
from aiogram import Bot

from application.services.proxy_service import ProxyService
from domain.value_objects.proxy_config import ProxyType
from domain.value_objects.user_id import UserId
from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)


# State для хранения промежуточных данных настройки прокси
# Структура: {user_id: {"type": "http", "host": "...", "port": 123, "step": "host|credentials"}}
proxy_setup_state: Dict[int, Dict] = {}


def is_proxy_input_active(user_id: int) -> bool:
    """Check if user is in proxy setup input mode"""
    return user_id in proxy_setup_state and "step" in proxy_setup_state[user_id]


def get_proxy_input_step(user_id: int) -> Optional[str]:
    """Get current proxy input step: 'host' or 'credentials'"""
    if user_id in proxy_setup_state:
        return proxy_setup_state[user_id].get("step")
    return None


class ProxyHandlers:
    """Handlers for proxy settings management via Telegram"""

    def __init__(self, proxy_service: ProxyService):
        self.proxy_service = proxy_service

    async def handle_proxy_menu(self, callback: CallbackQuery, **kwargs) -> None:
        """Show proxy settings menu"""
        user_id = UserId(callback.from_user.id)

        # Get current proxy
        proxy_config = await self.proxy_service.get_effective_proxy(user_id)

        has_proxy = proxy_config is not None and proxy_config.enabled
        proxy_status = proxy_config.mask_credentials() if has_proxy else "Не настроен"

        keyboard = Keyboards.proxy_settings_menu(has_proxy, proxy_status)

        await callback.message.edit_text(
            "⚙️ <b>Настройки прокси</b>\n\n"
            f"Текущий статус: {proxy_status}\n\n"
            "Прокси используется для доступа к claude.ai и внешним API.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()

    async def handle_proxy_setup(self, callback: CallbackQuery, **kwargs) -> None:
        """Start proxy setup wizard"""
        keyboard = Keyboards.proxy_type_selection()

        await callback.message.edit_text(
            "🔧 <b>Настройка прокси</b>\n\n"
            "Шаг 1: Выберите тип прокси",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()

    async def handle_proxy_type_selection(
        self,
        callback: CallbackQuery,
        proxy_type: str,
        **kwargs
    ) -> None:
        """Handle proxy type selection"""
        user_id = callback.from_user.id

        # Initialize state
        if user_id not in proxy_setup_state:
            proxy_setup_state[user_id] = {}

        proxy_setup_state[user_id]["type"] = proxy_type
        proxy_setup_state[user_id]["step"] = "host"  # Expecting host:port input

        await callback.message.edit_text(
            f"✅ Выбран тип: <b>{proxy_type.upper()}</b>\n\n"
            "Шаг 2: Отправьте адрес и порт прокси\n\n"
            "Формат: <code>host:port</code>\n"
            "Например: <code>148.253.208.124:3128</code>",
            parse_mode="HTML"
        )
        await callback.answer()

    async def handle_proxy_host_input(self, message: Message, **kwargs) -> None:
        """Handle proxy host:port input (also accepts full URL format)"""
        user_id = message.from_user.id

        if user_id not in proxy_setup_state:
            await message.answer("❌ Сессия настройки истекла. Начните заново через /settings")
            return

        text = message.text.strip()
        host = None
        port = None
        username = None
        password = None

        try:
            # Try to parse as full URL (http://user:pass@host:port)
            if "://" in text:
                from urllib.parse import urlparse
                parsed = urlparse(text)

                if parsed.hostname:
                    host = parsed.hostname
                if parsed.port:
                    port = parsed.port
                if parsed.username:
                    username = parsed.username
                if parsed.password:
                    password = parsed.password

                # Update proxy type from URL scheme if provided
                scheme = parsed.scheme.lower()
                if scheme in ("http", "https", "socks4", "socks5"):
                    proxy_setup_state[user_id]["type"] = scheme

            # Try to parse as simple host:port format
            else:
                parts = text.split(":")
                if len(parts) == 2:
                    host = parts[0].strip()
                    port = int(parts[1].strip())

            # Validate parsed values
            if not host or not port:
                raise ValueError("Could not parse host or port")

            if not (1 <= port <= 65535):
                raise ValueError("Invalid port number")

            # Save to state
            proxy_setup_state[user_id]["host"] = host
            proxy_setup_state[user_id]["port"] = port
            proxy_setup_state[user_id].pop("step", None)  # Clear input step

            # If credentials were parsed from URL, save and go directly to scope selection
            if username and password:
                proxy_setup_state[user_id]["username"] = username
                proxy_setup_state[user_id]["password"] = password

                keyboard = Keyboards.proxy_scope_selection()
                await message.answer(
                    f"✅ <b>Прокси настроен из URL</b>\n\n"
                    f"Тип: {proxy_setup_state[user_id]['type'].upper()}\n"
                    f"Адрес: <code>{host}:{port}</code>\n"
                    f"Авторизация: ✓\n\n"
                    "📍 Для кого настроить прокси?",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # Ask about auth
                keyboard = Keyboards.proxy_auth_options()
                await message.answer(
                    f"✅ Адрес: <code>{host}:{port}</code>\n\n"
                    "Шаг 3: Требуется ли авторизация?",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

        except (ValueError, AttributeError) as e:
            logger.debug(f"Proxy input parse error: {e}")
            await message.answer(
                "❌ Неверный формат!\n\n"
                "Поддерживаемые форматы:\n"
                "• <code>host:port</code>\n"
                "• <code>http://host:port</code>\n"
                "• <code>http://user:pass@host:port</code>\n\n"
                "Например:\n"
                "• <code>148.253.208.124:3128</code>\n"
                "• <code>http://proxyuser:pass@148.253.208.124:3128</code>",
                parse_mode="HTML"
            )

    async def handle_proxy_auth_selection(
        self,
        callback: CallbackQuery,
        needs_auth: bool,
        **kwargs
    ) -> None:
        """Handle authentication option"""
        user_id = callback.from_user.id

        if user_id not in proxy_setup_state:
            await callback.answer("❌ Сессия истекла", show_alert=True)
            return

        if needs_auth:
            proxy_setup_state[user_id]["step"] = "credentials"  # Expecting credentials input
            await callback.message.edit_text(
                "🔐 <b>Авторизация</b>\n\n"
                "Отправьте логин и пароль в формате:\n"
                "<code>username:password</code>",
                parse_mode="HTML"
            )
        else:
            # No auth, ask for scope
            proxy_setup_state[user_id]["username"] = None
            proxy_setup_state[user_id]["password"] = None

            keyboard = Keyboards.proxy_scope_selection()
            await callback.message.edit_text(
                "📍 <b>Область применения</b>\n\n"
                "Для кого настроить прокси?",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await callback.answer()

    async def handle_proxy_credentials_input(self, message: Message, **kwargs) -> None:
        """Handle username:password input"""
        user_id = message.from_user.id

        if user_id not in proxy_setup_state:
            await message.answer("❌ Сессия настройки истекла")
            return

        try:
            parts = message.text.strip().split(":", 1)
            if len(parts) != 2:
                raise ValueError("Invalid format")

            username = parts[0].strip()
            password = parts[1].strip()

            if not username or not password:
                raise ValueError("Empty credentials")

            proxy_setup_state[user_id]["username"] = username
            proxy_setup_state[user_id]["password"] = password
            proxy_setup_state[user_id].pop("step", None)  # Clear input step

            # Ask for scope
            keyboard = Keyboards.proxy_scope_selection()
            await message.answer(
                "✅ Учетные данные сохранены\n\n"
                "📍 Для кого настроить прокси?",
                reply_markup=keyboard
            )

        except ValueError:
            await message.answer(
                "❌ Неверный формат!\n\n"
                "Отправьте в формате: <code>username:password</code>",
                parse_mode="HTML"
            )

    async def handle_proxy_scope_selection(
        self,
        callback: CallbackQuery,
        is_global: bool,
        **kwargs
    ) -> None:
        """Handle scope selection and create proxy"""
        user_id = callback.from_user.id
        telegram_user_id = UserId(user_id)

        if user_id not in proxy_setup_state:
            await callback.answer("❌ Сессия истекла", show_alert=True)
            return

        state = proxy_setup_state[user_id]

        try:
            # Create proxy
            proxy_type = ProxyType(state["type"])
            host = state["host"]
            port = state["port"]
            username = state.get("username")
            password = state.get("password")

            target_user_id = None if is_global else telegram_user_id

            await self.proxy_service.set_custom_proxy(
                proxy_type=proxy_type,
                host=host,
                port=port,
                username=username,
                password=password,
                user_id=target_user_id
            )

            # Test proxy
            proxy_config = await self.proxy_service.get_effective_proxy(telegram_user_id)
            success, message = await self.proxy_service.test_proxy(proxy_config)

            scope_text = "глобально" if is_global else "для вас"

            if success:
                keyboard = Keyboards.proxy_confirm_test(True)
                await callback.message.edit_text(
                    f"✅ <b>Прокси настроен {scope_text}</b>\n\n"
                    f"Тип: {proxy_type.value.upper()}\n"
                    f"Адрес: {host}:{port}\n\n"
                    f"Результат теста:\n{message}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                keyboard = Keyboards.proxy_confirm_test(False)
                await callback.message.edit_text(
                    f"⚠️ <b>Прокси настроен, но тест не прошел</b>\n\n"
                    f"Тип: {proxy_type.value.upper()}\n"
                    f"Адрес: {host}:{port}\n\n"
                    f"Ошибка: {message}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

            # Clear state
            del proxy_setup_state[user_id]

        except Exception as e:
            logger.error(f"Error setting up proxy: {e}")
            await callback.message.edit_text(
                f"❌ Ошибка настройки прокси:\n{str(e)}"
            )

        await callback.answer()

    async def handle_proxy_test(self, callback: CallbackQuery, **kwargs) -> None:
        """Test current proxy"""
        user_id = UserId(callback.from_user.id)

        proxy_config = await self.proxy_service.get_effective_proxy(user_id)

        if not proxy_config:
            await callback.answer("❌ Прокси не настроен", show_alert=True)
            return

        await callback.answer("🧪 Тестирую прокси...")

        success, message = await self.proxy_service.test_proxy(proxy_config)

        if success:
            await callback.message.answer(
                f"✅ <b>Тест успешен</b>\n\n{message}",
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                f"❌ <b>Тест не прошел</b>\n\n{message}",
                parse_mode="HTML"
            )

    async def handle_proxy_disable(self, callback: CallbackQuery, **kwargs) -> None:
        """Disable proxy"""
        user_id = UserId(callback.from_user.id)

        await self.proxy_service.disable_user_proxy(user_id)

        await callback.message.edit_text(
            "✅ Прокси отключен"
        )
        await callback.answer()


class ProxyInputFilter:
    """Filter for proxy text input messages"""

    def __init__(self, step: str):
        self.step = step

    async def __call__(self, message) -> bool:
        if not message.text:
            return False
        user_id = message.from_user.id
        return get_proxy_input_step(user_id) == self.step


def register_proxy_handlers(dp, handlers: ProxyHandlers):
    """Register proxy handlers with dispatcher"""
    from aiogram import F

    # === MESSAGE HANDLERS (must be registered FIRST to intercept proxy input) ===
    # These handlers catch text input when user is in proxy setup mode

    # Handler for host:port input (step="host")
    dp.message.register(
        handlers.handle_proxy_host_input,
        ProxyInputFilter("host")
    )

    # Handler for username:password input (step="credentials")
    dp.message.register(
        handlers.handle_proxy_credentials_input,
        ProxyInputFilter("credentials")
    )

    # === CALLBACK HANDLERS ===

    # Callback для меню настроек прокси
    dp.callback_query.register(
        handlers.handle_proxy_menu,
        F.data == "menu:proxy"
    )

    # Callback для начала настройки
    dp.callback_query.register(
        handlers.handle_proxy_setup,
        F.data == "proxy:setup"
    )

    # Callback для выбора типа прокси - нужен wrapper для извлечения параметра
    async def handle_type(c):
        proxy_type = c.data.split(":")[2]
        await handlers.handle_proxy_type_selection(c, proxy_type)

    dp.callback_query.register(
        handle_type,
        F.data.startswith("proxy:type:")
    )

    # Callback для выбора авторизации
    async def handle_auth(c):
        with_auth = c.data.split(":")[2] == "yes"
        await handlers.handle_proxy_auth_selection(c, with_auth)

    dp.callback_query.register(
        handle_auth,
        F.data.startswith("proxy:auth:")
    )

    # Callback для выбора области (scope)
    async def handle_scope(c):
        is_global = c.data.split(":")[2] == "global"
        await handlers.handle_proxy_scope_selection(c, is_global)

    dp.callback_query.register(
        handle_scope,
        F.data.startswith("proxy:scope:")
    )

    # Callback для теста прокси
    dp.callback_query.register(
        handlers.handle_proxy_test,
        F.data == "proxy:test"
    )

    # Callback для отключения прокси
    dp.callback_query.register(
        handlers.handle_proxy_disable,
        F.data == "proxy:disable"
    )

    logger.info("✓ Proxy handlers registered")
