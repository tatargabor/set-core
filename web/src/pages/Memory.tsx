import { useEffect, useState } from 'react'
import { TuiProgress, TuiSection } from '../components/tui'

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

function TuiBar({ value, max, label, color }: { value: number; max: number; label: string; color: string }) {
  const barLen = 20
  const filled = max > 0 ? Math.round((value / max) * barLen) : 0
  const bar = '\u2588'.repeat(filled) + '\u2591'.repeat(barLen - filled)
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-neutral-400 w-24">{label}</span>
      <span className={color}>{bar}</span>
      <span className="text-neutral-300 w-12 text-right">{value}</span>
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

  const sortedTags = Object.entries(tags).sort((a, b) => b[1] - a[1]).slice(0, 12)

  return (
    <div className="p-6 max-w-3xl space-y-5">
      <h1 className="text-base font-semibold text-neutral-100">Memory</h1>

      {/* Health */}
      <section>
        <TuiSection label="HEALTH" />
        <div className="bg-neutral-900/50 border border-neutral-800 px-4 py-3 flex items-center gap-4">
          <span className={healthOk ? 'text-green-400' : 'text-red-400'}>{healthOk ? '\u25CF' : '\u2715'} {healthText}</span>
          <span className="ml-auto text-sm text-neutral-300">{total.toLocaleString()} memories</span>
          {stats.noise_ratio != null && (
            <span className="text-sm text-neutral-500">{Math.round(stats.noise_ratio * 100)}% noise</span>
          )}
        </div>
      </section>

      {/* Memory breakdown */}
      {Object.keys(types).length === 0 && total > 0 && (
        <section>
          <TuiSection label="BREAKDOWN" />
          <div className="bg-neutral-900/50 border border-neutral-800 px-4 py-3 space-y-1">
            {stats.long_term_memory_count != null && (
              <TuiBar value={stats.long_term_memory_count} max={total} label="Long-term" color="text-purple-400" />
            )}
            {stats.session_memory_count != null && stats.session_memory_count > 0 && (
              <TuiBar value={stats.session_memory_count} max={total} label="Session" color="text-blue-400" />
            )}
            {stats.working_memory_count != null && stats.working_memory_count > 0 && (
              <TuiBar value={stats.working_memory_count} max={total} label="Working" color="text-cyan-400" />
            )}
            {stats.total_retrievals != null && stats.total_retrievals > 0 && (
              <div className="flex items-center gap-3 pt-1 border-t border-neutral-800/50 text-sm">
                <span className="text-neutral-500 w-24">Retrievals</span>
                <span className="text-neutral-400">{stats.total_retrievals}</span>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Type distribution */}
      {Object.keys(types).length > 0 && (
        <section>
          <TuiSection label="BY TYPE" />
          <div className="bg-neutral-900/50 border border-neutral-800 px-4 py-3 space-y-1">
            {Object.entries(types).sort((a, b) => b[1] - a[1]).map(([type, count]) => {
              const pct = total > 0 ? Math.round((count / total) * 100) : 0
              const typeColor = type === 'Decision' ? 'text-purple-400' : type === 'Learning' ? 'text-blue-400' : 'text-cyan-400'
              return (
                <div key={type} className="flex items-center gap-3 text-sm">
                  <span className={`w-20 ${typeColor}`}>{type}</span>
                  <TuiProgress done={count} total={maxType} className="text-sm" />
                  <span className="text-neutral-500 w-10 text-right">{pct}%</span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Importance histogram */}
      {Object.keys(importance).length > 0 && (
        <section>
          <TuiSection label="IMPORTANCE" />
          <div className="bg-neutral-900/50 border border-neutral-800 px-4 py-3 space-y-1">
            {Object.entries(importance).map(([range, count]) => (
              <TuiBar key={range} value={count} max={maxImportance} label={range} color="text-amber-400" />
            ))}
          </div>
        </section>
      )}

      {/* Top tags */}
      {sortedTags.length > 0 && (
        <section>
          <TuiSection label="TOP TAGS" />
          <div className="bg-neutral-900/50 border border-neutral-800 px-4 py-3">
            <div className="flex flex-wrap gap-1.5">
              {sortedTags.map(([tag, count]) => (
                <span key={tag} className="px-2 py-0.5 bg-neutral-800 text-sm text-neutral-300">
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
          <TuiSection label="SYNC" />
          <pre className="bg-neutral-900/50 border border-neutral-800 px-4 py-3 text-sm text-neutral-400 whitespace-pre-wrap">
            {data.sync}
          </pre>
        </section>
      )}
    </div>
  )
}
