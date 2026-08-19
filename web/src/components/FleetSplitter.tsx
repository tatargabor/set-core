import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * A draggable divider between two panes.
 *
 * ## What it is responsible for, and what it deliberately is not
 *
 * It reports a size. It does not own one: the pane's width lives with whoever
 * renders the pane, so a divider that fails to mount cannot take the layout with
 * it. `onDrag` fires continuously so the pane follows the pointer, and `onCommit`
 * fires once on release — that split is why dragging an edge does not produce a
 * write per pixel.
 *
 * ## Both axes, because the second one is already promised
 *
 * The fleet screen has one divider today (the project column) and will have more
 * when views can be docked to an edge. A divider that only knows `x` would be
 * copied and edited for `y`, and the copy is where keyboard support and pointer
 * capture get left out — they are the parts nobody notices missing.
 *
 * ## Pointer capture, and why a mouse-move listener is not enough
 *
 * `setPointerCapture` keeps the events coming to this element after the pointer
 * leaves it, which is the ordinary case when dragging fast: without it the drag
 * silently stops at the element's edge and the pane freezes mid-motion, which
 * reads as a broken layout rather than as a lost event.
 *
 * ## It is reachable without a pointer
 *
 * `role="separator"` with the ARIA value attributes, focusable, and the arrow
 * keys move it. A divider that can only be dragged is a preference the keyboard
 * user cannot set at all — and unlike most such gaps, this one hides content
 * rather than merely being awkward.
 */
export interface FleetSplitterProps {
  /** Which way the pane grows. `x` = a vertical bar moved left/right. */
  axis?: 'x' | 'y'
  /** The pane's current size in px — this component renders from it, never from its own memory. */
  size: number
  /** Which side of the divider the pane is on: does dragging right make it bigger? */
  grows?: 'before' | 'after'
  min: number
  max: number
  /** Fires on every pointer move — for following the drag live. */
  onDrag: (px: number) => void
  /** Fires once, on release or after a key press — for persisting. */
  onCommit: (px: number) => void
  /** Spoken name, e.g. "project list width". */
  label: string
  /** Px per arrow key press; Shift multiplies by 4. */
  step?: number
}

export default function FleetSplitter({
  axis = 'x', size, grows = 'before', min, max, onDrag, onCommit, label, step = 16,
}: FleetSplitterProps) {
  const [dragging, setDragging] = useState(false)
  // The size at the moment the drag began, plus the pointer's origin. Deriving
  // from these rather than accumulating deltas means a dropped move event costs
  // nothing: the next one is still measured from the true origin.
  const origin = useRef<{ pointer: number; size: number } | null>(null)
  const latest = useRef(size)
  latest.current = size

  const clamp = useCallback((px: number) => Math.max(min, Math.min(max, Math.round(px))), [min, max])

  const onPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    // Only the primary button. A right-click drag would start a resize the user
    // never asked for and then lose it to the context menu.
    if (e.button !== 0) return
    e.preventDefault()
    // Guarded because pointer capture is an enhancement, not the mechanism: it
    // keeps a FAST drag alive past this element's edge. Where it is unavailable
    // — jsdom, an old engine — the drag must still work rather than throw on the
    // first press, which would make the divider immovable instead of imperfect.
    try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* not supported */ }
    origin.current = { pointer: axis === 'x' ? e.clientX : e.clientY, size: latest.current }
    setDragging(true)
  }, [axis])

  const onPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const start = origin.current
    if (!start) return
    const moved = (axis === 'x' ? e.clientX : e.clientY) - start.pointer
    onDrag(clamp(start.size + (grows === 'before' ? moved : -moved)))
  }, [axis, grows, onDrag, clamp])

  const end = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!origin.current) return
    origin.current = null
    setDragging(false)
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* already released */ }
    onCommit(latest.current)
  }, [onCommit])

  const onKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    const grow = axis === 'x' ? 'ArrowRight' : 'ArrowDown'
    const shrink = axis === 'x' ? 'ArrowLeft' : 'ArrowUp'
    let next: number | null = null
    const delta = step * (e.shiftKey ? 4 : 1)
    if (e.key === grow) next = clamp(latest.current + (grows === 'before' ? delta : -delta))
    else if (e.key === shrink) next = clamp(latest.current - (grows === 'before' ? delta : -delta))
    else if (e.key === 'Home') next = min
    else if (e.key === 'End') next = max
    if (next === null) return
    e.preventDefault()
    onDrag(next)
    // Committed per key press rather than on blur: a keyboard user gets no
    // release event, so "save when the drag ends" would never fire for them.
    onCommit(next)
  }, [axis, grows, step, clamp, min, max, onDrag, onCommit])

  // While dragging, the whole document must stop selecting text and stop
  // showing per-element cursors — otherwise a fast drag across a list selects
  // it, and the cursor flickers between shapes over every child it crosses.
  useEffect(() => {
    if (!dragging) return
    const body = document.body
    const prevCursor = body.style.cursor
    const prevSelect = body.style.userSelect
    body.style.cursor = axis === 'x' ? 'col-resize' : 'row-resize'
    body.style.userSelect = 'none'
    return () => { body.style.cursor = prevCursor; body.style.userSelect = prevSelect }
  }, [dragging, axis])

  const horizontal = axis === 'x'
  return (
    <div
      role="separator"
      tabIndex={0}
      aria-label={label}
      aria-orientation={horizontal ? 'vertical' : 'horizontal'}
      aria-valuenow={size}
      aria-valuemin={min}
      aria-valuemax={max}
      data-fleet-splitter={label}
      data-dragging={dragging ? 'true' : undefined}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={end}
      onPointerCancel={end}
      onKeyDown={onKeyDown}
      // A 1px line is what the eye should see; a wider transparent band is what
      // the pointer needs to hit. Hence a thin visible child inside a thicker
      // hit area, rather than a thick visible bar.
      className={`group relative shrink-0 z-10 ${
        horizontal ? 'w-1.5 cursor-col-resize' : 'h-1.5 cursor-row-resize'
      } focus:outline-none`}
      title={`${label} — drag, or focus and use the arrow keys`}
    >
      <div
        aria-hidden
        className={`absolute bg-surface-line transition-colors group-hover:bg-sky-500/60 group-focus:bg-sky-400 ${
          dragging ? '!bg-sky-400' : ''
        } ${horizontal ? 'inset-y-0 left-1/2 -translate-x-1/2 w-px' : 'inset-x-0 top-1/2 -translate-y-1/2 h-px'}`}
      />
    </div>
  )
}
