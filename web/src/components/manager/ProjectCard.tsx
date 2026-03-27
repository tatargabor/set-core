import { Link } from 'react-router-dom'
import type { ManagerProjectStatus } from '../../lib/api'
import { ModeBadge } from './ModeBadge'
import { IssueCountBadge } from '../issues/IssueCountBadge'

export function ProjectCard({ project }: { project: ManagerProjectStatus }) {
  const sentinelAlive = project.sentinel?.alive

  return (
    <Link
      to={`/manager/${project.name}`}
      className="block border border-neutral-800 rounded-lg p-4 bg-neutral-900/50 space-y-3 hover:border-neutral-600 transition-colors"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-100">{project.name}</h3>
        <ModeBadge mode={project.mode} />
      </div>

      {/* Status summary */}
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${sentinelAlive ? 'bg-green-400' : 'bg-neutral-600'}`} />
        <span className="text-xs text-neutral-400">
          {sentinelAlive ? 'Sentinel running' : 'Idle'}
        </span>
        {sentinelAlive && (project.sentinel?.crash_count ?? 0) > 0 && (
          <span className="text-xs text-red-400/60">({project.sentinel?.crash_count} crashes)</span>
        )}
      </div>

      {/* Issues summary */}
      <div className="flex items-center justify-between pt-1 border-t border-neutral-800">
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-500">Issues</span>
          <IssueCountBadge stats={project.issue_stats} />
        </div>
        <span className="text-xs text-neutral-500">→</span>
      </div>
    </Link>
  )
}
