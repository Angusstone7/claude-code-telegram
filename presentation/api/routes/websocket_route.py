"""WebSocket route for real-time chat with Claude Code."""

import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from infrastructure.websocket.message_types import (
    parse_client_message,
    ClientChatMessage,
    ClientHITLResponse,
    ClientQuestionAnswer,
    ClientPlanResponse,
    ClientCancelTask,
    ClientPing,
    ServerStreamChunk,
    ServerStreamEnd,
    ServerHITLRequest,
    ServerHITLResolved,
    ServerQuestion,
    ServerPlan,
    ServerTaskStatus,
    ServerSessionBusy,
    ServerToolUse,
    ServerError,
    ServerPong,
    ToolInput,
)
from presentation.api.dependencies import get_container

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


def _surrogate_user_id(user_id_str: str) -> int:
    """Derive a stable positive integer ID from a web user's string UUID.

    The SDK service uses positive Telegram user IDs (typically 6-10 digits).
    To avoid collisions we use the 2_000_000_000+ range which is above
    typical Telegram IDs.
    """
    return 2_000_000_000 + (abs(hash(user_id_str)) % (10**9))


async def _resolve_sdk_user_id(auth_service, user_id_str: str, container=None) -> int:
    """Return the integer user ID the SDK service should use.

    Resolution order:
    1. If the web user has a linked ``telegram_id``, use it directly so that
       the SDK session is shared with the Telegram interface.
    2. Fall back to the first admin Telegram ID from config so that the admin
       panel shares account settings (auth mode, proxy, model) with the
       Telegram bot.
    3. Last resort: deterministic surrogate from the UUID.
    """
    try:
        web_user = await auth_service.get_user(user_id_str)
        if web_user and web_user.telegram_id:
            return web_user.telegram_id
    except Exception:
        logger.debug("Failed to look up web user %s for telegram_id", user_id_str)

    # Fall back to the first configured admin Telegram ID so that
    # web users inherit the same SDK settings (auth mode, proxy, etc.)
    if container:
        try:
            admin_ids = container.config.admin_ids
            if admin_ids:
                logger.info("WS user %s: using admin Telegram ID %d for SDK", user_id_str, admin_ids[0])
                return admin_ids[0]
        except Exception:
            pass

    return _surrogate_user_id(user_id_str)


async def _resolve_working_dir(
    project_service, user_id_int: int, default: str = "/root"
) -> str:
    """Get the working directory for the user's active project."""
    try:
        from domain.value_objects.user_id import UserId

        project = await project_service.get_current(UserId(user_id_int))
        if project and project.path:
            return str(project.path)
    except Exception:
        logger.debug("Could not resolve working dir for user %d", user_id_int)
    return default


async def _send_ws_json(websocket: WebSocket, model) -> None:
    """Send a Pydantic model as JSON over the WebSocket, swallowing errors."""
    try:
        await websocket.send_json(model.model_dump(mode="json"))
    except Exception:
        logger.debug("Failed to send WS message: %s", type(model).__name__)


