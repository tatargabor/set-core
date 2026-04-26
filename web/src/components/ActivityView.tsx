import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { getActivityTimeline } from '../lib/api'
import type { ActivityTimelineData, ActivitySpan, ActivityBreakdown } from '../lib/api'
import { useSelectedLineage } from '../lib/lineage'
import ActivitySessionDetail from './ActivitySessionDetail'

interface Props {
  project: string | null
  isRunning?: boolean
}

// ─── Category colors (terminal/monospace aesthetic) ─────────────────

const CATEGORY_COLORS: Record<string, string> = {
  planning: '#a78bfa',       // violet
  implementing: '#22c55e',   // green
  fixing: '#f59e0b',         // amber
  // Orchestrator-side LLM calls (verifier/replanner/classifier) — warm hues
  'llm:review': '#fbbf24',       // amber-400
  'llm:spec_verify': '#f59e0b',  // amber-500
  'llm:replan': '#d97706',       // amber-600
  'llm:classify': '#fcd34d',     // amber-300
  // Build/test/e2e/etc. gates
  'gate:build': '#3b82f6',   // blue
  'gate:test': '#06b6d4',    // cyan
  'gate:review': '#ec4899',  // pink
  'gate:verify': '#8b5cf6',  // purple
  'gate:e2e': '#f97316',     // orange
  'gate:e2e-smoke': '#fb923c',
  'gate:smoke': '#84cc16',   // lime
  'gate:scope-check': '#64748b',
  'gate:rules': '#94a3b8',
  'gate:dep-install': '#475569',
  merge: '#10b981',          // emerald
  idle: '#262626',           // very dark gray (true terminal idle)
  'stall-recovery': '#ef4444', // red
  'dep-wait': '#737373',     // gray
  'manual-wait': '#a3a3a3',  // light gray
  sentinel: '#525252',       // dim
  // Sentinel-side LLM calls — muted cool hues to distinguish from orchestrator LLM
  'sentinel:llm:review': '#64748b',       // slate-500
  'sentinel:llm:spec_verify': '#475569',  // slate-600
  'sentinel:llm:replan': '#334155',       // slate-700
  'sentinel:llm:classify': '#94a3b8',     // slate-400
  // Per-iteration agent session markers (zero-width on the main timeline)
  // — orange = fresh `claude` session, green = `claude --resume` warm cache.
  'agent:session-fresh': '#f97316',     // orange — new session boundary
  'agent:session-resume': '#22c55e',    // green — resumed warm session
  // Drilldown sub-spans (used by ActivitySessionDetail)
  'agent:llm-wait': '#22c55e',     // green — Claude API time
  'agent:tool:bash': '#3b82f6',    // blue — shell
  'agent:tool:edit': '#06b6d4',    // cyan
  'agent:tool:read': '#0ea5e9',    // sky
  'agent:tool:write': '#0284c7',   // sky-darker
  'agent:tool:glob': '#a78bfa',    // violet
  'agent:tool:grep': '#8b5cf6',    // purple
  'agent:tool:webfetch': '#ec4899', // pink
  'agent:tool:websearch': '#db2777',
  'agent:tool:skill': '#f97316',   // orange
  'agent:tool:todowrite': '#94a3b8',
  'agent:tool:toolsearch': '#64748b',
  'agent:tool:multiedit': '#0891b2',
  'agent:tool:notebookedit': '#06b6d4',
  'agent:tool:other': '#737373',
  'agent:overhead': '#3f3f46',     // zinc-700 — legacy fallback
  // Gap categories — each gap in the session is classified by the prompt
  // content that appears after it (review findings / failing tests / etc.)
  'agent:review-wait': '#fb923c',  // orange — orchestrator review gate running
  'agent:verify-wait': '#ef4444',  // red — orchestrator verify/e2e gate running
  'agent:loop-restart': '#64748b', // slate — ralph iter boundary
  'agent:hook-overhead': '#6366f1', // indigo — hook processing between turns
  'agent:gap': '#3f3f46',          // zinc — unclassified gap
}

