/**
 * Reordering a list by pointer, with a keyboard path that is not a fallback.
 *
 * Extracted from the project column on 2026-08-26, when the agent tab strip
 * needed the same gesture along the other axis. It is shared rather than copied
 * because four of the things in it are not preferences — each is a defect that
 * reached the running screen once:
 *
 *  - the 4 px engagement threshold (a click that moved a row six positions and
 *    saved it),
 *  - the index read off the ELEMENT rather than counted from the rendered rows
 *    (a partially rendered list moved the wrong member),
 *  - the refocus after a keyboard move (without it the second arrow press goes
 *    nowhere, so the keyboard path moves something once and then stops),
 *  - and `CSS.escape` with a fallback (the unit environment does not have it).
 *
 * A second copy would be a second place for all four to come back.
 *
 * ## Why pointer events rather than HTML5 drag-and-drop
 *
 * The gesture has to be one a person can actually perform, so it is built on
 * pointer events with capture — which real mouse and touch input produce, and
 * which a synthetic `dispatchEvent` in a test would only imitate. The handle is
 * also a focusable button that moves its item with the arrow keys: that path is
 * genuinely user-performable too, and unlike the pointer path it can be asserted
 * without a layout engine.
 */

import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent, RefObject } from 'react'

/**
 * Which way the list runs. `y` is a column of rows, `x` a strip of tabs.
 *
 * It changes exactly two things — which coordinate the midpoint test reads, and
 * which arrow keys move an item — and nothing else. Everything above stays the
 * same because it is the same gesture.
 */
export type ReorderAxis = 'x' | 'y'

/**
 * `CSS.escape`, or a fallback.
 *
 * Not defensive habit: measured 2026-08-19, the unit environment's `localStorage`
 * is a plain object with none of its methods, so "the DOM globals are all there"
 * is not true here. A missing `CSS` would throw inside an effect and take the
 * landing screen down for a lookup that has a two-line substitute.
 */
