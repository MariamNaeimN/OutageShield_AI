/**
 * OutageShield AI — WebSocket Real-Time Service
 * 
 * Uses AWS API Gateway WebSocket API for instant updates.
 * When an incident changes (new signal, workflow step, approval, resolution),
 * the backend pushes the update immediately — no polling needed.
 * 
 * Architecture:
 *   DynamoDB Stream → Lambda → API Gateway WebSocket → Browser
 *   EventBridge → Lambda → API Gateway WebSocket → Browser
 */

type MessageHandler = (data: WebSocketMessage) => void

export interface WebSocketMessage {
  type: 'incident_created' | 'incident_updated' | 'incident_resolved' |
        'signal_detected' | 'workflow_step' | 'approval_requested' |
        'approval_responded' | 'ticket_created' | 'risk_updated' |
        'postmortem_generated' | 'notification_sent'
  payload: Record<string, unknown>
  timestamp: string
}

class RealtimeService {
  private ws: WebSocket | null = null
  private handlers: Map<string, Set<MessageHandler>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectDelay = 1000
  private url: string
  private connected = false

  constructor() {
    this.url = import.meta.env.VITE_WS_URL || 'wss://your-ws-api-id.execute-api.us-east-1.amazonaws.com/dev'
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Connection Management
  // ─────────────────────────────────────────────────────────────────────────

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        console.log('[WS] Connected to OutageShield real-time stream')
        this.connected = true
        this.reconnectAttempts = 0
        this.reconnectDelay = 1000
        this.emit('connection', { type: 'connected' } as unknown as WebSocketMessage)
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (err) {
          console.warn('[WS] Failed to parse message:', err)
        }
      }

      this.ws.onclose = (event) => {
        console.log(`[WS] Disconnected (code: ${event.code})`)
        this.connected = false
        this.emit('connection', { type: 'disconnected' } as unknown as WebSocketMessage)
        this.scheduleReconnect()
      }

      this.ws.onerror = (error) => {
        console.error('[WS] Error:', error)
        this.connected = false
      }
    } catch (err) {
      console.error('[WS] Failed to connect:', err)
      this.scheduleReconnect()
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnecting')
      this.ws = null
      this.connected = false
    }
  }

  isConnected(): boolean {
    return this.connected
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached. Falling back to polling.')
      this.emit('connection', { type: 'fallback_polling' } as unknown as WebSocketMessage)
      return
    }

    this.reconnectAttempts++
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000)
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)

    setTimeout(() => this.connect(), delay)
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Message Handling
  // ─────────────────────────────────────────────────────────────────────────

  private handleMessage(message: WebSocketMessage): void {
    // Emit to type-specific handlers
    this.emit(message.type, message)
    // Emit to wildcard handlers
    this.emit('*', message)
  }

  private emit(type: string, message: WebSocketMessage): void {
    const handlers = this.handlers.get(type)
    if (handlers) {
      handlers.forEach(handler => handler(message))
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Subscribe / Unsubscribe
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Subscribe to a specific message type.
   * Use '*' to receive all messages.
   */
  on(type: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)

    // Return unsubscribe function
    return () => {
      this.handlers.get(type)?.delete(handler)
    }
  }

  /**
   * Subscribe to all incident-related updates for a specific incident.
   */
  onIncident(incidentId: string, handler: MessageHandler): () => void {
    const filteredHandler: MessageHandler = (message) => {
      const payload = message.payload as Record<string, unknown>
      if (payload.incident_id === incidentId || payload.incidentId === incidentId) {
        handler(message)
      }
    }

    return this.on('*', filteredHandler)
  }
}

// Singleton instance
export const realtime = new RealtimeService()
