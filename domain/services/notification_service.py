from abc import ABC, abstractmethod
from typing import List, Optional
from enum import Enum


class NotificationPriority(Enum):
    """Priority levels for notifications"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Notification:
    """Notification entity"""

    def __init__(
        self,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        recipients: Optional[List[int]] = None,
    ):
        self.title = title
        self.message = message
        self.priority = priority
        self.recipients = recipients or []


class INotificationService(ABC):
    """Interface for notification service"""

    @abstractmethod
    async def send_notification(self, notification: Notification) -> bool:
        """Send notification to recipients"""
        pass

    @abstractmethod
    async def send_to_user(self, user_id: int, message: str) -> bool:
        """Send message to specific user"""
        pass

    @abstractmethod
    async def broadcast(self, message: str, roles: Optional[List[str]] = None) -> bool:
        """Broadcast message to users with specific roles"""
        pass

    @abstractmethod
    async def send_alert(
        self,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.HIGH,
    ) -> bool:
        """Send alert notification"""
        pass
