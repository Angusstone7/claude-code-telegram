// ---------------------------------------------------------------------------
// Zustand chat store — manages chat messages, streaming, and interactive
// requests (HITL, questions, plans) for the active coding session.
// ---------------------------------------------------------------------------

import { create } from 'zustand'

// ── Public types ─────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  /** When true the message is still receiving stream chunks. */
  isStreaming?: boolean
}

export interface HITLRequest {
  requestId: string
  toolName: string
  toolInput: Record<string, unknown>
  description: string
}

export interface QuestionRequest {
  requestId: string
  question: string
  options: string[] | null
}

export interface PlanRequest {
  requestId: string
  content: string
}

export interface ChatState {
  messages: ChatMessage[]
  activeSessionId: string | null
  isTaskRunning: boolean
  streamingMessageId: string | null
  hitlRequests: HITLRequest[]
  questionRequests: QuestionRequest[]
  planRequests: PlanRequest[]

  // ── Actions ──────────────────────────────────────────────────────────────

  /** Set (or clear) the active session id. Clears messages when changed. */
  setActiveSession: (sessionId: string | null) => void

  /** Append a user message and return its generated id. */
  addUserMessage: (content: string) => string

  /** Append a chunk of streamed content to an existing assistant message. */
  appendStreamChunk: (messageId: string, content: string) => void

  /** Mark a streaming message as finalized. */
  finalizeStream: (messageId: string) => void

  /** Toggle the task-running flag. */
  setTaskRunning: (running: boolean) => void

  /** Push a new HITL permission request. */
  addHITLRequest: (req: HITLRequest) => void
  /** Remove a HITL request after the user has responded. */
  removeHITLRequest: (requestId: string) => void

  /** Push a new question request from the agent. */
  addQuestionRequest: (req: QuestionRequest) => void
  /** Remove a question request after the user has answered. */
  removeQuestionRequest: (requestId: string) => void

  /** Push a new plan approval request. */
  addPlanRequest: (req: PlanRequest) => void
  /** Remove a plan request after the user has responded. */
  removePlanRequest: (requestId: string) => void

  /** Insert a tool-use notification as an assistant message. */
  addToolUseMessage: (
    toolName: string,
    toolInput: Record<string, unknown>,
    result?: string,
  ) => void

  /** Replace the entire message list (e.g. when loading history). */
  setMessages: (messages: ChatMessage[]) => void

  /** Clear all messages and interactive request queues. */
  clearMessages: () => void
}

// ── Helpers ──────────────────────────────────────────────────────────────────

let _nextId = 0

function generateId(): string {
  return `msg_${Date.now()}_${++_nextId}`
}

// ── Store ────────────────────────────────────────────────────────────────────

export const useChatStore = create<ChatState>()((set, get) => ({
  messages: [],
  activeSessionId: null,
  isTaskRunning: false,
  streamingMessageId: null,
  hitlRequests: [],
  questionRequests: [],
  planRequests: [],

  // ── Session ────────────────────────────────────────────────────────────

  setActiveSession: (sessionId) => {
    const current = get().activeSessionId
    if (current === sessionId) return

    set({
      activeSessionId: sessionId,
      messages: [],
      isTaskRunning: false,
      streamingMessageId: null,
      hitlRequests: [],
      questionRequests: [],
      planRequests: [],
    })
  },

  // ── Messages ───────────────────────────────────────────────────────────

  addUserMessage: (content) => {
    const id = generateId()
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id,
          role: 'user',
          content,
          timestamp: new Date(),
        },
      ],
    }))
    return id
  },

  appendStreamChunk: (messageId, content) => {
    set((state) => {
      const existing = state.messages.find((m) => m.id === messageId)

      if (existing) {
        // Append to existing streaming message
        return {
          messages: state.messages.map((m) =>
            m.id === messageId
              ? { ...m, content: m.content + content, isStreaming: true }
              : m,
          ),
        }
      }

      // First chunk for this messageId — create a new assistant message
      return {
        messages: [
          ...state.messages,
          {
            id: messageId,
            role: 'assistant' as const,
            content,
            timestamp: new Date(),
            isStreaming: true,
          },
        ],
        streamingMessageId: messageId,
      }
    })
  },

  finalizeStream: (messageId) => {
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === messageId ? { ...m, isStreaming: false } : m,
      ),
      streamingMessageId:
        state.streamingMessageId === messageId ? null : state.streamingMessageId,
    }))
  },

  setTaskRunning: (running) => set({ isTaskRunning: running }),

  // ── HITL ───────────────────────────────────────────────────────────────

  addHITLRequest: (req) =>
    set((state) => ({
      hitlRequests: [...state.hitlRequests, req],
    })),

  removeHITLRequest: (requestId) =>
    set((state) => ({
      hitlRequests: state.hitlRequests.filter((r) => r.requestId !== requestId),
    })),

  // ── Questions ──────────────────────────────────────────────────────────

  addQuestionRequest: (req) =>
    set((state) => ({
      questionRequests: [...state.questionRequests, req],
    })),

  removeQuestionRequest: (requestId) =>
    set((state) => ({
      questionRequests: state.questionRequests.filter(
        (r) => r.requestId !== requestId,
      ),
    })),

  // ── Plans ──────────────────────────────────────────────────────────────

  addPlanRequest: (req) =>
    set((state) => ({
      planRequests: [...state.planRequests, req],
    })),

  removePlanRequest: (requestId) =>
    set((state) => ({
      planRequests: state.planRequests.filter((r) => r.requestId !== requestId),
    })),

  // ── Tool use ───────────────────────────────────────────────────────────

  addToolUseMessage: (toolName, toolInput, result) => {
    const lines: string[] = [`**Tool:** \`${toolName}\``]

    const inputSummary = JSON.stringify(toolInput, null, 2)
    if (inputSummary.length <= 500) {
      lines.push(`\`\`\`json\n${inputSummary}\n\`\`\``)
    } else {
      lines.push(`\`\`\`json\n${inputSummary.slice(0, 497)}...\n\`\`\``)
    }

    if (result !== undefined) {
      lines.push(`**Result:** ${result}`)
    }

    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: generateId(),
          role: 'assistant',
          content: lines.join('\n'),
          timestamp: new Date(),
        },
      ],
    }))
  },

  // ── Bulk operations ────────────────────────────────────────────────────

  setMessages: (messages) => set({ messages }),

  clearMessages: () =>
    set({
      messages: [],
      streamingMessageId: null,
      isTaskRunning: false,
      hitlRequests: [],
      questionRequests: [],
      planRequests: [],
    }),
}))
