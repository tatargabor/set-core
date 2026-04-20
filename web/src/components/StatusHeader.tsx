import { useState, useEffect, useRef } from 'react'
import type { StateData } from '../lib/api'
import { stopOrchestrator, approve, getManagerProjectStatus, startSentinel, stopSentinel, restartSentinel, getProjectDocs, getState, getLineages, type ManagerProjectStatus, type LineageMeta } from '../lib/api'
import { useSelectedLineage } from '../lib/lineage'

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
  const [mgrStatus, setMgrStatus] = useState<ManagerProjectStatus | null>(null)
  const [sentinelBusy, setSentinelBusy] = useState(false)
  const [specPaths, setSpecPaths] = useState<string[]>([])
  const [spec, setSpec] = useState('docs/')
  const [showSpecInput, setShowSpecInput] = useState(false)
  const mgrJsonRef = useRef('')
  // Section 14.8 — the badge must reflect the LIVE lineage's status even
  // when the operator is viewing another lineage in the tabs.  We fetch
  // an unfiltered state alongside the filtered one used by the panels.
  const [liveState, setLiveState] = useState<StateData | null>(null)
  const [lineages, setLineages] = useState<LineageMeta[]>([])
  const { lineageId } = useSelectedLineage()

  // Poll manager status for sentinel state
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    let fails = 0
    const poll = () => {
      getManagerProjectStatus(project)
        .then(d => {
          fails = 0
          const json = JSON.stringify(d)
          if (json !== mgrJsonRef.current) {
            mgrJsonRef.current = json
            setMgrStatus(d)
          }
          timer = setTimeout(poll, 5000)
        })
        .catch(() => {
          fails++
          timer = setTimeout(poll, Math.min(5000 * Math.pow(2, fails), 30000))
        })
    }
    poll()
    return () => clearTimeout(timer)
  }, [project])

  // Live state (unfiltered) — drives the status badge regardless of the
  // lineage the tabs are currently viewing.  Poll with the same cadence
  // as the Dashboard state poll so the two stay in visual sync.
  useEffect(() => {
    let cancelled = false
    let iv: ReturnType<typeof setInterval>
    const poll = () => {
      getState(project)
        .then(d => { if (!cancelled) setLiveState(d) })
        .catch(() => {})
    }
    poll()
    iv = setInterval(poll, 5000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project])

  // Lineage metadata for display-name lookups.  We only need it when a
  // non-live lineage is selected, but fetching once on mount keeps the
  // dependency graph simple.
  useEffect(() => {
    let cancelled = false
    getLineages(project)
      .then(d => { if (!cancelled) setLineages(d.lineages) })
      .catch(() => {})
  }, [project, state?.spec_lineage_id])

  // Fetch spec paths once
  useEffect(() => {
    getProjectDocs(project)
      .then(d => {
        const paths = [
          ...d.docs.filter(e => e.type === 'dir').map(e => e.path),
          ...d.docs.filter(e => e.type === 'file').map(e => e.path),
        ]
        if (paths.length > 0 && !paths.includes('docs/')) paths.unshift('docs/')
        setSpecPaths(paths)
      })
      .catch(() => {})
  }, [project])

  const sentinelAlive = mgrStatus?.sentinel?.alive ?? false
  const activeSpec = mgrStatus?.sentinel?.spec

  const sentinelAct = async (fn: () => Promise<unknown>) => {
    setSentinelBusy(true)
    try { await fn() } catch {}
    finally { setSentinelBusy(false) }
  }

  // Status badge reflects the LIVE lineage (Section 14.8), not the
  // currently-viewed one.  `liveState` is the unfiltered /state fetch.
  const statusBadge = liveState?.status ?? state?.status ?? 'idle'
  const liveLineageId = liveState?.spec_lineage_id ?? null
  const viewingOtherLineage = lineageId != null
    && liveLineageId != null
    && lineageId !== liveLineageId
  const lookupDisplayName = (id: string | null): string => {
    if (id == null) return ''
    const m = lineages.find(l => l.id === id)
    return m?.display_name ?? id
  }
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
    done: 'bg-green-900 text-green-300',
    accepted: 'bg-green-900 text-green-300',
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
        <span className={`px-2 py-0.5 rounded text-sm font-medium ${badgeColor[statusBadge] ?? 'bg-neutral-800 text-neutral-400'}`}>
          {statusBadge}
        </span>
        <span className={`hidden md:inline-block ${connected ? 'text-green-500' : 'text-red-500'}`} title={connected ? 'Connected' : 'Disconnected'}>{connected ? '\u25CF' : '\u25CB'}</span>
        {viewingOtherLineage && (
          <span
            className="hidden md:inline text-xs text-amber-400 ml-1"
            title="The tabs below are filtered to a different lineage than the one the sentinel is running."
            data-testid="lineage-hint"
          >
            Viewing {lookupDisplayName(lineageId)} — sentinel running {lookupDisplayName(liveLineageId)}
          </span>
        )}
      </div>

      {state && (
        <>
          <div className="text-sm text-neutral-500 hidden md:block">
            {state.plan_version && <span>v{state.plan_version}</span>}
            {state.active_seconds ? (
              <span className="ml-2">{formatDuration(state.active_seconds)}</span>
            ) : null}
          </div>

          <div className="flex gap-3 ml-auto text-sm text-neutral-400">
            <span>{done}/{changes.length} changes</span>
            <span className="hidden md:inline" title="Total = input + output">{formatTokens(totals.input + totals.output)}</span>
            {totals.cacheRead > 0 && (
              <span className="hidden md:inline text-purple-400/60" title="Cache read (included in total)">({formatTokens(totals.cacheRead)} cached)</span>
            )}
          </div>

          <div className="flex gap-2 ml-2">
            {statusBadge === 'checkpoint' && (
              <button
                onClick={handleApprove}
                disabled={loading === 'approve'}
                className={`px-3 min-h-[44px] md:min-h-0 md:py-1 text-sm md:text-sm rounded font-medium disabled:opacity-50 ${
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
                className={`px-3 min-h-[44px] md:min-h-0 md:py-1 text-sm md:text-sm rounded font-medium disabled:opacity-50 ${
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
        <span className="ml-auto text-sm text-neutral-500">Waiting for data...</span>
      )}

      {/* Sentinel controls — right side */}
      {mgrStatus && (
        <div className="flex items-center gap-2 ml-auto md:ml-2 border-l border-neutral-800 pl-3">
          <span className={`w-2 h-2 rounded-full shrink-0 ${sentinelAlive ? 'bg-green-400' : 'bg-neutral-600'}`} />
          <span className="text-xs text-neutral-500 hidden md:inline">
            {sentinelAlive ? 'Sentinel' : 'Sentinel idle'}
          </span>
          {sentinelAlive ? (
            <>
              <button
                disabled={sentinelBusy}
                onClick={() => sentinelAct(() => stopSentinel(project))}
                className="px-2 py-0.5 text-xs rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400 disabled:opacity-50"
              >
                Stop
              </button>
              <button
                disabled={sentinelBusy}
                onClick={() => sentinelAct(() => restartSentinel(project, (activeSpec ?? spec) || undefined))}
                className="px-2 py-0.5 text-xs rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400 disabled:opacity-50"
              >
                Restart
              </button>
            </>
          ) : (
            <>
              {showSpecInput ? (
                <div className="flex items-center gap-1">
                  <input
                    type="text"
                    value={spec}
                    onChange={e => setSpec(e.target.value)}
                    list="spec-paths"
                    placeholder="docs/"
                    className="w-32 px-1.5 py-0.5 text-xs bg-neutral-800 border border-neutral-700 rounded text-neutral-200 focus:outline-none focus:border-blue-500"
                  />
                  <datalist id="spec-paths">
                    {specPaths.map(p => <option key={p} value={p} />)}
                  </datalist>
                  <button
                    disabled={sentinelBusy}
                    onClick={() => sentinelAct(() => startSentinel(project, spec || undefined))}
                    className="px-2 py-0.5 text-xs rounded bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 disabled:opacity-50"
                  >
                    {sentinelBusy ? 'Starting...' : 'Go'}
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowSpecInput(true)}
                  className="px-2 py-0.5 text-xs rounded bg-blue-600/20 hover:bg-blue-600/30 text-blue-400"
                >
                  Start
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
