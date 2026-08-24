import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { getFleet, getProjectsWithArchiveInfo, type ProjectInfo } from '../lib/api'
import type { FleetResponse } from '../lib/fleetTypes'
import { buildProjectsView, type ProjectsViewMode } from '../lib/projectsView'
import { sortByLastUpdated } from '../lib/sort'
import { formatDuration } from '../lib/duration'

const statusStyle: Record<string, { char: string; color: string; label: string }> = {
  running: { char: '\u25C9', color: 'text-green-400', label: 'Running' },
  planning: { char: '\u25C9', color: 'text-cyan-400', label: 'Planning' },
  checkpoint: { char: '\u25C9', color: 'text-yellow-400', label: 'Checkpoint' },
  completed: { char: '\u25CF', color: 'text-blue-400', label: 'Completed' },
  done: { char: '\u25CF', color: 'text-blue-400', label: 'Done' },
  stopped: { char: '\u25CB', color: 'text-fg-faint', label: 'Stopped' },
  failed: { char: '\u2715', color: 'text-red-400', label: 'Failed' },
  idle: { char: '\u25CB', color: 'text-fg-ghost', label: 'Idle' },
  error: { char: '\u2715', color: 'text-red-400', label: 'Error' },
  corrupt: { char: '\u2715', color: 'text-red-400', label: 'Corrupt' },
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatTokens(n?: number): string {
  if (!n) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}



export default function Manager() {
  const [projects, setProjects] = useState<ProjectInfo[]>([])
  const [archivedCount, setArchivedCount] = useState(0)
  const [showArchived, setShowArchived] = useState(false)
  const [loading, setLoading] = useState(true)
  /**
   * The fleet's answer, or `null` for "not measured". The two are rendered
   * differently everywhere below: a fleet outage that produced a column of
   * zeros would be more convincing than the screen this replaced.
   */
  const [fleet, setFleet] = useState<FleetResponse | null>(null)
  /**
   * Neither the view nor the filter is persisted — deliberately. The screen
   * must open on the full listing, and a remembered filter is how a reader ends
   * up looking at three rows believing they are all of them.
   */
  const [mode, setMode] = useState<ProjectsViewMode>('all')
  const [query, setQuery] = useState('')
  const jsonRef = useRef('')

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    let fails = 0
    const poll = () => {
      getProjectsWithArchiveInfo(showArchived)
        .then(({ projects: data, archivedCount: n }) => {
          fails = 0
          const json = JSON.stringify(data)
          if (json !== jsonRef.current) {
            jsonRef.current = json
            setProjects(data)
          }
          setArchivedCount(n)
          setLoading(false)
          timer = setTimeout(poll, 5000)
        })
        .catch(() => {
          fails++
          setLoading(false)
          timer = setTimeout(poll, Math.min(5000 * Math.pow(2, fails), 30000))
        })
    }
    poll()
    return () => clearTimeout(timer)
  }, [showArchived])

  // The fleet is polled on its own timer so the two answers fail
  // independently: a fleet outage must leave the listing intact, and a projects
  // outage must not make live work look absent.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    const poll = () => {
      getFleet()
        .then(d => setFleet(d))
        .catch(() => setFleet(null))
        .finally(() => { timer = setTimeout(poll, 5000) })
    }
    poll()
    return () => clearTimeout(timer)
  }, [])

  const sorted = sortByLastUpdated(projects)
  const view = buildProjectsView(sorted, fleet, { mode, query })
  const hidden = view.hiddenByView + view.hiddenByFilter

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-baseline gap-3 mb-3 md:mb-4">
        <h1 className="text-lg md:text-xl font-semibold text-fg-loud">Projects</h1>
        {archivedCount > 0 && (
          // Hidden rows must stay counted where the reader is standing — a
          // shorter list otherwise reads as "that is everything".
          <button
            onClick={() => setShowArchived(v => !v)}
            className="text-xs text-fg-faint hover:text-fg-normal underline underline-offset-2 transition-colors"
          >
            {showArchived ? 'hide' : 'show'} {archivedCount} archived
          </button>
        )}
      </div>

      {/* The control strip. Both view sizes are on it, so the reader learns what
          the other view holds without switching to it — and the live count is
          the one fact the `Status` column below cannot be trusted for. */}
      <div className="flex flex-wrap items-center gap-2 mb-3 md:mb-4" data-projects-controls>
        <div className="inline-flex rounded-md border border-surface-line overflow-hidden text-xs">
          {(['all', 'live'] as ProjectsViewMode[]).map(m => {
            const on = mode === m
            const size = m === 'all'
              ? String(view.totalAll)
              // A live size of 0 with no measurement behind it would read as
              // "measured: nothing is live". Say the measurement is missing.
              : view.liveMeasured ? String(view.totalLive) : '?'
            return (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={on}
                data-projects-view={m}
                data-projects-view-active={on ? 'on' : undefined}
                onClick={() => setMode(m)}
                title={m === 'live' && !view.liveMeasured
                  ? 'Live sessions are unmeasured — the fleet did not answer.'
                  : undefined}
                className={`px-3 py-1.5 transition-colors ${
                  on ? 'bg-surface-raised text-fg-loud' : 'text-fg-faint hover:text-fg-normal'
                } ${m === 'live' ? 'border-l border-surface-line' : ''}`}
              >
                {m === 'all' ? 'All' : 'Live sessions'}{' '}
                <span className="tabular-nums text-fg-muted">{size}</span>
              </button>
            )
          })}
        </div>

        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Filter by name…"
            aria-label="Filter projects by name"
            data-projects-filter
            className="w-56 bg-surface-panel border border-surface-line rounded-md px-2.5 py-1.5 text-xs text-fg-normal placeholder:text-fg-ghost focus:outline-none focus:border-fg-dim"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              aria-label="Clear the name filter"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-fg-faint hover:text-fg-normal text-xs px-1"
            >
              ✕
            </button>
          )}
        </div>

        {/* What is NOT on screen, next to the table rather than only at the
            control that caused it. A view and a filter are compaction
            mechanisms whose blast radius is whole rows, and the reader chose
            them — which is when a hidden failure is least likely to be sought. */}
        {hidden > 0 && (
          <span className="text-xs text-fg-faint" data-projects-hidden={hidden}>
            {hidden} not shown
            <span className="text-fg-ghost">
              {' '}({[
                view.hiddenByView > 0 ? `${view.hiddenByView} without a live session` : null,
                view.hiddenByFilter > 0 ? `${view.hiddenByFilter} filtered out` : null,
              ].filter(Boolean).join(', ')})
            </span>
            {' · '}
            <button
              type="button"
              onClick={() => { setMode('all'); setQuery('') }}
              data-projects-clear
              className="underline underline-offset-2 hover:text-fg-normal"
            >
              show all
            </button>
          </span>
        )}

        {!view.liveMeasured && (
          <span className="text-xs text-amber-400" data-projects-live-unmeasured
                title="GET /api/fleet/agents did not answer. A zero here would state that nothing is live, which was not measured.">
            live sessions unmeasured
          </span>
        )}
      </div>

      {loading && projects.length === 0 && (
        <div className="text-sm text-fg-faint">Loading...</div>
      )}

      {!loading && sorted.length === 0 && (
        <div className="text-sm text-fg-faint bg-surface-panel rounded-lg p-4">
          No projects found. Register one with: <code className="text-fg-normal">set-project init</code>
        </div>
      )}

      {/* An empty table must never read as an empty answer. Each reason for the
          emptiness says which one it is, and leaves the way back one click. */}
      {!loading && sorted.length > 0 && view.rows.length === 0 && (
        <div className="text-sm bg-surface-panel rounded-lg p-4" data-projects-empty>
          {mode === 'live' && !view.liveMeasured ? (
            <span className="text-amber-400">
              Live sessions could not be measured — the fleet did not answer. This is not
              a measurement that nothing is live.
            </span>
          ) : mode === 'live' && view.totalLive === 0 ? (
            <span className="text-fg-faint">No project has a live agent session right now.</span>
          ) : (
            <span className="text-fg-faint">No project name matches “{query}”.</span>
          )}
          {' '}
          <button
            type="button"
            onClick={() => { setMode('all'); setQuery('') }}
            data-projects-clear
            className="text-fg-faint underline underline-offset-2 hover:text-fg-normal"
          >
            show all {view.totalAll}
          </button>
        </div>
      )}

      {/* The wrapper below carries no overflow-hidden: that would make it a scroll
          container, anchoring the sticky header to a box that never scrolls —
          measured, the header still slid to y=-916. Rounding lives on the border. */}
      {view.rows.length > 0 && (
        <div className="border border-surface-line rounded-lg">
          <table className="w-full text-sm">
            {/* Sticky since the page became scrollable: at 38 rows the header
                scrolls away, and an unlabelled column of numbers is not data
                anyone can read. */}
            <thead className="sticky top-0 z-10 bg-surface-page">
              <tr className="border-b border-surface-line text-xs text-fg-faint uppercase tracking-wider">
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                {/* In BOTH views. The `Status` column beside it is the
                    orchestration record, measured saying "Stopped, 24 days ago"
                    over six working agents; this one is counted from live
                    processes. Hiding it behind the live view would leave the
                    default screen exactly as misleading as before. */}
                <th className="text-right px-4 py-2 font-medium">Live</th>
                <th className="text-right px-4 py-2 font-medium">Changes</th>
                <th className="text-right px-4 py-2 font-medium">Tokens</th>
                <th className="text-right px-4 py-2 font-medium">Duration</th>
                <th className="text-right px-4 py-2 font-medium">Issues</th>
                <th className="text-right px-4 py-2 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {view.rows.map((row) => {
                const p = row.project
                // A row the fleet measured as live that the registry never
                // returned. It has a name and a session count and nothing else
                // — and no link, because `/p/<name>/status` does not resolve for
                // a project the registry does not hold.
                if (!p) return (
                  <tr key={`unregistered:${row.name}`}
                      data-projects-unregistered={row.name}
                      className="border-b border-surface-line/50 hover:bg-surface-raised/30 transition-colors">
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2">
                        <span className="shrink-0 text-green-400">◉</span>
                        <span className="text-fg-strong font-medium">{row.name}</span>
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs text-amber-400"
                            title="The fleet measures a live session here, and the project registry does not hold this project. Register it with: set-project init">
                        not registered
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-green-400 tabular-nums"
                        data-projects-live={row.liveSessions ?? 'unmeasured'}>
                      {row.liveSessions}
                    </td>
                    {/* One dash per column, not a single spanning cell: a
                        right-aligned span put its dash under `Issues`, where it
                        reads as a value for that column rather than as four
                        facts the registry does not hold. */}
                    {['changes', 'tokens', 'duration', 'issues', 'updated'].map(c => (
                      <td key={c} className="px-4 py-2.5 text-right text-fg-ghost">—</td>
                    ))}
                  </tr>
                )
                const s = statusStyle[p.status ?? 'idle'] ?? statusStyle.idle
                const hasChanges = (p.changes_total ?? 0) > 0
                return (
                  <tr key={p.name} className="border-b border-surface-line/50 hover:bg-surface-raised/30 transition-colors">
                    <td className="px-4 py-2.5">
                      {/* The archived mark rides on the status glyph rather than
                          adding a badge: a badge widened this column enough to
                          wrap names, issue labels and token counts onto two
                          lines — the toggle made the whole table less legible,
                          which the row/badge counts could not see. */}
                      <Link
                        to={`/p/${p.name}/status`}
                        className="flex items-center gap-2 hover:text-fg-loud"
                        title={p.archived ? `archived ${p.archivedAt?.slice(0, 10) ?? ''}` : undefined}
                      >
                        <span className={`shrink-0 ${p.archived ? 'text-fg-dim' : s.color}`}>
                          {p.archived ? '◌' : s.char}
                        </span>
                        <span className={p.archived ? 'text-fg-faint' : 'text-fg-strong font-medium'}>
                          {p.name}
                        </span>
                      </Link>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs ${s.color}`}>{s.label}</span>
                    </td>
                    {/* Three states, not two: a count, a measured zero (a dash),
                        and unmeasured — which is never rendered as a zero. */}
                    <td className="px-4 py-2.5 text-right tabular-nums"
                        data-projects-live={row.liveSessions ?? 'unmeasured'}>
                      {row.liveSessions === null ? (
                        <span className="text-amber-400 text-xs"
                              title="The fleet did not answer, so this is unknown — not zero.">?</span>
                      ) : row.liveSessions > 0 ? (
                        <span className="text-green-400">{row.liveSessions}</span>
                      ) : (
                        <span className="text-fg-ghost">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right text-fg-muted">
                      {hasChanges ? `${p.changes_merged}/${p.changes_total}` : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right text-fg-muted">
                      {formatTokens(p.total_tokens)}
                      {(p as any).cache_tokens > 0 && (
                        <span className="text-purple-400/50 text-xs ml-1">({formatTokens((p as any).cache_tokens)} cached)</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right text-fg-muted">
                      {formatDuration(p.active_seconds)}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {(p.issues_open ?? 0) > 0
                        ? <span className="text-amber-400">{p.issues_open} open</span>
                        : (p.issues_total ?? 0) > 0
                          ? <span className="text-fg-faint">{p.issues_total} closed</span>
                          : <span className="text-fg-ghost">—</span>
                      }
                    </td>
                    <td className="px-4 py-2.5 text-right text-fg-faint">
                      {timeAgo(p.last_updated)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
