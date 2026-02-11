export type * from './api'

// Re-export websocket types explicitly to avoid ToolInput name collision with api.ts
export type {
  // Shared
  ToolInput as WsToolInput,

  // Client → Server
  ClientChatMessage,
  ClientHITLResponse,
  ClientQuestionAnswer,
  ClientPlanResponse,
  ClientCancelTask,
  ClientPing,
  ClientMessage,

  // Server → Client
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
  ServerMessage,
} from './websocket'
