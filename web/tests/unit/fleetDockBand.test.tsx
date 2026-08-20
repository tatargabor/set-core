/**
 * A docked band, and the one requirement in this change most likely to be
 * quietly skipped: a collapsed band must still report a failure inside it.
 *
 * Everything else here renders visibly and gets noticed if it breaks. This does
 * not — a band with no marker looks exactly like a band with nothing wrong, and
 * looks *better*, because it is tidier. `ui-quality.md` states the rule and its
 * direction: a tidy screen reporting calm it has not verified is worse than a
 * cluttered one, because it is more convincing.
 *
 * The three-way distinction is the whole test file:
 *
 *   failing > 0   → said loudly
 *   failing === 0 → checked, nothing wrong
 *   failing null  → COULD NOT CHECK, which is not zero
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import FleetDockBand from '../../src/components/FleetDockBand'
import type { DockedBand } from '../../src/lib/fleetDocks'

afterEach(() => cleanup())

const band = (over: Partial<DockedBand> = {}): DockedBand => ({
  kind: 'changes', id: 'v1', edge: 'right', size: 320, ...over,
})

function show(over: Partial<React.ComponentProps<typeof FleetDockBand>> = {}) {
  const onResize = vi.fn()
  const onResizeCommit = vi.fn()
  const { container } = render(
    <FleetDockBand
      band={band()}
      title="changes"
      max={800}
      onResize={onResize}
      onResizeCommit={onResizeCommit}
      {...over}
    />,
  )
  return { container, onResize, onResizeCommit }
}

describe('a collapsed band still reports what is wrong inside it', () => {
  it('marks a failure on the collapsed edge, where the reader is standing', () => {
    const { container } = show({ collapsed: true, failing: 3 })
    const marker = container.querySelector('[data-fleet-dock-marker]')
    expect(marker).not.toBeNull()
    expect(marker?.getAttribute('data-fleet-dock-failing')).toBe('3')
    expect(marker?.textContent).toContain('3')
  })

  it('marks it when expanded too — the marker is not a collapsed-only feature', () => {
    const { container } = show({ collapsed: false, failing: 2 })
    expect(container.querySelector('[data-fleet-dock-marker]')?.getAttribute('data-fleet-dock-failing'))
      .toBe('2')
  })

  it('distinguishes "checked, nothing wrong" from "could not check"', () => {
    // The false-absence class in its exact form. Rendering an unknown as zero
    // is a claim of calm that was never measured, and it is the reassuring
    // direction: the reader stops looking.
    const { container: zero } = show({ failing: 0 })
    expect(zero.querySelector('[data-fleet-dock-marker]')?.getAttribute('data-fleet-dock-failing'))
      .toBe('0')
    cleanup()
    const { container: unknown } = show({ failing: null })
    expect(unknown.querySelector('[data-fleet-dock-marker]')?.getAttribute('data-fleet-dock-failing'))
      .toBe('unknown')
  })

  it('an unstated count is unknown, not zero', () => {
    // A caller that simply does not pass the prop has not said "nothing is
    // wrong" — it has said nothing. Defaulting that to zero would let every
    // view that forgets to report look calm.
    const { container } = show({})
    expect(container.querySelector('[data-fleet-dock-marker]')?.getAttribute('data-fleet-dock-failing'))
      .toBe('unknown')
  })

  it('says in words what the marker means, for a reader who hovers', () => {
    const { container } = show({ failing: null })
    expect(container.querySelector('[data-fleet-dock-marker]')?.getAttribute('title'))
      .toMatch(/could not determine/i)
  })
})

describe('the band geometry', () => {
  it('sizes along its own axis — width on a side edge, height on a top or bottom one', () => {
    const { container } = show({ band: band({ edge: 'right', size: 300 }) })
    expect((container.querySelector('[data-fleet-dock]') as HTMLElement).style.width).toBe('300px')
    cleanup()
    const { container: horizontal } = show({ band: band({ edge: 'bottom', size: 240 }) })
    const el = horizontal.querySelector('[data-fleet-dock]') as HTMLElement
    expect(el.style.height).toBe('240px')
    expect(el.style.width).toBe('')
  })

  it('collapses to a strip without losing the size it will reopen at', () => {
    // The stored size must survive collapsing: reopening at a default would
    // throw away a position the user set, which reads as the screen deciding.
    const { container } = show({ band: band({ size: 300 }), collapsed: true })
    const el = container.querySelector('[data-fleet-dock]') as HTMLElement
    expect(parseInt(el.style.width, 10)).toBeLessThan(300)
    expect(el.getAttribute('data-fleet-dock-collapsed')).toBe('true')
  })
})

describe('the divider', () => {
  it('is the shared component, with the axis and side its edge implies', () => {
    // Not a second implementation: the copy is where the keyboard support and
    // the bounds get left out.
    const { container } = show({ band: band({ edge: 'right' }) })
    const sep = container.querySelector('[role="separator"]')
    expect(sep?.getAttribute('aria-orientation')).toBe('vertical')
    cleanup()
    const { container: horizontal } = show({ band: band({ edge: 'bottom' }) })
    expect(horizontal.querySelector('[role="separator"]')?.getAttribute('aria-orientation'))
      .toBe('horizontal')
  })

  it('grows the band in the direction its edge implies — measured by dragging', () => {
    // Found by mutation: hard-coding `grows` to one side passed every assertion
    // this file had, because the direction is not in the DOM. It is only visible
    // in what a DRAG does, so the test has to drag. On a right-hand band the
    // pointer moving right makes the band SMALLER; on a left-hand one, bigger.
    const { container, onResize } = show({ band: band({ edge: 'right', size: 320 }) })
    const sep = container.querySelector('[role="separator"]') as HTMLElement
    fireEvent.pointerDown(sep, { button: 0, clientX: 500, pointerId: 1 })
    fireEvent.pointerMove(sep, { clientX: 560, pointerId: 1 })
    expect(onResize).toHaveBeenLastCalledWith(260)

    cleanup()
    const left = show({ band: band({ edge: 'left', size: 320 }) })
    const leftSep = left.container.querySelector('[role="separator"]') as HTMLElement
    fireEvent.pointerDown(leftSep, { button: 0, clientX: 500, pointerId: 1 })
    fireEvent.pointerMove(leftSep, { clientX: 560, pointerId: 1 })
    expect(left.onResize).toHaveBeenLastCalledWith(380)
  })

  it('is absent while collapsed', () => {
    // Dragging a strip that shows nothing sets a size whose effect is invisible,
    // and overwrites the one the reader chose before collapsing.
    const { container } = show({ collapsed: true })
    expect(container.querySelector('[role="separator"]')).toBeNull()
  })
})

describe('the controls', () => {
  it('offers undocking, which is how the space comes back', () => {
    const onUndock = vi.fn()
    show({ onUndock })
    screen.getByRole('button', { name: /undock changes/i }).click()
    expect(onUndock).toHaveBeenCalledTimes(1)
  })

  it('undocking does not ALSO collapse — asserted in both directions', () => {
    // Found by mutation: asserting only that collapse does not undock left the
    // other direction open, and a control that quietly did both would have
    // shipped. A one-directional check on a two-directional claim is the
    // narrowing this repository already names.
    const onToggleCollapsed = vi.fn()
    const onUndock = vi.fn()
    show({ onToggleCollapsed, onUndock })
    screen.getByRole('button', { name: /undock changes/i }).click()
    expect(onUndock).toHaveBeenCalledTimes(1)
    expect(onToggleCollapsed).not.toHaveBeenCalled()
  })

  it('offers collapsing separately from undocking', () => {
    // Two acts, two controls. One button that did both would make every reader
    // who wanted to tidy the screen close the thing they were tidying — the
    // same distinction the terminal already draws between detach and stop.
    const onToggleCollapsed = vi.fn()
    const onUndock = vi.fn()
    show({ onToggleCollapsed, onUndock })
    screen.getByRole('button', { name: /collapse changes/i }).click()
    expect(onToggleCollapsed).toHaveBeenCalledTimes(1)
    expect(onUndock).not.toHaveBeenCalled()
  })
})

describe('a collapsed band can still be identified', () => {
  it('shows its name even when the open band would not repeat it', () => {
    // Found by looking at the screen: a tidied side band was a bare arrow at
    // the edge. It does not hide a FAILURE — the marker still renders — but it
    // hides WHAT is there, and a reader cannot choose to reopen something they
    // cannot name. `showTitle: false` is about not duplicating a name the open
    // content already prints; collapsed, there is no such content.
    const { container } = show({ collapsed: true, showTitle: false })
    expect(container.textContent).toContain('changes')
  })

  it('does not repeat the name when OPEN and the content carries it', () => {
    // The other direction, so the fix cannot become "always print the name".
    const { container } = show({ collapsed: false, showTitle: false })
    const header = container.querySelector('[data-fleet-dock] > div') as HTMLElement
    expect(header.textContent).not.toContain('changes')
  })
})
