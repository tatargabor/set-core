import { useState, useEffect, useMemo, useCallback } from 'react'
import { getSessionDetail } from '../lib/api'
import type { ActivitySpan, ActivitySessionDetail as DetailData } from '../lib/api'
import {
  GanttTimeline,
  getCategoryColor,
  getCategoryLabel,
  formatDuration,
  type GanttSpan,
} from './ActivityView'

interface Props {
  project: string
  span: ActivitySpan
  onClose: () => void
}

/**
 * Drilldown panel: shows the per-tool / LLM-wait breakdown for a clicked
 * implementing span. Fetches /activity-timeline/session-detail and renders:
 *   - Header with totals + close button
 *   - Per-category breakdown bars
 *   - Mini-Gantt of the sub-spans
 *   - Top 5 longest individual operations
 */
export default function ActivitySessionDetail({ project, span, onClose }: Props) {
  const [data, setData] = useState<DetailData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Re-fetch on prop change
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setData(null)
    getSessionDetail(project, span.change || '', span.start, span.end)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || 'Failed to load session detail')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [project, span.start, span.end, span.change])

  // Compute per-category aggregates from sub_spans
  const breakdown = useMemo(() => {
    if (!data) return [] as { category: string; total_ms: number; pct: number }[]
    const totals: Record<string, number> = {}
    let grand = 0
    for (const s of data.sub_spans) {
      totals[s.category] = (totals[s.category] || 0) + s.duration_ms
      grand += s.duration_ms
    }
    const rows = Object.entries(totals)
      .map(([category, total_ms]) => ({
        category,
        total_ms,
        pct: grand > 0 ? Math.round((total_ms / grand) * 1000) / 10 : 0,
      }))
      .sort((a, b) => b.total_ms - a.total_ms)
    return rows
  }, [data])

  // Compute mini-Gantt categories (only those with spans, sorted)
  const { categories, minTime, maxTime } = useMemo(() => {
    if (!data?.sub_spans.length) return { categories: [] as string[], minTime: 0, maxTime: 0 }
    const seen = new Set(data.sub_spans.map((s) => s.category))
    const cats = [...seen].sort()
    let mn = Infinity
    let mx = -Infinity
    for (const s of data.sub_spans) {
      const st = new Date(s.start).getTime()
      const et = new Date(s.end).getTime()
      if (st < mn) mn = st
      if (et > mx) mx = et
    }
    return { categories: cats, minTime: mn, maxTime: mx }
  }, [data])

  // Mini-Gantt zoom — fit to a fixed 900px width by default
  const miniPxPerSecond = useMemo(() => {
    if (maxTime <= minTime) return 0.1
    const wallSec = (maxTime - minTime) / 1000
    return Math.max(0.005, Math.min(900 / Math.max(wallSec, 1), 5))
  }, [minTime, maxTime])

  const handleSubSpanClick = useCallback((s: GanttSpan) => {
    // Sub-spans are leaves in current Claude Code (subagents run in-process,
    // no separate jsonl). No second-level drilldown for now.
    void s
  }, [])

  return (
    <div className="border border-neutral-700 bg-black p-3 mt-2 font-mono text-xs">
      {/* Header — ASCII bordered */}
      <div className="flex items-center gap-4 border-b border-neutral-800 pb-2 mb-3">
        <div className="text-neutral-100 font-bold">┌─ Drilldown: {span.change || '(no change)'}</div>
        <div className="text-neutral-500">│ {formatDuration(span.duration_ms)}</div>
        {data && (
          <>
            <div className="text-neutral-500">│ {data.total_llm_calls} LLM calls</div>
            <div className="text-neutral-500">│ {data.total_tool_calls} tool calls</div>
            {data.subagent_count > 0 && (
              <div className="text-neutral-300">│ {data.subagent_count} subagents</div>
            )}
            {data.cache_hit && <div className="text-neutral-600">│ (cached)</div>}
          </>
        )}
        <div className="flex-1" />
        <button
          onClick={onClose}
          className="text-neutral-500 hover:text-neutral-100 px-2"
          title="Close drilldown"
        >
          ×
        </button>
      </div>

      {loading && <div className="text-neutral-500 py-4">Loading drilldown…</div>}
      {error && <div className="text-red-400 py-2">{error}</div>}

      {data && data.sub_spans.length === 0 && (
        <div className="text-neutral-600 py-4">
          No session data available. The agent may not have written any session JSONL files yet,
          or the worktree was cleaned up after the run.
        </div>
      )}

      {data && data.sub_spans.length > 0 && (
        <>
          {/* Per-category breakdown bars */}
          <div className="space-y-1 mb-4">
            {breakdown.map((b) => (
              <div key={b.category} className="flex items-center gap-2">
                <span
                  className="w-32 text-right text-neutral-400 truncate"
                  title={getCategoryLabel(b.category)}
                >
                  {getCategoryLabel(b.category)}
                </span>
                <div className="flex-1 h-3 bg-neutral-900">
                  <div
                    className="h-full"
                    style={{
                      width: `${Math.max(1, (b.total_ms / Math.max(breakdown[0].total_ms, 1)) * 100)}%`,
                      backgroundColor: getCategoryColor(b.category),
                      opacity: 0.8,
                    }}
                  />
                </div>
                <span className="w-16 text-right text-neutral-300">{formatDuration(b.total_ms)}</span>
                <span className="w-10 text-right text-neutral-500">{b.pct}%</span>
              </div>
            ))}
          </div>

          {/* Mini-Gantt of sub-spans */}
          {categories.length > 0 && (
            <div className="border-t border-neutral-900 pt-3 mb-3">
              <div className="text-neutral-500 mb-2">┌──── Timeline ────┐</div>
              <div className="flex">
                <div className="flex-shrink-0 w-32 pt-7">
                  {categories.map((cat) => (
                    <div
                      key={cat}
                      className="h-6 flex items-center text-neutral-400 text-right pr-2 truncate"
                      title={getCategoryLabel(cat)}
                    >
                      <span
                        className="inline-block w-2 h-2 mr-1 flex-shrink-0"
                        style={{ backgroundColor: getCategoryColor(cat) }}
                      />
                      {getCategoryLabel(cat)}
                    </div>
                  ))}
                </div>
                <div className="flex-1 overflow-x-auto overflow-y-hidden bg-black">
                  <GanttTimeline
                    spans={data.sub_spans as unknown as GanttSpan[]}
                    categories={categories}
                    minTime={minTime}
                    maxTime={maxTime}
                    pxPerSecond={miniPxPerSecond}
                    onSpanClick={handleSubSpanClick}
                    hoverLattice
                  />
                </div>
              </div>
            </div>
          )}

          {/* Top 5 longest operations */}
          {data.top_operations.length > 0 && (
            <div className="border-t border-neutral-900 pt-3">
              <div className="text-neutral-500 mb-2">┌──── Top operations ────┐</div>
              <div className="space-y-1">
                {data.top_operations.map((op, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span
                      className="inline-block w-2 h-2 flex-shrink-0"
                      style={{ backgroundColor: getCategoryColor(op.category) }}
                    />
                    <span className="w-32 text-neutral-300 truncate">{getCategoryLabel(op.category)}</span>
                    <span className="w-16 text-right text-neutral-200">{formatDuration(op.duration_ms)}</span>
                    <span className="text-neutral-500 truncate flex-1" title={op.preview}>
                      │ {op.preview || '(no preview)'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
