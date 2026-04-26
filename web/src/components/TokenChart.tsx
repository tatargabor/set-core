import { Fragment, useState, useEffect, useMemo, useCallback } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { ChangeInfo, LLMCall } from '../lib/api'
import { getLLMCalls } from '../lib/api'
import { useSelectedLineage } from '../lib/lineage'

interface Props {
  changes: ChangeInfo[]
  project: string | null
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

const MODEL_COLOR: Record<string, string> = {
  opus: '#3b82f6',
  sonnet: '#22c55e',
  haiku: '#737373',
}

const PHASE_MAP: Record<string, string> = {
  digest: 'Planning',
  decompose: 'Planning',
  decompose_summary: 'Planning',
  decompose_brief: 'Planning',
  decompose_domain: 'Planning',
  decompose_merge: 'Planning',
  sentinel: 'Monitoring',
  task: 'Implementation',
  review: 'Review gate',
  smoke_fix: 'Smoke gate',
  build_fix: 'Build gate',
  replan: 'Replan',
  classify: 'Classification',
  audit: 'Audit',
  spec_verify: 'Verification',
}

function getPhase(purposeRaw: string): string {
  return PHASE_MAP[purposeRaw] ?? 'Other'
}

function formatK(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}k`
  return String(v)
}

function formatDuration(ms: number): string {
  if (ms <= 0) return '-'
  if (ms < 1000) return `${ms}ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  const rem = Math.round(s % 60)
  return `${m}m${rem}s`
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso.slice(11, 19)
  }
}

interface BarData {
  name: string
  shortName: string
  input: number
  output: number
  cache: number
  total: number
  status: string
  archived: boolean
}

type SortKey = 'timestamp' | 'phase' | 'purpose' | 'model' | 'change' | 'source' | 'input_tokens' | 'output_tokens' | 'cache_tokens' | 'duration_ms'

