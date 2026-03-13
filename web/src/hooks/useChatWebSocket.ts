import { useState, useEffect, useRef, useCallback } from 'react'

export interface ChatEvent {
  type: string
  content?: string
  result?: string
  tool?: string
  tool_use_id?: string
  input?: string
  output?: string
  message?: string
  status?: string
  cost_usd?: number
  duration_ms?: number
  num_turns?: number
  messages?: any[]
}

interface UseChatWebSocketOptions {
  project: string | null
  onEvent: (event: ChatEvent) => void
}

export function useChatWebSocket({ project, onEvent }: UseChatWebSocketOptions) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const backoffRef = useRef(1000)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    if (!project) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/${project}/chat`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      backoffRef.current = 1000
    }

    ws.onmessage = (e) => {
      try {
        const event: ChatEvent = JSON.parse(e.data)
        onEventRef.current(event)
      } catch {
        // ignore non-JSON messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      // Auto-reconnect with exponential backoff
      reconnectRef.current = globalThis.setTimeout(() => {
        backoffRef.current = Math.min(backoffRef.current * 1.5, 30000)
        connect()
      }, backoffRef.current)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [project])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect])

  const send = useCallback((msg: { type: string; content?: string }) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  const sendMessage = useCallback((content: string) => {
    send({ type: 'message', content })
  }, [send])

  const stopAgent = useCallback(() => {
    send({ type: 'stop' })
  }, [send])

  const newSession = useCallback(() => {
    send({ type: 'new_session' })
  }, [send])

  return { connected, sendMessage, stopAgent, newSession }
}
