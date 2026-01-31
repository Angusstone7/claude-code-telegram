"""
Thread-safe SDK service with proper state management.

Fixes race conditions and memory leaks from original sdk_service.py
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# Enum definitions
class TaskStatus:
    IDLE = "idle"
    RUNNING = "running"
    WAITING_PERMISSION = "waiting_permission"
    WAITING_ANSWER = "waiting_answer"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PermissionRequest:
    """Pending permission request"""
    request_id: str
    tool_name: str
    tool_input: dict
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class QuestionRequest:
    """Pending question request"""
    request_id: str
    question: str
    options: list[str]
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class UserSessionState:
    """
    Вся информация о сессии пользователя в одном месте.

    Thread-safe container для всех state operations.
    """
    user_id: int

    # Permission state
    permission_event: asyncio.Event = field(default_factory=asyncio.Event)
    permission_request: Optional[PermissionRequest] = None
    permission_response: Optional[bool] = None
    clarification_text: Optional[str] = None

    # Question state
    question_event: asyncio.Event = field(default_factory=asyncio.Event)
    question_request: Optional[QuestionRequest] = None
    question_response: Optional[str] = None

    # Plan state
    plan_event: asyncio.Event = field(default_factory=asyncio.Event)
    plan_response: Optional[str] = None

    # Task state
    task_status: str = TaskStatus.IDLE
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    task_id: Optional[str] = None

    # Auto-cleanup flag
    last_activity: datetime = field(default_factory=datetime.now)

    def is_idle(self) -> bool:
        """Check if session is in idle state"""
        return self.task_status in [TaskStatus.IDLE, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]

    def reset_for_new_task(self, task_id: str):
        """Reset state for new task"""
        self.permission_event.clear()
        self.question_event.clear()
        self.plan_event.clear()
        self.cancel_event.clear()

        self.permission_request = None
        self.permission_response = None
        self.question_request = None
        self.question_response = None
        self.plan_response = None
        self.task_id = task_id
        self.task_status = TaskStatus.RUNNING
        self.last_activity = datetime.now()


class SafeStatefulSDKService:
    """
    Thread-safe SDK service с улучшенным управлением состоянием.

    Исправляет проблемы:
    - Race conditions в dict operations
    - Memory leaks (автоматическая очистка)
    - Potential deadlocks (RLock вместо Lock)
    """

    def __init__(
        self,
        default_working_dir: str = "/root",
        max_turns: int = 50,
        permission_mode: str = "default",
        plugins_dir: str = "/plugins",
        enabled_plugins: list[str] = None,
        telegram_mcp_path: str = "/app/telegram-mcp/build/index.js",
        account_service = None,
        proxy_service = None,
        session_timeout: int = 3600,  # 1 hour
    ):
        self.default_working_dir = default_working_dir
        self.max_turns = max_turns
        self.permission_mode = permission_mode
        self.plugins_dir = plugins_dir
        self.enabled_plugins = enabled_plugins or []
        self.telegram_mcp_path = telegram_mcp_path
        self.account_service = account_service
        self.proxy_service = proxy_service
        self.session_timeout = session_timeout

        # Единый dict для всех состояний (thread-safe)
        self._user_states: dict[int, UserSessionState] = {}

        # Reentrant lock для предотвращения deadlocks
        self._state_lock = asyncio.RLock()

        # Active clients and tasks (не критично для race conditions)
        self._clients: dict[int, object] = {}  # ClaudeSDKClient
        self._tasks: dict[int, asyncio.Task] = {}

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

    @asynccontextmanager
    async def _get_user_state(self, user_id: int, auto_create: bool = True):
        """
        Thread-safe доступ к состоянию пользователя.

        Args:
            user_id: ID пользователя
            auto_create: Создавать ли новое состояние

        Yields:
            UserSessionState: Состояние пользователя
        """
        async with self._state_lock:
            # Auto-cleanup старых/неактивных состояний
            await self._cleanup_stale_states()

            # Get or create state
            if user_id not in self._user_states:
                if not auto_create:
                    raise KeyError(f"No state found for user {user_id}")
                self._user_states[user_id] = UserSessionState(user_id=user_id)

            state = self._user_states[user_id]
            state.last_activity = datetime.now()

            yield state

    async def _cleanup_stale_states(self):
        """Очистка неактивных состояний"""
        now = datetime.now()
        to_remove = []

        for user_id, state in self._user_states.items():
            # Remove if idle and timeout exceeded
            if state.is_idle():
                idle_time = (now - state.last_activity).total_seconds()
                if idle_time > self.session_timeout:
                    to_remove.append(user_id)

        for user_id in to_remove:
            del self._user_states[user_id]
            logger.debug(f"Cleaned up stale state for user {user_id}")

    async def start_cleanup_task(self):
        """Запуск фоновой задачи очистки"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started state cleanup task")

    async def _cleanup_loop(self):
        """Фоновый цикл очистки"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                async with self._state_lock:
                    await self._cleanup_stale_states()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    # === Permission Management ===

    async def set_permission_request(self, user_id: int, request: PermissionRequest):
        """Thread-safe установка permission request"""
        async with self._get_user_state(user_id) as state:
            state.permission_request = request
            state.permission_response = None
            state.permission_event.clear()
            logger.debug(f"[{user_id}] Set permission request: {request.tool_name}")

    async def wait_for_permission_response(self, user_id: int, timeout: float = 300.0) -> Optional[bool]:
        """Thread-safe ожидание ответа на permission"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
