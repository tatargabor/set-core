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
    return <div className="p-4 text-sm text-neutral-500">Loading context analysis...</div>
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
        <div className="border border-neutral-800 rounded-lg p-3 bg-neutral-900/50">
          <div className="text-xs text-neutral-500">Total Input</div>
          <div className="text-lg font-semibold text-neutral-100">{fmtK(data.summary.total_input)}</div>
        </div>
        <div className="border border-neutral-800 rounded-lg p-3 bg-neutral-900/50">
          <div className="text-xs text-neutral-500">Avg Base Ratio</div>
          <div className="text-lg font-semibold text-neutral-100">
            {data.summary.avg_base_ratio != null ? pct(data.summary.avg_base_ratio, 1) : 'N/A'}
          </div>
        </div>
        <div className="border border-neutral-800 rounded-lg p-3 bg-neutral-900/50">
          <div className="text-xs text-neutral-500">Most Expensive</div>
          <div className="text-sm font-semibold text-neutral-100 truncate">{data.summary.most_expensive ?? 'N/A'}</div>
        </div>
        <div className="border border-neutral-800 rounded-lg p-3 bg-neutral-900/50">
          <div className="text-xs text-neutral-500">Avg Efficiency</div>
          <div className="text-lg font-semibold text-neutral-100">
            {data.summary.avg_efficiency != null ? `${(data.summary.avg_efficiency * 100).toFixed(1)}%` : 'N/A'}
          </div>
        </div>
      </div>

      {/* Stacked bar chart */}
      {chartData.length > 0 && (
        <div className="border border-neutral-800 rounded-lg p-4 bg-neutral-900/50">
          <h3 className="text-xs font-medium text-neutral-500 uppercase tracking-wide mb-3">
            Context Breakdown by Change (avg per iteration)
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 40)}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 30 }}>
              <XAxis type="number" tickFormatter={fmtK} tick={{ fill: '#a3a3a3', fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={150} tick={{ fill: '#a3a3a3', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#262626', border: '1px solid #404040', borderRadius: 6 }}
                labelStyle={{ color: '#e5e5e5' }}
                formatter={(value: unknown, name: unknown) => [fmtK(Number(value) || 0), String(name)]}
                labelFormatter={(_label, payload) => {
                  const entry = payload?.[0]?.payload as Record<string, unknown> | undefined
                  return String(entry?.fullName ?? _label)
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: '#a3a3a3' }} />
              <Bar dataKey="base" stackId="ctx" fill="#3b82f6" name="Base Context" />
              <Bar dataKey="memory" stackId="ctx" fill="#22c55e" name="Memory Injection" />
              <Bar dataKey="prompt" stackId="ctx" fill="#737373" name="Prompt" />
              <Bar dataKey="tools" stackId="ctx" fill="#f97316" name="Tool Output" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Per-change table */}
      <div className="border border-neutral-800 rounded-lg bg-neutral-900/50 overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-neutral-800 text-neutral-500">
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
                <tr key={c.name} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="p-2 text-neutral-200 truncate max-w-[200px]" title={c.name}>{c.name}</td>
                  <td className="p-2 text-right text-neutral-400">{c.iterations}</td>
                  <td className={`p-2 text-right ${baseRatio > 0.3 ? 'text-orange-400' : 'text-neutral-400'}`}>
                    {bd ? fmtK(bd.base_context) : '-'}
                  </td>
                  <td className="p-2 text-right text-neutral-400">{bd ? fmtK(bd.memory_injection) : '-'}</td>
                  <td className="p-2 text-right text-neutral-400">{bd ? fmtK(bd.prompt_overhead) : '-'}</td>
                  <td className="p-2 text-right text-neutral-400">{bd ? fmtK(bd.tool_output) : '-'}</td>
                  <td className="p-2 text-right text-neutral-200 font-medium">{fmtK(c.total_input_tokens)}</td>
                  <td className={`p-2 text-right ${c.efficiency_ratio < 0.05 ? 'text-red-400' : 'text-neutral-400'}`}>
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
