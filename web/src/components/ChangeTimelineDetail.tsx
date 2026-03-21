import { useState, useEffect } from 'react'
import { getChangeTimeline, type ChangeTimelineData, type TimelineIteration } from '../lib/api'

interface Props {
  project: string
  changeName: string
}

// Background color for timeline blocks
const STATE_BG: Record<string, string> = {
  pending: 'bg-neutral-500',
  running: 'bg-blue-500',
  dispatched: 'bg-blue-400',
  verify: 'bg-yellow-500',
  verifying: 'bg-yellow-500',
  'merge-queue': 'bg-purple-500',
  merged: 'bg-green-500',
  done: 'bg-green-500',
  failed: 'bg-red-500',
  'merge-blocked': 'bg-red-400',
  stopped: 'bg-neutral-400',
}

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

function iterDurationMs(it: TimelineIteration): number {
  try {
    return new Date(it.ended).getTime() - new Date(it.started).getTime()
  } catch { return 0 }
}

const RESULT_ICON: Record<string, string> = {
  pass: '\u2713',
  fail: '\u2717',
  skipped: '\u2013',
  skip: '\u2013',
}

const RESULT_COLOR: Record<string, string> = {
  pass: 'text-green-400',
  fail: 'text-red-400',
  skipped: 'text-neutral-500',
  skip: 'text-neutral-500',
}

function IterationTimeline({ iterations }: { iterations: TimelineIteration[] }) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  return (
    <div className="relative">
      <div className="flex items-end gap-0.5 flex-wrap pb-2">
        {iterations.map((it, i) => {
          const prevState = i > 0 ? iterations[i - 1].state : null
          const stateChanged = prevState !== null && prevState !== it.state
          const showLabel = i === 0 || stateChanged

          return (
            <div key={it.n} className="flex items-end gap-0.5 shrink-0">
              {stateChanged && <div className="w-px h-5 bg-neutral-600 mx-0.5 self-center" />}
              <div
                className="relative"
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
              >
                <div
                  className={`w-5 h-5 rounded-sm cursor-default ${STATE_BG[it.state] ?? 'bg-neutral-500'} ${it.no_op ? 'opacity-40' : ''} ${it.timed_out ? 'ring-1 ring-red-500/60' : ''}`}
                  title={`#${it.n}`}
                >
                  <span className="flex items-center justify-center h-full text-[8px] text-white/70 font-mono">
                    {it.n}
                  </span>
                </div>
                {showLabel && (
                  <div className="text-[9px] text-neutral-500 leading-none mt-0.5 text-center">{it.state}</div>
                )}
                {hoveredIdx === i && (
                  <div className="absolute z-50 top-full left-1/2 -translate-x-1/2 mt-1.5 px-2 py-1.5 bg-neutral-900 border border-neutral-700 rounded shadow-lg text-xs text-neutral-200 whitespace-nowrap pointer-events-none">
                    <div className="font-medium">Iteration {it.n}</div>
                    <div className="text-neutral-400">State: {it.state}</div>
                    <div className="text-neutral-400">Duration: {formatDuration(iterDurationMs(it))}</div>
                    <div className="text-neutral-400">Tokens: {it.tokens_used.toLocaleString()}</div>
                    <div className="text-neutral-400">Commits: {it.commits}</div>
                    {it.timed_out && <div className="text-red-400">Timed out</div>}
                    {it.no_op && <div className="text-neutral-500">No-op (no work done)</div>}
                    <div className="text-[10px] text-neutral-500 mt-0.5">{formatTime(it.started)} - {formatTime(it.ended)}</div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TransitionTimeline({ transitions }: { transitions: ChangeTimelineData['transitions'] }) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  return (
    <div className="relative">
      <div className="flex items-end gap-0.5 flex-wrap pb-2">
        {transitions.map((t, i) => {
          const prevState = i > 0 ? transitions[i - 1].to : null
          const stateChanged = prevState !== null && prevState !== t.to
          const showLabel = i === 0 || stateChanged

          let stepDurationMs = 0
          if (i < transitions.length - 1) {
            try {
              stepDurationMs = new Date(transitions[i + 1].ts).getTime() - new Date(t.ts).getTime()
            } catch { /* ignore */ }
          }

          return (
            <div key={i} className="flex items-end gap-0.5 shrink-0">
              {stateChanged && <div className="w-px h-5 bg-neutral-600 mx-0.5 self-center" />}
              <div
                className="relative"
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
              >
                <div
                  className={`w-5 h-5 rounded-sm cursor-default ${STATE_BG[t.to] ?? 'bg-neutral-500'} ${(t.to === 'failed' || t.to === 'merge-blocked') ? 'ring-1 ring-red-500/60' : ''}`}
                  title={t.to}
                />
                {showLabel && (
                  <div className="text-[9px] text-neutral-500 leading-none mt-0.5 text-center">{t.to}</div>
                )}
                {hoveredIdx === i && (
                  <div className="absolute z-50 top-full left-1/2 -translate-x-1/2 mt-1.5 px-2 py-1.5 bg-neutral-900 border border-neutral-700 rounded shadow-lg text-xs text-neutral-200 whitespace-nowrap pointer-events-none">
                    <div className="font-medium">{t.to}</div>
                    {t.from && <div className="text-neutral-400">From: {t.from}</div>}
                    <div className="text-[10px] text-neutral-500 mt-0.5">{formatTime(t.ts)}</div>
                    {stepDurationMs > 0 && <div className="text-neutral-400">Duration: {formatDuration(stepDurationMs)}</div>}
                  </div>
                )}
              </div>
            </div>
          )
        })}
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
  if (data.transitions.length === 0) return <div className="text-neutral-600 text-sm p-2">No state transitions recorded</div>

  const hasIterations = data.iterations && data.iterations.length > 0

  // Count retries
  const retryCount = data.transitions.filter(t => t.from === 'failed' || (t.from === 'verify' && t.to !== 'merge-queue' && t.to !== 'merged' && t.to !== 'done')).length
  const verifyCount = data.transitions.filter(t => t.to === 'verify' || t.to === 'verifying').length

  // Gate results
  const gates = data.current_gate_results
  const gateEntries = Object.entries(gates).filter(([k]) => k.endsWith('_result'))

  return (
    <div className="p-3 space-y-3">
      {/* Timeline: iteration-based or state-transition fallback */}
      {hasIterations ? (
        <IterationTimeline iterations={data.iterations} />
      ) : (
        <TransitionTimeline transitions={data.transitions} />
      )}

      {/* Gate results */}
      {gateEntries.length > 0 && (
        <div className="flex gap-3 text-sm">
          {gateEntries.map(([key, val]) => {
            const name = key.replace('_result', '')
            const v = String(val)
            return (
              <span key={key} className="flex items-center gap-1">
                <span className="text-neutral-500">{name}:</span>
                <span className={RESULT_COLOR[v] ?? 'text-neutral-400'}>
                  {RESULT_ICON[v] ?? v} {v}
                </span>
              </span>
            )
          })}
          {gates.verify_retry_count != null && Number(gates.verify_retry_count) > 0 && (
            <span className="text-neutral-500">retries: {gates.verify_retry_count}</span>
          )}
        </div>
      )}

      {/* Summary line */}
      <div className="text-sm text-neutral-500">
        Duration: {formatDuration(data.duration_ms)}
        {hasIterations && <span> · {data.iterations.length} iterations</span>}
        {retryCount > 0 && <span> · {retryCount} retries</span>}
        {verifyCount > 0 && <span> · {verifyCount} gate runs</span>}
      </div>
    </div>
  )
}