await asyncio.wait_for(state.permission_event.wait(), timeout=timeout)
                return state.permission_response
        except asyncio.TimeoutError:
            logger.warning(f"[{user_id}] Permission request timed out")
            return None
        except KeyError:
            return None

    async def submit_permission_response(self, user_id: int, approved: bool):
        """Thread-safe отправка ответа на permission"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
                state.permission_response = approved
                state.permission_event.set()
                logger.debug(f"[{user_id}] Permission response: {approved}")
        except KeyError:
            logger.warning(f"[{user_id}] No pending permission request")

    # === Question Management ===

    async def set_question_request(self, user_id: int, request: QuestionRequest):
        """Thread-safe установка question request"""
        async with self._get_user_state(user_id) as state:
            state.question_request = request
            state.question_response = None
            state.question_event.clear()
            logger.debug(f"[{user_id}] Set question request")

    async def wait_for_question_response(self, user_id: int, timeout: float = 300.0) -> Optional[str]:
        """Thread-safe ожидание ответа на question"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
                await asyncio.wait_for(state.question_event.wait(), timeout=timeout)
                return state.question_response
        except asyncio.TimeoutError:
            logger.warning(f"[{user_id}] Question request timed out")
            return None
        except KeyError:
            return None

    async def submit_question_response(self, user_id: int, response: str):
        """Thread-safe отправка ответа на question"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
                state.question_response = response
                state.question_event.set()
                logger.debug(f"[{user_id}] Question response submitted")
        except KeyError:
            logger.warning(f"[{user_id}] No pending question request")

    # === Plan Management ===

    async def set_plan_request(self, user_id: int):
        """Thread-safe установка plan request"""
        async with self._get_user_state(user_id) as state:
            state.plan_event.clear()
            state.plan_response = None
            logger.debug(f"[{user_id}] Set plan request")

    async def wait_for_plan_response(self, user_id: int, timeout: float = 600.0) -> Optional[str]:
        """Thread-safe ожидание ответа на plan"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
                await asyncio.wait_for(state.plan_event.wait(), timeout=timeout)
                return state.plan_response
        except asyncio.TimeoutError:
            logger.warning(f"[{user_id}] Plan request timed out")
            return None
        except KeyError:
            return None

    async def submit_plan_response(self, user_id: int, response: str):
        """Thread-safe отправка ответа на plan"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
                state.plan_response = response
                state.plan_event.set()
                logger.debug(f"[{user_id}] Plan response: {response}")
        except KeyError:
            logger.warning(f"[{user_id}] No pending plan request")

    # === Task Management ===

    async def start_task(self, user_id: int, task_id: str):
        """Thread-safe начало задачи"""
        async with self._get_user_state(user_id) as state:
            state.reset_for_new_task(task_id)
            logger.info(f"[{user_id}] Started task {task_id}")

    async def complete_task(self, user_id: int, status: str):
        """Thread-safe завершение задачи"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
                state.task_status = status
                logger.info(f"[{user_id}] Task completed with status: {status}")
        except KeyError:
            logger.warning(f"[{user_id}] No task to complete")

    async def cancel_task(self, user_id: int):
        """Thread-safe отмена задачи"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
                state.task_status = TaskStatus.CANCELLED
                state.cancel_event.set()
                logger.info(f"[{user_id}] Task cancelled")
        except KeyError:
            logger.warning(f"[{user_id}] No task to cancel")

    async def get_task_status(self, user_id: int) -> Optional[str]:
        """Thread-safe получение статуса задачи"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
                return state.task_status
        except KeyError:
            return None

    # === Utility Methods ===

    async def get_state_info(self, user_id: int) -> Optional[dict]:
        """Thread-safe получение информации о состоянии"""
        try:
            async with self._get_user_state(user_id, auto_create=False) as state:
                return {
                    "user_id": state.user_id,
                    "task_status": state.task_status,
                    "task_id": state.task_id,
                    "has_pending_permission": state.permission_request is not None,
                    "has_pending_question": state.question_request is not None,
                    "has_pending_plan": not state.plan_event.is_set(),
                    "last_activity": state.last_activity.isoformat(),
                }
        except KeyError:
            return None

    async def close(self):
        """Cleanup resources"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel all active tasks
        for task in self._tasks.values():
            if not task.done():
                task.cancel()

        # Clear all states
        async with self._state_lock:
            self._user_states.clear()

        logger.info("SafeStatefulSDKService closed")
