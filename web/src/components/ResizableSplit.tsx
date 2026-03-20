import { useRef, useState, useCallback, useEffect, type ReactNode } from 'react'

interface Props {
  top: ReactNode
  bottom: ReactNode
  defaultRatio?: number // 0-1, portion for top panel
  minTopPx?: number
  minBottomPx?: number
  storageKey?: string // localStorage key to persist ratio
}

export default function ResizableSplit({
  top,
  bottom,
  defaultRatio = 0.6,
  minTopPx = 100,
  minBottomPx = 80,
  storageKey = 'set-split-ratio',
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [ratio, setRatio] = useState(() => {
    if (storageKey) {
      const saved = localStorage.getItem(storageKey)
      if (saved) {
        const n = parseFloat(saved)
        if (!isNaN(n) && n > 0 && n < 1) return n
      }
    }
    return defaultRatio
  })
  const [collapsed, setCollapsed] = useState<'none' | 'bottom'>('none')
  const dragging = useRef(false)

  // Persist ratio
  useEffect(() => {
    if (storageKey && !dragging.current) {
      localStorage.setItem(storageKey, String(ratio))
    }
  }, [ratio, storageKey])

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault()
    dragging.current = true
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
  }, [])

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging.current || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const y = e.clientY - rect.top
    const total = rect.height
    const newRatio = Math.max(minTopPx / total, Math.min(1 - minBottomPx / total, y / total))
    setRatio(newRatio)
    setCollapsed('none')
  }, [minTopPx, minBottomPx])

  const onPointerUp = useCallback(() => {
    if (dragging.current && storageKey) {
      localStorage.setItem(storageKey, String(ratio))
    }
    dragging.current = false
  }, [ratio, storageKey])

  const topHeight = collapsed === 'bottom' ? '100%' : `${ratio * 100}%`
  const bottomHeight = collapsed === 'bottom' ? '0' : `${(1 - ratio) * 100}%`

  return (
    <div ref={containerRef} className="flex flex-col h-full">
      <div style={{ height: topHeight }} className="min-h-0 overflow-auto">
        {top}
      </div>
      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        className="h-1.5 shrink-0 bg-neutral-800 hover:bg-neutral-700 cursor-row-resize flex items-center justify-center"
      >
        <button
          onClick={() => setCollapsed(collapsed === 'bottom' ? 'none' : 'bottom')}
          className="text-neutral-600 hover:text-neutral-400 text-xs px-2"
        >
          {collapsed === 'bottom' ? '▲' : '▼'}
        </button>
      </div>
      <div style={{ height: bottomHeight }} className="min-h-0 overflow-hidden">
        {bottom}
      </div>
    </div>
  )
}
