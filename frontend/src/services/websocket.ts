// ---------------------------------------------------------------------------
// WebSocket manager – reconnecting WS client with typed event handling
// ---------------------------------------------------------------------------

import type { ClientMessage, ServerMessage } from '@/types/websocket'

// ── Types ─────────────────────────────────────────────────────────────────

type MessageCallback = (message: ServerMessage) => void

interface WebSocketManagerOptions {
  /** Base URL for the WS endpoint (default: auto-detected from window.location) */
  baseUrl?: string
  /** Ping interval in ms (default: 30_000) */
  pingInterval?: number
  /** Maximum reconnect delay in ms (default: 30_000) */
  maxReconnectDelay?: number
}

// ── WebSocket Manager ─────────────────────────────────────────────────────

export class WebSocketManager {
  private ws: WebSocket | null = null
  private sessionId: string | null = null
  private token: string | null = null

  // Reconnection state
  private reconnectAttempt = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private shouldReconnect = false

  // Ping/pong
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private readonly pingInterval: number
  private readonly maxReconnectDelay: number

  // Event listeners keyed by message type
  private listeners: Map<string, Set<MessageCallback>> = new Map()

  // Wildcard listeners (receive every message)
  private wildcardListeners: Set<MessageCallback> = new Set()

  private readonly baseUrl: string

  constructor(options: WebSocketManagerOptions = {}) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.baseUrl = options.baseUrl ?? `${protocol}//${window.location.host}`
    this.pingInterval = options.pingInterval ?? 30_000
    this.maxReconnectDelay = options.maxReconnectDelay ?? 30_000
  }

  // ─── Public API ─────────────────────────────────────────────────────

  /**
   * Open a WebSocket connection for the given session.
   */
  connect(sessionId: string, token: string): void {
    // Tear down any existing connection first
    this.disconnect()

    this.sessionId = sessionId
    this.token = token
    this.shouldReconnect = true
    this.reconnectAttempt = 0

    this.open()
  }

  /**
   * Gracefully close the connection (no auto-reconnect).
   */
  disconnect(): void {
    this.shouldReconnect = false
    this.clearTimers()

    if (this.ws) {
      this.ws.onclose = null // prevent reconnect handler from firing
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }
  }

  /**
   * Send a typed client message over the WebSocket.
   */
  send(message: ClientMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[WS] Cannot send – connection not open')
      return
    }
    this.ws.send(JSON.stringify(message))
  }

  /**
   * Register a callback for a specific server message type.
   * Pass `'*'` to listen for all message types.
   */
  onMessage(type: string, callback: MessageCallback): void {
    if (type === '*') {
      this.wildcardListeners.add(callback)
      return
    }

    let set = this.listeners.get(type)
    if (!set) {
      set = new Set()
      this.listeners.set(type, set)
    }
    set.add(callback)
  }

  /**
   * Remove a previously registered callback.
   */
  offMessage(type: string, callback?: MessageCallback): void {
    if (type === '*') {
      if (callback) {
        this.wildcardListeners.delete(callback)
      } else {
        this.wildcardListeners.clear()
      }
      return
    }

    if (callback) {
      this.listeners.get(type)?.delete(callback)
    } else {
      this.listeners.delete(type)
    }
  }

  /**
   * Whether the WebSocket is currently open.
   */
  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  // ─── Internals ──────────────────────────────────────────────────────

  private open(): void {
    if (!this.sessionId || !this.token) return

    const url = `${this.baseUrl}/api/v1/ws/${this.sessionId}?token=${encodeURIComponent(this.token)}`

    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.reconnectAttempt = 0
      this.startPing()
    }

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data as string) as ServerMessage
        this.dispatch(message)
      } catch {
        console.error('[WS] Failed to parse message:', event.data)
      }
    }

    this.ws.onclose = (event: CloseEvent) => {
      this.clearTimers()

      // 4001 = auth error – do not reconnect
      if (event.code === 4001) {
        this.shouldReconnect = false
        this.dispatch({
          type: 'error',
          code: 'AUTH_ERROR',
          message: 'Authentication failed',
        })
        return
      }

      if (this.shouldReconnect) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
      // The onclose handler takes care of reconnection
    }
  }

  private dispatch(message: ServerMessage): void {
    // Type-specific listeners
    const set = this.listeners.get(message.type)
    if (set) {
      for (const cb of set) {
        try {
          cb(message)
        } catch (err) {
          console.error('[WS] Listener error:', err)
        }
      }
    }

    // Wildcard listeners
    for (const cb of this.wildcardListeners) {
      try {
        cb(message)
      } catch (err) {
        console.error('[WS] Wildcard listener error:', err)
      }
    }
  }

  // ─── Ping / Pong ───────────────────────────────────────────────────

  private startPing(): void {
    this.stopPing()
    this.pingTimer = setInterval(() => {
      this.send({
        type: 'ping',
        timestamp: Date.now(),
      })
    }, this.pingInterval)
  }

  private stopPing(): void {
    if (this.pingTimer !== null) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  // ─── Reconnection ──────────────────────────────────────────────────

  private scheduleReconnect(): void {
    if (this.reconnectTimer !== null) return

    // Exponential backoff: 1s, 2s, 4s, 8s, …, capped at maxReconnectDelay
    const delay = Math.min(
      1000 * Math.pow(2, this.reconnectAttempt),
      this.maxReconnectDelay,
    )

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectAttempt++
      this.open()
    }, delay)
  }

  private clearTimers(): void {
    this.stopPing()
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }
}

// ── Singleton instance ────────────────────────────────────────────────────

export const wsManager = new WebSocketManager()
