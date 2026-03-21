import { useState, useEffect } from 'react'
import { getChangeTimeline, type ChangeTimelineData } from '../lib/api'

interface Props {
  project: string
  changeName: string
}

const STATE_COLORS: Record<string, string> = {
  pending: 'bg-neutral-700 text-neutral-300',
  running: 'bg-blue-800 text-blue-200',
  dispatched: 'bg-blue-700 text-blue-200',
  verify: 'bg-yellow-800 text-yellow-200',
  verifying: 'bg-yellow-800 text-yellow-200',
  'merge-queue': 'bg-purple-800 text-purple-200',
  merged: 'bg-green-800 text-green-200',
  done: 'bg-green-800 text-green-200',
  failed: 'bg-red-800 text-red-200',
  'merge-blocked': 'bg-red-700 text-red-200',
  stopped: 'bg-neutral-600 text-neutral-300',
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

  // Count retries (transitions back to running/dispatched after verify/failed)
  const retryCount = data.transitions.filter(t => t.from === 'failed' || (t.from === 'verify' && t.to !== 'merge-queue' && t.to !== 'merged' && t.to !== 'done')).length
  const verifyCount = data.transitions.filter(t => t.to === 'verify' || t.to === 'verifying').length

  // Gate results
  const gates = data.current_gate_results
  const gateEntries = Object.entries(gates).filter(([k]) => k.endsWith('_result'))

  return (
    <div className="p-3 space-y-3">
      {/* Horizontal flow */}
      <div className="flex items-center gap-1 overflow-x-auto pb-2">
        {data.transitions.map((t, i) => {
          const isFail = t.to === 'failed' || t.to === 'merge-blocked'
          return (
            <div key={i} className="flex items-center gap-1 shrink-0">
              {i > 0 && (
                <span className={`text-sm ${isFail ? 'text-red-500' : 'text-neutral-600'}`}>{'\u2192'}</span>
              )}
              <div className={`px-2 py-1 rounded text-xs ${STATE_COLORS[t.to] ?? 'bg-neutral-800 text-neutral-400'} ${isFail ? 'ring-1 ring-red-500/50' : ''}`}>
                <div className="font-medium">{t.to}</div>
                <div className="text-[10px] opacity-70">{formatTime(t.ts)}</div>
              </div>
            </div>
          )
        })}
      </div>

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
        {retryCount > 0 && <span> · {retryCount} retries</span>}
        {verifyCount > 0 && <span> · {verifyCount} gate runs</span>}
      </div>
    </div>
  )
}
