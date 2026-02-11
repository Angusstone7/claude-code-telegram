"""Pydantic models for WebSocket messages per contracts/websocket.md."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


# --- Shared typed model for tool input (Constitution VIII) ---


class ToolInput(BaseModel):
    """Dynamic tool input — schema varies per tool."""

    model_config = ConfigDict(extra="allow")


# --- Client → Server ---


class ClientChatMessage(BaseModel):
    type: Literal["chat_message"] = "chat_message"
    content: str
    context_id: Optional[int] = None


class ClientHITLResponse(BaseModel):
    type: Literal["hitl_response"] = "hitl_response"
    request_id: str
    approved: bool


class ClientQuestionAnswer(BaseModel):
    type: Literal["question_answer"] = "question_answer"
    request_id: str
    answer: str


class ClientPlanResponse(BaseModel):
    type: Literal["plan_response"] = "plan_response"
    request_id: str
    approved: bool
    feedback: Optional[str] = None


class ClientCancelTask(BaseModel):
    type: Literal["cancel_task"] = "cancel_task"


class ClientPing(BaseModel):
    type: Literal["ping"] = "ping"


# --- Server → Client ---


class ServerStreamChunk(BaseModel):
    type: Literal["stream_chunk"] = "stream_chunk"
    content: str
    message_id: str


class ServerStreamEnd(BaseModel):
    type: Literal["stream_end"] = "stream_end"
    message_id: str
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    session_id: Optional[str] = None


class ServerHITLRequest(BaseModel):
    type: Literal["hitl_request"] = "hitl_request"
    request_id: str
    tool_name: str
    tool_input: ToolInput
    description: str


class ServerHITLResolved(BaseModel):
    type: Literal["hitl_resolved"] = "hitl_resolved"
    request_id: str
    approved: bool
    resolved_by: str


class ServerQuestion(BaseModel):
    type: Literal["question"] = "question"
    request_id: str
    question: str
    options: Optional[list[str]] = None


class ServerPlan(BaseModel):
    type: Literal["plan"] = "plan"
    request_id: str
    content: str


class ServerTaskStatus(BaseModel):
    type: Literal["task_status"] = "task_status"
    status: str  # "running" | "completed" | "error" | "cancelled"
    message: Optional[str] = None


class ServerSessionBusy(BaseModel):
    type: Literal["session_busy"] = "session_busy"
    message: str = "Задача уже выполняется в этой сессии"
    busy_since: Optional[datetime] = None


class ServerToolUse(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    tool_name: str
    tool_input: ToolInput
    result: Optional[str] = None


class ServerError(BaseModel):
    type: Literal["error"] = "error"
    message: str
    code: Optional[str] = None


class ServerPong(BaseModel):
    type: Literal["pong"] = "pong"


# --- Message type discriminators for parsing ---

CLIENT_MESSAGE_TYPES = {
    "chat_message": ClientChatMessage,
    "hitl_response": ClientHITLResponse,
    "question_answer": ClientQuestionAnswer,
    "plan_response": ClientPlanResponse,
    "cancel_task": ClientCancelTask,
    "ping": ClientPing,
}


def parse_client_message(data: dict) -> BaseModel:
    """Parse a raw dict into the appropriate client message type."""
    msg_type = data.get("type")
    model_class = CLIENT_MESSAGE_TYPES.get(msg_type)
    if model_class is None:
        raise ValueError(f"Unknown client message type: {msg_type}")
    return model_class.model_validate(data)
