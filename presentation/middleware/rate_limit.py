"""
Rate Limiting Middleware для защиты от DoS атак.

Предоставляет настраиваемый rate limiting для Telegram бота.
"""

import time
import logging
from collections import defaultdict
from typing import Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для rate limiting.

    Ограничивает частоту сообщений от пользователей для защиты от DoS.

    Usage:
        # В main.py:
        from presentation.middleware.rate_limit import RateLimitMiddleware

        # 2 сообщения в секунду (default)
        dp.message.middleware(RateLimitMiddleware(rate_limit=0.5))

        # 10 сообщений в минуту
        dp.message.middleware(RateLimitMiddleware(rate_limit=6.0, per_user=True))

        # Custom limits для разных пользователей
        dp.message.middleware(RateLimitMiddleware(
            rate_limit=1.0,  # 1 сообщение в секунду
            admin_ids=[123456789],  # Admins без ограничений
        ))
    """

    def __init__(
        self,
        rate_limit: float = 0.5,
        burst: int = 5,
        per_user: bool = True,
        admin_ids: Optional[list[int]] = None,
        whitelist_ids: Optional[list[int]] = None,
    ):
        """
        Args:
            rate_limit: Минимальный интервал между сообщениями (в секундах)
                       Меньше = быстрее (0.1 = 10 сообщений в секунду)
                       Больше = медленнее (1.0 = 1 сообщение в секунду)
            burst: Максимальное количество сообщений, которые можно отправить мгновенно
            per_user: Применять ли rate limit для каждого пользователя отдельно
            admin_ids: Список admin ID, которые exempt от rate limiting
            whitelist_ids: Список ID пользователей, exempt от rate limiting
        """
        self.rate_limit = rate_limit
        self.burst = burst
        self.per_user = per_user
        self.admin_ids = set(admin_ids or [])
        self.whitelist_ids = set(whitelist_ids or [])

        # Track last message time per user
        self._last_message_time = defaultdict(float)

        # Track message count for burst detection
        self._message_count = defaultdict(int)
        self._burst_window_start = defaultdict(float)

        # Statistics
        self._rate_limited_count = defaultdict(int)
        self._total_messages = defaultdict(int)

        logger.info(
            f"RateLimitMiddleware initialized: "
            f"limit={rate_limit}s, burst={burst}, per_user={per_user}"
        )

    async def __call__(
        self,
        handler,
        event: TelegramObject,
        data: dict
    ):
        """
        Process update and apply rate limiting.

        Returns:
            None if rate limited (blocks the update)
            Handler result otherwise
        """
        # Check if event has from_user
        if not hasattr(event, 'from_user') or event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        current_time = time.time()

        # Skip rate limiting for admins and whitelisted users
        if user_id in self.admin_ids or user_id in self.whitelist_ids:
            return await handler(event, data)

        # Track total messages
        self._total_messages[user_id] += 1

        # Check rate limit
        last_time = self._last_message_time[user_id]
        time_since_last = current_time - last_time

        # Initialize burst window if first message or window expired
        if self._burst_window_start[user_id] == 0:
            self._burst_window_start[user_id] = current_time
            self._message_count[user_id] = 0

        window_age = current_time - self._burst_window_start[user_id]

        # Reset burst window if expired
        if window_age > self.rate_limit * self.burst:
            self._burst_window_start[user_id] = current_time
            self._message_count[user_id] = 0

        # Increment message count
        self._message_count[user_id] += 1

        # Check if burst limit exceeded
        if self._message_count[user_id] > self.burst:
            self._rate_limited_count[user_id] += 1

            # Log warning
            logger.warning(
                f"[{user_id}] Rate limited: {self._message_count[user_id]}/{self.burst} "
                f"messages in {window_age:.2f}s (limit: {self.rate_limit}s)"
            )

            # Send rate limit message to user
            if hasattr(event, 'answer') and callable(event.answer):
                try:
                    wait_time = self.rate_limit - time_since_last
                    await event.answer(
                        f"⏳ Too fast! Please wait {wait_time:.1f}s before sending another message."
                    )
                except Exception as e:
                    logger.debug(f"Could not send rate limit message: {e}")

            return None  # Block the update

        # Check minimum interval
        if time_since_last < self.rate_limit:
            # Too fast!
            self._rate_limited_count[user_id] += 1

            logger.debug(
                f"[{user_id}] Rate limited: {time_since_last:.3f}s < {self.rate_limit}s"
            )

            # Send rate limit message
            if hasattr(event, 'answer') and callable(event.answer):
                try:
                    wait_time = self.rate_limit - time_since_last
                    await event.answer(
                        f"⏳ Too fast! Wait {wait_time:.1f}s"
                    )
                except Exception as e:
                    logger.debug(f"Could not send rate limit message: {e}")

            return None  # Block the update

        # Update last message time
        self._last_message_time[user_id] = current_time

        # Continue with handler
        return await handler(event, data)

    def get_stats(self, user_id: Optional[int] = None) -> dict:
        """
        Get rate limiting statistics.

        Args:
            user_id: Specific user ID or None for global stats

        Returns:
            Dictionary with statistics
        """
        if user_id:
            return {
                "user_id": user_id,
                "total_messages": self._total_messages.get(user_id, 0),
                "rate_limited": self._rate_limited_count.get(user_id, 0),
                "last_message": self._last_message_time.get(user_id, 0),
            }
        else:
            return {
                "total_users": len(self._total_messages),
                "total_messages": sum(self._total_messages.values()),
                "total_rate_limited": sum(self._rate_limited_count.values()),
                "rate_limit": self.rate_limit,
                "burst": self.burst,
            }

    def clear_user(self, user_id: int):
        """Clear rate limit data for specific user"""
        self._last_message_time.pop(user_id, None)
        self._message_count.pop(user_id, None)
        self._burst_window_start.pop(user_id, None)
        self._rate_limited_count.pop(user_id, None)
        self._total_messages.pop(user_id, None)
        logger.debug(f"Cleared rate limit data for user {user_id}")

    def clear_all(self):
        """Clear all rate limit data"""
        self._last_message_time.clear()
        self._message_count.clear()
        self._burst_window_start.clear()
        self._rate_limited_count.clear()
        self._total_messages.clear()
        logger.info("Cleared all rate limit data")


class SmartRateLimitMiddleware(RateLimitMiddleware):
    """
    Умный rate limiting с адаптивными ограничениями.

    Автоматически увеличивает limit для активных пользователей
    и уменьшает для спамеров.
    """

    def __init__(
        self,
        initial_rate_limit: float = 0.5,
        min_rate_limit: float = 0.1,
        max_rate_limit: float = 2.0,
        adjustment_factor: float = 1.5,
        spam_threshold: int = 10,
        **kwargs
    ):
        """
        Args:
            initial_rate_limit: Начальный rate limit
            min_rate_limit: Минимальный rate limit (для спамеров)
            max_rate_limit: Максимальный rate limit (для доверенных пользователей)
            adjustment_factor: Коэффициент ajustment rate limit
            spam_threshold: Порог для определения спамера
            **kwargs: Передаются в RateLimitMiddleware
        """
        super().__init__(rate_limit=initial_rate_limit, **kwargs)

        self.initial_rate_limit = initial_rate_limit
        self.min_rate_limit = min_rate_limit
        self.max_rate_limit = max_rate_limit
        self.adjustment_factor = adjustment_factor
        self.spam_threshold = spam_threshold

        # Per-user rate limits
        self._user_rate_limits = defaultdict(lambda: initial_rate_limit)

        # Spam score per user
        self._spam_score = defaultdict(int)

        logger.info(
            f"SmartRateLimitMiddleware initialized: "
            f"initial={initial_rate_limit}s, min={min_rate_limit}s, max={max_rate_limit}s"
        )

    async def __call__(self, handler, event: TelegramObject, data: dict):
        """Process with adaptive rate limiting"""
        if not hasattr(event, 'from_user') or event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id

        # Skip for admins/whitelist
        if user_id in self.admin_ids or user_id in self.whitelist_ids:
            return await handler(event, data)

        # Get user-specific rate limit
        current_limit = self._user_rate_limits[user_id]
        self.rate_limit = current_limit

        # Call parent handler
        result = await super().__call__(handler, event, data)

        # Adjust rate limit based on behavior
        if result is None:  # Rate limited
            self._spam_score[user_id] += 1

            # Decrease rate limit for spammers
            if self._spam_score[user_id] >= self.spam_threshold:
                new_limit = max(
                    current_limit / self.adjustment_factor,
                    self.min_rate_limit
                )
                self._user_rate_limits[user_id] = new_limit
                logger.warning(
                    f"[{user_id}] Decreased rate limit to {new_limit:.2f}s "
                    f"(spam score: {self._spam_score[user_id]})"
                )
        else:  # Not rate limited
            # Decrease spam score
            self._spam_score[user_id] = max(0, self._spam_score[user_id] - 1)

            # Increase rate limit for good users
            if self._spam_score[user_id] == 0:
                new_limit = min(
                    current_limit * self.adjustment_factor,
                    self.max_rate_limit
                )
                self._user_rate_limits[user_id] = new_limit

        return result
