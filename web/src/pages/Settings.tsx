import { useEffect, useState, useCallback } from 'react'
import { shutdownOrchestration, stopOrchestrator } from '../lib/api'

interface Props {
  project: string | null
}

interface DataSource {
  available: boolean
  count?: number
  changes?: number
}

interface SettingsData {
  project_path: string
  state_path?: string | null
  config_path?: string
  config: Record<string, unknown>
  config_raw?: string
  has_claude_md: boolean
  has_project_knowledge: boolean
  runs_dir?: string | null
  runs_count?: number
  orchestrator_pid?: number | null
  sentinel_pid?: number | null
  plan_version?: string | number | null
  data_sources?: Record<string, DataSource>
}

function ConfigValue({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className="text-xs text-neutral-500 w-36 shrink-0">{label}</span>
      <span className="text-xs text-neutral-300 break-all">{value ?? <span className="text-neutral-600">—</span>}</span>
    </div>
  )
}

export default function Settings({ project }: Props) {
  const [data, setData] = useState<SettingsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)

  useEffect(() => {
    if (!project) { setData(null); return }
    setLoading(true)
    fetch(`/api/${project}/settings`)
      .then(r => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [project])

  const handleShutdown = useCallback(async () => {
    if (!project) return
    setShowConfirm(false)
    setActionLoading('shutdown')
    try {
      await shutdownOrchestration(project)
    } catch {
      try { await stopOrchestrator(project) } catch {}
    }
    setActionLoading(null)
    fetch(`/api/${project}/settings`).then(r => r.json()).then(setData).catch(() => {})
  }, [project])

  const handleResume = useCallback(async () => {
    if (!project) return
    setActionLoading('resume')
    try {
      await fetch(`/api/${project}/start`, { method: 'POST' })
    } catch {}
    setActionLoading(null)
    fetch(`/api/${project}/settings`).then(r => r.json()).then(setData).catch(() => {})
  }, [project])

  if (!project) {
    return <div className="flex items-center justify-center h-full text-neutral-500">Select a project</div>
  }
  if (loading) {
    return <div className="p-6 text-neutral-500 text-sm">Loading...</div>
  }
  if (!data) {
    return <div className="p-6 text-neutral-500 text-sm">Failed to load settings</div>
  }

  const directives = data.config?.directives as Record<string, unknown> | undefined

  const orchStatus = (data.config as Record<string, unknown>)?.status as string | undefined
  const isShutdown = orchStatus === 'shutdown'
  const isRunning = orchStatus === 'running' || orchStatus === 'checkpoint'

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <h1 className="text-lg font-semibold text-neutral-100">Settings</h1>

      {/* Orchestration Control */}
      <section>
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Orchestration Control</h2>
        <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs text-neutral-500">Status</span>
              <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${
                isRunning ? 'bg-green-900/50 text-green-300' :
                isShutdown ? 'bg-amber-900/50 text-amber-300' :
                orchStatus === 'done' ? 'bg-blue-900/50 text-blue-300' :
                'bg-neutral-800 text-neutral-400'
              }`}>
                <span className={
                  isRunning ? 'text-green-400' :
                  isShutdown ? 'text-amber-400' :
                  orchStatus === 'done' ? 'text-blue-400' :
                  'text-neutral-500'
                }>{isRunning ? '\u25C9' : orchStatus === 'done' ? '\u25CF' : '\u25CB'}</span>
                {orchStatus ?? 'unknown'}
              </span>
            </div>
            <div className="flex gap-2">
              {isShutdown ? (
                <button
                  onClick={handleResume}
                  disabled={actionLoading === 'resume'}
                  className="px-3 py-1 text-xs bg-green-900/50 text-green-300 rounded hover:bg-green-900 disabled:opacity-50 font-medium"
                >
                  {actionLoading === 'resume' ? 'Resuming...' : 'Resume'}
                </button>
              ) : isRunning ? (
                <>
                  <button
                    onClick={() => setShowConfirm(true)}
                    disabled={actionLoading === 'shutdown'}
                    className="px-3 py-1 text-xs bg-red-900/50 text-red-300 rounded hover:bg-red-900 disabled:opacity-50 font-medium"
                  >
                    {actionLoading === 'shutdown' ? 'Shutting down...' : 'Shutdown'}
                  </button>
                </>
              ) : null}
            </div>
          </div>

          {/* Confirmation dialog */}
          {showConfirm && (
            <div className="mt-3 p-3 bg-red-950/30 border border-red-900/50 rounded-lg">
              <p className="text-xs text-red-300 mb-2">
                This will gracefully stop all agents and the orchestrator. Worktree state will be preserved for resume. Continue?
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleShutdown}
                  className="px-3 py-1 text-xs bg-red-800 text-red-100 rounded hover:bg-red-700 font-medium"
                >
                  Confirm Shutdown
                </button>
                <button
                  onClick={() => setShowConfirm(false)}
                  className="px-3 py-1 text-xs bg-neutral-800 text-neutral-300 rounded hover:bg-neutral-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Paths */}
      <section>
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Paths</h2>
        <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-2 divide-y divide-neutral-800/50">
          <ConfigValue label="Project path" value={data.project_path} />
          <ConfigValue label="State file" value={data.state_path} />
          <ConfigValue label="Config file" value={data.config_path} />
          <ConfigValue label="Runs directory" value={data.runs_dir ? `${data.runs_dir} (${data.runs_count ?? '?'} runs)` : null} />
        </div>
      </section>

      {/* Status */}
      <section>
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Runtime</h2>
        <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-2 divide-y divide-neutral-800/50">
          <ConfigValue label="Orchestrator PID" value={data.orchestrator_pid} />
          <ConfigValue label="Sentinel PID" value={data.sentinel_pid} />
          <ConfigValue label="Plan version" value={data.plan_version != null ? `v${data.plan_version}` : null} />
          <ConfigValue label="CLAUDE.md" value={data.has_claude_md ? 'Present' : 'Not found'} />
          <ConfigValue label="Project knowledge" value={data.has_project_knowledge ? 'Present' : 'Not found'} />
        </div>
      </section>

      {/* Directives */}
      {directives && Object.keys(directives).length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Orchestration Directives</h2>
          <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-2 divide-y divide-neutral-800/50">
            {Object.entries(directives).map(([k, v]) => (
              <ConfigValue key={k} label={k} value={typeof v === 'object' ? JSON.stringify(v) : String(v ?? '')} />
            ))}
          </div>
        </section>
      )}

      {/* Data Sources */}
      {data.data_sources && (
        <section>
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Data Sources</h2>
          <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-2 divide-y divide-neutral-800/50">
            {Object.entries(data.data_sources).map(([key, src]) => {
              const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
              let detail = src.available ? 'Available' : 'Not found'
              if (src.available && src.count != null) detail = `${src.count} file${src.count !== 1 ? 's' : ''}`
              if (src.available && src.changes != null) detail = `${src.changes} change${src.changes !== 1 ? 's' : ''}`
              return (
                <ConfigValue
                  key={key}
                  label={label}
                  value={
                    <span className={src.available ? 'text-green-400' : 'text-neutral-600'}>
                      {detail}
                    </span>
                  }
                />
              )
            })}
          </div>
        </section>
      )}

      {/* Raw config fallback */}
      {data.config_raw && !directives && (
        <section>
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Config (raw)</h2>
          <pre className="bg-neutral-900/50 rounded-lg border border-neutral-800 p-4 text-xs text-neutral-400 whitespace-pre-wrap overflow-auto max-h-64">
            {data.config_raw}
          </pre>
        </section>
      )}
    </div>
  )
}
