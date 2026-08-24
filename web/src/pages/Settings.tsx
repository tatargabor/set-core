import { useEffect, useState, useCallback } from 'react'
import { shutdownOrchestration, stopOrchestrator, startOrchestration } from '../lib/api'
import { TuiSection } from '../components/tui'
import ProcessTree from '../components/ProcessTree'

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
  orch_status?: string | null
  data_sources?: Record<string, DataSource>
}

function ConfigValue({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className="text-sm text-fg-faint w-40 shrink-0">{label}</span>
      <span className="text-sm text-fg-normal break-all">{value ?? <span className="text-fg-ghost">—</span>}</span>
    </div>
  )
}

/**
 * A titled panel holding one record's worth of key/value rows.
 *
 * `wide` is a claim about the CONTENT, not a layout preference: this panel carries values
 * that need room — a filesystem path, a command line — and asking for the full row is how it
 * says so. The alternative the page used to have was a single `max-w-3xl` column for
 * everything, which is the same decision made once for six panels that do not agree: the
 * 85-character state-file path wrapped to two lines inside 768px while 904px of the window
 * sat empty to its right. Cramping and waste were one bug, not two.
 */
function Panel({ label, wide, children }: { label: string; wide?: boolean; children: React.ReactNode }) {
  return (
    <section className={wide ? 'col-span-full' : undefined}>
      <TuiSection label={label} />
      <div className="bg-surface-panel/50 rounded-lg border border-surface-line px-4 py-2 divide-y divide-surface-line/50">
        {children}
      </div>
    </section>
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
      await startOrchestration(project)
    } catch {}
    setActionLoading(null)
    fetch(`/api/${project}/settings`).then(r => r.json()).then(setData).catch(() => {})
  }, [project])

  if (!project) {
    return <div className="flex items-center justify-center h-full text-fg-faint">Select a project</div>
  }
  if (loading) {
    return <div className="p-6 text-fg-faint text-sm">Loading...</div>
  }
  if (!data) {
    return <div className="p-6 text-fg-faint text-sm">Failed to load settings</div>
  }

  const directives = data.config?.directives as Record<string, unknown> | undefined

  const orchStatus = data.orch_status ?? (data.config as Record<string, unknown>)?.status as string | undefined
  const isShutdown = orchStatus === 'shutdown'
  const isStopped = orchStatus === 'stopped'
  const isResumable = isShutdown || isStopped
  const isRunning = orchStatus === 'running' || orchStatus === 'checkpoint'

  return (
    <div className="p-6 h-full overflow-y-auto">
      <h1 className="text-lg font-semibold text-fg-loud mb-6">Settings</h1>

      {/*
        Panels flow into as many columns as the window affords, each at least 30rem wide, and
        a panel carrying long values claims the whole row. Two things follow, and they are the
        two findings this screen was chosen to answer: the vertical stack no longer pushes half
        the page below the fold, and the width is spent where the values actually are rather
        than being capped at one figure for every panel at once.

        `items-start` because a record panel's height is its content's business — stretching a
        four-row panel to match an eight-row neighbour invents empty space and calls it layout.
      */}
      <div className="grid gap-6 items-start [grid-template-columns:repeat(auto-fit,minmax(30rem,1fr))]">

      {/* Orchestration Control */}
      <section className="col-span-full">
        <TuiSection label="Orchestration Control" />
        <div className="bg-surface-panel/50 rounded-lg border border-surface-line px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-sm text-fg-faint">Status</span>
              <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-sm font-medium ${
                isRunning ? 'bg-green-900/50 text-green-300' :
                isShutdown ? 'bg-green-900/50 text-green-300' :
                isStopped ? 'bg-amber-900/50 text-amber-300' :
                orchStatus === 'done' ? 'bg-blue-900/50 text-blue-300' :
                'bg-surface-raised text-fg-muted'
              }`}>
                <span className={
                  isRunning ? 'text-green-400' :
                  isShutdown ? 'text-green-400' :
                  isStopped ? 'text-amber-400' :
                  orchStatus === 'done' ? 'text-blue-400' :
                  'text-fg-faint'
                }>{isRunning ? '\u25C9' : orchStatus === 'done' ? '\u25CF' : '\u25CB'}</span>
                {isShutdown ? 'Paused (clean shutdown)' : isStopped ? 'Stopped (unexpected)' : orchStatus ?? 'unknown'}
              </span>
            </div>
            <div className="flex gap-2">
              {isResumable ? (
                <button
                  onClick={handleResume}
                  disabled={actionLoading === 'resume'}
                  className={`px-3 py-1 text-sm rounded disabled:opacity-50 disabled:cursor-not-allowed font-medium ${
                    isShutdown ? 'bg-green-900/50 text-green-300 hover:bg-green-900' : 'bg-amber-900/50 text-amber-300 hover:bg-amber-900'
                  }`}
                >
                  {actionLoading === 'resume' ? 'Resuming...' : 'Resume'}
                </button>
              ) : isRunning ? (
                <>
                  <button
                    onClick={() => setShowConfirm(true)}
                    disabled={actionLoading === 'shutdown'}
                    className="px-3 py-1 text-sm bg-red-900/50 text-red-300 rounded hover:bg-red-900 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
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
              <p className="text-sm text-red-300 mb-2">
                This will gracefully stop all agents and the orchestrator. Worktree state will be preserved for resume. Continue?
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleShutdown}
                  className="px-3 py-1 text-sm bg-red-800 text-red-100 rounded hover:bg-red-700 font-medium"
                >
                  Confirm Shutdown
                </button>
                <button
                  onClick={() => setShowConfirm(false)}
                  className="px-3 py-1 text-sm bg-surface-raised text-fg-normal rounded hover:bg-surface-strong"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Paths — `wide`: filesystem paths are the longest values this page carries. */}
      <Panel label="Paths" wide>
        <ConfigValue label="Project path" value={data.project_path} />
        <ConfigValue label="State file" value={data.state_path} />
        <ConfigValue label="Config file" value={data.config_path} />
        <ConfigValue label="Runs directory" value={data.runs_dir ? `${data.runs_dir} (${data.runs_count ?? '?'} runs)` : null} />
      </Panel>

      {/* Runtime */}
      <Panel label="Runtime">
        <ConfigValue label="Orchestrator PID" value={data.orchestrator_pid} />
        <ConfigValue label="Sentinel PID" value={data.sentinel_pid} />
        <ConfigValue label="Plan version" value={data.plan_version != null ? `v${data.plan_version}` : null} />
        <ConfigValue label="CLAUDE.md" value={data.has_claude_md ? 'Present' : 'Not found'} />
        <ConfigValue label="Project knowledge" value={data.has_project_knowledge ? 'Present' : 'Not found'} />
      </Panel>

      {/* Processes */}
      <section>
        <TuiSection label="Processes" />
        <div className="bg-surface-panel/50 rounded-lg border border-surface-line px-4 py-3">
          <ProcessTree project={project} />
        </div>
      </section>

      {/* Directives */}
      {directives && Object.keys(directives).length > 0 && (
        <Panel label="Orchestration Directives">
          {Object.entries(directives).map(([k, v]) => (
            <ConfigValue key={k} label={k} value={typeof v === 'object' ? JSON.stringify(v) : String(v ?? '')} />
          ))}
        </Panel>
      )}

      {/* Data Sources */}
      {data.data_sources && (
        <Panel label="Data Sources">
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
                    <span className={src.available ? 'text-status-active' : 'text-fg-ghost'}>
                      {detail}
                    </span>
                  }
                />
              )
            })}
        </Panel>
      )}

      {/* Raw config fallback */}
      {data.config_raw && !directives && (
        <section>
          <TuiSection label="Config (raw)" />
          <pre className="bg-surface-panel/50 rounded-lg border border-surface-line p-4 text-sm text-fg-muted whitespace-pre-wrap overflow-auto max-h-64">
            {data.config_raw}
          </pre>
        </section>
      )}
      </div>
    </div>
  )
}
