// ---------------------------------------------------------------------------
// useWebSocket — React hook wrapping WebSocketManager for component use
// ---------------------------------------------------------------------------

import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { WebSocketManager } from '@/services/websocket'
import type { ServerMessage } from '@/types/websocket'

// ── Types ────────────────────────────────────────────────────────────────────

type OnMessageCallback = (message: ServerMessage) => void

interface UseWebSocketOptions {
  /** Called for every server message received on the socket. */
  onMessage?: OnMessageCallback
}

interface UseWebSocketReturn {
  /** Whether the WebSocket is currently connected. */
  isConnected: boolean
  /** Whether the manager is attempting to reconnect. */
  isReconnecting: boolean

  /** Send a chat message to the current session. */
  sendMessage: (content: string) => void
  /** Respond to a HITL (Human-in-the-Loop) permission request. */
  sendHITLResponse: (requestId: string, approved: boolean) => void
  /** Answer a question posed by the agent. */
  sendQuestionAnswer: (requestId: string, answer: string) => void
  /** Respond to a plan approval request. */
  sendPlanResponse: (requestId: string, approved: boolean, feedback?: string) => void
  /** Cancel the currently running task. */
  cancelTask: () => void
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useWebSocket(
  sessionId: string | null,
  options: UseWebSocketOptions = {},
): UseWebSocketReturn {
  const { onMessage } = options

  const accessToken = useAuthStore((s) => s.accessToken)
  const managerRef = useRef<WebSocketManager | null>(null)

  const [isConnected, setIsConnected] = useState(false)
  const [isReconnecting, setIsReconnecting] = useState(false)

  // Keep the latest onMessage callback in a ref so we don't re-subscribe on
  // every render while still calling the most recent version.
  const onMessageRef = useRef<OnMessageCallback | undefined>(onMessage)
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  // ── Connection lifecycle ────────────────────────────────────────────────

  useEffect(() => {
    // Nothing to connect to
    if (!sessionId || !accessToken) {
      // Clean up any lingering manager
      if (managerRef.current) {
        managerRef.current.disconnect()
        managerRef.current = null
      }
      setIsConnected(false)
      setIsReconnecting(false)
      return
    }

    const manager = new WebSocketManager()
    managerRef.current = manager

    // ── Internal listeners for connection state ──────────────────────────

    // We derive connected/reconnecting state from task_status or raw
    // WebSocket events. The manager dispatches typed messages — we listen
    // on the wildcard channel and track open/close through them.

    const handleMessage = (message: ServerMessage) => {
      // Forward every message to the consumer callback
      onMessageRef.current?.(message)
    }

    manager.onMessage('*', handleMessage)

    // Poll connection state at a reasonable cadence. The WebSocketManager
    // exposes `isConnected` as a getter which inspects readyState, so a
    // small interval is the simplest reliable approach without touching the
    // manager internals.
    const stateInterval = setInterval(() => {
      const connected = manager.isConnected
      setIsConnected(connected)
      // If we previously were connected and now we aren't, we are
      // reconnecting (the manager auto-reconnects unless disconnect()
      // was explicitly called).
      setIsReconnecting((prev) => {
        if (connected) return false
        // Only start showing "reconnecting" after we've seen at least one
        // connection attempt — otherwise the initial connect isn't
        // considered a reconnect.
        return prev || false
      })
    }, 500)

    // Track transitions via WebSocket events by overriding after connect
    const originalOpen = manager['ws']
    // We connect, then start tracking.
    manager.connect(sessionId, accessToken)

    // After the first open event, set connected. We do this with a short
    // timeout to let the WS handshake complete, then rely on the interval.
    const initialCheck = setTimeout(() => {
      setIsConnected(manager.isConnected)
    }, 100)

    // Listen for task_status to detect reconnection states
    manager.onMessage('error', (msg) => {
      if (msg.type === 'error' && msg.code === 'AUTH_ERROR') {
        setIsConnected(false)
        setIsReconnecting(false)
      }
    })

    // Use a MutationObserver-like pattern: intercept the underlying ws
    // events by re-checking state whenever we receive *any* message.
    manager.onMessage('*', () => {
      setIsConnected(manager.isConnected)
      if (manager.isConnected) {
        setIsReconnecting(false)
      }
    })

    return () => {
      clearInterval(stateInterval)
      clearTimeout(initialCheck)
      manager.disconnect()
      managerRef.current = null
      setIsConnected(false)
      setIsReconnecting(false)
    }
  }, [sessionId, accessToken])

  // ── Stable action callbacks ────────────────────────────────────────────

  const sendMessage = useCallback((content: string) => {
    managerRef.current?.send({
      type: 'chat_message',
      content,
    })
  }, [])

  const sendHITLResponse = useCallback((requestId: string, approved: boolean) => {
    managerRef.current?.send({
      type: 'hitl_response',
      request_id: requestId,
      approved,
    })
  }, [])

  const sendQuestionAnswer = useCallback((requestId: string, answer: string) => {
    managerRef.current?.send({
      type: 'question_answer',
      request_id: requestId,
      answer,
    })
  }, [])

  const sendPlanResponse = useCallback(
    (requestId: string, approved: boolean, feedback?: string) => {
      managerRef.current?.send({
        type: 'plan_response',
        request_id: requestId,
        approved,
        ...(feedback !== undefined && { feedback }),
      })
    },
    [],
  )

  const cancelTask = useCallback(() => {
    managerRef.current?.send({
      type: 'cancel_task',
      task_id: '', // server uses current active task for the session
    })
  }, [])

  return {
    isConnected,
    isReconnecting,
    sendMessage,
    sendHITLResponse,
    sendQuestionAnswer,
    sendPlanResponse,
    cancelTask,
  }
}
