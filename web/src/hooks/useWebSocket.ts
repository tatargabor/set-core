import { useEffect, useRef, useCallback, useState } from 'react'

export interface WSEvent {
  event: 'state_update' | 'log_lines' | 'checkpoint_pending' | 'change_complete' | 'error' | 'gate_start' | 'gate_pass' | 'gate_fail' | 'merge_start' | 'merge_complete'
  data: unknown
}

interface UseWebSocketOptions {
  project: string | null
  onEvent: (event: WSEvent) => void
}

export function useWebSocket({ project, onEvent }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const backoffRef = useRef(1000)
  const [connected, setConnected] = useState(false)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    if (!project) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${project}/stream`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      backoffRef.current = 1000
    }

    ws.onmessage = (evt) => {
      try {
        const parsed = JSON.parse(evt.data) as WSEvent
        onEventRef.current(parsed)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      // Exponential backoff reconnect
      reconnectTimer.current = setTimeout(() => {
        backoffRef.current = Math.min(backoffRef.current * 2, 30000)
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
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect])

  return { connected }
}