export function escapeAttr(value: string): string {
  const css = (globalThis as { CSS?: { escape?: (s: string) => string } }).CSS
  if (typeof css?.escape === 'function') return css.escape(value)
  return value.replace(/["\\]/g, m => '\\' + m)
}

export interface ReorderHandlers {
  onPointerDown: (e: ReactPointerEvent<HTMLElement>) => void
  onPointerMove: (e: ReactPointerEvent<HTMLElement>) => void
  onPointerUp: (e: ReactPointerEvent<HTMLElement>) => void
  onPointerCancel: () => void
  onKeyDown: (e: ReactKeyboardEvent<HTMLElement>) => void
}

export interface ReorderApi {
  handlers: ReorderHandlers
  dragFrom: number | null
  dragTo: number | null
}

/**
 * Handles that carry their own index, rather than a factory called per row.
 *
 * The index and the identity live on the element as `data-drag-index` and
 * `data-drag-handle`, and every handler is a stable callback that reads them
 * off `currentTarget`. That is not a style choice: props built by calling into
 * the hook on every render close over refs, and a closure captured during
 * render is how a drag ends up moving the row that *used* to be at that index.
 * Reading the index from the element at the moment of the gesture means the
 * index cannot be stale, because it is not remembered at all.
 */
export function useReorder(
  onMove: (from: number, to: number) => void,
  container: RefObject<HTMLElement | null>,
  /**
   * How many entries the STORED list has. Not `items().length`: a list may
   * render fewer rows than it holds (the ungrouped filter), and bounding the
   * keyboard move by what is on screen would stop an arrow key one row short of
   * the real end, or worse, at a boundary that moves when a filter is toggled.
   */
  count: number,
  /** Which way the list runs — see `ReorderAxis`. Defaults to a column. */
  axis: ReorderAxis = 'y',
): ReorderApi {
  /**
   * `engaged` is what separates a CLICK from a DRAG, and it is not defensive
   * polish — it is a defect found on the live screen on 2026-08-19.
   *
   * Clicking a handle and releasing without moving reordered the list. The cause
   * is that `indexAt` answers "which row is under this point", and a press in the
   * lower half of a row is already past that row's midpoint, so it answers with
   * the NEXT row — a move of one position, committed by a gesture that looks like
   * nothing happening. Measured against the running server: one click on
   * `consumer-h`'s grip moved it six positions and saved the result, because the
   * rows in between were hidden by the ungrouped filter and the answer is a
   * STORED index.
   *
   * Its direction is what makes it worth this comment. Nothing fails, nothing is
   * lost, and the arrangement is hand-made work that the user is not watching a
   * diff of — so the screen quietly rewrites the thing they built, one accidental
   * click at a time.
   */
  const live = useRef<{ from: number; to: number; pointerId: number; start: number; engaged: boolean } | null>(null)
  /** Pixels the pointer must travel before this counts as a drag at all. */
  const DRAG_THRESHOLD = 4
  const refocus = useRef<string | null>(null)
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null)


  // After a keyboard move the row is re-rendered at its new index, so the
  // handle loses focus and the next arrow press goes nowhere. Restoring it is
  // what makes the keyboard path a real way to reorder rather than a way to
  // move something once.
  useEffect(() => {
    const key = refocus.current
    if (!key) return
    refocus.current = null
    container.current?.querySelector<HTMLElement>(`[data-drag-handle="${escapeAttr(key)}"]`)?.focus()
  })

  const items = (): HTMLElement[] =>
    Array.from(container.current?.querySelectorAll<HTMLElement>(':scope > [data-drag-item]') ?? [])

  const indexOf = (el: HTMLElement): number => Number(el.dataset.dragIndex ?? -1)

  /**
   * The STORED index of the row under the pointer — read off the element, not
   * counted from its position among the rendered rows.
   *
   * The two are the same only while every member of the list is on screen, and
   * they stopped being the same when the ungrouped block gained a filter that
   * hides its agent-less projects. Counting rendered rows would then move a
   * project to the position of the *visible* row it was dropped on, which is a
   * different project — and the arrangement is hand-made work, so the mistake is
   * silent and expensive. Reading the index the row carries makes a partially
   * rendered list behave exactly like a complete one.
   */
  const indexAt = (position: number): number => {
    const list = items()
    if (list.length === 0) return 0
    for (const el of list) {
      const rect = el.getBoundingClientRect()
      const middle = axis === 'x' ? rect.left + rect.width / 2 : rect.top + rect.height / 2
      if (position < middle) return indexOf(el)
    }
    return indexOf(list[list.length - 1])
  }

  /** The coordinate this axis measures along. */
  const along = (e: { clientX: number; clientY: number }): number =>
    (axis === 'x' ? e.clientX : e.clientY)

  const handlers: ReorderHandlers = {
    onPointerDown: (e) => {
      if (e.button !== 0) return
      const from = indexOf(e.currentTarget)
      if (from < 0) return
      e.preventDefault()
      e.stopPropagation()
      // `preventDefault` above stops the browser's own focus-on-mousedown, so
      // without this the handle can only be reached with Tab — and the arrow-key
      // path, which is the only reordering a keyboard user has, would be
      // unreachable from the gesture that obviously starts a drag.
      e.currentTarget.focus()
      e.currentTarget.setPointerCapture?.(e.pointerId)
      live.current = { from, to: from, pointerId: e.pointerId, start: along(e), engaged: false }
      // Deliberately NOT `setDrag` yet: a press is not a drag, and highlighting
      // a drop target before the pointer has moved tells the reader a move is
      // under way when one click would commit nothing.
    },
    onPointerMove: (e) => {
      const s = live.current
      if (!s || e.pointerId !== s.pointerId) return
      if (!s.engaged) {
        if (Math.abs(along(e) - s.start) < DRAG_THRESHOLD) return
        s.engaged = true
      }
      const to = indexAt(along(e))
      if (to !== s.to) {
        s.to = to
        setDrag({ from: s.from, to })
      }
    },
    onPointerUp: (e) => {
      const s = live.current
      if (!s || e.pointerId !== s.pointerId) return
      e.currentTarget.releasePointerCapture?.(e.pointerId)
      live.current = null
      setDrag(null)
      // `engaged` first: without it, a release inside the row it started in
      // still commits, because the press point alone already resolves to a
      // different index.
      if (s.engaged && s.to !== s.from && s.to >= 0) {
        refocus.current = e.currentTarget.dataset.dragHandle ?? null
        onMove(s.from, s.to)
      }
    },
    onPointerCancel: () => { live.current = null; setDrag(null) },
    onKeyDown: (e) => {
      // The arrows that match the axis, and ONLY those: left/right on a column
      // would move a row while the reader was moving a caret, and up/down on a
      // strip would do the same the other way.
      const back = axis === 'x' ? 'ArrowLeft' : 'ArrowUp'
      const forward = axis === 'x' ? 'ArrowRight' : 'ArrowDown'
      if (e.key !== back && e.key !== forward) return
      const from = indexOf(e.currentTarget)
      const to = e.key === back ? from - 1 : from + 1
      if (from < 0 || to < 0 || to >= count) return
      e.preventDefault()
      refocus.current = e.currentTarget.dataset.dragHandle ?? null
      onMove(from, to)
    },
  }

  return { handlers, dragFrom: drag?.from ?? null, dragTo: drag?.to ?? null }
}
