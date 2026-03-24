import { useState, useRef, useEffect } from 'react'
import { startSentinel, stopSentinel, restartSentinel } from '../../lib/api'

interface Props {
  project: string
  alive: boolean
  startedAt?: string | null
  crashCount?: number
  specPaths: string[]
  onAction?: () => void
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

export function SentinelControl({ project, alive, startedAt, crashCount, specPaths, onAction }: Props) {
  const [busy, setBusy] = useState(false)
  const [spec, setSpec] = useState(specPaths[0] ?? 'docs/')
  const [showDropdown, setShowDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
      onAction?.()
    } catch { /* status poll will update */ }
    finally { setBusy(false) }
  }

  const filtered = specPaths.filter(p =>
    p.toLowerCase().includes(spec.toLowerCase())
  )

  return (
    <div className="space-y-3">
      {/* Status */}
      <div className="flex items-center gap-2">
        <span className={`w-2.5 h-2.5 rounded-full ${alive ? 'bg-green-400' : 'bg-neutral-600'}`} />
        <span className="text-sm font-medium text-neutral-200">Sentinel</span>
        {alive && startedAt && (
          <span className="text-xs text-neutral-500">running {formatUptime(startedAt)}</span>
        )}
        {!alive && (
          <span className="text-xs text-neutral-500">idle</span>
        )}
        {crashCount != null && crashCount > 0 && (
          <span className="text-xs text-red-400/60">({crashCount} crashes)</span>
        )}
      </div>

      {/* Spec path input + buttons */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1" ref={dropdownRef}>
          <label className="text-xs text-neutral-500 block mb-1">Spec path</label>
          <input
            type="text"
            value={spec}
            onChange={e => { setSpec(e.target.value); setShowDropdown(true) }}
            onFocus={() => setShowDropdown(true)}
            placeholder="docs/"
            className="w-full px-2 py-1.5 text-sm bg-neutral-800 border border-neutral-700 rounded text-neutral-200 placeholder:text-neutral-600 focus:border-blue-500 focus:outline-none"
          />
          {showDropdown && filtered.length > 0 && (
            <div className="absolute z-10 mt-1 w-full bg-neutral-800 border border-neutral-700 rounded shadow-lg max-h-40 overflow-y-auto">
              {filtered.map(p => (
                <button
                  key={p}
                  onClick={() => { setSpec(p); setShowDropdown(false) }}
                  className="block w-full text-left px-2 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700"
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-1 pt-5">
          {alive ? (
            <>
              <button
                disabled={busy}
                onClick={() => act(() => stopSentinel(project))}
                className="px-3 py-1.5 text-xs rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400 disabled:opacity-50"
              >
                Stop
              </button>
              <button
                disabled={busy}
                onClick={() => act(() => restartSentinel(project, spec || undefined))}
                className="px-3 py-1.5 text-xs rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400 disabled:opacity-50"
              >
                Restart
              </button>
            </>
          ) : (
            <button
              disabled={busy}
              onClick={() => act(() => startSentinel(project, spec || undefined))}
              className="px-3 py-1.5 text-xs rounded bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 disabled:opacity-50"
            >
              Start Sentinel
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
