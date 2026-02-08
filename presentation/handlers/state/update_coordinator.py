"""
Message Update Coordinator

Централизованная точка для ВСЕХ обновлений сообщений Telegram.
Предотвращает rate limiting путём:
1. Единой очереди обновлений на сообщение
2. Строгого интервала 2 секунды между обновлениями
3. Объединения множественных запросов в один
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Callable, Awaitable, Any

from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

logger = logging.getLogger(__name__)


@dataclass
class PendingUpdate:
    """Ожидающее обновление сообщения."""
    text: str
    parse_mode: Optional[str] = "HTML"
    reply_markup: Optional[InlineKeyboardMarkup] = None
    priority: int = 0  # Выше = важнее (final updates имеют высший приоритет)
    is_final: bool = False  # Финальное обновление - игнорировать последующие


@dataclass
class MessageState:
    """Состояние одного сообщения."""
    message: Message
    last_update_time: float = 0.0
    last_sent_text: str = ""
    pending_update: Optional[PendingUpdate] = None
    update_task: Optional[asyncio.Task] = None
    is_finalized: bool = False
    parse_error_count: int = 0  # Count of consecutive HTML parse errors
    force_plain_text: bool = False  # If True, always use parse_mode=None


class MessageUpdateCoordinator:
    """
    Координатор обновлений сообщений Telegram.

    ВАЖНО: Все обновления сообщений ДОЛЖНЫ проходить через этот класс!

    Гарантии:
    - Минимум 2 секунды между обновлениями одного сообщения
    - Множественные запросы объединяются (последний побеждает)
    - Rate limit обрабатывается gracefully
    - Финальные обновления имеют приоритет

    Использование:
        coordinator = MessageUpdateCoordinator(bot)

        # Обычное обновление (будет отложено если <2с с прошлого)
        await coordinator.update(message, "новый текст")

        # Финальное обновление (гарантированно выполнится)
        await coordinator.update(message, "финал", is_final=True)
    """

    # Строгий минимальный интервал между обновлениями
    MIN_UPDATE_INTERVAL = 2.0  # секунды

    # Максимальное время ожидания rate limit
    MAX_RATE_LIMIT_WAIT = 10.0  # секунды

    def __init__(self, bot: Bot):
        self.bot = bot
        self._messages: Dict[int, MessageState] = {}  # message_id -> state
        self._global_lock = asyncio.Lock()

    def _get_state(self, message: Message) -> MessageState:
        """Получить или создать состояние сообщения."""
        msg_id = message.message_id
        if msg_id not in self._messages:
            self._messages[msg_id] = MessageState(message=message)
        return self._messages[msg_id]

    async def update(
        self,
        message: Message,
        text: str,
        parse_mode: Optional[str] = "HTML",
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        is_final: bool = False,
        priority: int = 0
    ) -> bool:
        """
        Запланировать обновление сообщения.

        Args:
            message: Сообщение для обновления
            text: Новый текст
            parse_mode: Режим парсинга (HTML, Markdown, None)
            reply_markup: Клавиатура
            is_final: Финальное обновление (приоритет, гарантированно выполнится)
            priority: Приоритет (0=обычный, 1=важный, 2=критический)

        Returns:
            True если обновление запланировано/выполнено
        """
        state = self._get_state(message)

        # Логируем входящий вызов
        logger.info(
            f"Coordinator.update: msg={message.message_id}, text={len(text)}ch, "
            f"is_final={is_final}, last_sent={len(state.last_sent_text)}ch"
        )

        # Игнорируем обновления для финализированных сообщений
        if state.is_finalized and not is_final:
            logger.debug(f"Message {message.message_id}: ignoring update, already finalized")
            return False

        # Если текст не изменился - пропускаем
        if text == state.last_sent_text and not is_final:
            logger.debug(f"Message {message.message_id}: text unchanged ({len(text)}ch), skipping")
            return False

        # Создаём pending update
        pending = PendingUpdate(
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            priority=priority if not is_final else 100,
            is_final=is_final
        )

        # Если есть pending с меньшим приоритетом - заменяем
        if state.pending_update is None or pending.priority >= state.pending_update.priority:
            state.pending_update = pending
            logger.debug(f"Message {message.message_id}: pending_update set ({len(text)}ch)")

        # Проверяем можно ли обновить сейчас
        now = time.time()
        time_since_update = now - state.last_update_time

        if time_since_update >= self.MIN_UPDATE_INTERVAL or is_final:
            # Можно обновить сейчас
            logger.info(f"Message {message.message_id}: executing update NOW (elapsed={time_since_update:.1f}s)")
            return await self._execute_update(state)
        else:
            # Планируем отложенное обновление
            delay = self.MIN_UPDATE_INTERVAL - time_since_update
            logger.info(f"Message {message.message_id}: scheduling update in {delay:.1f}s")
            await self._schedule_update(state, delay)
            return True

    async def _schedule_update(self, state: MessageState, delay: float) -> None:
        """Запланировать отложенное обновление."""
        # Если уже есть scheduled task - он выполнит pending_update
        # pending_update уже был обновлён в update() до этого вызова
        if state.update_task and not state.update_task.done():
            pending_size = len(state.pending_update.text) if state.pending_update else 0
            logger.debug(
                f"Message {state.message.message_id}: task already scheduled, "
                f"pending updated to {pending_size}ch (will be sent when task fires)"
            )
            return

        async def delayed_update():
            await asyncio.sleep(delay)
            logger.debug(f"Message {state.message.message_id}: delayed_update firing after {delay:.1f}s")
            await self._execute_update(state)

        state.update_task = asyncio.create_task(delayed_update())
        pending_size = len(state.pending_update.text) if state.pending_update else 0
        logger.info(f"Message {state.message.message_id}: NEW scheduled update in {delay:.1f}s ({pending_size}ch)")

    async def _execute_update(self, state: MessageState) -> bool:
        """Выполнить обновление сообщения."""
        pending = state.pending_update
        if not pending:
            logger.debug(f"Message {state.message.message_id}: _execute_update - no pending update")
            return False

        # Очищаем pending до выполнения (чтобы новые запросы создали новый)
        state.pending_update = None

        # Финальное обновление
        if pending.is_final:
            state.is_finalized = True

        # If forced plain text mode due to repeated parse errors, strip HTML
        if state.force_plain_text and pending.parse_mode == "HTML":
            import re
            pending = PendingUpdate(
                text=re.sub(r'<[^>]+>', '', pending.text),
                parse_mode=None,
                reply_markup=pending.reply_markup,
                priority=pending.priority,
                is_final=pending.is_final,
            )

        # КРИТИЧЕСКОЕ ЛОГИРОВАНИЕ - момент отправки в Telegram
        logger.info(
            f">>> TELEGRAM EDIT: msg={state.message.message_id}, "
            f"text={len(pending.text)}ch, is_final={pending.is_final}"
        )

        try:
            await state.message.edit_text(
                pending.text,
                parse_mode=pending.parse_mode,
                reply_markup=pending.reply_markup
            )
            state.last_update_time = time.time()
            state.last_sent_text = pending.text
            state.parse_error_count = 0  # Reset on success
            logger.info(f">>> TELEGRAM EDIT SUCCESS: msg={state.message.message_id}, {len(pending.text)}ch")
            return True

        except TelegramRetryAfter as e:
            # Rate limited
            if e.retry_after > self.MAX_RATE_LIMIT_WAIT:
                logger.warning(
                    f"Message {state.message.message_id}: rate limited for {e.retry_after}s, "
                    f"skipping (max wait {self.MAX_RATE_LIMIT_WAIT}s)"
                )
                # Для финальных - пытаемся позже
                if pending.is_final:
                    state.is_finalized = False
                    state.pending_update = pending
                    await self._schedule_update(state, self.MAX_RATE_LIMIT_WAIT)
                return False

            # Короткий rate limit - ждём и повторяем
            logger.info(f"Message {state.message.message_id}: rate limited, waiting {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 0.5)
            state.pending_update = pending  # Восстанавливаем
            return await self._execute_update(state)

        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                # Контент не изменился - это нормально
                state.last_update_time = time.time()
                state.last_sent_text = pending.text
                return True
            elif "message to edit not found" in str(e).lower():
                # Сообщение удалено
                logger.warning(f"Message {state.message.message_id}: deleted, removing from coordinator")
                self._messages.pop(state.message.message_id, None)
                return False
            else:
                state.parse_error_count += 1
                logger.error(
                    f"Message {state.message.message_id}: Telegram error (count={state.parse_error_count}): {e}"
                )

                # After 2 consecutive parse errors, switch to permanent plain text mode
                if state.parse_error_count >= 2:
                    state.force_plain_text = True
                    logger.warning(
                        f"Message {state.message.message_id}: switching to permanent plain text mode "
                        f"after {state.parse_error_count} parse errors"
                    )

                # Пробуем без форматирования
                try:
                    import re
                    plain_text = re.sub(r'<[^>]+>', '', pending.text)
                    await state.message.edit_text(
                        plain_text,
                        parse_mode=None,
                        reply_markup=pending.reply_markup
                    )
                    state.last_update_time = time.time()
                    # CRITICAL: save original HTML text to prevent re-sending the same broken HTML
                    state.last_sent_text = pending.text
                    return True
                except Exception as fallback_err:
                    logger.error(
                        f"Message {state.message.message_id}: plain text fallback also failed: {fallback_err}"
                    )
                    # Still save the text to prevent infinite retry loop
                    state.last_sent_text = pending.text
                    return False

        except Exception as e:
            logger.error(f"Message {state.message.message_id}: unexpected error: {e}")
            return False

    async def send_new(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = "HTML",
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> Optional[Message]:
        """
        Отправить новое сообщение.

        Автоматически регистрирует его в координаторе.
        """
        try:
            message = await self.bot.send_message(
                chat_id,
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            # Регистрируем в координаторе
            state = self._get_state(message)
            state.last_update_time = time.time()
            state.last_sent_text = text
            return message

        except TelegramRetryAfter as e:
            if e.retry_after > self.MAX_RATE_LIMIT_WAIT:
                logger.error(f"send_new: rate limited for {e.retry_after}s, giving up")
                return None
            logger.info(f"send_new: rate limited, waiting {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 0.5)
            return await self.send_new(chat_id, text, parse_mode, reply_markup)

        except TelegramBadRequest as e:
            logger.error(f"send_new: Telegram error: {e}")
            # Пробуем без форматирования
            try:
                import re
                plain_text = re.sub(r'<[^>]+>', '', text)
                message = await self.bot.send_message(
                    chat_id,
                    plain_text,
                    parse_mode=None,
                    reply_markup=reply_markup
                )
                state = self._get_state(message)
                state.last_update_time = time.time()
                state.last_sent_text = plain_text
                return message
            except Exception:
                return None

        except Exception as e:
            logger.error(f"send_new: unexpected error: {e}")
            return None

    def get_time_until_next_update(self, message: Message) -> float:
        """
        Получить время до следующего возможного обновления.

        Returns:
            Секунды до следующего обновления (0 если можно сейчас)
        """
        state = self._get_state(message)
        elapsed = time.time() - state.last_update_time
        remaining = max(0, self.MIN_UPDATE_INTERVAL - elapsed)
        return remaining

    def is_finalized(self, message: Message) -> bool:
        """Проверить финализировано ли сообщение."""
        state = self._get_state(message)
        return state.is_finalized

    def cleanup(self, message: Message) -> None:
        """Очистить состояние сообщения."""
        msg_id = message.message_id
        state = self._messages.pop(msg_id, None)
        if state and state.update_task:
            state.update_task.cancel()
        logger.debug(f"Message {msg_id}: cleaned up")

    def cleanup_chat(self, chat_id: int) -> None:
        """Очистить все сообщения чата."""
        to_remove = [
            msg_id for msg_id, state in self._messages.items()
            if state.message.chat.id == chat_id
        ]
        for msg_id in to_remove:
            state = self._messages.pop(msg_id, None)
            if state and state.update_task:
                state.update_task.cancel()
        logger.debug(f"Chat {chat_id}: cleaned up {len(to_remove)} messages")


# Глобальный экземпляр координатора (инициализируется в main.py)
_coordinator: Optional[MessageUpdateCoordinator] = None


def get_coordinator() -> Optional[MessageUpdateCoordinator]:
    """Получить глобальный координатор."""
    return _coordinator


def init_coordinator(bot: Bot) -> MessageUpdateCoordinator:
    """Инициализировать глобальный координатор."""
    global _coordinator
    _coordinator = MessageUpdateCoordinator(bot)
    logger.info("MessageUpdateCoordinator initialized")
    return _coordinator
