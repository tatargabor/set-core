import { useState, useEffect } from 'react'
import { getChangeTimeline, type ChangeTimelineData, type TimelineSession } from '../lib/api'

interface Props {
  project: string
  changeName: string
}

const STATE_BG: Record<string, string> = {
  dispatched: 'bg-blue-400',
  running: 'bg-blue-500',
  verify: 'bg-yellow-500',
  verifying: 'bg-yellow-500',
  retry: 'bg-orange-500',
  'merge-queue': 'bg-purple-500',
  merged: 'bg-green-500',
  done: 'bg-green-500',
  failed: 'bg-red-500',
  'merge-blocked': 'bg-red-400',
  stopped: 'bg-neutral-400',
}

const GATE_ICON: Record<string, string> = {
  pass: '\u2713',
  fail: '\u2717',
  skipped: '\u2013',
  skip: '\u2013',
}

const GATE_COLOR: Record<string, string> = {
  pass: 'text-green-400',
  fail: 'text-red-400',
  skipped: 'text-neutral-600',
  skip: 'text-neutral-600',
}

// Gates we care about showing (in order)
const MAIN_GATES = ['build', 'test', 'review', 'e2e', 'smoke']

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return ts }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const secs = Math.floor(ms / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  const remSecs = secs % 60
  if (mins < 60) return `${mins}m ${remSecs}s`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ${mins % 60}m`
}

function SessionBlock({ session }: { session: TimelineSession }) {
  const [hovered, setHovered] = useState(false)
  const isRunning = !session.ended && !session.duration_ms
  const gateEntries = MAIN_GATES
    .filter(g => session.gates[g] && session.gates[g] !== 'skipped' && session.gates[g] !== 'skip')
    .map(g => ({ gate: g, result: session.gates[g] }))

  // Determine session outcome color
  const hasFail = gateEntries.some(g => g.result === 'fail')
  const allPass = gateEntries.length > 0 && gateEntries.every(g => g.result === 'pass')
  const bgClass = isRunning ? 'bg-blue-500 animate-pulse'
    : session.merged ? 'bg-green-600'
    : allPass ? 'bg-green-500'
    : hasFail ? 'bg-red-500/80'
    : STATE_BG[session.state] ?? 'bg-neutral-500'

  return (
    <div className="flex items-center gap-1 shrink-0">
      {session.n > 1 && (
        <div className="text-neutral-600 text-xs mx-0.5">{'\u2192'}</div>
      )}
      <div
        className="relative"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {/* Session block */}
        <div className={`px-3 py-2 rounded cursor-default ${bgClass}`}>
          <div className="text-xs text-white/90 font-mono text-center mb-1.5">#{session.n}</div>
          {/* Gate results as text labels */}
          {gateEntries.length > 0 && (
            <div className="flex items-center justify-center gap-1">
              {gateEntries.map(({ gate, result }) => (
                <span
                  key={gate}
                  className={`px-1.5 py-0.5 rounded text-[11px] font-mono font-medium ${
                    result === 'pass' ? 'bg-green-600/80 text-green-100' :
                    result === 'fail' ? 'bg-red-700 text-red-100 ring-1 ring-red-400/50' :
                    'bg-neutral-700 text-neutral-300'
                  }`}
                  title={`${gate}: ${result}`}
                >
                  {gate}
                </span>
              ))}
            </div>
          )}
          {/* Duration inside block */}
          {session.duration_ms ? (
            <div className="text-[10px] text-white/50 text-center mt-1 font-mono">{formatDuration(session.duration_ms)}</div>
          ) : isRunning ? (
            <div className="text-[10px] text-white/50 text-center mt-1">running...</div>
          ) : null}
        </div>

        {/* Tooltip */}
        {hovered && (
          <div className="absolute z-50 top-full left-1/2 -translate-x-1/2 mt-4 px-2.5 py-2 bg-neutral-900 border border-neutral-700 rounded shadow-lg text-xs text-neutral-200 whitespace-nowrap pointer-events-none">
            <div className="font-medium mb-1">Session {session.n}</div>
            <div className="text-neutral-400">State: {session.state}{session.merged ? ' → merged' : ''}</div>
            {session.duration_ms ? (
              <div className="text-neutral-400">Duration: {formatDuration(session.duration_ms)}</div>
            ) : isRunning ? (
              <div className="text-blue-400">In progress...</div>
            ) : null}
            {/* Gate details */}
            {Object.keys(session.gates).length > 0 && (
              <div className="mt-1 pt-1 border-t border-neutral-700 space-y-0.5">
                {MAIN_GATES.filter(g => session.gates[g]).map(g => (
                  <div key={g} className="flex items-center gap-1.5">
                    <span className="text-neutral-500 w-12">{g}:</span>
                    <span className={GATE_COLOR[session.gates[g]] ?? 'text-neutral-400'}>
                      {GATE_ICON[session.gates[g]] ?? session.gates[g]} {session.gates[g]}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <div className="text-[10px] text-neutral-500 mt-1">
              {formatTime(session.started)}
              {session.ended ? ` - ${formatTime(session.ended)}` : ''}
            </div>
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
    getChangeTimeline(project, changeName)
      .then(d => { if (!cancelled) { setData(d); setError(null) } })
      .catch(e => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [project, changeName])

  if (error) return <div className="text-red-400 text-sm p-2">{error}</div>
  if (!data) return <div className="text-neutral-500 text-sm p-2">Loading timeline...</div>
  if (data.sessions.length === 0) return <div className="text-neutral-600 text-sm p-2">No sessions recorded</div>

  const retryCount = data.sessions.filter(s => s.state === 'retry').length

  return (
    <div className="p-3 space-y-3">
      {/* Session timeline */}
      <div className="flex items-start gap-0 overflow-x-auto pb-1">
        {data.sessions.map(s => (
          <SessionBlock key={s.n} session={s} />
        ))}
      </div>

      {/* Summary line */}
      <div className="text-sm text-neutral-500">
        Duration: {formatDuration(data.duration_ms)}
        <span> · {data.sessions.length} session{data.sessions.length !== 1 ? 's' : ''}</span>
        {retryCount > 0 && <span> · {retryCount} retries</span>}
      </div>
    </div>
  )
}
