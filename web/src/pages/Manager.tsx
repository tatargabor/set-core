import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { getProjectsWithArchiveInfo, type ProjectInfo } from '../lib/api'
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

  const sorted = sortByLastUpdated(projects)

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-baseline gap-3 mb-4 md:mb-6">
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

      {loading && projects.length === 0 && (
        <div className="text-sm text-fg-faint">Loading...</div>
      )}

      {!loading && sorted.length === 0 && (
        <div className="text-sm text-fg-faint bg-surface-panel rounded-lg p-4">
          No projects found. Register one with: <code className="text-fg-normal">set-project init</code>
        </div>
      )}

      {/* The wrapper below carries no overflow-hidden: that would make it a scroll
          container, anchoring the sticky header to a box that never scrolls —
          measured, the header still slid to y=-916. Rounding lives on the border. */}
      {sorted.length > 0 && (
        <div className="border border-surface-line rounded-lg">
          <table className="w-full text-sm">
            {/* Sticky since the page became scrollable: at 38 rows the header
                scrolls away, and an unlabelled column of numbers is not data
                anyone can read. */}
            <thead className="sticky top-0 z-10 bg-surface-page">
              <tr className="border-b border-surface-line text-xs text-fg-faint uppercase tracking-wider">
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-right px-4 py-2 font-medium">Changes</th>
                <th className="text-right px-4 py-2 font-medium">Tokens</th>
                <th className="text-right px-4 py-2 font-medium">Duration</th>
                <th className="text-right px-4 py-2 font-medium">Issues</th>
                <th className="text-right px-4 py-2 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((p) => {
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