@router.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
) -> None:
    """Real-time chat with Claude Code over WebSocket.

    Protocol:
        1. Client connects with a JWT token in the ``token`` query parameter.
        2. Server verifies the token and accepts the connection.
        3. Client sends JSON messages (see ``message_types.py`` for schemas).
        4. Server streams responses back as JSON messages.
    """
    container = get_container()

    # --- 1. Authenticate ---
    auth_service = container.auth_service()
    claims = auth_service.verify_access_token(token)
    if claims is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id_str: str = claims.sub  # UUID string from JWT
    username: str = claims.username

    # --- 2. Resolve integer user ID for SDK ---
    user_id_int = await _resolve_sdk_user_id(auth_service, user_id_str, container=container)

    # --- 3. Connect via ConnectionManager ---
    conn_manager = container.connection_manager()
    conn = await conn_manager.connect(websocket, user_id_str, session_id)

    # --- 4. Obtain shared services ---
    event_bus = container.event_bus()
    sdk = container.claude_sdk()
    project_service = container.project_service()

    # Subscriber ID unique to this WS connection
    subscriber_id = f"ws:{user_id_str}:{session_id}:{uuid.uuid4().hex[:8]}"

    # Mutable container so the receive loop can update the running task
    # reference and the finally block can cancel it on disconnect.
    running_task_holder: list[Optional[asyncio.Task]] = [None]

    # ------------------------------------------------------------------
    # EventBus subscriber: receives notifications when HITL is resolved
    # by *another* interface (e.g. Telegram).
    # ------------------------------------------------------------------

    async def _on_hitl_resolved(data: dict) -> None:
        """Forward HITL resolution from EventBus to this WebSocket."""
        try:
            resolved_msg = ServerHITLResolved(
                request_id=data.get("request_id", ""),
                approved=data.get("approved", False),
                resolved_by=data.get("resolved_by", "unknown"),
            )
            await _send_ws_json(websocket, resolved_msg)
        except Exception:
            logger.debug("Failed to forward hitl_resolved to WS %s", subscriber_id)

    # Subscribe to HITL resolved events for this user.
    hitl_channel = f"hitl:{user_id_int}"
    hitl_resolved_channel = f"hitl:{user_id_int}_resolved"
    event_bus.subscribe(hitl_resolved_channel, subscriber_id, _on_hitl_resolved)

    # ------------------------------------------------------------------

    try:
        await _receive_loop(
            websocket=websocket,
            session_id=session_id,
            user_id_str=user_id_str,
            user_id_int=user_id_int,
            username=username,
            sdk=sdk,
            event_bus=event_bus,
            project_service=project_service,
            conn_manager=conn_manager,
            hitl_channel=hitl_channel,
            subscriber_id=subscriber_id,
            running_task_holder=running_task_holder,
        )
    except WebSocketDisconnect:
        logger.info(
            "WS disconnected: user='%s' session='%s'", username, session_id
        )
    except Exception:
        logger.exception(
            "Unexpected error in WS loop: user='%s' session='%s'",
            username,
            session_id,
        )
    finally:
        # --- Cleanup ---
        event_bus.unsubscribe(hitl_resolved_channel, subscriber_id)
        event_bus.unsubscribe(hitl_channel, subscriber_id)
        await conn_manager.disconnect(conn)

        # Cancel in-flight SDK task if the client disappeared.
        task = running_task_holder[0]
        if task is not None and not task.done():
            task.cancel()
            logger.info(
                "Cancelled in-flight task on WS disconnect: user='%s' session='%s'",
                username,
                session_id,
            )

        logger.debug("WS cleanup complete for %s", subscriber_id)


async def _receive_loop(
    *,
    websocket: WebSocket,
    session_id: str,
    user_id_str: str,
    user_id_int: int,
    username: str,
    sdk,
    event_bus,
    project_service,
    conn_manager,
    hitl_channel: str,
    subscriber_id: str,
    running_task_holder: list,
) -> None:
    """Main receive loop — reads JSON frames from the client."""

    while True:
        raw = await websocket.receive_json()

        try:
            msg = parse_client_message(raw)
        except (ValueError, Exception) as exc:
            await _send_ws_json(
                websocket,
                ServerError(message=f"Invalid message: {exc}", code="PARSE_ERROR"),
            )
            continue

        # --- Dispatch by message type ---

        if isinstance(msg, ClientPing):
            await _send_ws_json(websocket, ServerPong())

        elif isinstance(msg, ClientChatMessage):
            await _handle_chat_message(
                websocket=websocket,
                msg=msg,
                session_id=session_id,
                user_id_str=user_id_str,
                user_id_int=user_id_int,
                sdk=sdk,
                event_bus=event_bus,
                project_service=project_service,
                hitl_channel=hitl_channel,
                running_task_holder=running_task_holder,
            )

        elif isinstance(msg, ClientHITLResponse):
            await _handle_hitl_response(
                msg=msg,
                user_id_int=user_id_int,
                sdk=sdk,
                event_bus=event_bus,
            )

        elif isinstance(msg, ClientQuestionAnswer):
            await _handle_question_answer(
                msg=msg,
                user_id_int=user_id_int,
                sdk=sdk,
                event_bus=event_bus,
            )

        elif isinstance(msg, ClientPlanResponse):
            await _handle_plan_response(
                msg=msg,
                user_id_int=user_id_int,
                sdk=sdk,
                event_bus=event_bus,
            )

        elif isinstance(msg, ClientCancelTask):
            await _handle_cancel_task(
                websocket=websocket,
                user_id_int=user_id_int,
                sdk=sdk,
                running_task_holder=running_task_holder,
            )

        else:
            await _send_ws_json(
                websocket,
                ServerError(
                    message=f"Unsupported message type: {type(msg).__name__}",
                    code="UNSUPPORTED",
                ),
            )


