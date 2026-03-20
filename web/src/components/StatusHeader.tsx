import { useState } from 'react'
import type { StateData } from '../lib/api'
import { stopOrchestrator, approve } from '../lib/api'

interface Props {
  state: StateData | null
  connected: boolean
  project: string
}

function formatTokens(n?: number): string {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

function formatDuration(secs?: number): string {
  if (!secs) return ''
  const m = Math.floor(secs / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  return `${h}h${m % 60}m`
}

export default function StatusHeader({ state, connected, project }: Props) {
  const [loading, setLoading] = useState<string | null>(null)
  const [confirmAction, setConfirmAction] = useState<string | null>(null)
  const statusBadge = state?.status ?? 'idle'
  const isActive = ['running', 'planning', 'checkpoint'].includes(statusBadge)
  const badgeColor: Record<string, string> = {
    running: 'bg-green-900 text-green-300',
    planning: 'bg-cyan-900 text-cyan-300',
    checkpoint: 'bg-yellow-900 text-yellow-300',
    completed: 'bg-blue-900 text-blue-300',
    stopped: 'bg-neutral-800 text-neutral-400',
    failed: 'bg-red-900 text-red-300',
    corrupt: 'bg-red-900 text-red-300',
    idle: 'bg-neutral-800 text-neutral-500',
  }

  // Aggregate tokens from changes
  const changes = state?.changes ?? []
  const totals = changes.reduce(
    (acc, c) => ({
      input: acc.input + (c.input_tokens ?? 0),
      output: acc.output + (c.output_tokens ?? 0),
      cacheRead: acc.cacheRead + (c.cache_read_tokens ?? 0),
      cacheCreate: acc.cacheCreate + (c.cache_create_tokens ?? 0),
    }),
    { input: 0, output: 0, cacheRead: 0, cacheCreate: 0 },
  )
  const done = changes.filter((c) => ['done', 'merged', 'completed'].includes(c.status)).length

  const handleApprove = async () => {
    if (confirmAction !== 'approve') {
      setConfirmAction('approve')
      return
    }
    setConfirmAction(null)
    setLoading('approve')
    try { await approve(project) } catch {}
    setLoading(null)
  }

  const handleStop = async () => {
    if (confirmAction !== 'stop') {
      setConfirmAction('stop')
      return
    }
    setConfirmAction(null)
    setLoading('stop')
    try { await stopOrchestrator(project) } catch {}
    setLoading(null)
  }

  return (
    <div className="flex flex-wrap items-center gap-2 md:gap-4 px-3 md:px-4 py-2 md:py-3 border-b border-neutral-800 bg-neutral-900/50 shrink-0">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold text-neutral-100">{project}</h2>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${badgeColor[statusBadge] ?? 'bg-neutral-800 text-neutral-400'}`}>
          {statusBadge}
        </span>
        <span className={`hidden md:inline-block ${connected ? 'text-green-500' : 'text-red-500'}`} title={connected ? 'Connected' : 'Disconnected'}>{connected ? '\u25CF' : '\u25CB'}</span>
      </div>

      {state && (
        <>
          <div className="text-xs text-neutral-500 hidden md:block">
            {state.plan_version && <span>v{state.plan_version}</span>}
            {state.active_seconds ? (
              <span className="ml-2">{formatDuration(state.active_seconds)}</span>
            ) : null}
          </div>

          <div className="flex gap-3 ml-auto text-xs text-neutral-400">
            <span>{done}/{changes.length} changes</span>
            <span className="hidden md:inline" title="Input tokens">In: {formatTokens(totals.input)}</span>
            <span className="hidden md:inline" title="Output tokens">Out: {formatTokens(totals.output)}</span>
            {totals.cacheRead > 0 && (
              <span className="hidden md:inline" title="Cache read">Cache: {formatTokens(totals.cacheRead)}</span>
            )}
          </div>

          <div className="flex gap-2 ml-2">
            {statusBadge === 'checkpoint' && (
              <button
                onClick={handleApprove}
                disabled={loading === 'approve'}
                className={`px-3 min-h-[44px] md:min-h-0 md:py-1 text-sm md:text-xs rounded font-medium disabled:opacity-50 ${
                  confirmAction === 'approve'
                    ? 'bg-green-600 text-white hover:bg-green-500'
                    : 'bg-green-900/60 text-green-300 hover:bg-green-900'
                }`}
              >
                {confirmAction === 'approve' ? 'Are you sure?' : 'Approve'}
              </button>
            )}
            {isActive && (
              <button
                onClick={handleStop}
                disabled={loading === 'stop'}
                className={`px-3 min-h-[44px] md:min-h-0 md:py-1 text-sm md:text-xs rounded font-medium disabled:opacity-50 ${
                  confirmAction === 'stop'
                    ? 'bg-red-700 text-white hover:bg-red-600'
                    : 'bg-red-900/50 text-red-300 hover:bg-red-900'
                }`}
              >
                {confirmAction === 'stop' ? 'Are you sure?' : 'Stop'}
              </button>
            )}
          </div>
        </>
      )}

      {!state && (
        <span className="ml-auto text-xs text-neutral-500">Waiting for data...</span>
      )}
    </div>
  )
}
