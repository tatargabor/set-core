import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getProjects, type ProjectInfo } from '../lib/api'
import { sortByLastUpdated } from '../lib/sort'

const statusStyle: Record<string, { char: string; color: string; label: string }> = {
  running: { char: '\u25C9', color: 'text-green-400', label: 'Running' },
  planning: { char: '\u25C9', color: 'text-cyan-400', label: 'Planning' },
  checkpoint: { char: '\u25C9', color: 'text-yellow-400', label: 'Checkpoint' },
  completed: { char: '\u25CF', color: 'text-blue-400', label: 'Completed' },
  stopped: { char: '\u25CB', color: 'text-neutral-500', label: 'Stopped' },
  failed: { char: '\u2715', color: 'text-red-400', label: 'Failed' },
  idle: { char: '\u25CB', color: 'text-neutral-600', label: 'Idle' },
  error: { char: '\u2715', color: 'text-red-400', label: 'Error' },
  corrupt: { char: '\u2715', color: 'text-red-400', label: 'Corrupt State' },
}

export default function Home() {
  const [projects, setProjects] = useState<ProjectInfo[]>([])

  useEffect(() => {
    const load = () => getProjects().then(setProjects).catch(() => {})
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [])

  const active = sortByLastUpdated(projects.filter((p) => p.status && !['idle', 'error'].includes(p.status)))
  const idle = sortByLastUpdated(projects.filter((p) => !p.status || p.status === 'idle'))
  const errored = sortByLastUpdated(projects.filter((p) => p.status === 'error'))

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <h1 className="text-lg md:text-xl font-semibold text-neutral-100 mb-4 md:mb-6">Projects</h1>

      {active.length > 0 && (
        <section className="mb-8">
          <h2 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-3">Active Orchestrations</h2>
          <div className="space-y-2">
            {active.map((p) => (
              <ProjectCard key={p.name} project={p} />
            ))}
          </div>
        </section>
      )}

      <section className="mb-8">
        <h2 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-3">
          Projects ({idle.length})
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {idle.map((p) => (
            <ProjectCard key={p.name} project={p} compact />
          ))}
        </div>
      </section>

      {errored.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-3">
            Unavailable ({errored.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {errored.map((p) => (
              <ProjectCard key={p.name} project={p} compact />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

function formatDuration(secs: number): string {
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(mins / 60)
  const remMins = mins % 60
  return remMins > 0 ? `${hours}h${remMins}m` : `${hours}h`
}

function ProjectCard({ project, compact }: { project: ProjectInfo; compact?: boolean }) {
  const s = statusStyle[project.status ?? 'idle'] ?? statusStyle.idle
  const ago = timeAgo(project.last_updated)
  const hasStats = project.changes_total != null && project.changes_total > 0

  return (
    <Link
      to={`/set/${project.name}`}
      className={`block rounded-lg border border-neutral-800 hover:border-neutral-700 transition-colors ${
        compact ? 'p-3' : 'p-4 bg-neutral-900/50'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className={`shrink-0 ${s.color}`}>{s.char}</span>
        <span className="text-sm text-neutral-200 truncate">{project.name}</span>
        <span className="ml-auto text-sm text-neutral-600 shrink-0">{ago}</span>
        {!compact && (
          <span className="text-sm text-neutral-500 shrink-0">{s.label}</span>
        )}
      </div>
      {hasStats && (
        <div className="mt-1.5 flex items-center gap-3 text-xs text-neutral-500">
          <span>{project.changes_merged}/{project.changes_total} merged</span>
          {(project.total_tokens ?? 0) > 0 && (
            <span>{formatTokens(project.total_tokens!)} tokens</span>
          )}
          {(project.active_seconds ?? 0) > 0 && (
            <span>{formatDuration(project.active_seconds!)}</span>
          )}
        </div>
      )}
      {!compact && !hasStats && (
        <div className="mt-1 text-sm text-neutral-500 truncate">{project.path}</div>
      )}
    </Link>
  )
}
