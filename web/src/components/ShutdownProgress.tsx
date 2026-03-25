import { useState, useEffect, useRef } from 'react'

interface ShutdownEvent {
  ts: string
  type: string
  change?: string
  data: Record<string, unknown>
}

interface ChangeProgress {
  name: string
  status: 'stopping' | 'stopped' | 'timed_out'
  duration_ms?: number
  forced?: boolean
}

interface Props {
  project: string
}

export default function ShutdownProgress({ project }: Props) {
  const [active, setActive] = useState(false)
  const [changes, setChanges] = useState<Map<string, ChangeProgress>>(new Map())
  const [totalDuration, setTotalDuration] = useState<number | null>(null)
  const [stale, setStale] = useState(false)
  const lastEventRef = useRef<number>(0)
  const staleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!project) return

    const poll = async () => {
      try {
        const since = lastEventRef.current || (Date.now() / 1000 - 120)
        const res = await fetch(`/api/${project}/events?since=${since}`)
        if (!res.ok) return
        const events: ShutdownEvent[] = await res.json()

        for (const ev of events) {
          const evTime = new Date(ev.ts).getTime() / 1000
          if (evTime > lastEventRef.current) lastEventRef.current = evTime

          if (ev.type === 'SHUTDOWN_STARTED') {
            setActive(true)
            setStale(false)
            setTotalDuration(null)
            const names = (ev.data.changes as string[]) || []
            setChanges(new Map(names.map(n => [n, { name: n, status: 'stopping' }])))
          } else if (ev.type === 'CHANGE_STOPPING' && ev.change) {
            setChanges(prev => {
              const next = new Map(prev)
              next.set(ev.change!, { name: ev.change!, status: 'stopping' })
              return next
            })
          } else if (ev.type === 'CHANGE_STOPPED' && ev.change) {
            setChanges(prev => {
              const next = new Map(prev)
              next.set(ev.change!, {
                name: ev.change!,
                status: ev.data.forced ? 'timed_out' : 'stopped',
                duration_ms: ev.data.duration_ms as number,
                forced: ev.data.forced as boolean,
              })
              return next
            })
          } else if (ev.type === 'SHUTDOWN_COMPLETE') {
            setTotalDuration(ev.data.total_duration_ms as number)
          }
        }

        // Reset stale timer on any events
        if (events.length > 0) {
          setStale(false)
          if (staleTimerRef.current) clearTimeout(staleTimerRef.current)
          staleTimerRef.current = setTimeout(() => setStale(true), 30_000)
        }
      } catch {
        // ignore poll errors
      }
    }

    const interval = setInterval(poll, 2000)
    poll()

    return () => {
      clearInterval(interval)
      if (staleTimerRef.current) clearTimeout(staleTimerRef.current)
    }
  }, [project])

  // Auto-hide after complete + 5s
  useEffect(() => {
    if (totalDuration != null) {
      const t = setTimeout(() => setActive(false), 5000)
      return () => clearTimeout(t)
    }
  }, [totalDuration])

  if (!active) return null

  return (
    <div className="bg-red-950/30 border border-red-900/50 rounded-lg p-3 mb-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-red-300 text-sm font-medium">
          {totalDuration != null ? 'Shutdown complete' : 'Shutting down...'}
        </span>
        {totalDuration != null && (
          <span className="text-neutral-500 text-sm">({(totalDuration / 1000).toFixed(1)}s)</span>
        )}
        {stale && !totalDuration && (
          <span className="text-amber-400 text-sm">Shutdown may have stalled</span>
        )}
      </div>
      <div className="space-y-1">
        {Array.from(changes.values()).map(c => (
          <div key={c.name} className="flex items-center gap-2 text-sm">
            <span className="w-4 text-center">
              {c.status === 'stopping' && <span className="text-amber-400 animate-pulse">{'\u25CB'}</span>}
              {c.status === 'stopped' && <span className="text-green-400">{'\u2713'}</span>}
              {c.status === 'timed_out' && <span className="text-red-400">{'\u26A0'}</span>}
            </span>
            <span className="text-neutral-300 flex-1">{c.name}</span>
            <span className="text-neutral-500">
              {c.status === 'stopping' ? 'stopping...' :
               c.status === 'timed_out' ? 'timed out' :
               c.duration_ms != null ? `stopped (${(c.duration_ms / 1000).toFixed(1)}s)` : 'stopped'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
