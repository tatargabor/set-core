import { useEffect, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

interface Props {
  project: string
}

interface TokenEvent {
  ts: string
  input_tokens?: number
  output_tokens?: number
  cache_read_tokens?: number
  [key: string]: unknown
}

interface ChartPoint {
  time: string
  ts: number
  input: number
  output: number
  cache: number
}

export default function TokenChart({ project }: Props) {
  const [data, setData] = useState<ChartPoint[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/${project}/events?type=TOKENS&limit=2000`)
      .then(r => r.json())
      .then((resp: { events: TokenEvent[] }) => {
        const events = resp.events ?? []
        const points: ChartPoint[] = events.map(e => {
          const d = new Date(e.ts)
          return {
            time: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            ts: d.getTime(),
            input: e.input_tokens ?? 0,
            output: e.output_tokens ?? 0,
            cache: e.cache_read_tokens ?? 0,
          }
        })
        setData(points)
      })
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }, [project])

  if (loading) {
    return <div className="p-4 text-xs text-neutral-500">Loading token data...</div>
  }

  if (data.length === 0) {
    return <div className="p-4 text-xs text-neutral-500">No token events</div>
  }

  const formatK = (v: number) => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
    if (v >= 1_000) return `${(v / 1_000).toFixed(0)}k`
    return String(v)
  }

  return (
    <div className="h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <defs>
            <linearGradient id="inputGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="outputGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="cacheGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#a855f7" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="time"
            tick={{ fill: '#525252', fontSize: 10 }}
            axisLine={{ stroke: '#333' }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={formatK}
            tick={{ fill: '#525252', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={50}
          />
          <Tooltip
            contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: 6, fontSize: 11 }}
            labelStyle={{ color: '#aaa' }}
            formatter={(value, name) => [formatK(value as number), name as string]}
          />
          <Area type="monotone" dataKey="input" stroke="#3b82f6" fill="url(#inputGrad)" strokeWidth={1.5} />
          <Area type="monotone" dataKey="output" stroke="#22c55e" fill="url(#outputGrad)" strokeWidth={1.5} />
          <Area type="monotone" dataKey="cache" stroke="#a855f7" fill="url(#cacheGrad)" strokeWidth={1} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