// Pretty labels for categories that benefit from a longer name in tooltips/labels.
export const CATEGORY_LABELS: Record<string, string> = {
  'llm:review': 'LLM: Review',
  'llm:spec_verify': 'LLM: Spec Verify',
  'llm:replan': 'LLM: Replan',
  'llm:classify': 'LLM: Classify',
  'sentinel:llm:review': 'Sentinel: Review',
  'sentinel:llm:spec_verify': 'Sentinel: Spec Verify',
  'sentinel:llm:replan': 'Sentinel: Replan',
  'sentinel:llm:classify': 'Sentinel: Classify',
  'agent:session-fresh': 'New Session',
  'agent:session-resume': 'Resumed Session',
  'agent:llm-wait': 'LLM Work',
  'agent:tool:bash': 'Bash',
  'agent:tool:edit': 'Edit',
  'agent:tool:read': 'Read',
  'agent:tool:write': 'Write',
  'agent:tool:glob': 'Glob',
  'agent:tool:grep': 'Grep',
  'agent:tool:webfetch': 'WebFetch',
  'agent:tool:websearch': 'WebSearch',
  'agent:tool:skill': 'Skill',
  'agent:tool:todowrite': 'Todo',
  'agent:tool:toolsearch': 'ToolSearch',
  'agent:tool:multiedit': 'MultiEdit',
  'agent:tool:notebookedit': 'NotebookEdit',
  'agent:tool:other': 'Tool: other',
  'agent:overhead': 'Overhead',
  'agent:review-wait': 'Review Gate',
  'agent:verify-wait': 'Verify Gate',
  'agent:loop-restart': 'Iter Restart',
  'agent:hook-overhead': 'Hook Overhead',
  'agent:gap': 'Gap',
}

export function getCategoryColor(cat: string): string {
  if (CATEGORY_COLORS[cat]) return CATEGORY_COLORS[cat]
  // Fallback for unknown llm:* / sentinel:llm:* / agent:tool:* / agent:subagent:* purposes
  if (cat.startsWith('sentinel:llm:')) return '#475569'
  if (cat.startsWith('llm:')) return '#f59e0b'
  if (cat.startsWith('agent:subagent:')) return '#f97316' // orange — subagent dispatch
  if (cat.startsWith('agent:tool:')) return '#737373'
  return '#525252'
}

export function getCategoryLabel(cat: string): string {
  if (CATEGORY_LABELS[cat]) return CATEGORY_LABELS[cat]
  if (cat.startsWith('agent:subagent:')) {
    const slug = cat.slice('agent:subagent:'.length)
    return `Subagent: ${slug.replace(/-/g, ' ')}`
  }
  return cat
}

// ─── Time formatting ────────────────────────────────────────────────

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export function formatTime(isoStr: string): string {
  try {
    const d = new Date(isoStr)
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return isoStr.slice(11, 19)
  }
}

// ─── Gantt timeline renderer ────────────────────────────────────────

// Generic span shape — both ActivitySpan and SubSpan satisfy this.
export interface GanttSpan {
  category: string
  change?: string
  start: string
  end: string
  duration_ms: number
  result?: string
  retry?: number
  detail?: Record<string, unknown>
}

interface GanttProps {
  spans: GanttSpan[]
  categories: string[]
  minTime: number
  maxTime: number
  pxPerSecond: number
  onSpanClick?: (span: GanttSpan) => void
  /** Show a vertical line at the cursor across all lanes (terminal hover lattice). */
  hoverLattice?: boolean
  /** Minimum SVG width in pixels. Defaults to 600 for the main timeline; embed
   *  Gantts (e.g., drilldown mini-Gantt) should pass 0 to fit their container. */
  minWidth?: number
}

