import { useState, useEffect } from 'react'
import { getChangeTimeline, type ChangeTimelineData, type TimelineSession } from '../lib/api'

interface Props {
  project: string
  changeName: string
}

const GATE_ICON: Record<string, string> = {
  pass: '\u2713',
  fail: '\u2717',
  skipped: '\u2013',
  skip: '\u2013',
}

const MAIN_GATES = ['build', 'test', 'review', 'e2e', 'smoke']

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

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return ts }
}

function SessionCard({ session }: { session: TimelineSession }) {
  const [hovered, setHovered] = useState(false)
  const isRunning = !session.ended && !session.duration_ms
  const gateEntries = MAIN_GATES
    .filter(g => session.gates[g] && session.gates[g] !== 'skipped' && session.gates[g] !== 'skip')
    .map(g => ({ gate: g, result: session.gates[g] }))

  const hasFail = gateEntries.some(g => g.result === 'fail')
  const allPass = gateEntries.length > 0 && gateEntries.every(g => g.result === 'pass')

  // Border color based on outcome
  const borderColor = isRunning ? 'border-blue-500'
    : session.merged ? 'border-green-500'
    : allPass ? 'border-green-600'
    : hasFail ? 'border-red-500'
    : 'border-neutral-600'

  const headerColor = isRunning ? 'text-blue-400'
    : session.merged ? 'text-green-400'
    : allPass ? 'text-green-400'
    : hasFail ? 'text-red-400'
    : 'text-neutral-400'

  const outcome = isRunning ? 'running'
    : session.merged ? 'merged'
    : allPass ? 'pass'
    : hasFail ? 'retry'
    : session.state

  return (
    <div
      className="relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <pre className={`font-mono text-xs leading-tight border ${borderColor} rounded px-2 py-1.5 bg-neutral-900/50 cursor-default min-w-[120px]`}>
        <div className={`${headerColor} font-bold`}>
          {`#${session.n} ${outcome}`}
          {session.duration_ms ? <span className="text-neutral-500 font-normal">{` ${formatDuration(session.duration_ms)}`}</span> : null}
          {isRunning ? <span className="animate-pulse"> ...</span> : null}
        </div>
        {gateEntries.map(({ gate, result }) => {
          const icon = GATE_ICON[result] ?? '?'
          const color = result === 'pass' ? 'text-green-400' : result === 'fail' ? 'text-red-400' : 'text-neutral-500'
          const ms = session.gate_ms?.[gate]
          const timeStr = ms ? ` ${formatDuration(ms)}` : ''
          return (
            <div key={gate}>
              <span className={color}>{icon}</span>
              <span className="text-neutral-300">{` ${gate.padEnd(7)}`}</span>
              {timeStr && <span className="text-neutral-600">{timeStr}</span>}
            </div>
          )
        })}
      </pre>

      {/* Tooltip with timestamps */}
      {hovered && (
        <div className="absolute z-50 top-full left-1/2 -translate-x-1/2 mt-1.5 px-2 py-1.5 bg-neutral-900 border border-neutral-700 rounded shadow-lg text-xs text-neutral-400 whitespace-nowrap pointer-events-none font-mono">
          {formatTime(session.started)}{session.ended ? ` → ${formatTime(session.ended)}` : ''}
        </div>
      )}
    </div>
  )
}

export default function ChangeTimelineDetail({ project, changeName }: Props) {
  const [data, setData] = useState<ChangeTimelineData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getChangeTimeline(project, changeName)
      .then(d => { if (!cancelled) { setData(d); setError(null) } })
      .catch(e => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [project, changeName])

  if (error) return <pre className="text-red-400 text-xs p-2 font-mono">{error}</pre>
  if (!data) return <pre className="text-neutral-500 text-xs p-2 font-mono">Loading timeline...</pre>
  if (data.sessions.length === 0) return <pre className="text-neutral-600 text-xs p-2 font-mono">No sessions recorded</pre>

  const retryCount = data.sessions.filter(s => s.state === 'retry').length

  return (
    <div className="p-3 space-y-2">
      {/* Session cards */}
      <div className="flex items-start gap-1.5 overflow-x-auto pb-1">
        {data.sessions.map((s, i) => (
          <div key={s.n} className="flex items-center gap-1.5 shrink-0">
            {i > 0 && <span className="text-neutral-600 font-mono text-xs">→</span>}
            <SessionCard session={s} />
          </div>
        ))}
      </div>

      {/* Summary */}
      <pre className="text-xs text-neutral-500 font-mono">
        {`Total: ${formatDuration(data.duration_ms)} · ${data.sessions.length} session${data.sessions.length !== 1 ? 's' : ''}${retryCount > 0 ? ` · ${retryCount} retries` : ''}`}
      </pre>
    </div>
  )
}
