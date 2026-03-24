import { useProjectOverview } from '../hooks/useProjectOverview'
import { ProjectCard } from '../components/manager/ProjectCard'

export default function Manager() {
  const { projects, loading, error } = useProjectOverview()

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-neutral-100">Management Console</h1>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-red-950/30 border border-red-800 text-sm">
          <p className="text-red-400 font-medium">set-manager is not running</p>
          <p className="text-red-400/70 mt-1">Start it with: <code className="px-1 py-0.5 bg-neutral-800 rounded text-xs">set-manager serve</code></p>
        </div>
      )}

      {loading && !error && (
        <div className="text-sm text-neutral-500">Loading projects...</div>
      )}

      {!loading && !error && projects.length === 0 && (
        <div className="p-4 rounded-lg bg-neutral-900 border border-neutral-800 text-sm text-neutral-400">
          No projects registered. Add one with: <code className="px-1 py-0.5 bg-neutral-800 rounded text-xs">set-manager project add &lt;name&gt; &lt;path&gt;</code>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {projects.map(p => (
          <ProjectCard key={p.name} project={p} />
        ))}
      </div>

      {/* Service status bar */}
      {!error && (
        <div className="text-xs text-neutral-600 border-t border-neutral-800 pt-3">
          Manager: running | {projects.length} project{projects.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  )
}
