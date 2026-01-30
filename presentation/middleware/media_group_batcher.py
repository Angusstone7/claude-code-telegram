"""
Media Group Batcher

Собирает все сообщения из одной медиагруппы (альбома) перед обработкой.

Telegram отправляет каждый файл из альбома как отдельное сообщение,
но все они имеют одинаковый media_group_id. Этот батчер:
1. Собирает все сообщения с одинаковым media_group_id
2. Ждёт короткий таймаут (0.5с) для получения всех файлов
3. Вызывает callback со списком всех сообщений группы
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Awaitable, Optional
from datetime import datetime

from aiogram.types import Message

logger = logging.getLogger(__name__)


@dataclass
class PendingMediaGroup:
    """Ожидающая медиагруппа"""
    media_group_id: str
    user_id: int
    messages: List[Message] = field(default_factory=list)
    timer_task: Optional[asyncio.Task] = None
    created_at: datetime = field(default_factory=datetime.now)


class MediaGroupBatcher:
    """
    Собирает сообщения из одной медиагруппы (альбома).

    Логика:
    1. Первое сообщение с media_group_id запускает таймер
    2. Все последующие сообщения с тем же media_group_id добавляются в группу
    3. Когда таймер срабатывает - вызывается callback со всеми сообщениями

    Использование:
        batcher = MediaGroupBatcher()

        async def process_album(messages: List[Message]):
            # Обработать все файлы альбома
            pass

        # В handler:
        if message.media_group_id:
            await batcher.add_message(message, process_album)
            return  # Обработка произойдёт позже
    """

    BATCH_DELAY = 0.5  # секунды - время ожидания всех файлов альбома

    def __init__(self, batch_delay: float = 0.5):
        self.batch_delay = batch_delay
        self._groups: Dict[str, PendingMediaGroup] = {}  # media_group_id -> group
        self._lock = asyncio.Lock()

    def is_collecting(self, media_group_id: str) -> bool:
        """Проверить, собирается ли группа"""
        return media_group_id in self._groups

    async def add_message(
        self,
        message: Message,
        process_callback: Callable[[List[Message]], Awaitable[None]]
    ) -> bool:
        """
        Добавить сообщение в медиагруппу.

        Args:
            message: Сообщение с media_group_id
            process_callback: Функция для обработки собранных сообщений
                             Сигнатура: (messages: List[Message]) -> None

        Returns:
            True если сообщение добавлено в batch
        """
        media_group_id = message.media_group_id
        if not media_group_id:
            return False

        user_id = message.from_user.id

        async with self._lock:
            if media_group_id not in self._groups:
                # Первое сообщение группы - создаём batch
                self._groups[media_group_id] = PendingMediaGroup(
                    media_group_id=media_group_id,
                    user_id=user_id,
                    messages=[message]
                )
                logger.info(
                    f"[{user_id}] Media group {media_group_id[:8]}... started, "
                    f"first file: {self._get_file_info(message)}"
                )
            else:
                # Добавляем к существующей группе
                group = self._groups[media_group_id]
                group.messages.append(message)

                # Отменяем старый таймер
                if group.timer_task and not group.timer_task.done():
                    group.timer_task.cancel()
                    try:
                        await asyncio.wait_for(group.timer_task, timeout=0.1)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass

                logger.debug(
                    f"[{user_id}] Media group {media_group_id[:8]}... "
                    f"added file #{len(group.messages)}: {self._get_file_info(message)}"
                )

            # Запускаем/перезапускаем таймер
            group = self._groups[media_group_id]
            group.timer_task = asyncio.create_task(
                self._process_after_delay(media_group_id, process_callback)
            )

        return True

    async def _process_after_delay(
        self,
        media_group_id: str,
        process_callback: Callable[[List[Message]], Awaitable[None]]
    ):
        """Обработать группу после задержки"""
        try:
            await asyncio.sleep(self.batch_delay)

            async with self._lock:
                group = self._groups.pop(media_group_id, None)

            if not group or not group.messages:
                return

            # Сортируем по message_id для правильного порядка
            group.messages.sort(key=lambda m: m.message_id)

            logger.info(
                f"[{group.user_id}] Media group {media_group_id[:8]}... complete: "
                f"{len(group.messages)} files"
            )

            # Вызываем callback
            await process_callback(group.messages)

        except asyncio.CancelledError:
            # Таймер отменён - новое сообщение пришло
            pass
        except Exception as e:
            logger.error(f"Error processing media group {media_group_id}: {e}", exc_info=True)
            # Очищаем группу при ошибке
            async with self._lock:
                self._groups.pop(media_group_id, None)

    def _get_file_info(self, message: Message) -> str:
        """Получить информацию о файле для логирования"""
        if message.photo:
            photo = message.photo[-1]
            return f"photo ({photo.file_size or 0} bytes)"
        elif message.document:
            doc = message.document
            return f"{doc.file_name or 'document'} ({doc.file_size or 0} bytes)"
        else:
            return "unknown"

    async def cancel_group(self, media_group_id: str) -> List[Message]:
        """
        Отменить группу и вернуть накопленные сообщения.
        """
        async with self._lock:
            group = self._groups.pop(media_group_id, None)

            if group:
                if group.timer_task and not group.timer_task.done():
                    group.timer_task.cancel()
                return group.messages

            return []

    def get_group_size(self, media_group_id: str) -> int:
        """Получить текущий размер группы"""
        group = self._groups.get(media_group_id)
        return len(group.messages) if group else 0


# Глобальный экземпляр (создаётся в main.py или container)
_media_group_batcher: Optional[MediaGroupBatcher] = None


def get_media_group_batcher() -> Optional[MediaGroupBatcher]:
    """Получить глобальный batcher"""
    return _media_group_batcher


def init_media_group_batcher(batch_delay: float = 0.5) -> MediaGroupBatcher:
    """Инициализировать глобальный batcher"""
    global _media_group_batcher
    _media_group_batcher = MediaGroupBatcher(batch_delay=batch_delay)
    logger.info(f"MediaGroupBatcher initialized (delay={batch_delay}s)")
    return _media_group_batcher