export default function TokenChart({ changes, project }: Props) {
  const [calls, setCalls] = useState<LLMCall[]>([])
  const [sortKey, setSortKey] = useState<SortKey>('timestamp')
  const [sortAsc, setSortAsc] = useState(false)
  // Expanded rows by index — clicking the chevron on a session row with
  // an `iterations` array reveals one sub-row per ralph iteration.
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())

  const { lineageId } = useSelectedLineage()
  useEffect(() => {
    if (!project) return
    // Clear the prior lineage's calls so stale bars do not linger on
    // screen during the refetch.
    setCalls([])
    getLLMCalls(project, 500, lineageId).then(r => setCalls(r.calls)).catch(() => {})
  }, [project, lineageId])

  // Section 10.3 / AC-23 — archived rows carry the "(archived)" label,
  // sort AFTER every live row regardless of token totals, and source
  // their token values from the archive entry's own fields (the state
  // endpoint already surfaces those for _archived=true entries).
  const data = useMemo<BarData[]>(() => {
    const prepared = changes
      .filter(c => (c.tokens_used ?? 0) > 0 || (c.input_tokens ?? 0) > 0)
      .map(c => {
        const totalInput = c.input_tokens ?? 0
        const cache = c.cache_read_tokens ?? 0
        const rawInput = Math.max(0, totalInput - cache)
        const label = c._archived ? `${c.name} (archived)` : c.name
        return {
          name: c.name,
          shortName: label.length > 26 ? label.slice(0, 24) + '\u2026' : label,
          input: rawInput,
          output: c.output_tokens ?? 0,
          cache,
          total: totalInput + (c.output_tokens ?? 0),
          status: c.status,
          archived: Boolean(c._archived),
        }
      })
    // Primary sort: live first, archived last.  Secondary: total tokens desc.
    prepared.sort((a, b) => {
      if (a.archived !== b.archived) return a.archived ? 1 : -1
      return b.total - a.total
    })
    return prepared
  }, [changes])

  const totals = useMemo(() => {
    // Per-change tokens from state (authoritative — loop-state accumulator)
    let input = 0, output = 0, cache = 0
    for (const c of changes) {
      input += c.input_tokens ?? 0
      output += c.output_tokens ?? 0
      cache += c.cache_read_tokens ?? 0
    }
    // Add orchestration-level calls NOT tied to a change (sentinel, digest, decompose)
    for (const c of calls) {
      if (!c.change) {
        input += c.input_tokens
        output += c.output_tokens
        cache += c.cache_tokens
      }
    }
    return { input, output, cache, total: input + output }
  }, [changes, calls])

  const sortedCalls = useMemo(() => {
    const sorted = [...calls].sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'timestamp': {
          // Parse to epoch so UTC vs local-with-offset strings compare correctly.
          // String-compare would sort "...+00:00" before "...+02:00" even when
          // the former represents a later wall-clock time.
          cmp = (Date.parse(a.timestamp) || 0) - (Date.parse(b.timestamp) || 0)
          break
        }
        case 'phase': cmp = getPhase(a.purpose_raw).localeCompare(getPhase(b.purpose_raw)); break
        case 'purpose': cmp = a.purpose.localeCompare(b.purpose); break
        case 'model': cmp = a.model.localeCompare(b.model); break
        case 'change': cmp = a.change.localeCompare(b.change); break
        case 'source': cmp = a.source.localeCompare(b.source); break
        case 'input_tokens': cmp = a.input_tokens - b.input_tokens; break
        case 'output_tokens': cmp = a.output_tokens - b.output_tokens; break
        case 'cache_tokens': cmp = a.cache_tokens - b.cache_tokens; break
        case 'duration_ms': cmp = a.duration_ms - b.duration_ms; break
      }
      return sortAsc ? cmp : -cmp
    })
    return sorted
  }, [calls, sortKey, sortAsc])

  const handleSort = useCallback((key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(prev => !prev)
    } else {
      setSortKey(key)
      setSortAsc(false)
    }
  }, [sortKey])

  const barHeight = Math.max(data.length * 32, 120)

  const SortHeader = ({ k, label, align }: { k: SortKey; label: string; align?: string }) => (
    <th
      className={`px-3 py-2 text-xs font-medium text-neutral-400 cursor-pointer hover:text-neutral-200 select-none ${align === 'right' ? 'text-right' : 'text-left'}`}
      onClick={() => handleSort(k)}
    >
      {label} {sortKey === k ? (sortAsc ? '\u25B2' : '\u25BC') : ''}
    </th>
  )

  return (
    <div className="flex flex-col h-full">
      {/* Summary header */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-neutral-800/50 shrink-0 flex-wrap">
        <span className="text-sm font-medium text-neutral-300">
          Total: {formatK(totals.total)}
        </span>
        <div className="flex items-center gap-3 text-sm">
          <span className="flex items-center gap-1">
            <span className="text-blue-400">{'\u2588'}</span>
            <span className="text-neutral-400">Input {formatK(totals.input)}</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="text-green-400">{'\u2588'}</span>
            <span className="text-neutral-400">Output {formatK(totals.output)}</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="text-purple-400">{'\u2588'}</span>
            <span className="text-neutral-400">Cache {formatK(totals.cache)}</span>
          </span>
        </div>
        <span className="text-sm text-neutral-600 ml-auto">
          {data.length} change{data.length !== 1 ? 's' : ''} with usage
        </span>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {/* Chart */}
        {data.length > 0 && (
          <div className="px-2 py-2" style={{ height: barHeight }}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
              <BarChart
                data={data}
                layout="vertical"
                margin={{ top: 0, right: 20, bottom: 0, left: 0 }}
                barCategoryGap="20%"
              >
                <XAxis
                  type="number"
                  tickFormatter={formatK}
                  tick={{ fill: '#525252', fontSize: 12 }}
                  axisLine={{ stroke: '#333' }}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="shortName"
                  tick={{ fill: '#737373', fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  width={140}
                />
                <Tooltip
                  contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: 6, fontSize: 12 }}
                  labelStyle={{ color: '#aaa' }}
                  formatter={(value) => [formatK(Number(value ?? 0)), undefined]}
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
        )}

        {/* LLM Call Log Table */}
        {calls.length > 0 && (
          <div className="border-t border-neutral-800/50 mt-1">
            <div className="px-4 py-2 flex items-center justify-between">
              <span className="text-sm font-medium text-neutral-300">LLM Call Log</span>
              <span className="text-xs text-neutral-600">{calls.length} call{calls.length !== 1 ? 's' : ''}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-neutral-900/50 sticky top-0">
                  <tr>
                    <th className="px-1 py-1.5 w-4"></th>
                    <SortHeader k="timestamp" label="Time" />
                    <SortHeader k="phase" label="Phase" />
                    <SortHeader k="purpose" label="Purpose" />
                    <SortHeader k="model" label="Model" />
                    <SortHeader k="change" label="Change" />
                    <SortHeader k="source" label="Source" />
                    <SortHeader k="input_tokens" label="Input" align="right" />
                    <SortHeader k="output_tokens" label="Output" align="right" />
                    <SortHeader k="cache_tokens" label="Cache" align="right" />
                    <SortHeader k="duration_ms" label="Duration" align="right" />
                  </tr>
                </thead>
                <tbody>
                  {sortedCalls.map((call, i) => {
                    const modelShort = call.model.includes('opus') ? 'opus'
                      : call.model.includes('sonnet') ? 'sonnet'
                      : call.model.includes('haiku') ? 'haiku'
                      : call.model
                    const modelColor = MODEL_COLOR[modelShort] ?? '#737373'
                    const iters = call.iterations ?? []
                    const hasIters = iters.length > 0
                    const isExpanded = expandedRows.has(i)
                    const toggle = () => {
                      if (!hasIters) return
                      setExpandedRows(prev => {
                        const next = new Set(prev)
                        if (next.has(i)) next.delete(i)
                        else next.add(i)
                        return next
                      })
                    }
                    return (
                      <Fragment key={i}>
                      <tr
                        className={`border-t border-neutral-800/30 hover:bg-neutral-800/30 ${call.active ? 'bg-green-950/30' : ''} ${hasIters ? 'cursor-pointer' : ''}`}
                        onClick={hasIters ? toggle : undefined}
                      >
                        <td className="px-1 py-1.5 text-neutral-500 text-center select-none w-4">
                          {hasIters ? (isExpanded ? '▼' : '▶') : ''}
                        </td>
                        <td className="px-3 py-1.5 text-neutral-500 whitespace-nowrap">{formatTime(call.timestamp)}</td>
                        <td className="px-3 py-1.5 text-neutral-400">{getPhase(call.purpose_raw)}</td>
                        <td className="px-3 py-1.5 text-neutral-300">
                          {call.purpose}
                          {hasIters && (
                            <span className="ml-1.5 text-neutral-600 text-[10px]">({iters.length} iter{iters.length !== 1 ? 's' : ''})</span>
                          )}
                        </td>
                        <td className="px-3 py-1.5 whitespace-nowrap">
                          <span style={{ color: modelColor }} className="font-medium">{modelShort}</span>
                        </td>
                        <td className="px-3 py-1.5 text-neutral-400 max-w-[160px] truncate">{call.change || '-'}</td>
                        <td className="px-3 py-1.5 text-neutral-600 text-xs">{call.source === 'orchestration' ? 'event' : 'session'}</td>
                        <td className="px-3 py-1.5 text-right text-blue-400/80">{call.input_tokens ? formatK(call.input_tokens) : '-'}</td>
                        <td className="px-3 py-1.5 text-right text-green-400/80">{call.output_tokens ? formatK(call.output_tokens) : '-'}</td>
                        <td className="px-3 py-1.5 text-right text-purple-400/80">{call.cache_tokens ? formatK(call.cache_tokens) : '-'}</td>
                        <td className="px-3 py-1.5 text-right text-neutral-500">{formatDuration(call.duration_ms)}</td>
                      </tr>
                      {isExpanded && iters.map((it) => {
                        const itEffectiveInput = it.input_tokens + it.cache_read_tokens + it.cache_create_tokens
                        const itDuration = it.started && it.ended
                          ? Math.max(0, (Date.parse(it.ended) - Date.parse(it.started)))
                          : 0
                        return (
                          <tr key={`${i}-iter-${it.n}`} className="border-t border-neutral-900/50 bg-neutral-950/40 text-neutral-400">
                            <td className="px-1 py-1 text-neutral-700 text-center">↳</td>
                            <td className="px-3 py-1 whitespace-nowrap text-neutral-600">{it.started ? formatTime(it.started) : ''}</td>
                            <td className="px-3 py-1 text-neutral-600">iter {it.n}</td>
                            <td className="px-3 py-1 whitespace-nowrap">
                              {it.resumed ? (
                                <span className="text-green-500">● resume</span>
                              ) : (
                                <span className="text-orange-500">● fresh</span>
                              )}
                              {it.session_id && (
                                <span className="ml-2 text-neutral-700 font-mono text-[10px]">{it.session_id.slice(0, 8)}</span>
                              )}
                            </td>
                            <td className="px-3 py-1"></td>
                            <td className="px-3 py-1"></td>
                            <td className="px-3 py-1 text-neutral-700 text-xs">{it.no_op ? 'no-op' : it.ff_exhausted ? 'ff-exhausted' : ''}</td>
                            <td className="px-3 py-1 text-right text-blue-400/60">{itEffectiveInput ? formatK(itEffectiveInput) : '-'}</td>
                            <td className="px-3 py-1 text-right text-green-400/60">{it.output_tokens ? formatK(it.output_tokens) : '-'}</td>
                            <td className="px-3 py-1 text-right text-purple-400/60">{it.cache_read_tokens ? formatK(it.cache_read_tokens) : '-'}</td>
                            <td className="px-3 py-1 text-right text-neutral-600">{itDuration ? formatDuration(itDuration) : '-'}</td>
                          </tr>
                        )
                      })}
                      </Fragment>
                    )
                  })}
                  {/* Summary row */}
                  <tr className="border-t-2 border-neutral-700 bg-neutral-900/70 font-medium">
                    <td className="px-1 py-2"></td>
                    <td className="px-3 py-2 text-neutral-400" colSpan={5}>Total ({calls.length} calls)</td>
                    <td className="px-3 py-2 text-neutral-500 text-xs"></td>
                    <td className="px-3 py-2 text-right text-blue-400">{formatK(calls.reduce((s, c) => s + c.input_tokens, 0))}</td>
                    <td className="px-3 py-2 text-right text-green-400">{formatK(calls.reduce((s, c) => s + c.output_tokens, 0))}</td>
                    <td className="px-3 py-2 text-right text-purple-400">{formatK(calls.reduce((s, c) => s + c.cache_tokens, 0))}</td>
                    <td className="px-3 py-2 text-right text-neutral-400">{formatDuration(calls.reduce((s, c) => s + c.duration_ms, 0))}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {data.length === 0 && calls.length === 0 && (
          <div className="p-4 text-sm text-neutral-500">No token usage data</div>
        )}
      </div>
    </div>
  )
}
