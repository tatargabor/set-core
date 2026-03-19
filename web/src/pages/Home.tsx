import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getProjects, type ProjectInfo } from '../lib/api'
import { sortByLastUpdated } from '../lib/sort'

const statusStyle: Record<string, { dot: string; label: string }> = {
  running: { dot: 'bg-green-500 animate-pulse', label: 'Running' },
  planning: { dot: 'bg-cyan-500 animate-pulse', label: 'Planning' },
  checkpoint: { dot: 'bg-yellow-500 animate-pulse', label: 'Checkpoint' },
  completed: { dot: 'bg-blue-500', label: 'Completed' },
  stopped: { dot: 'bg-neutral-500', label: 'Stopped' },
  failed: { dot: 'bg-red-500', label: 'Failed' },
  idle: { dot: 'bg-neutral-700', label: 'Idle' },
  error: { dot: 'bg-red-900', label: 'Error' },
  corrupt: { dot: 'bg-red-500 animate-pulse', label: 'Corrupt State' },
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

function ProjectCard({ project, compact }: { project: ProjectInfo; compact?: boolean }) {
  const s = statusStyle[project.status ?? 'idle'] ?? statusStyle.idle
  const ago = timeAgo(project.last_updated)

  return (
    <Link
      to={`/set/${project.name}`}
      className={`block rounded-lg border border-neutral-800 hover:border-neutral-700 transition-colors ${
        compact ? 'p-3' : 'p-4 bg-neutral-900/50'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${s.dot}`} />
        <span className="font-mono text-sm text-neutral-200 truncate">{project.name}</span>
        <span className="ml-auto text-[10px] text-neutral-600 shrink-0">{ago}</span>
        {!compact && (
          <span className="text-xs text-neutral-500 shrink-0">{s.label}</span>
        )}
      </div>
      {!compact && (
        <div className="mt-1 text-xs text-neutral-500 font-mono truncate">{project.path}</div>
      )}
    </Link>
  )
}
