import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { ChangeInfo } from '../lib/api'

interface Props {
  changes: ChangeInfo[]
}

const STATUS_BAR_COLOR: Record<string, string> = {
  merged: '#3b82f6',
  done: '#3b82f6',
  completed: '#3b82f6',
  skip_merged: '#60a5fa',
  running: '#22c55e',
  implementing: '#22c55e',
  verifying: '#06b6d4',
  failed: '#ef4444',
  'verify-failed': '#ef4444',
  stalled: '#eab308',
  pending: '#525252',
  planned: '#404040',
}

function formatK(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}k`
  return String(v)
}

interface BarData {
  name: string
  shortName: string
  input: number
  output: number
  cache: number
  total: number
  status: string
}

export default function TokenChart({ changes }: Props) {
  const data = useMemo<BarData[]>(() => {
    return changes
      .filter(c => (c.tokens_used ?? 0) > 0 || (c.input_tokens ?? 0) > 0)
      .sort((a, b) => (b.tokens_used ?? 0) - (a.tokens_used ?? 0))
      .map(c => ({
        name: c.name,
        shortName: c.name.length > 20 ? c.name.slice(0, 18) + '…' : c.name,
        input: c.input_tokens ?? 0,
        output: c.output_tokens ?? 0,
        cache: c.cache_read_tokens ?? 0,
        total: (c.input_tokens ?? 0) + (c.output_tokens ?? 0) + (c.cache_read_tokens ?? 0),
        status: c.status,
      }))
  }, [changes])

  const totals = useMemo(() => {
    let input = 0, output = 0, cache = 0
    for (const c of changes) {
      input += c.input_tokens ?? 0
      output += c.output_tokens ?? 0
      cache += c.cache_read_tokens ?? 0
    }
    return { input, output, cache, total: input + output + cache }
  }, [changes])

  if (data.length === 0) {
    return <div className="p-4 text-xs text-neutral-500">No token usage data</div>
  }

  const barHeight = Math.max(data.length * 32, 120)

  return (
    <div className="flex flex-col h-full">
      {/* Summary header */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-neutral-800/50 shrink-0 flex-wrap">
        <span className="text-xs font-medium text-neutral-300">
          Total: {formatK(totals.total)}
        </span>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm bg-blue-500" />
            <span className="text-neutral-400">Input {formatK(totals.input)}</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm bg-green-500" />
            <span className="text-neutral-400">Output {formatK(totals.output)}</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm bg-purple-500" />
            <span className="text-neutral-400">Cache {formatK(totals.cache)}</span>
          </span>
        </div>
        <span className="text-[10px] text-neutral-600 ml-auto">
          {data.length} change{data.length !== 1 ? 's' : ''} with usage
        </span>
      </div>

      {/* Chart */}
      <div className="flex-1 overflow-y-auto min-h-0 px-2 py-2">
        <div style={{ height: barHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 0, right: 20, bottom: 0, left: 0 }}
              barCategoryGap="20%"
            >
              <XAxis
                type="number"
                tickFormatter={formatK}
                tick={{ fill: '#525252', fontSize: 10 }}
                axisLine={{ stroke: '#333' }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="shortName"
                tick={{ fill: '#737373', fontSize: 10, fontFamily: 'monospace' }}
                axisLine={false}
                tickLine={false}
                width={140}
              />
              <Tooltip
                contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: 6, fontSize: 11 }}
                labelStyle={{ color: '#aaa', fontFamily: 'monospace' }}
                formatter={(value: number, name: string) => [formatK(value), name]}
                labelFormatter={(label) => {
                  const item = data.find(d => d.shortName === label)
                  return item ? `${item.name} (${item.status})` : label
                }}
              />
              <Bar dataKey="input" stackId="tokens" name="Input" fill="#3b82f6" radius={0}>
                {data.map((entry) => (
                  <Cell key={entry.name} fill={STATUS_BAR_COLOR[entry.status] ?? '#525252'} fillOpacity={0.9} />
                ))}
              </Bar>
              <Bar dataKey="output" stackId="tokens" name="Output" fill="#22c55e" radius={0} />
              <Bar dataKey="cache" stackId="tokens" name="Cache" fill="#a855f7" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
