import { useEffect, useState } from 'react'

interface Props {
  project: string | null
}

interface MemoryStats {
  total?: number
  total_memories?: number
  long_term_memory_count?: number
  session_memory_count?: number
  working_memory_count?: number
  compressed_count?: number
  promotions_to_longterm?: number
  promotions_to_session?: number
  total_retrievals?: number
  type_distribution?: Record<string, number>
  tag_distribution?: Record<string, number>
  importance_histogram?: Record<string, number>
  noise_ratio?: number
}

interface MemoryHealth {
  status?: string
  project?: string
  uptime_s?: number
  requests?: number
  connections?: number
  error?: string
}

interface MemoryData {
  health: string | MemoryHealth
  stats: MemoryStats
  sync: string
}

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="flex-1 h-2 rounded-full overflow-hidden bg-neutral-800">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

export default function Memory({ project }: Props) {
  const [data, setData] = useState<MemoryData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!project) { setData(null); return }
    setLoading(true)
    fetch(`/api/${project}/memory`)
      .then(r => r.json())
      .then(d => { setData(d); setError(null) })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [project])

  if (!project) return <div className="flex items-center justify-center h-full text-neutral-500">Select a project</div>
  if (loading) return <div className="p-6 text-neutral-500 text-sm">Loading memory stats...</div>
  if (error) return <div className="p-6 text-red-400 text-sm">{error}</div>
  if (!data) return <div className="p-6 text-neutral-500 text-sm">No data</div>

  const healthObj = typeof data.health === 'object' ? data.health : null
  const healthOk = typeof data.health === 'string' ? data.health === 'ok' : healthObj?.status === 'ok'
  const healthText = typeof data.health === 'string' ? data.health : healthObj?.status ?? healthObj?.error ?? 'unknown'
  const stats = data.stats ?? {}
  const types = stats.type_distribution ?? {}
  const tags = stats.tag_distribution ?? {}
  const importance = stats.importance_histogram ?? {}
  const total = stats.total ?? stats.total_memories ?? 0
  const maxType = Math.max(...Object.values(types), 1)
  const maxImportance = Math.max(...Object.values(importance), 1)

  // Sort tags by count descending, take top 12
  const sortedTags = Object.entries(tags).sort((a, b) => b[1] - a[1]).slice(0, 12)

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <h1 className="text-lg font-semibold text-neutral-100">Memory</h1>

      {/* Health + total */}
      <section>
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Health</h2>
        <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-3 flex items-center gap-4">
          <span className={`w-2.5 h-2.5 rounded-full ${healthOk ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className={`text-sm ${healthOk ? 'text-green-400' : 'text-red-400'}`}>{healthText}</span>
          <span className="ml-auto text-sm text-neutral-300 font-mono">{total.toLocaleString()} memories</span>
          {stats.noise_ratio != null && (
            <span className="text-xs text-neutral-500">{Math.round(stats.noise_ratio * 100)}% noise</span>
          )}
        </div>
      </section>

      {/* Memory breakdown (from API stats) */}
      {Object.keys(types).length === 0 && total > 0 && (
        <section>
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Breakdown</h2>
          <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-3 space-y-2">
            {stats.long_term_memory_count != null && (
              <div className="flex items-center gap-3">
                <span className="text-xs text-neutral-400 w-24">Long-term</span>
                <Bar value={stats.long_term_memory_count} max={total} color="bg-purple-500" />
                <span className="text-xs text-neutral-300 font-mono w-12 text-right">{stats.long_term_memory_count}</span>
              </div>
            )}
            {stats.session_memory_count != null && stats.session_memory_count > 0 && (
              <div className="flex items-center gap-3">
                <span className="text-xs text-neutral-400 w-24">Session</span>
                <Bar value={stats.session_memory_count} max={total} color="bg-blue-500" />
                <span className="text-xs text-neutral-300 font-mono w-12 text-right">{stats.session_memory_count}</span>
              </div>
            )}
            {stats.working_memory_count != null && stats.working_memory_count > 0 && (
              <div className="flex items-center gap-3">
                <span className="text-xs text-neutral-400 w-24">Working</span>
                <Bar value={stats.working_memory_count} max={total} color="bg-cyan-500" />
                <span className="text-xs text-neutral-300 font-mono w-12 text-right">{stats.working_memory_count}</span>
              </div>
            )}
            {stats.total_retrievals != null && stats.total_retrievals > 0 && (
              <div className="flex items-center gap-3 pt-1 border-t border-neutral-800/50">
                <span className="text-xs text-neutral-500 w-24">Retrievals</span>
                <span className="text-xs text-neutral-400 font-mono">{stats.total_retrievals}</span>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Type distribution */}
      {Object.keys(types).length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">By Type</h2>
          <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-3 space-y-2">
            {Object.entries(types).sort((a, b) => b[1] - a[1]).map(([type, count]) => {
              const pct = total > 0 ? Math.round((count / total) * 100) : 0
              const color = type === 'Decision' ? 'bg-purple-500' : type === 'Learning' ? 'bg-blue-500' : 'bg-cyan-500'
              return (
                <div key={type} className="flex items-center gap-3">
                  <span className="text-xs text-neutral-400 w-20">{type}</span>
                  <Bar value={count} max={maxType} color={color} />
                  <span className="text-xs text-neutral-300 font-mono w-12 text-right">{count}</span>
                  <span className="text-[10px] text-neutral-500 w-10 text-right">{pct}%</span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Importance histogram */}
      {Object.keys(importance).length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Importance Distribution</h2>
          <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-3 space-y-2">
            {Object.entries(importance).map(([range, count]) => (
              <div key={range} className="flex items-center gap-3">
                <span className="text-xs text-neutral-500 font-mono w-14">{range}</span>
                <Bar value={count} max={maxImportance} color="bg-amber-500" />
                <span className="text-xs text-neutral-300 font-mono w-12 text-right">{count}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Top tags */}
      {sortedTags.length > 0 && (
        <section>
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Top Tags</h2>
          <div className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-3">
            <div className="flex flex-wrap gap-1.5">
              {sortedTags.map(([tag, count]) => (
                <span key={tag} className="px-2 py-0.5 bg-neutral-800 rounded text-[11px] text-neutral-300 font-mono">
                  {tag} <span className="text-neutral-500">{count}</span>
                </span>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Sync status */}
      {data.sync && typeof data.sync === 'string' && !data.sync.startsWith('{') && (
        <section>
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Sync</h2>
          <pre className="bg-neutral-900/50 rounded-lg border border-neutral-800 px-4 py-3 text-xs text-neutral-400 font-mono whitespace-pre-wrap">
            {data.sync}
          </pre>
        </section>
      )}
    </div>
  )
}
