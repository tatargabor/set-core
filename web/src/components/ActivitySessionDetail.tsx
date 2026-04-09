import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
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

  // Mini-Gantt zoom — auto-fit to actual container width via ResizeObserver.
  // The drilldown is a sub-breakdown of the main timeline; it should never
  // need its own horizontal scrollbar.
  const miniContainerRef = useRef<HTMLDivElement>(null)
  const [miniContainerWidth, setMiniContainerWidth] = useState(0)
  useEffect(() => {
    const el = miniContainerRef.current
    if (!el) return
    const update = () => setMiniContainerWidth(el.clientWidth)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [data])

  const miniPxPerSecond = useMemo(() => {
    if (maxTime <= minTime || miniContainerWidth <= 0) return 0.1
    const wallSec = (maxTime - minTime) / 1000
    if (wallSec <= 0) return 0.1
    // Subtract a small padding so the rightmost span doesn't touch the edge.
    const usable = Math.max(100, miniContainerWidth - 8)
    return Math.max(0.001, usable / wallSec)
  }, [minTime, maxTime, miniContainerWidth])

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
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-x-4 gap-y-3">
          {/* Mini-Gantt — ~58% width (col-span-7 of 12) */}
          {categories.length > 0 && (
            <div className="lg:col-span-7 min-w-0">
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
                <div ref={miniContainerRef} className="flex-1 overflow-hidden bg-black min-w-0">
                  <GanttTimeline
                    spans={data.sub_spans as unknown as GanttSpan[]}
                    categories={categories}
                    minTime={minTime}
                    maxTime={maxTime}
                    pxPerSecond={miniPxPerSecond}
                    onSpanClick={handleSubSpanClick}
                    hoverLattice
                    minWidth={0}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Top operations — ~25% width (col-span-3 of 12) */}
          {data.top_operations.length > 0 && (
            <div className="lg:col-span-3 min-w-0">
              <div className="text-neutral-500 mb-2">┌──── Top operations ────┐</div>
              <div className="space-y-1">
                {data.top_operations.map((op, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <span
                      className="inline-block w-2 h-2 flex-shrink-0"
                      style={{ backgroundColor: getCategoryColor(op.category) }}
                    />
                    <span className="text-neutral-200 flex-shrink-0">{formatDuration(op.duration_ms)}</span>
                    <span className="text-neutral-500 truncate flex-1 min-w-0" title={`${getCategoryLabel(op.category)} — ${op.preview}`}>
                      {op.preview || getCategoryLabel(op.category)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Breakdown — ~17% width (col-span-2 of 12) */}
          <div className="lg:col-span-2 min-w-0">
            <div className="text-neutral-500 mb-2">┌──── Breakdown ────┐</div>
            <div className="space-y-1">
              {breakdown.map((b) => (
                <div key={b.category} className="flex items-center gap-1.5">
                  <span
                    className="inline-block w-2 h-2 flex-shrink-0"
                    style={{ backgroundColor: getCategoryColor(b.category) }}
                  />
                  <span
                    className="text-neutral-400 truncate flex-1 min-w-0"
                    title={getCategoryLabel(b.category)}
                  >
                    {getCategoryLabel(b.category)}
                  </span>
                  <span className="text-neutral-500 w-9 text-right flex-shrink-0">{b.pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
