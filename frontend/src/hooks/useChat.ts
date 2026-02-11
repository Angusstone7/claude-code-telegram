// ---------------------------------------------------------------------------
// useChat — high-level hook combining WebSocket, Zustand chat store, and
// TanStack Query for message history loading.
// ---------------------------------------------------------------------------

import { useCallback, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { useWebSocket } from './useWebSocket'
import { useChatStore } from '@/stores/chatStore'
import type { ChatMessage } from '@/stores/chatStore'
import type { ServerMessage } from '@/types/websocket'

// ── API response type for message history ────────────────────────────────────

interface ApiChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

// ── Query keys ───────────────────────────────────────────────────────────────

export const chatKeys = {
  all: ['chat'] as const,
  messages: (projectId: string, contextId: number) =>
    [...chatKeys.all, 'messages', projectId, contextId] as const,
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useChat(projectId: string | null, contextId: number | null) {
  // ── Store selectors ──────────────────────────────────────────────────────

  const messages = useChatStore((s) => s.messages)
  const isTaskRunning = useChatStore((s) => s.isTaskRunning)
  const hitlRequests = useChatStore((s) => s.hitlRequests)
  const questionRequests = useChatStore((s) => s.questionRequests)
  const planRequests = useChatStore((s) => s.planRequests)

  const setActiveSession = useChatStore((s) => s.setActiveSession)
  const addUserMessage = useChatStore((s) => s.addUserMessage)
  const appendStreamChunk = useChatStore((s) => s.appendStreamChunk)
  const finalizeStream = useChatStore((s) => s.finalizeStream)
  const setTaskRunning = useChatStore((s) => s.setTaskRunning)
  const addHITLRequest = useChatStore((s) => s.addHITLRequest)
  const removeHITLRequest = useChatStore((s) => s.removeHITLRequest)
  const addQuestionRequest = useChatStore((s) => s.addQuestionRequest)
  const removeQuestionRequest = useChatStore((s) => s.removeQuestionRequest)
  const addPlanRequest = useChatStore((s) => s.addPlanRequest)
  const removePlanRequest = useChatStore((s) => s.removePlanRequest)
  const addToolUseMessage = useChatStore((s) => s.addToolUseMessage)
  const setMessages = useChatStore((s) => s.setMessages)

  // ── Derive the session id from project + context ─────────────────────────

  const sessionId =
    projectId && contextId !== null ? `${projectId}:${contextId}` : null

  // Keep store in sync with the active session
  useEffect(() => {
    setActiveSession(sessionId)
  }, [sessionId, setActiveSession])

  // ── Ref for tracking the current streaming task_id → message id mapping ──

  const taskMessageMap = useRef<Map<string, string>>(new Map())

  // Clear the task map when the session changes
  useEffect(() => {
    taskMessageMap.current.clear()
  }, [sessionId])

  // ── WebSocket message handler ────────────────────────────────────────────

  const handleServerMessage = useCallback(
    (message: ServerMessage) => {
      switch (message.type) {
        // ── Streaming ──────────────────────────────────────────────────
        case 'stream_chunk': {
          let messageId = taskMessageMap.current.get(message.task_id)
          if (!messageId) {
            messageId = `stream_${message.task_id}`
            taskMessageMap.current.set(message.task_id, messageId)
          }
          appendStreamChunk(messageId, message.content)
          break
        }

        case 'stream_end': {
          const messageId = taskMessageMap.current.get(message.task_id)
          if (messageId) {
            finalizeStream(messageId)
            taskMessageMap.current.delete(message.task_id)
          }
          setTaskRunning(false)
          break
        }

        // ── Task status ────────────────────────────────────────────────
        case 'task_status': {
          const running =
            message.status === 'running' || message.status === 'pending'
          setTaskRunning(running)
          break
        }

        // ── HITL ───────────────────────────────────────────────────────
        case 'hitl_request': {
          addHITLRequest({
            requestId: message.request_id,
            toolName: message.tool_name,
            toolInput: message.tool_input,
            description: message.description,
          })
          break
        }

        case 'hitl_resolved': {
          removeHITLRequest(message.request_id)
          break
        }

        // ── Questions ──────────────────────────────────────────────────
        case 'question': {
          addQuestionRequest({
            requestId: message.request_id,
            question: message.question,
            options: null, // server type has `context`, not `options`
          })
          break
        }

        // ── Plans ──────────────────────────────────────────────────────
        case 'plan': {
          const planContent = message.description
            ? `## ${message.title}\n\n${message.description}\n\n${message.steps.map((s, i) => `${i + 1}. ${s}`).join('\n')}`
            : `## ${message.title}\n\n${message.steps.map((s, i) => `${i + 1}. ${s}`).join('\n')}`

          addPlanRequest({
            requestId: message.request_id,
            content: planContent,
          })
          break
        }

        // ── Tool use ───────────────────────────────────────────────────
        case 'tool_use': {
          if (message.status === 'completed' || message.status === 'failed') {
            addToolUseMessage(
              message.tool_name,
              message.tool_input,
              message.result,
            )
          }
          break
        }

        // ── Session busy ───────────────────────────────────────────────
        case 'session_busy': {
          setTaskRunning(true)
          break
        }

        // ── Errors ─────────────────────────────────────────────────────
        case 'error': {
          setTaskRunning(false)
          break
        }

        // pong — no action needed
        case 'pong':
          break
      }
    },
    [
      appendStreamChunk,
      finalizeStream,
      setTaskRunning,
      addHITLRequest,
      removeHITLRequest,
      addQuestionRequest,
      addPlanRequest,
      addToolUseMessage,
    ],
  )

  // ── WebSocket connection ─────────────────────────────────────────────────

  const { isConnected, sendMessage: wsSendMessage, sendHITLResponse, sendQuestionAnswer, sendPlanResponse, cancelTask: wsCancelTask } =
    useWebSocket(sessionId, { onMessage: handleServerMessage })

  // ── Load message history via REST ────────────────────────────────────────

  const historyQuery = useQuery({
    queryKey: chatKeys.messages(projectId ?? '', contextId ?? 0),
    queryFn: async () => {
      const { data } = await api.get<ApiChatMessage[]>(
        `/projects/${projectId}/contexts/${contextId}/messages`,
      )
      return data
    },
    enabled: projectId !== null && contextId !== null,
    staleTime: 30_000, // history doesn't change frequently
  })

  // Seed chat store when history loads
  useEffect(() => {
    if (historyQuery.data) {
      const mapped: ChatMessage[] = historyQuery.data.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: new Date(m.timestamp),
      }))
      setMessages(mapped)
    }
  }, [historyQuery.data, setMessages])

  // ── High-level action methods ────────────────────────────────────────────

  const sendMessage = useCallback(
    (text: string) => {
      addUserMessage(text)
      setTaskRunning(true)
      wsSendMessage(text)
    },
    [addUserMessage, setTaskRunning, wsSendMessage],
  )

  const approveHITL = useCallback(
    (requestId: string) => {
      sendHITLResponse(requestId, true)
      removeHITLRequest(requestId)
    },
    [sendHITLResponse, removeHITLRequest],
  )

  const rejectHITL = useCallback(
    (requestId: string) => {
      sendHITLResponse(requestId, false)
      removeHITLRequest(requestId)
    },
    [sendHITLResponse, removeHITLRequest],
  )

  const answerQuestion = useCallback(
    (requestId: string, answer: string) => {
      sendQuestionAnswer(requestId, answer)
      removeQuestionRequest(requestId)
    },
    [sendQuestionAnswer, removeQuestionRequest],
  )

  const approvePlan = useCallback(
    (requestId: string) => {
      sendPlanResponse(requestId, true)
      removePlanRequest(requestId)
    },
    [sendPlanResponse, removePlanRequest],
  )

  const rejectPlan = useCallback(
    (requestId: string, feedback?: string) => {
      sendPlanResponse(requestId, false, feedback)
      removePlanRequest(requestId)
    },
    [sendPlanResponse, removePlanRequest],
  )

  const cancelTask = useCallback(() => {
    wsCancelTask()
    setTaskRunning(false)
  }, [wsCancelTask, setTaskRunning])

  // ── Return ─────────────────────────────────────────────────────────────

  return {
    // State
    messages,
    isConnected,
    isTaskRunning,
    hitlRequests,
    questionRequests,
    planRequests,

    // Actions
    sendMessage,
    approveHITL,
    rejectHITL,
    answerQuestion,
    approvePlan,
    rejectPlan,
    cancelTask,
  }
}