# ------------------------------------------------------------------
# Handler: chat_message
# ------------------------------------------------------------------


async def _handle_chat_message(
    *,
    websocket: WebSocket,
    msg: ClientChatMessage,
    session_id: str,
    user_id_str: str,
    user_id_int: int,
    sdk,
    event_bus,
    project_service,
    hitl_channel: str,
    running_task_holder: list,
) -> None:
    """Process a chat message — start a Claude task in the background."""

    if sdk is None:
        await _send_ws_json(
            websocket,
            ServerError(
                message="Claude SDK backend not available",
                code="SDK_UNAVAILABLE",
            ),
        )
        return

    # Check if a task is already running for this user.
    if sdk.is_task_running(user_id_int):
        await _send_ws_json(websocket, ServerSessionBusy())
        return

    # Resolve working directory from the user's active project.
    working_dir = await _resolve_working_dir(project_service, user_id_int)

    # A unique ID for streaming chunks of this particular response.
    message_id = uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Build SDK callbacks that push messages over the WebSocket.
    # ------------------------------------------------------------------

    async def on_text(text: str) -> None:
        await _send_ws_json(
            websocket,
            ServerStreamChunk(content=text, message_id=message_id),
        )

    async def on_tool_use(tool_name: str, tool_input: dict) -> None:
        await _send_ws_json(
            websocket,
            ServerToolUse(
                tool_name=tool_name,
                tool_input=ToolInput(**tool_input) if tool_input else ToolInput(),
            ),
        )

    async def on_permission_request(
        request_id: str, tool_name: str, tool_input: dict
    ) -> None:
        description = f"{tool_name}: {_summarise_tool_input(tool_input)}"
        hitl_msg = ServerHITLRequest(
            request_id=request_id,
            tool_name=tool_name,
            tool_input=ToolInput(**tool_input) if tool_input else ToolInput(),
            description=description,
        )
        # Send to WebSocket.
        await _send_ws_json(websocket, hitl_msg)
        # Publish to EventBus so Telegram (or other interfaces) can respond.
        await event_bus.publish(
            hitl_channel,
            {
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "description": description,
            },
        )

    async def on_permission_completed(approved: bool) -> None:
        # No-op for WS — the HITL resolved notification arrives via EventBus.
        pass

    async def on_question(question: str, options: list[str]) -> None:
        req_id = uuid.uuid4().hex
        question_msg = ServerQuestion(
            request_id=req_id,
            question=question,
            options=options if options else None,
        )
        await _send_ws_json(websocket, question_msg)
        # Also publish so Telegram can answer.
        await event_bus.publish(
            hitl_channel,
            {
                "type": "question",
                "request_id": req_id,
                "question": question,
                "options": options,
            },
        )

    async def on_question_completed(answer: str) -> None:
        pass

    async def on_plan_request(content: str, metadata: dict) -> None:
        req_id = uuid.uuid4().hex
        plan_msg = ServerPlan(request_id=req_id, content=content)
        await _send_ws_json(websocket, plan_msg)
        await event_bus.publish(
            hitl_channel,
            {
                "type": "plan",
                "request_id": req_id,
                "content": content,
                "metadata": metadata,
            },
        )

    async def on_thinking(text: str) -> None:
        # Forward thinking as stream chunks with a distinct marker so the
        # client can style them differently if desired.
        pass

    async def on_error(error_msg: str) -> None:
        await _send_ws_json(
            websocket,
            ServerError(message=error_msg, code="TASK_ERROR"),
        )

    # ------------------------------------------------------------------
    # Launch the task in the background so the WS loop stays responsive.
    # ------------------------------------------------------------------

    async def _run_task() -> None:
        await _send_ws_json(
            websocket,
            ServerTaskStatus(status="running", message="Task started"),
        )

        try:
            result = await sdk.run_task(
                user_id=user_id_int,
                prompt=msg.content,
                working_dir=working_dir,
                session_id=session_id,
                on_text=on_text,
                on_tool_use=on_tool_use,
                on_tool_result=None,
                on_permission_request=on_permission_request,
                on_permission_completed=on_permission_completed,
                on_question=on_question,
                on_question_completed=on_question_completed,
                on_plan_request=on_plan_request,
                on_thinking=on_thinking,
                on_error=on_error,
            )

            # Send stream-end with metadata.
            await _send_ws_json(
                websocket,
                ServerStreamEnd(
                    message_id=message_id,
                    cost_usd=result.total_cost_usd,
                    duration_ms=result.duration_ms,
                    session_id=result.session_id,
                ),
            )

            if result.cancelled:
                status = "cancelled"
                status_message = "Task cancelled"
            elif result.success:
                status = "completed"
                status_message = "Task completed"
            else:
                status = "error"
                status_message = result.error or "Task failed"

            await _send_ws_json(
                websocket,
                ServerTaskStatus(status=status, message=status_message),
            )

        except asyncio.CancelledError:
            await _send_ws_json(
                websocket,
                ServerStreamEnd(message_id=message_id),
            )
            await _send_ws_json(
                websocket,
                ServerTaskStatus(status="cancelled", message="Task cancelled"),
            )
        except Exception as exc:
            logger.exception("SDK task failed for user %s", user_id_int)
            await _send_ws_json(
                websocket,
                ServerError(message=str(exc), code="TASK_EXCEPTION"),
            )
            await _send_ws_json(
                websocket,
                ServerStreamEnd(message_id=message_id),
            )
            await _send_ws_json(
                websocket,
                ServerTaskStatus(status="error", message=str(exc)),
            )

    task = asyncio.create_task(_run_task())
    running_task_holder[0] = task


