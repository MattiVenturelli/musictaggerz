import type { WSMessage } from '@/types'

type Listener = (msg: WSMessage) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private listeners = new Set<Listener>()
  private reconnectDelay = 1000
  private maxReconnectDelay = 30000
  private shouldReconnect = false

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    this.shouldReconnect = true
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws`

    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.reconnectDelay = 1000
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage
        this.listeners.forEach((fn) => fn(msg))
      } catch {
        // ignore malformed messages
      }
    }

    this.ws.onclose = () => {
      if (this.shouldReconnect) {
        setTimeout(() => this.connect(), this.reconnectDelay)
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
      }
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  disconnect() {
    this.shouldReconnect = false
    this.ws?.close()
    this.ws = null
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn)
    return () => this.listeners.delete(fn)
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const wsService = new WebSocketService()
