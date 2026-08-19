/**
 * The divider, driven the way a person drives it.
 *
 * ## Why every one of these goes through a pointer or a key event
 *
 * `evidence-discipline.md` records the measurement that makes this mandatory: a
 * regression spec once scrolled a container with `element.scrollTo()` and passed
 * identically on the broken page and the fixed one, because the harness had a
 * power the user does not. Calling `onDrag` directly here would be the same
 * mistake in its purest form — it would assert that a prop this file declares
 * can be called, which is true of every prop ever declared.
 *
 * So: `pointerDown` → `pointerMove` → `pointerUp`, and arrow keys. What is being
 * measured is that a gesture moves the pane, and that the WRITE happens once.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import FleetSplitter from '../../src/components/FleetSplitter'

afterEach(() => cleanup())

function setup(over: Partial<React.ComponentProps<typeof FleetSplitter>> = {}) {
  const onDrag = vi.fn()
  const onCommit = vi.fn()
  render(
    <FleetSplitter
      label="project list width"
      size={288}
      min={180}
      max={900}
      onDrag={onDrag}
      onCommit={onCommit}
      {...over}
    />,
  )
  return { handle: screen.getByRole('separator'), onDrag, onCommit }
}

describe('dragging the divider', () => {
  it('moves the pane by the distance the pointer moved', () => {
    const { handle, onDrag } = setup()
    fireEvent.pointerDown(handle, { button: 0, clientX: 300, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 360, pointerId: 1 })
    expect(onDrag).toHaveBeenLastCalledWith(348) // 288 + 60
  })

  it('measures from where the drag STARTED, so a dropped move event costs nothing', () => {
    // Accumulating deltas would drift: one missed event and every later position
    // is wrong by that amount, permanently, with nothing on screen to say so.
    const { handle, onDrag } = setup()
    fireEvent.pointerDown(handle, { button: 0, clientX: 300, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 340, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 400, pointerId: 1 })
    expect(onDrag).toHaveBeenLastCalledWith(388) // 288 + 100, not 288 + 40 + 100
  })

  it('does not move at all until a press has happened', () => {
    // A pointer crossing the divider is the ordinary case — the mouse passes
    // over it on the way to everything on the right.
    const { handle, onDrag } = setup()
    fireEvent.pointerMove(handle, { clientX: 500, pointerId: 1 })
    expect(onDrag).not.toHaveBeenCalled()
  })

  it('ignores a non-primary button, which would start a resize nobody asked for', () => {
    const { handle, onDrag } = setup()
    fireEvent.pointerDown(handle, { button: 2, clientX: 300, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 400, pointerId: 1 })
    expect(onDrag).not.toHaveBeenCalled()
  })

  it('stays inside the bounds however far the pointer travels', () => {
    const { handle, onDrag } = setup()
    fireEvent.pointerDown(handle, { button: 0, clientX: 300, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: -5000, pointerId: 1 })
    expect(onDrag).toHaveBeenLastCalledWith(180)
    fireEvent.pointerMove(handle, { clientX: 5000, pointerId: 1 })
    expect(onDrag).toHaveBeenLastCalledWith(900)
  })

  it('writes ONCE, on release — not on every pixel of the drag', () => {
    // The reason the two callbacks exist. A write per move would be one HTTP
    // request per pixel, and the last one to land would not be the last one sent.
    const { handle, onDrag, onCommit } = setup()
    fireEvent.pointerDown(handle, { button: 0, clientX: 300, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 320, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 340, pointerId: 1 })
    expect(onCommit).not.toHaveBeenCalled()
    expect(onDrag.mock.calls.length).toBe(2)
    fireEvent.pointerUp(handle, { pointerId: 1 })
    expect(onCommit).toHaveBeenCalledTimes(1)
  })

  it('commits on a cancelled pointer too, so a lost drag is not a lost setting', () => {
    const { handle, onCommit } = setup()
    fireEvent.pointerDown(handle, { button: 0, clientX: 300, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 340, pointerId: 1 })
    fireEvent.pointerCancel(handle, { pointerId: 1 })
    expect(onCommit).toHaveBeenCalledTimes(1)
  })

  it('does not commit on a release that never had a press', () => {
    const { handle, onCommit } = setup()
    fireEvent.pointerUp(handle, { pointerId: 1 })
    expect(onCommit).not.toHaveBeenCalled()
  })
})

describe('reaching the divider without a pointer', () => {
  it('moves on the arrow keys, and commits each press', () => {
    // A keyboard user gets no release event, so "save when the drag ends" would
    // never fire for them — the setting would look adjustable and never persist.
    const { handle, onDrag, onCommit } = setup()
    fireEvent.keyDown(handle, { key: 'ArrowRight' })
    expect(onDrag).toHaveBeenLastCalledWith(304)
    expect(onCommit).toHaveBeenLastCalledWith(304)
    fireEvent.keyDown(handle, { key: 'ArrowLeft' })
    expect(onDrag).toHaveBeenLastCalledWith(272)
  })

  it('jumps to the bounds on Home and End', () => {
    const { handle, onDrag } = setup()
    fireEvent.keyDown(handle, { key: 'Home' })
    expect(onDrag).toHaveBeenLastCalledWith(180)
    fireEvent.keyDown(handle, { key: 'End' })
    expect(onDrag).toHaveBeenLastCalledWith(900)
  })

  it('leaves other keys alone', () => {
    const { handle, onDrag } = setup()
    fireEvent.keyDown(handle, { key: 'Enter' })
    fireEvent.keyDown(handle, { key: 'a' })
    expect(onDrag).not.toHaveBeenCalled()
  })

  it('announces its position, so the value is not pointer-only knowledge', () => {
    const { handle } = setup()
    expect(handle.getAttribute('aria-valuenow')).toBe('288')
    expect(handle.getAttribute('aria-valuemin')).toBe('180')
    expect(handle.getAttribute('aria-valuemax')).toBe('900')
    expect(handle.getAttribute('aria-orientation')).toBe('vertical')
  })
})

describe('the horizontal axis, which the docked views will need', () => {
  it('moves on the vertical pointer distance and the vertical arrows', () => {
    const { handle, onDrag } = setup({ axis: 'y', size: 240 })
    fireEvent.pointerDown(handle, { button: 0, clientY: 100, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientY: 160, pointerId: 1 })
    expect(onDrag).toHaveBeenLastCalledWith(300)
    fireEvent.keyDown(handle, { key: 'ArrowUp' })
    expect(onDrag).toHaveBeenLastCalledWith(224)
  })
})

describe('a pane on the OTHER side of the divider', () => {
  it('shrinks when the pointer moves right', () => {
    // `grows: 'after'` is what a right-docked view needs: the same gesture must
    // move the edge the same way while the pane it sizes is on the other side.
    const { handle, onDrag } = setup({ grows: 'after' })
    fireEvent.pointerDown(handle, { button: 0, clientX: 300, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 360, pointerId: 1 })
    expect(onDrag).toHaveBeenLastCalledWith(228) // 288 - 60
  })
})