# ------------------------------------------------------------------
# Handler: hitl_response
# ------------------------------------------------------------------


async def _handle_hitl_response(
    *,
    msg: ClientHITLResponse,
    user_id_int: int,
    sdk,
    event_bus,
) -> None:
    """Web client responded to an HITL permission request."""
    # Notify EventBus (first-response-wins).
    await event_bus.respond(
        msg.request_id,
        {"approved": msg.approved},
        "web",
    )
    # Also directly resolve the SDK's pending permission so the task
    # continues even if the EventBus path wasn't wired to the SDK.
    if sdk is not None:
        await sdk.respond_to_permission(user_id_int, msg.approved)


# ------------------------------------------------------------------
# Handler: question_answer
# ------------------------------------------------------------------


async def _handle_question_answer(
    *,
    msg: ClientQuestionAnswer,
    user_id_int: int,
    sdk,
    event_bus,
) -> None:
    """Web client answered a question from Claude."""
    await event_bus.respond(
        msg.request_id,
        {"answer": msg.answer},
        "web",
    )
    if sdk is not None:
        await sdk.respond_to_question(user_id_int, msg.answer)


# ------------------------------------------------------------------
# Handler: plan_response
# ------------------------------------------------------------------


async def _handle_plan_response(
    *,
    msg: ClientPlanResponse,
    user_id_int: int,
    sdk,
    event_bus,
) -> None:
    """Web client responded to a plan approval request."""
    if msg.approved:
        response_str = "approve"
    elif msg.feedback:
        response_str = f"clarify:{msg.feedback}"
    else:
        response_str = "reject"

    await event_bus.respond(
        msg.request_id,
        {"approved": msg.approved, "feedback": msg.feedback},
        "web",
    )
    if sdk is not None:
        await sdk.respond_to_plan(user_id_int, response_str)


# ------------------------------------------------------------------
# Handler: cancel_task
# ------------------------------------------------------------------


async def _handle_cancel_task(
    *,
    websocket: WebSocket,
    user_id_int: int,
    sdk,
    running_task_holder: list,
) -> None:
    """Cancel the currently running task."""
    cancelled = False

    if sdk is not None:
        cancelled = await sdk.cancel_task(user_id_int)

    # Also cancel the asyncio task wrapper.
    task: Optional[asyncio.Task] = running_task_holder[0]
    if task and not task.done():
        task.cancel()
        cancelled = True

    status = "cancelled" if cancelled else "error"
    message = "Task cancelled" if cancelled else "No running task to cancel"
    await _send_ws_json(
        websocket,
        ServerTaskStatus(status=status, message=message),
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _summarise_tool_input(tool_input: dict, max_len: int = 120) -> str:
    """Create a short human-readable summary of tool input for HITL descriptions."""
    if not tool_input:
        return "(no input)"

    # Common patterns: command, file_path, content, query …
    for key in ("command", "file_path", "path", "query", "content", "url"):
        if key in tool_input:
            val = str(tool_input[key])
            if len(val) > max_len:
                val = val[:max_len] + "..."
            return val

    # Fallback: serialize keys
    keys = ", ".join(tool_input.keys())
    if len(keys) > max_len:
        keys = keys[:max_len] + "..."
    return keys
