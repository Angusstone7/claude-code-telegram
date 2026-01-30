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
proxy_setup_state: Dict[int, Dict] = {}


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

        await callback.message.edit_text(
            f"✅ Выбран тип: <b>{proxy_type.upper()}</b>\n\n"
            "Шаг 2: Отправьте адрес и порт прокси\n\n"
            "Формат: <code>host:port</code>\n"
            "Например: <code>148.253.208.124:3128</code>",
            parse_mode="HTML"
        )
        await callback.answer()

    async def handle_proxy_host_input(self, message: Message, **kwargs) -> None:
        """Handle proxy host:port input"""
        user_id = message.from_user.id

        if user_id not in proxy_setup_state:
            await message.answer("❌ Сессия настройки истекла. Начните заново через /settings")
            return

        try:
            # Parse host:port
            parts = message.text.strip().split(":")
            if len(parts) != 2:
                raise ValueError("Invalid format")

            host = parts[0].strip()
            port = int(parts[1].strip())

            if not host or not (1 <= port <= 65535):
                raise ValueError("Invalid host or port")

            # Save to state
            proxy_setup_state[user_id]["host"] = host
            proxy_setup_state[user_id]["port"] = port

            # Ask about auth
            keyboard = Keyboards.proxy_auth_options()
            await message.answer(
                f"✅ Адрес: <code>{host}:{port}</code>\n\n"
                "Шаг 3: Требуется ли авторизация?",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        except ValueError:
            await message.answer(
                "❌ Неверный формат!\n\n"
                "Отправьте в формате: <code>host:port</code>\n"
                "Например: <code>148.253.208.124:3128</code>",
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


def register_proxy_handlers(dp, handlers: ProxyHandlers):
    """Register proxy handlers with dispatcher"""
    from aiogram import F

    # Callback для меню настроек прокси
    dp.callback_query.register(
        lambda c: handlers.handle_proxy_menu(c),
        F.data == "menu:proxy"
    )

    # Callback для начала настройки
    dp.callback_query.register(
        lambda c: handlers.handle_proxy_setup(c),
        F.data == "proxy:setup"
    )

    # Callback для выбора типа прокси
    dp.callback_query.register(
        lambda c: handlers.handle_proxy_type_selection(c, c.data.split(":")[2]),
        F.data.startswith("proxy:type:")
    )

    # Callback для выбора авторизации
    dp.callback_query.register(
        lambda c: handlers.handle_proxy_auth_selection(c, c.data.split(":")[2] == "yes"),
        F.data.startswith("proxy:auth:")
    )

    # Callback для выбора области (scope)
    dp.callback_query.register(
        lambda c: handlers.handle_proxy_scope_selection(c, c.data.split(":")[2] == "global"),
        F.data.startswith("proxy:scope:")
    )

    # Callback для теста прокси
    dp.callback_query.register(
        lambda c: handlers.handle_proxy_test(c),
        F.data == "proxy:test"
    )

    # Callback для отключения прокси
    dp.callback_query.register(
        lambda c: handlers.handle_proxy_disable(c),
        F.data == "proxy:disable"
    )

    logger.info("✓ Proxy handlers registered")