export function GanttTimeline({
  spans,
  categories,
  minTime,
  maxTime,
  pxPerSecond,
  onSpanClick,
  hoverLattice = true,
  minWidth = 600,
}: GanttProps) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; span: GanttSpan } | null>(null)
  const [hoverX, setHoverX] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const laneHeight = 24
  const headerHeight = 28
  const totalWidth = Math.max(minWidth, ((maxTime - minTime) / 1000) * pxPerSecond)
  const totalHeight = headerHeight + categories.length * laneHeight

  // Time axis tick marks
  const tickInterval = _bestTickInterval((maxTime - minTime) / 1000, totalWidth)
  const ticks: { x: number; label: string }[] = []
  const firstTick = Math.ceil(minTime / 1000 / tickInterval) * tickInterval * 1000
  for (let t = firstTick; t <= maxTime; t += tickInterval * 1000) {
    const x = ((t - minTime) / 1000) * pxPerSecond
    ticks.push({ x, label: formatTime(new Date(t).toISOString()) })
  }

  // Build per-category span groups with parallel overlap detection.
  // `sentinel:session_boundary` is a zero-width marker that does NOT
  // belong on a normal category lane — peel it off and render it as a
  // full-height divider in a separate pass (Section 8.3 / AC-19).
  const SESSION_BOUNDARY = 'sentinel:session_boundary'
  const { categorySpans, sessionBoundaries } = useMemo(() => {
    const map: Record<string, { span: GanttSpan; x: number; w: number }[]> = {}
    for (const cat of categories) map[cat] = []
    const boundaries: { span: GanttSpan; x: number }[] = []
    for (const span of spans) {
      if (span.category === SESSION_BOUNDARY) {
        const startMs = new Date(span.start).getTime()
        const x = ((startMs - minTime) / 1000) * pxPerSecond
        boundaries.push({ span, x })
        continue
      }
      const cat = span.category
      if (!map[cat]) continue
      const startMs = new Date(span.start).getTime()
      const endMs = new Date(span.end).getTime()
      const x = ((startMs - minTime) / 1000) * pxPerSecond
      const w = Math.max(2, ((endMs - startMs) / 1000) * pxPerSecond)
      map[cat].push({ span, x, w })
    }
    return { categorySpans: map, sessionBoundaries: boundaries }
  }, [spans, categories, minTime, pxPerSecond])

  const handleMouseEnter = useCallback((e: React.MouseEvent, span: GanttSpan) => {
    setTooltip({ x: e.clientX, y: e.clientY, span })
  }, [])

  const handleMouseLeave = useCallback(() => setTooltip(null), [])

  const handleSvgMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!hoverLattice || !svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    setHoverX(e.clientX - rect.left)
  }, [hoverLattice])

  const handleSvgMouseLeave = useCallback(() => setHoverX(null), [])

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        width={totalWidth}
        height={totalHeight}
        className="block"
        onMouseMove={handleSvgMouseMove}
        onMouseLeave={handleSvgMouseLeave}
      >
        {/* Time axis */}
        <line x1={0} y1={headerHeight} x2={totalWidth} y2={headerHeight} stroke="#404040" strokeWidth={1} />
        {ticks.map((tick, i) => (
          <g key={i}>
            <line x1={tick.x} y1={headerHeight - 4} x2={tick.x} y2={headerHeight} stroke="#525252" />
            <text x={tick.x} y={headerHeight - 8} fill="#a3a3a3" fontSize={10} textAnchor="middle" fontFamily="monospace">
              {tick.label}
            </text>
            <line x1={tick.x} y1={headerHeight} x2={tick.x} y2={totalHeight} stroke="#1a1a1a" strokeWidth={1} strokeDasharray="2,4" />
          </g>
        ))}

        {/* Lanes */}
        {categories.map((cat, laneIdx) => {
          const y = headerHeight + laneIdx * laneHeight
          const laneSpans = categorySpans[cat] || []

          return (
            <g key={cat}>
              {/* Lane background — terminal stripe */}
              <rect x={0} y={y} width={totalWidth} height={laneHeight} fill={laneIdx % 2 === 0 ? '#000000' : '#0a0a0a'} />

              {/* Span blocks */}
              {laneSpans.map((item, si) => {
                const color = getCategoryColor(cat)
                // Count overlapping spans at this position for opacity
                const overlapCount = laneSpans.filter(
                  (other) => other.x < item.x + item.w && other.x + other.w > item.x,
                ).length
                const opacity = Math.min(1, 0.5 + overlapCount * 0.2)
                const isClickable = !!onSpanClick && item.span.duration_ms > 60_000

                return (
                  <g key={si}>
                    <rect
                      x={item.x}
                      y={y + 2}
                      width={item.w}
                      height={laneHeight - 4}
                      fill={color}
                      opacity={opacity}
                      stroke={color}
                      strokeWidth={1}
                      rx={1}
                      className={isClickable ? 'cursor-pointer' : 'cursor-default'}
                      onMouseEnter={(e) => handleMouseEnter(e, item.span)}
                      onMouseLeave={handleMouseLeave}
                      onClick={isClickable ? () => onSpanClick!(item.span) : undefined}
                    />
                    {/* Pass/fail markers for gates */}
                    {item.span.result === 'fail' && item.w > 8 && (
                      <text x={item.x + item.w / 2} y={y + laneHeight / 2 + 4} fill="#fff" fontSize={10} textAnchor="middle" fontFamily="monospace">x</text>
                    )}
                    {item.span.result === 'pass' && item.w > 8 && (
                      <text x={item.x + item.w / 2} y={y + laneHeight / 2 + 4} fill="#fff" fontSize={10} textAnchor="middle" fontFamily="monospace">v</text>
                    )}
                    {/* Parallel count indicator */}
                    {overlapCount > 1 && item.w > 20 && (
                      <text x={item.x + 4} y={y + laneHeight / 2 + 3} fill="#fff" fontSize={8} fontFamily="monospace">x{overlapCount}</text>
                    )}
                  </g>
                )
              })}
            </g>
          )
        })}

        {/* Section 8.3 — sentinel session boundaries as full-height dividers
            with a "Session <short-id>" label anchored to the top of the lane. */}
        {sessionBoundaries.map((b, i) => {
          const detail = (b.span.detail || {}) as { session_id?: string; session_started_at?: string }
          const short = detail.session_id ? String(detail.session_id).slice(0, 8) : ''
          return (
            <g key={`sb-${i}`} data-testid="session-boundary">
              <line
                x1={b.x}
                y1={headerHeight}
                x2={b.x}
                y2={totalHeight}
                stroke="#f59e0b"
                strokeWidth={1}
                strokeDasharray="3,3"
              />
              <text
                x={b.x + 3}
                y={headerHeight + 10}
                fill="#f59e0b"
                fontSize={9}
                fontFamily="monospace"
              >
                Session {short}
              </text>
            </g>
          )
        })}

        {/* Hover lattice — vertical line tracking the cursor across all lanes */}
        {hoverLattice && hoverX !== null && (
          <line x1={hoverX} y1={headerHeight} x2={hoverX} y2={totalHeight} stroke="#52525b" strokeWidth={1} strokeDasharray="1,2" pointerEvents="none" />
        )}
      </svg>

      {/* Tooltip — terminal-style ASCII border */}
      {tooltip && (
        <div
          className="fixed z-50 bg-black border border-neutral-600 px-3 py-2 text-xs font-mono pointer-events-none shadow-lg"
          style={{
            left: tooltip.x + 12,
            top: Math.max(8, tooltip.y - 60),
            borderRadius: 0,
          }}
        >
          <div className="text-neutral-100 font-bold">┌─ {getCategoryLabel(tooltip.span.category)}</div>
          {tooltip.span.change && <div className="text-neutral-400">│ change: {tooltip.span.change}</div>}
          <div className="text-neutral-400">│ {formatTime(tooltip.span.start)} → {formatTime(tooltip.span.end)}</div>
          <div className="text-neutral-300">│ duration: {formatDuration(tooltip.span.duration_ms)}</div>
          {tooltip.span.result && (
            <div className={tooltip.span.result === 'pass' ? 'text-green-400' : 'text-red-400'}>
              │ result: {tooltip.span.result}
              {tooltip.span.retry !== undefined && tooltip.span.retry > 0 && ` (retry #${tooltip.span.retry})`}
            </div>
          )}
          {tooltip.span.detail && (tooltip.span.detail.preview as string) && (
            <div className="text-neutral-400">│ {(tooltip.span.detail.preview as string).slice(0, 60)}</div>
          )}
          {!!onSpanClick && tooltip.span.duration_ms > 60_000 && (
            <div className="text-neutral-500 mt-1">└─ click to drill down</div>
          )}
        </div>
      )}
    </div>
  )
}

