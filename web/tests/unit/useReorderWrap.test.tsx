/**
 * `useReorder` on a strip that WRAPS onto a second line — asked for 2026-10-20,
 * when the agent tab strip stopped scrolling sideways and started wrapping.
 *
 * The positions are mocked per element (the unit environment has no layout
 * engine), and the gesture is driven by pointer events: the same events a real
 * drag produces. Layout, 60 px wide tabs, 30 px tall lines:
 *
 *   line 1 (y 0–30):   [0] x 0–60   [1] x 60–120   [2] x 120–180
 *   line 2 (y 34–64):  [3] x 0–60   [4] x 60–120
 */
import { fireEvent, render } from '@testing-library/react'
import { useRef } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { useReorder, type ReorderAxis } from '../../src/lib/useReorder'

const RECTS: Array<[number, number]> = [[0, 0], [60, 0], [120, 0], [0, 34], [60, 34]]

function Strip({ onMove, axis = 'x' }: { onMove: (from: number, to: number) => void; axis?: ReorderAxis }) {
  const ref = useRef<HTMLDivElement | null>(null)
  const { handlers } = useReorder(onMove, ref, RECTS.length, axis)
  return (
    <div ref={ref}>
      {RECTS.map((_, i) => (
        <button key={i} data-drag-item="" data-drag-index={i} data-drag-handle={`t${i}`} {...handlers}>t{i}</button>
      ))}
    </div>
  )
}

function layout(container: HTMLElement) {
  container.querySelectorAll<HTMLElement>('[data-drag-item]').forEach((el, i) => {
    const [left, top] = RECTS[i]
    el.getBoundingClientRect = () => ({
      left, top, right: left + 60, bottom: top + 30, width: 60, height: 30, x: left, y: top,
      toJSON: () => ({}),
    }) as DOMRect
  })
}

function drag(container: HTMLElement, from: number, to: { x: number; y: number }) {
  const el = container.querySelectorAll<HTMLElement>('[data-drag-item]')[from]
  const [left, top] = RECTS[from]
  const at = { pointerId: 1, button: 0 }
  fireEvent.pointerDown(el, { ...at, clientX: left + 10, clientY: top + 10 })
  fireEvent.pointerMove(el, { ...at, clientX: to.x, clientY: to.y })
  fireEvent.pointerUp(el, { ...at, clientX: to.x, clientY: to.y })
}

describe('useReorder on a wrapped strip', () => {
  it('drops a tab dragged onto the second line among the second line', () => {
    const onMove = vi.fn()
    const { container } = render(<Strip onMove={onMove} />)
    layout(container)
    // Tab 0 dragged onto the left half of tab 4, on line 2. An x-only test would
    // answer 1 — the tab on line 1 whose midpoint is to the right of x 70.
    drag(container, 0, { x: 70, y: 45 })
    expect(onMove).toHaveBeenCalledWith(0, 4)
  })

  it('drops a tab from the second line onto the first', () => {
    const onMove = vi.fn()
    const { container } = render(<Strip onMove={onMove} />)
    layout(container)
    drag(container, 4, { x: 130, y: 12 })
    expect(onMove).toHaveBeenCalledWith(4, 2)
  })

  it('engages on a straight vertical move between lines', () => {
    const onMove = vi.fn()
    const { container } = render(<Strip onMove={onMove} />)
    layout(container)
    // Tab 3 straight up onto tab 0: no horizontal travel at all.
    drag(container, 3, { x: 10, y: 10 })
    expect(onMove).toHaveBeenCalledWith(3, 0)
  })

  it('keeps a single line as it was: a pointer above the strip reads by x', () => {
    const onMove = vi.fn()
    const { container } = render(<Strip onMove={onMove} />)
    layout(container)
    // Above line 1 entirely; the nearest line is line 1, and x 150 is past tab 1's midpoint.
    drag(container, 0, { x: 150, y: -40 })
    expect(onMove).toHaveBeenCalledWith(0, 2)
  })

  it('still treats a press without travel as a click', () => {
    const onMove = vi.fn()
    const { container } = render(<Strip onMove={onMove} />)
    layout(container)
    drag(container, 0, { x: 12, y: 11 })
    expect(onMove).not.toHaveBeenCalled()
  })
})
