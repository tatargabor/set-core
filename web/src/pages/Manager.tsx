import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { getProjects, type ProjectInfo } from '../lib/api'
import { sortByLastUpdated } from '../lib/sort'

const statusStyle: Record<string, { char: string; color: string; label: string }> = {
  running: { char: '\u25C9', color: 'text-green-400', label: 'Running' },
  planning: { char: '\u25C9', color: 'text-cyan-400', label: 'Planning' },
  checkpoint: { char: '\u25C9', color: 'text-yellow-400', label: 'Checkpoint' },
  completed: { char: '\u25CF', color: 'text-blue-400', label: 'Completed' },
  done: { char: '\u25CF', color: 'text-blue-400', label: 'Done' },
  stopped: { char: '\u25CB', color: 'text-neutral-500', label: 'Stopped' },
  failed: { char: '\u2715', color: 'text-red-400', label: 'Failed' },
  idle: { char: '\u25CB', color: 'text-neutral-600', label: 'Idle' },
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

function formatDuration(secs?: number): string {
  if (!secs) return '—'
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(mins / 60)
  const remMins = mins % 60
  return remMins > 0 ? `${hours}h${remMins}m` : `${hours}h`
}

export default function Manager() {
  const [projects, setProjects] = useState<ProjectInfo[]>([])
  const [loading, setLoading] = useState(true)
  const jsonRef = useRef('')

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    let fails = 0
    const poll = () => {
      getProjects()
        .then(data => {
          fails = 0
          const json = JSON.stringify(data)
          if (json !== jsonRef.current) {
            jsonRef.current = json
            setProjects(data)
          }
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
  }, [])

  const sorted = sortByLastUpdated(projects)

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <h1 className="text-lg md:text-xl font-semibold text-neutral-100 mb-4 md:mb-6">Projects</h1>

      {loading && projects.length === 0 && (
        <div className="text-sm text-neutral-500">Loading...</div>
      )}

      {!loading && sorted.length === 0 && (
        <div className="text-sm text-neutral-500 bg-neutral-900 rounded-lg p-4">
          No projects found. Register one with: <code className="text-neutral-300">set-project init</code>
        </div>
      )}

      {sorted.length > 0 && (
        <div className="border border-neutral-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-800 text-xs text-neutral-500 uppercase tracking-wider">
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-right px-4 py-2 font-medium">Changes</th>
                <th className="text-right px-4 py-2 font-medium">Tokens</th>
                <th className="text-right px-4 py-2 font-medium">Duration</th>
                <th className="text-right px-4 py-2 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((p) => {
                const s = statusStyle[p.status ?? 'idle'] ?? statusStyle.idle
                const hasChanges = (p.changes_total ?? 0) > 0
                return (
                  <tr key={p.name} className="border-b border-neutral-800/50 hover:bg-neutral-800/30 transition-colors">
                    <td className="px-4 py-2.5">
                      <Link to={`/p/${p.name}/orch`} className="flex items-center gap-2 hover:text-neutral-100">
                        <span className={`shrink-0 ${s.color}`}>{s.char}</span>
                        <span className="text-neutral-200 font-medium">{p.name}</span>
                      </Link>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs ${s.color}`}>{s.label}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-neutral-400">
                      {hasChanges ? `${p.changes_merged}/${p.changes_total}` : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right text-neutral-400">
                      {formatTokens(p.total_tokens)}
                    </td>
                    <td className="px-4 py-2.5 text-right text-neutral-400">
                      {formatDuration(p.active_seconds)}
                    </td>
                    <td className="px-4 py-2.5 text-right text-neutral-500">
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
