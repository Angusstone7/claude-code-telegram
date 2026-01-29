"""
Message Batcher Middleware

Объединяет несколько сообщений от одного пользователя,
пришедших за короткий промежуток времени (0.5с), в один запрос.

Это решает проблему, когда пользователь отправляет несколько сообщений подряд
и каждое из них запускает отдельную задачу Claude.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Awaitable, Optional, Any
from datetime import datetime

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


@dataclass
class PendingBatch:
    """Ожидающий batch сообщений"""
    messages: List[Message] = field(default_factory=list)
    timer_task: Optional[asyncio.Task] = None
    created_at: datetime = field(default_factory=datetime.now)


class MessageBatcher:
    """
    Собирает несколько сообщений от одного пользователя в batch.

    Логика:
    1. Первое сообщение запускает таймер на BATCH_DELAY секунд
    2. Каждое новое сообщение добавляется в batch и сбрасывает таймер
    3. Когда таймер срабатывает - все сообщения объединяются и обрабатываются

    Особые случаи (НЕ батчуются, обрабатываются сразу):
    - Команды (/start, /cancel и т.д.)
    - Документы и фото
    - Сообщения во время ожидания ввода (HITL, переменные)
    """

    BATCH_DELAY = 0.5  # секунды

    def __init__(self, batch_delay: float = 0.5):
        self.batch_delay = batch_delay
        self._batches: Dict[int, PendingBatch] = {}
        self._lock = asyncio.Lock()

    def is_batching(self, user_id: int) -> bool:
        """Проверить, есть ли активный batch для пользователя"""
        return user_id in self._batches

    async def add_message(
        self,
        message: Message,
        process_callback: Callable[[Message, str], Awaitable[None]]
    ) -> bool:
        """
        Добавить сообщение в batch.

        Args:
            message: Telegram сообщение
            process_callback: Функция для обработки объединённых сообщений
                             Сигнатура: (original_message, combined_text) -> None

        Returns:
            True если сообщение добавлено в batch,
            False если batch обработан сразу
        """
        user_id = message.from_user.id
        text = message.text or ""

        async with self._lock:
            if user_id not in self._batches:
                # Первое сообщение - создаём batch
                self._batches[user_id] = PendingBatch(messages=[message])
                logger.debug(f"[{user_id}] Created new batch with message: {text[:50]}...")
            else:
                # Добавляем к существующему batch
                batch = self._batches[user_id]
                batch.messages.append(message)

                # Отменяем старый таймер
                if batch.timer_task and not batch.timer_task.done():
                    batch.timer_task.cancel()
                    try:
                        await batch.timer_task
                    except asyncio.CancelledError:
                        pass

                logger.debug(f"[{user_id}] Added to batch ({len(batch.messages)} messages): {text[:50]}...")

            # Запускаем новый таймер
            batch = self._batches[user_id]
            batch.timer_task = asyncio.create_task(
                self._process_after_delay(user_id, process_callback)
            )

        return True

    async def _process_after_delay(
        self,
        user_id: int,
        process_callback: Callable[[Message, str], Awaitable[None]]
    ):
        """Обработать batch после задержки"""
        try:
            await asyncio.sleep(self.batch_delay)

            async with self._lock:
                batch = self._batches.pop(user_id, None)

            if not batch or not batch.messages:
                return

            # Объединяем все тексты
            texts = [m.text for m in batch.messages if m.text]
            combined_text = "\n\n".join(texts)

            # Используем первое сообщение как основу
            first_message = batch.messages[0]

            msg_count = len(batch.messages)
            if msg_count > 1:
                logger.info(
                    f"[{user_id}] Batched {msg_count} messages into one request"
                )

            # Вызываем callback с объединённым текстом
            await process_callback(first_message, combined_text)

        except asyncio.CancelledError:
            # Таймер отменён - новое сообщение пришло
            pass
        except Exception as e:
            logger.error(f"[{user_id}] Error processing batch: {e}", exc_info=True)
            # Пробуем очистить batch при ошибке
            async with self._lock:
                self._batches.pop(user_id, None)

    async def cancel_batch(self, user_id: int) -> List[Message]:
        """
        Отменить batch и вернуть накопленные сообщения.
        Используется когда нужно обработать сообщения немедленно.
        """
        async with self._lock:
            batch = self._batches.pop(user_id, None)

            if batch:
                if batch.timer_task and not batch.timer_task.done():
                    batch.timer_task.cancel()
                return batch.messages

            return []

    async def flush_batch(
        self,
        user_id: int,
        process_callback: Callable[[Message, str], Awaitable[None]]
    ) -> bool:
        """
        Принудительно обработать batch сейчас (без ожидания таймера).
        Возвращает True если batch был обработан.
        """
        messages = await self.cancel_batch(user_id)

        if messages:
            texts = [m.text for m in messages if m.text]
            combined_text = "\n\n".join(texts)
            await process_callback(messages[0], combined_text)
            return True

        return False


class MessageBatcherMiddleware(BaseMiddleware):
    """
    Aiogram middleware для batching сообщений.

    Перехватывает текстовые сообщения и объединяет их.
    Пропускает без изменений:
    - Команды (начинаются с /)
    - Документы и фото
    - Callback queries
    """

    def __init__(
        self,
        batcher: MessageBatcher,
        should_batch_callback: Optional[Callable[[Message], Awaitable[bool]]] = None
    ):
        """
        Args:
            batcher: Экземпляр MessageBatcher
            should_batch_callback: Функция для проверки нужно ли батчить сообщение.
                                   Если None - батчатся все текстовые сообщения без команд.
        """
        self.batcher = batcher
        self.should_batch_callback = should_batch_callback
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Работаем только с сообщениями
        if not isinstance(event, Message):
            return await handler(event, data)

        message: Message = event

        # Проверяем нужно ли батчить
        should_batch = await self._should_batch(message)

        if not should_batch:
            # Обрабатываем сразу
            return await handler(event, data)

        # Добавляем в batch
        async def process_batched(first_message: Message, combined_text: str):
            # Создаём data с объединённым текстом
            data['batched_text'] = combined_text
            data['is_batched'] = True
            data['batch_original_text'] = first_message.text
            await handler(first_message, data)

        await self.batcher.add_message(message, process_batched)

        # Возвращаем None - сообщение будет обработано позже
        return None

    async def _should_batch(self, message: Message) -> bool:
        """Определить нужно ли батчить сообщение"""
        # Не батчим если нет текста
        if not message.text:
            return False

        # Не батчим команды
        if message.text.startswith('/'):
            return False

        # Не батчим документы и фото
        if message.document or message.photo:
            return False

        # Если есть custom callback - используем его
        if self.should_batch_callback:
            return await self.should_batch_callback(message)

        return True
