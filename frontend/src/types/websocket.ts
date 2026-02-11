// ---------------------------------------------------------------------------
// WebSocket message type definitions
// ---------------------------------------------------------------------------

// ── Shared ────────────────────────────────────────────────────────────────

export type ToolInput = Record<string, unknown>

// ── Client → Server ───────────────────────────────────────────────────────

export interface ClientChatMessage {
  type: 'chat_message'
  content: string
  context_id?: string
  attachments?: string[]
}

export interface ClientHITLResponse {
  type: 'hitl_response'
  request_id: string
  approved: boolean
}

export interface ClientQuestionAnswer {
  type: 'question_answer'
  request_id: string
  answer: string
}

export interface ClientPlanResponse {
  type: 'plan_response'
  request_id: string
  approved: boolean
  feedback?: string
}

export interface ClientCancelTask {
  type: 'cancel_task'
  task_id: string
}

export interface ClientPing {
  type: 'ping'
  timestamp: number
}

export type ClientMessage =
  | ClientChatMessage
  | ClientHITLResponse
  | ClientQuestionAnswer
  | ClientPlanResponse
  | ClientCancelTask
  | ClientPing

// ── Server → Client ───────────────────────────────────────────────────────

export interface ServerStreamChunk {
  type: 'stream_chunk'
  task_id: string
  content: string
  is_tool_output?: boolean
}

export interface ServerStreamEnd {
  type: 'stream_end'
  task_id: string
  final_content: string
  tokens_used?: number
  duration_ms?: number
}

export interface ServerHITLRequest {
  type: 'hitl_request'
  request_id: string
  tool_name: string
  tool_input: ToolInput
  description: string
}

export interface ServerHITLResolved {
  type: 'hitl_resolved'
  request_id: string
  approved: boolean
}

export interface ServerQuestion {
  type: 'question'
  request_id: string
  question: string
  context?: string
}

export interface ServerPlan {
  type: 'plan'
  request_id: string
  title: string
  steps: string[]
  description?: string
}

export interface ServerTaskStatus {
  type: 'task_status'
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress?: number
  message?: string
}

export interface ServerSessionBusy {
  type: 'session_busy'
  task_id: string
  message: string
}

export interface ServerToolUse {
  type: 'tool_use'
  task_id: string
  tool_name: string
  tool_input: ToolInput
  status: 'started' | 'completed' | 'failed'
  result?: string
}

export interface ServerError {
  type: 'error'
  code: string
  message: string
  task_id?: string
}

export interface ServerPong {
  type: 'pong'
  timestamp: number
}

export type ServerMessage =
  | ServerStreamChunk
  | ServerStreamEnd
  | ServerHITLRequest
  | ServerHITLResolved
  | ServerQuestion
  | ServerPlan
  | ServerTaskStatus
  | ServerSessionBusy
  | ServerToolUse
  | ServerError
  | ServerPong