function _bestTickInterval(totalSeconds: number, totalWidth: number): number {
  // Choose tick interval so ticks are ~80-150px apart
  const targetPx = 100
  const approxTicks = totalWidth / targetPx
  const approxInterval = totalSeconds / approxTicks
  const candidates = [10, 30, 60, 120, 300, 600, 900, 1800, 3600]
  for (const c of candidates) {
    if (c >= approxInterval) return c
  }
  return 3600
}

// ─── Breakdown bars ─────────────────────────────────────────────────

function BreakdownBars({ breakdown, compact = false }: { breakdown: ActivityBreakdown[]; compact?: boolean }) {
  if (!breakdown.length) return null
  const maxMs = breakdown[0]?.total_ms || 1

  if (compact) {
    // Compact mode: color dot + label + duration + pct (no bar graph).
    // Used when the breakdown sits in a narrow side column.
    return (
      <div className="font-mono text-xs space-y-1">
        {breakdown.map((b) => (
          <div key={b.category} className="flex items-center gap-1.5">
            <span
              className="inline-block w-2 h-2 flex-shrink-0"
              style={{ backgroundColor: getCategoryColor(b.category) }}
            />
            <span className="text-neutral-400 truncate flex-1 min-w-0" title={getCategoryLabel(b.category)}>
              {getCategoryLabel(b.category)}
            </span>
            <span className="text-neutral-300 flex-shrink-0">{formatDuration(b.total_ms)}</span>
            <span className="text-neutral-500 w-9 text-right flex-shrink-0">{b.pct}%</span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="font-mono text-xs space-y-1">
      {breakdown.map((b) => (
        <div key={b.category} className="flex items-center gap-2">
          <span className="w-28 text-right text-neutral-400 truncate" title={getCategoryLabel(b.category)}>{getCategoryLabel(b.category)}</span>
          <div className="flex-1 h-4 bg-neutral-900 rounded overflow-hidden">
            <div
              className="h-full rounded"
              style={{
                width: `${Math.max(1, b.total_ms / maxMs * 100)}%`,
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
  )
}

// ─── Main component ─────────────────────────────────────────────────

export default function ActivityView({ project, isRunning }: Props) {
  const [data, setData] = useState<ActivityTimelineData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<string>('')
  const [pxPerSecond, setPxPerSecond] = useState(0.5)
  const [manualZoom, setManualZoom] = useState(false)
  const [containerWidth, setContainerWidth] = useState(0)
  const [expandedSpan, setExpandedSpan] = useState<ActivitySpan | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const { lineageId } = useSelectedLineage()
  // Reset timeline data when the lineage selection flips so the prior
  // lineage's spans do not linger on screen during the refetch.
  useEffect(() => {
    setData(null)
    setError(null)
    setManualZoom(false)
  }, [lineageId])
  const fetchData = useCallback(() => {
    if (!project) return
    setLoading(true)
    getActivityTimeline(project, undefined, undefined, lineageId)
      .then((d) => {
        setData(d)
        setError(null)
        setLastRefresh(new Date().toLocaleTimeString('en-GB'))
        // Reset manual zoom on each refresh — auto-fit takes over again
        setManualZoom(false)
      })
      .catch((e) => setError(e?.message || 'Failed to load activity data'))
      .finally(() => setLoading(false))
  }, [project, lineageId])

  // Initial fetch
  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Auto-refresh every 30s when running
  useEffect(() => {
    if (!isRunning) return
    const interval = setInterval(fetchData, 30_000)
    return () => clearInterval(interval)
  }, [isRunning, fetchData])

  // Track container width via ResizeObserver
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const update = () => setContainerWidth(el.clientWidth)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [data])

  // Manual zoom handlers — set the manualZoom flag so resize doesn't override
  const zoomIn = useCallback(() => {
    setPxPerSecond((p) => Math.min(p * 1.5, 10))
    setManualZoom(true)
  }, [])
  const zoomOut = useCallback(() => {
    setPxPerSecond((p) => Math.max(p / 1.5, 0.005))
    setManualZoom(true)
  }, [])

  // Wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault()
      if (e.deltaY < 0) zoomIn()
      else zoomOut()
    }
  }, [zoomIn, zoomOut])

  // Click handler for drilldown
  const handleSpanClick = useCallback((span: GanttSpan) => {
    // Toggle off if same span clicked again
    if (expandedSpan && expandedSpan.start === span.start && expandedSpan.category === span.category) {
      setExpandedSpan(null)
      return
    }
    setExpandedSpan(span as ActivitySpan)
  }, [expandedSpan])

  // Compute visible categories (only those with spans)
  const { categories, minTime, maxTime } = useMemo(() => {
    if (!data?.spans.length) return { categories: [] as string[], minTime: 0, maxTime: 0 }
    const catSet = new Set(data.spans.map((s) => s.category))
    const cats = [...catSet].sort((a, b) => {
      const ai = Object.keys(CATEGORY_COLORS).indexOf(a)
      const bi = Object.keys(CATEGORY_COLORS).indexOf(b)
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi)
    })
    let mn = Infinity
    let mx = -Infinity
    for (const s of data.spans) {
      const st = new Date(s.start).getTime()
      const et = new Date(s.end).getTime()
      if (st < mn) mn = st
      if (et > mx) mx = et
    }
    return { categories: cats, minTime: mn, maxTime: mx }
  }, [data])

  // Auto-fit zoom: compute pxPerSecond from container width on data load + resize.
  // Disabled when the user has manually zoomed since the last refresh.
  useEffect(() => {
    if (manualZoom || !containerWidth || maxTime <= minTime) return
    const wallSeconds = (maxTime - minTime) / 1000
    if (wallSeconds <= 0) return
    // Account for the 112px-wide left label column when computing fit width.
    const usableWidth = Math.max(200, containerWidth - 8)
    let fit = usableWidth / wallSeconds
    // Clamp very-short timelines so single spans don't stretch to full width
    if (wallSeconds < 60) fit = Math.min(fit, 5)
    setPxPerSecond(fit)
  }, [containerWidth, minTime, maxTime, manualZoom])

  if (!project) return <div className="p-3 text-neutral-500 font-mono text-sm">No project selected</div>

  return (
    <div className="p-3 space-y-4 font-mono text-xs bg-black min-h-full">
      {/* Error state */}
      {error && (
        <div className="text-red-400 bg-red-950/30 border border-red-900 px-3 py-2">
          {error}
        </div>
      )}

      {/* Summary header */}
      {data && (
        <div className="flex items-center gap-6 text-neutral-300 border-b border-neutral-800 pb-2">
          <span>
            Wall: <span className="text-neutral-100">{formatDuration(data.wall_time_ms)}</span>
          </span>
          <span>
            Activity: <span className="text-neutral-100">{formatDuration(data.activity_time_ms)}</span>
          </span>
          <span title="Parallel efficiency = activity_time / wall_time. >1.0x means LLM verifier and agent sessions overlap, or multiple changes ran in parallel.">
            Parallel: <span className="text-neutral-100">{data.parallel_efficiency}x</span>
          </span>
          <div className="flex-1" />
          <div className="flex items-center gap-2">
            <button onClick={zoomOut} className="px-2 py-0.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 text-neutral-300">-</button>
            <span className="text-neutral-500 w-20 text-center">
              {pxPerSecond < 0.1 ? pxPerSecond.toFixed(3) : pxPerSecond.toFixed(2)}px/s{manualZoom && '*'}
            </span>
            <button onClick={zoomIn} className="px-2 py-0.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 text-neutral-300">+</button>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-2 py-0.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 text-neutral-300 disabled:opacity-50"
          >
            {loading ? '...' : 'Refresh'}
          </button>
          {lastRefresh && <span className="text-neutral-600">Last: {lastRefresh}</span>}
        </div>
      )}

      {/* Top row: Gantt (75%) + Breakdown (25%) side by side.
          On narrow screens (<lg) Breakdown stacks under the Gantt. */}
      {data && categories.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-x-4">
          {/* Main Gantt chart — 3/4 width */}
          <div className="lg:col-span-3 min-w-0">
            <div className="flex">
              {/* Fixed category labels */}
              <div className="flex-shrink-0 w-28 pt-7">
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

              {/* Scrollable timeline */}
              <div
                ref={scrollRef}
                className="flex-1 overflow-x-auto overflow-y-hidden bg-black min-w-0"
                onWheel={handleWheel}
              >
                <GanttTimeline
                  spans={data.spans as GanttSpan[]}
                  categories={categories}
                  minTime={minTime}
                  maxTime={maxTime}
                  pxPerSecond={pxPerSecond}
                  onSpanClick={handleSpanClick}
                  hoverLattice
                />
              </div>
            </div>
          </div>

          {/* Breakdown — 1/4 width column on the right */}
          {data.breakdown.length > 0 && (
            <div className="lg:col-span-1 min-w-0 lg:pt-7">
              <div className="text-neutral-500 mb-2">┌──── Breakdown ────┐</div>
              <BreakdownBars breakdown={data.breakdown} compact />
            </div>
          )}
        </div>
      )}

      {/* Drilldown panel — opens on click */}
      {data && expandedSpan && project && (
        <ActivitySessionDetail
          project={project}
          span={expandedSpan}
          onClose={() => setExpandedSpan(null)}
        />
      )}

      {/* Empty state */}
      {data && categories.length === 0 && (
        <div className="text-neutral-600 text-center py-8">No activity data available</div>
      )}
    </div>
  )
}
