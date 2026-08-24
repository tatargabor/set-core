import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { getContextAnalysis } from '../lib/api'
import type { ContextAnalysis } from '../lib/api'

function fmtK(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`
  return String(n)
}

function pct(n: number, total: number): string {
  if (total === 0) return '0%'
  return `${Math.round((n / total) * 100)}%`
}

export default function ContextPanel({ project }: { project: string }) {
  const [data, setData] = useState<ContextAnalysis | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getContextAnalysis(project)
      .then(setData)
      .catch((e) => setError(e.message))
  }, [project])

  if (error) {
    return <div className="p-4 text-sm text-red-400">Failed to load context analysis: {error}</div>
  }
  if (!data) {
    return <div className="p-4 text-sm text-fg-faint">Loading context analysis...</div>
  }

  const chartData = data.changes
    .filter((c) => c.total_input_tokens > 0)
    .map((c) => ({
      name: c.name.length > 20 ? c.name.slice(0, 18) + '...' : c.name,
      fullName: c.name,
      base: c.context_breakdown_avg?.base_context ?? 0,
      memory: c.context_breakdown_avg?.memory_injection ?? 0,
      prompt: c.context_breakdown_avg?.prompt_overhead ?? 0,
      tools: c.context_breakdown_avg?.tool_output ?? 0,
      total: c.total_input_tokens,
    }))

  return (
    <div className="p-4 space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="border border-surface-line rounded-lg p-3 bg-surface-panel/50">
          <div className="text-xs text-fg-faint">Total Input</div>
          <div className="text-lg font-semibold text-fg-loud">{fmtK(data.summary.total_input)}</div>
        </div>
        <div className="border border-surface-line rounded-lg p-3 bg-surface-panel/50">
          <div className="text-xs text-fg-faint">Avg Base Ratio</div>
          <div className="text-lg font-semibold text-fg-loud">
            {data.summary.avg_base_ratio != null ? pct(data.summary.avg_base_ratio, 1) : 'N/A'}
          </div>
        </div>
        <div className="border border-surface-line rounded-lg p-3 bg-surface-panel/50">
          <div className="text-xs text-fg-faint">Most Expensive</div>
          <div className="text-sm font-semibold text-fg-loud truncate">{data.summary.most_expensive ?? 'N/A'}</div>
        </div>
        <div className="border border-surface-line rounded-lg p-3 bg-surface-panel/50">
          <div className="text-xs text-fg-faint">Avg Efficiency</div>
          <div className="text-lg font-semibold text-fg-loud">
            {data.summary.avg_efficiency != null ? `${(data.summary.avg_efficiency * 100).toFixed(1)}%` : 'N/A'}
          </div>
        </div>
      </div>

      {/* Stacked bar chart */}
      {chartData.length > 0 && (
        <div className="border border-surface-line rounded-lg p-4 bg-surface-panel/50">
          <h3 className="text-xs font-medium text-fg-faint uppercase tracking-wide mb-3">
            Context Breakdown by Change (avg per iteration)
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 40)}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 30 }}>
              <XAxis type="number" tickFormatter={fmtK} tick={{ fill: '#a9afbc', fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={150} tick={{ fill: '#a9afbc', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#2f343e', border: '1px solid #464b57', borderRadius: 6 }}
                labelStyle={{ color: '#dce0e5' }}
                formatter={(value: unknown, name: unknown) => [fmtK(Number(value) || 0), String(name)]}
                labelFormatter={(_label, payload) => {
                  const entry = payload?.[0]?.payload as Record<string, unknown> | undefined
                  return String(entry?.fullName ?? _label)
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: '#a9afbc' }} />
              <Bar dataKey="base" stackId="ctx" fill="#3b82f6" name="Base Context" />
              <Bar dataKey="memory" stackId="ctx" fill="#22c55e" name="Memory Injection" />
              <Bar dataKey="prompt" stackId="ctx" fill="#878a98" name="Prompt" />
              <Bar dataKey="tools" stackId="ctx" fill="#f97316" name="Tool Output" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Per-change table */}
      <div className="border border-surface-line rounded-lg bg-surface-panel/50 overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-line text-fg-faint">
              <th className="text-left p-2 font-medium">Change</th>
              <th className="text-right p-2 font-medium">Iters</th>
              <th className="text-right p-2 font-medium">Base</th>
              <th className="text-right p-2 font-medium">Memory</th>
              <th className="text-right p-2 font-medium">Prompt</th>
              <th className="text-right p-2 font-medium">Tools</th>
              <th className="text-right p-2 font-medium">Total In</th>
              <th className="text-right p-2 font-medium">Eff%</th>
            </tr>
          </thead>
          <tbody>
            {data.changes.map((c) => {
              const bd = c.context_breakdown_avg
              const baseRatio = c.base_context_tokens && c.total_input_tokens > 0
                ? c.base_context_tokens / c.total_input_tokens
                : 0
              return (
                <tr key={c.name} className="border-b border-surface-line/50 hover:bg-surface-raised/30">
                  <td className="p-2 text-fg-strong truncate max-w-[200px]" title={c.name}>{c.name}</td>
                  <td className="p-2 text-right text-fg-muted">{c.iterations}</td>
                  <td className={`p-2 text-right ${baseRatio > 0.3 ? 'text-orange-400' : 'text-fg-muted'}`}>
                    {bd ? fmtK(bd.base_context) : '-'}
                  </td>
                  <td className="p-2 text-right text-fg-muted">{bd ? fmtK(bd.memory_injection) : '-'}</td>
                  <td className="p-2 text-right text-fg-muted">{bd ? fmtK(bd.prompt_overhead) : '-'}</td>
                  <td className="p-2 text-right text-fg-muted">{bd ? fmtK(bd.tool_output) : '-'}</td>
                  <td className="p-2 text-right text-fg-strong font-medium">{fmtK(c.total_input_tokens)}</td>
                  <td className={`p-2 text-right ${c.efficiency_ratio < 0.05 ? 'text-red-400' : 'text-fg-muted'}`}>
                    {(c.efficiency_ratio * 100).toFixed(1)}%
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
