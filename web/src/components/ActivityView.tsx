import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { getActivityTimeline } from '../lib/api'
import type { ActivityTimelineData, ActivitySpan, ActivityBreakdown } from '../lib/api'

interface Props {
  project: string | null
  isRunning?: boolean
}

// ─── Category colors (terminal/monospace aesthetic) ─────────────────

const CATEGORY_COLORS: Record<string, string> = {
  planning: '#a78bfa',       // violet
  implementing: '#22c55e',   // green
  fixing: '#f59e0b',         // amber
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
  idle: '#404040',           // dark gray
  'stall-recovery': '#ef4444', // red
  'dep-wait': '#737373',     // gray
  'manual-wait': '#a3a3a3',  // light gray
  sentinel: '#525252',       // dim
}

function getCategoryColor(cat: string): string {
  return CATEGORY_COLORS[cat] || '#525252'
}

// ─── Time formatting ────────────────────────────────────────────────

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function formatTime(isoStr: string): string {
  try {
    const d = new Date(isoStr)
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return isoStr.slice(11, 19)
  }
}

// ─── Gantt timeline renderer ────────────────────────────────────────

interface GanttProps {
  spans: ActivitySpan[]
  categories: string[]
  minTime: number
  maxTime: number
  pxPerSecond: number
}

