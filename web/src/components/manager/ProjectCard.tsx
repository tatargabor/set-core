import { Link } from 'react-router-dom'
import type { ManagerProjectStatus } from '../../lib/api'
import { startSentinel, stopSentinel, restartSentinel, startOrchestration, stopOrchestration } from '../../lib/api'
import { ModeBadge } from './ModeBadge'
import { ProcessControl } from './ProcessControl'
import { IssueCountBadge } from '../issues/IssueCountBadge'

export function ProjectCard({ project }: { project: ManagerProjectStatus }) {
  return (
    <div className="border border-neutral-800 rounded-lg p-4 bg-neutral-900/50 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-100">{project.name}</h3>
        <ModeBadge mode={project.mode} />
      </div>

      {/* Processes */}
      <div className="space-y-2">
        <ProcessControl
          label="Orchestrator"
          alive={project.orchestrator.alive}
          startedAt={project.orchestrator.started_at}
          onStart={() => startOrchestration(project.name)}
          onStop={() => stopOrchestration(project.name)}
          onRestart={async () => { await stopOrchestration(project.name); await startOrchestration(project.name) }}
        />
        <ProcessControl
          label="Sentinel"
          alive={project.sentinel.alive}
          startedAt={project.sentinel.started_at}
          crashCount={project.sentinel.crash_count}
          onStart={() => startSentinel(project.name)}
          onStop={() => stopSentinel(project.name)}
          onRestart={() => restartSentinel(project.name)}
        />
      </div>

      {/* Issues summary */}
      <div className="flex items-center justify-between pt-1 border-t border-neutral-800">
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-500">Issues</span>
          <IssueCountBadge stats={project.issue_stats} />
        </div>
        <Link
          to={`/manager/${project.name}/issues`}
          className="text-xs text-blue-400 hover:text-blue-300"
        >
          View Issues
        </Link>
      </div>
    </div>
  )
}
