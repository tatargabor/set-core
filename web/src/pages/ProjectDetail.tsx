import { Link, useParams } from 'react-router-dom'
import { useProjectDetail } from '../hooks/useProjectDetail'
import { SentinelControl } from '../components/manager/SentinelControl'
import { ModeBadge } from '../components/manager/ModeBadge'
import { IssueCountBadge } from '../components/issues/IssueCountBadge'

export default function ProjectDetail() {
  const { project: projectName } = useParams<{ project: string }>()
  const { project, specPaths, loading, error } = useProjectDetail(projectName)

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-sm text-neutral-500">Loading project...</div>
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="p-6 space-y-4">
        <Link to="/manager" className="text-xs text-blue-400 hover:text-blue-300">← Back to overview</Link>
        <div className="p-4 rounded-lg bg-red-950/30 border border-red-800 text-sm">
          <p className="text-red-400 font-medium">{error === 'Project not found' ? `Project "${projectName}" not found` : error || 'Failed to load project'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/manager" className="text-neutral-500 hover:text-neutral-300 text-sm">← Back</Link>
          <h1 className="text-lg font-semibold text-neutral-100">{project.name}</h1>
          <ModeBadge mode={project.mode} />
        </div>
      </div>

      {/* Status overview */}
      <div className="border border-neutral-800 rounded-lg p-4 bg-neutral-900/50 space-y-2">
        <h2 className="text-xs font-medium text-neutral-500 uppercase tracking-wide">Status</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-neutral-500">Orchestrator: </span>
            <span className={project.orchestrator?.alive ? 'text-green-400' : 'text-neutral-400'}>
              {project.orchestrator?.alive ? `running (PID ${project.orchestrator?.pid})` : 'idle'}
            </span>
          </div>
          <div>
            <span className="text-neutral-500">Path: </span>
            <span className="text-neutral-400 text-xs font-mono">{project.path}</span>
          </div>
        </div>
      </div>

      {/* Sentinel Control */}
      <div className="border border-neutral-800 rounded-lg p-4 bg-neutral-900/50">
        <h2 className="text-xs font-medium text-neutral-500 uppercase tracking-wide mb-3">Sentinel Control</h2>
        <SentinelControl
          project={project.name}
          alive={project.sentinel?.alive ?? false}
          startedAt={project.sentinel?.started_at ?? null}
          crashCount={project.sentinel?.crash_count ?? 0}
          activeSpec={project.sentinel?.spec ?? null}
          specPaths={specPaths}
        />
      </div>

      {/* Issues summary */}
      <div className="border border-neutral-800 rounded-lg p-4 bg-neutral-900/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-medium text-neutral-500 uppercase tracking-wide">Issues</h2>
            {project.issue_stats && <IssueCountBadge stats={project.issue_stats} />}
          </div>
          <Link
            to={`/manager/${project.name}/issues`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            View Issues →
          </Link>
        </div>
      </div>
    </div>
  )
}