function GanttTimeline({ spans, categories, minTime, maxTime, pxPerSecond }: GanttProps) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; span: ActivitySpan } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const laneHeight = 24
  const headerHeight = 28
  const totalWidth = Math.max(600, (maxTime - minTime) / 1000 * pxPerSecond)
  const totalHeight = headerHeight + categories.length * laneHeight

  // Time axis tick marks
  const tickInterval = _bestTickInterval((maxTime - minTime) / 1000, totalWidth)
  const ticks: { x: number; label: string }[] = []
  const firstTick = Math.ceil(minTime / 1000 / tickInterval) * tickInterval * 1000
  for (let t = firstTick; t <= maxTime; t += tickInterval * 1000) {
    const x = (t - minTime) / 1000 * pxPerSecond
    ticks.push({ x, label: formatTime(new Date(t).toISOString()) })
  }

  // Build per-category span groups with parallel overlap detection
  const categorySpans = useMemo(() => {
    const map: Record<string, { span: ActivitySpan; x: number; w: number }[]> = {}
    for (const cat of categories) map[cat] = []
    for (const span of spans) {
      const cat = span.category
      if (!map[cat]) continue
      const startMs = new Date(span.start).getTime()
      const endMs = new Date(span.end).getTime()
      const x = (startMs - minTime) / 1000 * pxPerSecond
      const w = Math.max(2, (endMs - startMs) / 1000 * pxPerSecond)
      map[cat].push({ span, x, w })
    }
    return map
  }, [spans, categories, minTime, pxPerSecond])

  const handleMouseEnter = useCallback((e: React.MouseEvent, span: ActivitySpan) => {
    setTooltip({ x: e.clientX, y: e.clientY, span })
  }, [])

  const handleMouseLeave = useCallback(() => setTooltip(null), [])

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        width={totalWidth}
        height={totalHeight}
        className="block"
      >
        {/* Time axis */}
        <line x1={0} y1={headerHeight} x2={totalWidth} y2={headerHeight} stroke="#404040" strokeWidth={1} />
        {ticks.map((tick, i) => (
          <g key={i}>
            <line x1={tick.x} y1={headerHeight - 4} x2={tick.x} y2={headerHeight} stroke="#525252" />
            <text x={tick.x} y={headerHeight - 8} fill="#a3a3a3" fontSize={10} textAnchor="middle" fontFamily="monospace">
              {tick.label}
            </text>
            <line x1={tick.x} y1={headerHeight} x2={tick.x} y2={totalHeight} stroke="#262626" strokeWidth={1} strokeDasharray="2,4" />
          </g>
        ))}

        {/* Lanes */}
        {categories.map((cat, laneIdx) => {
          const y = headerHeight + laneIdx * laneHeight
          const laneSpans = categorySpans[cat] || []

          // Detect parallel overlap count per pixel region
          return (
            <g key={cat}>
              {/* Lane background */}
              <rect x={0} y={y} width={totalWidth} height={laneHeight} fill={laneIdx % 2 === 0 ? '#0a0a0a' : '#111111'} />

              {/* Span blocks */}
              {laneSpans.map((item, si) => {
                const color = getCategoryColor(cat)
                // Count overlapping spans at this position for opacity
                const overlapCount = laneSpans.filter(
                  other => other.x < item.x + item.w && other.x + other.w > item.x
                ).length
                const opacity = Math.min(1, 0.5 + overlapCount * 0.2)

                return (
                  <g key={si}>
                    <rect
                      x={item.x}
                      y={y + 2}
                      width={item.w}
                      height={laneHeight - 4}
                      fill={color}
                      opacity={opacity}
                      rx={2}
                      className="cursor-pointer"
                      onMouseEnter={(e) => handleMouseEnter(e, item.span)}
                      onMouseLeave={handleMouseLeave}
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
      </svg>

      {/* Tooltip — fixed to viewport to avoid scroll/overflow issues */}
      {tooltip && (
        <div
          className="fixed z-50 bg-neutral-800 border border-neutral-600 rounded px-3 py-2 text-xs font-mono pointer-events-none shadow-lg"
          style={{
            left: tooltip.x + 12,
            top: Math.max(8, tooltip.y - 60),
          }}
        >
          <div className="text-neutral-200 font-bold">{tooltip.span.category}</div>
          {tooltip.span.change && <div className="text-neutral-400">change: {tooltip.span.change}</div>}
          <div className="text-neutral-400">{formatTime(tooltip.span.start)} — {formatTime(tooltip.span.end)}</div>
          <div className="text-neutral-300">duration: {formatDuration(tooltip.span.duration_ms)}</div>
          {tooltip.span.result && (
            <div className={tooltip.span.result === 'pass' ? 'text-green-400' : 'text-red-400'}>
              result: {tooltip.span.result}
              {tooltip.span.retry !== undefined && tooltip.span.retry > 0 && ` (retry #${tooltip.span.retry})`}
            </div>
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

function BreakdownBars({ breakdown }: { breakdown: ActivityBreakdown[] }) {
  if (!breakdown.length) return null
  const maxMs = breakdown[0]?.total_ms || 1

  return (
    <div className="font-mono text-xs space-y-1">
      {breakdown.map((b) => (
        <div key={b.category} className="flex items-center gap-2">
          <span className="w-28 text-right text-neutral-400 truncate">{b.category}</span>
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
  const scrollRef = useRef<HTMLDivElement>(null)
  const autoScrolled = useRef(false)

  const fetchData = useCallback(() => {
    if (!project) return
    setLoading(true)
    getActivityTimeline(project)
      .then((d) => {
        setData(d)
        setError(null)
        setLastRefresh(new Date().toLocaleTimeString('en-GB'))
      })
      .catch((e) => setError(e?.message || 'Failed to load activity data'))
      .finally(() => setLoading(false))
  }, [project])

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

  // Auto-scroll to end on first load
  useEffect(() => {
    if (data && !autoScrolled.current && scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth
      autoScrolled.current = true
    }
  }, [data])

  // Zoom handlers
  const zoomIn = useCallback(() => setPxPerSecond((p) => Math.min(p * 1.5, 10)), [])
  const zoomOut = useCallback(() => setPxPerSecond((p) => Math.max(p / 1.5, 0.05)), [])

  // Wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault()
      if (e.deltaY < 0) zoomIn()
      else zoomOut()
    }
  }, [zoomIn, zoomOut])

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

  if (!project) return <div className="p-3 text-neutral-500 font-mono text-sm">No project selected</div>

  return (
    <div className="p-3 space-y-4 font-mono text-xs">
      {/* Error state */}
      {error && (
        <div className="text-red-400 bg-red-950/30 border border-red-900 rounded px-3 py-2">
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
          <span>
            Parallel: <span className="text-neutral-100">{data.parallel_efficiency}x</span>
          </span>
          <div className="flex-1" />
          <div className="flex items-center gap-2">
            <button onClick={zoomOut} className="px-2 py-0.5 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300">-</button>
            <span className="text-neutral-500 w-16 text-center">{pxPerSecond.toFixed(2)}px/s</span>
            <button onClick={zoomIn} className="px-2 py-0.5 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300">+</button>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-2 py-0.5 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300 disabled:opacity-50"
          >
            {loading ? '...' : 'Refresh'}
          </button>
          {lastRefresh && <span className="text-neutral-600">Last: {lastRefresh}</span>}
        </div>
      )}

      {/* Gantt chart */}
      {data && categories.length > 0 && (
        <div className="flex">
          {/* Fixed category labels */}
          <div className="flex-shrink-0 w-28 pt-7">
            {categories.map((cat) => (
              <div
                key={cat}
                className="h-6 flex items-center text-neutral-400 text-right pr-2 truncate"
                title={cat}
              >
                <span
                  className="inline-block w-2 h-2 rounded-full mr-1 flex-shrink-0"
                  style={{ backgroundColor: getCategoryColor(cat) }}
                />
                {cat}
              </div>
            ))}
          </div>

          {/* Scrollable timeline */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-x-auto overflow-y-hidden"
            onWheel={handleWheel}
          >
            <GanttTimeline
              spans={data.spans}
              categories={categories}
              minTime={minTime}
              maxTime={maxTime}
              pxPerSecond={pxPerSecond}
            />
          </div>
        </div>
      )}

      {/* Empty state */}
      {data && categories.length === 0 && (
        <div className="text-neutral-600 text-center py-8">No activity data available</div>
      )}

      {/* Breakdown */}
      {data && data.breakdown.length > 0 && (
        <div className="border-t border-neutral-800 pt-3">
          <div className="text-neutral-500 mb-2">Breakdown</div>
          <BreakdownBars breakdown={data.breakdown} />
        </div>
      )}
    </div>
  )
}
