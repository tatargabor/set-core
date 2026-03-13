import { useEffect, useState } from 'react'

interface Props {
  project: string | null
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
  plan_version?: string | number | null
}

function ConfigValue({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className="text-xs text-neutral-500 w-36 shrink-0">{label}</span>
      <span className="text-xs text-neutral-300 font-mono break-all">{value ?? <span className="text-neutral-600">—</span>}</span>
    </div>
  )
}

export default function Settings({ project }: Props) {
  const [data, setData] = useState<SettingsData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!project) { setData(null); return }
    setLoading(true)
    fetch(`/api/${project}/settings`)
      .then(r => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
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

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <h1 className="text-lg font-semibold text-neutral-100">Settings</h1>

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

      {/* Raw config fallback */}
      {data.config_raw && !directives && (
        <section>
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Config (raw)</h2>
          <pre className="bg-neutral-900/50 rounded-lg border border-neutral-800 p-4 text-xs text-neutral-400 font-mono whitespace-pre-wrap overflow-auto max-h-64">
            {data.config_raw}
          </pre>
        </section>
      )}
    </div>
  )
}
