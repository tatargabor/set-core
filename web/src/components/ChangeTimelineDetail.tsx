import { useState, useEffect } from 'react'
import { getChangeTimeline, type ChangeTimelineData, type TimelineSession } from '../lib/api'

interface Props {
  project: string
  changeName: string
}

const GATE_ICON: Record<string, string> = {
  pass: '✓',
  fail: '✗',
  warn: '⚠',
  skip: '–',
  skipped: '–',
}

const GATE_COLOR: Record<string, string> = {
  pass: 'text-green-400',
  fail: 'text-red-400',
  warn: 'text-amber-400',
  skip: 'text-neutral-500',
  skipped: 'text-neutral-500',
}

const STATE_COLOR: Record<string, string> = {
  merged: 'bg-green-500',
  success: 'bg-green-500',
  done: 'bg-blue-500',
  running: 'bg-blue-500',
  active: 'bg-blue-500',
  retry: 'bg-amber-500',
  error: 'bg-red-500',
  unknown: 'bg-neutral-500',
}

const STATE_BORDER: Record<string, string> = {
  merged: 'border-green-500/30',
  success: 'border-green-500/20',
  done: 'border-blue-500/20',
  running: 'border-blue-500/30',
  active: 'border-blue-500/30',
  retry: 'border-amber-500/30',
  error: 'border-red-500/30',
  unknown: 'border-neutral-700',
}

const MAIN_GATES = ['build', 'test', 'e2e', 'review', 'smoke']

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const secs = Math.floor(ms / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  const remSecs = secs % 60
  if (mins < 60) return `${mins}m${remSecs > 0 ? ` ${remSecs}s` : ''}`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ${mins % 60}m`
}

function formatTokens(n?: number): string {
  if (!n) return '–'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

function SessionRow({ session, isLast }: { session: TimelineSession; isLast: boolean }) {
  const isRunning = session.state === 'running' || session.state === 'active'
  const gateEntries = MAIN_GATES
    .filter(g => session.gates[g])
    .map(g => ({ gate: g, result: session.gates[g] }))

  const dotColor = STATE_COLOR[session.state] ?? STATE_COLOR.unknown
  const borderColor = STATE_BORDER[session.state] ?? STATE_BORDER.unknown

  return (
    <div className="flex gap-3">
      {/* Vertical line + dot */}
      <div className="flex flex-col items-center w-4 shrink-0">
        <div className={`w-3 h-3 rounded-full ${dotColor} shrink-0 mt-1.5 ring-2 ring-neutral-950`} />
        {!isLast && <div className="w-px flex-1 bg-neutral-800 mt-1" />}
      </div>

      {/* Session card */}
      <div className={`flex-1 mb-3 rounded-lg border ${borderColor} bg-neutral-900/50 p-3 space-y-2`}>
        {/* Header row */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-neutral-200">
              #{session.n}
            </span>
            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
              session.merged ? 'bg-green-900/50 text-green-300' :
              isRunning ? 'bg-blue-900/50 text-blue-300' :
              session.state === 'retry' || session.state === 'error' ? 'bg-red-900/50 text-red-300' :
              session.state === 'success' || session.state === 'done' ? 'bg-green-900/40 text-green-400' :
              'bg-neutral-800 text-neutral-400'
            }`}>
              {session.state}
              {isRunning && <span className="animate-pulse ml-1">...</span>}
            </span>
            {session.model && (
              <span className="text-xs text-neutral-600">{session.model}</span>
            )}
          </div>
          <div className="text-xs text-neutral-500">
            {formatTime(session.started)}
            {session.ended && ` → ${formatTime(session.ended)}`}
            {session.duration_ms ? ` · ${formatDuration(session.duration_ms)}` : ''}
          </div>
        </div>

        {/* Label */}
        {session.label && session.label !== 'Task' && (
          <div className="text-xs text-neutral-500 truncate">{session.label}</div>
        )}

        {/* Tokens row */}
        {(session.input_tokens || session.output_tokens) ? (
          <div className="flex gap-4 text-xs">
            <span className="text-neutral-500">
              In: <span className="text-neutral-300">{formatTokens(session.input_tokens)}</span>
            </span>
            <span className="text-neutral-500">
              Out: <span className="text-neutral-300">{formatTokens(session.output_tokens)}</span>
            </span>
            {session.cache_read_tokens ? (
              <span className="text-neutral-600">
                Cache: {formatTokens(session.cache_read_tokens)}
              </span>
            ) : null}
          </div>
        ) : null}

        {/* Gates row */}
        {gateEntries.length > 0 && (
          <div className="flex gap-3 text-xs">
            {gateEntries.map(({ gate, result }) => {
              const icon = GATE_ICON[result] ?? '?'
              const color = GATE_COLOR[result] ?? 'text-neutral-500'
              const ms = session.gate_ms?.[gate]
              return (
                <span key={gate} className="flex items-center gap-1">
                  <span className={color}>{icon}</span>
                  <span className="text-neutral-400 capitalize">{gate}</span>
                  {ms ? <span className="text-neutral-600">{formatDuration(ms)}</span> : null}
                </span>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChangeTimelineDetail({ project, changeName }: Props) {
  const [data, setData] = useState<ChangeTimelineData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = () => {
      getChangeTimeline(project, changeName)
        .then(d => { if (!cancelled) { setData(d); setError(null) } })
        .catch(e => { if (!cancelled) setError(e.message) })
    }
    load()
    const iv = setInterval(load, 10000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project, changeName])

  if (error) return <div className="text-red-400 text-xs p-3">{error}</div>
  if (!data) return <div className="text-neutral-500 text-xs p-3">Loading timeline...</div>
  if (data.sessions.length === 0) return <div className="text-neutral-600 text-xs p-3">No sessions recorded</div>

  const totalIn = data.sessions.reduce((s, x) => s + (x.input_tokens ?? 0), 0)
  const totalOut = data.sessions.reduce((s, x) => s + (x.output_tokens ?? 0), 0)
  const retryCount = data.sessions.filter(s => s.state === 'retry' || s.state === 'error').length

  return (
    <div className="p-3">
      {/* Summary bar */}
      <div className="flex items-center gap-4 text-xs text-neutral-500 mb-3 pb-2 border-b border-neutral-800">
        <span>{data.sessions.length} session{data.sessions.length !== 1 ? 's' : ''}</span>
        <span>{formatDuration(data.duration_ms)}</span>
        {totalIn > 0 && <span>In: {formatTokens(totalIn)} · Out: {formatTokens(totalOut)}</span>}
        {retryCount > 0 && <span className="text-amber-400">{retryCount} retries</span>}
      </div>

      {/* Vertical timeline */}
      <div>
        {data.sessions.map((s, i) => (
          <SessionRow key={s.n} session={s} isLast={i === data.sessions.length - 1} />
        ))}
      </div>
    </div>
  )
}
