import { useState } from 'react'

interface Props {
  label: string
  alive: boolean
  startedAt?: string | null
  crashCount?: number
  onStart: () => Promise<unknown>
  onStop: () => Promise<unknown>
  onRestart: () => Promise<unknown>
}

function formatUptime(startedAt: string): string {
  const ms = Date.now() - new Date(startedAt).getTime()
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h${m % 60}m`
  return `${Math.floor(h / 24)}d`
}

export function ProcessControl({ label, alive, startedAt, crashCount, onStart, onStop, onRestart }: Props) {
  const [busy, setBusy] = useState(false)

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try { await fn() } catch { /* shown via status update */ }
    finally { setBusy(false) }
  }

  return (
    <div className="flex items-center justify-between gap-2">
      <div className="flex items-center gap-2 min-w-0">
        <span className={`w-2 h-2 rounded-full ${alive ? 'bg-green-400' : 'bg-neutral-600'}`} />
        <span className="text-sm text-neutral-300">{label}</span>
        {alive && startedAt && (
          <span className="text-xs text-neutral-500">{formatUptime(startedAt)}</span>
        )}
        {!alive && crashCount != null && crashCount > 0 && (
          <span className="text-xs text-red-400/60">({crashCount} crashes)</span>
        )}
      </div>
      <div className="flex items-center gap-1">
        {alive ? (
          <>
            <button disabled={busy} onClick={() => act(onStop)} className="px-2 py-0.5 text-xs rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400 disabled:opacity-50">Stop</button>
            <button disabled={busy} onClick={() => act(onRestart)} className="px-2 py-0.5 text-xs rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400 disabled:opacity-50">Restart</button>
          </>
        ) : (
          <button disabled={busy} onClick={() => act(onStart)} className="px-2 py-0.5 text-xs rounded bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 disabled:opacity-50">Start</button>
        )}
      </div>
    </div>
  )
}
