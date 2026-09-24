/**
 * The shared panel mechanism — the thing every header opener now opens with.
 *
 * ## What this file can and cannot prove
 *
 * The requirement is that opening a panel changes the size and position of
 * NOTHING else. The mechanism by which that holds is `position: fixed`, which
 * takes the panel out of the flow of the `flex-wrap` header row so the row
 * cannot lay it out.
 *
 * **jsdom has no layout engine and no stylesheet**, so `offsetHeight` is 0 for
 * everything here and `getComputedStyle` never sees a Tailwind class. A test in
 * this file asserting "the header did not grow" would pass on a panel that
 * pushes the page across the screen, which is worse than no test: it is a green
 * check that answers a different question than the one it appears to answer.
 *
 * So the split is deliberate:
 *
 *  - **here**: the panel is not laid out by its parent (it declares `fixed`),
 *    the chrome contract, and the open/close behaviour;
 *  - **`tests/e2e/fleet-panels.spec.ts`**: the actual geometry, measured in a
 *    real browser, where a pixel is a pixel.
 *
 * Neither is redundant and neither is sufficient.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, renderHook, act } from '@testing-library/react'

import { Panel, PanelRow, PanelTable } from '../../src/components/Panel'
import TileControls from '../../src/components/TileControls'
import { useDisclosure } from '../../src/lib/useDisclosure'

afterEach(cleanup)

describe('useDisclosure', () => {
  it('starts closed and reports its state through a marker', () => {
    const { result } = renderHook(() => useDisclosure('modules'))
    expect(result.current.open).toBe(false)
    expect(result.current.triggerData).toEqual({ 'data-fleet-modules-open': 'off' })
  })

  it('names the marker after the opener, so every opener is addressable', () => {
    // The waiters trigger had NO stable selector — its test found it as "the
    // only button" in an isolated render. Every opener getting the same marker
    // is the repair, not merely consistency.
    const { result } = renderHook(() => useDisclosure('waiters'))
    expect(Object.keys(result.current.triggerData)).toEqual(['data-fleet-waiters-open'])
  })

  it('toggles, and the marker follows', () => {
    const { result } = renderHook(() => useDisclosure('modules'))
    act(() => result.current.toggle())
    expect(result.current.open).toBe(true)
    expect(result.current.triggerData).toEqual({ 'data-fleet-modules-open': 'on' })
    act(() => result.current.close())
    expect(result.current.open).toBe(false)
  })

  it('closes on Escape while open, and does not listen while closed', () => {
    const { result } = renderHook(() => useDisclosure('waiters'))
    // Closed: the key must not be swallowed by a listener that should not exist.
    act(() => { fireEvent.keyDown(window, { key: 'Escape' }) })
    expect(result.current.open).toBe(false)

    act(() => result.current.toggle())
    act(() => { fireEvent.keyDown(window, { key: 'Escape' }) })
    expect(result.current.open).toBe(false)
  })
})

describe('Panel — out of flow', () => {
  it('declares itself fixed, which is what keeps it from being laid out', () => {
    // A class-name assertion is weak evidence on its own; it is here so that
    // REMOVING the mechanism fails loudly. The geometry itself is measured in
    // the e2e spec, where layout exists.
    const { container } = render(
      <Panel title="Waiters" onClose={() => {}}><p>body</p></Panel>,
    )
    const root = container.querySelector('[role="dialog"]')!
    expect(root.className).toContain('fixed')
    expect(root.className).toContain('inset-0')
  })

  it('caps its height instead of claiming a fixed slice of the viewport', () => {
    // `h-[76vh]` is what left one recorded entry above 380px of nothing.
    const { container } = render(
      <Panel title="Recorded" onClose={() => {}}><p>one entry</p></Panel>,
    )
    const box = container.querySelector('[role="dialog"] > div')!
    expect(box.className).toContain('max-h-[76vh]')
    expect(box.className).not.toMatch(/(^|\s)h-\[\d+vh\]/)
  })
})

describe('Panel — chrome', () => {
  it('always offers a close control', () => {
    const onClose = vi.fn()
    const { container } = render(
      <Panel title="Waiters" onClose={onClose}><p>body</p></Panel>,
    )
    fireEvent.click(container.querySelector('[data-fleet-panel-close]')!)
    expect(onClose).toHaveBeenCalled()
  })

  it('renders NO footer when no panel-wide actions are passed', () => {
    // Waiters and modules act per row, not per panel. A footer they do not need
    // is also where a bulk action would arrive by accident.
    const { container } = render(
      <Panel title="Waiters" onClose={() => {}}><p>body</p></Panel>,
    )
    expect(container.querySelector('[data-fleet-panel-footer]')).toBeNull()
  })

  it('renders a footer when panel-wide actions ARE passed', () => {
    const { container } = render(
      <Panel title="Recorded" onClose={() => {}} footer={<button>Restore 1 selected</button>}>
        <p>body</p>
      </Panel>,
    )
    expect(container.querySelector('[data-fleet-panel-footer]')!.textContent)
      .toMatch(/Restore 1 selected/)
  })

  it('omits the counts entirely rather than printing a zero it did not measure', () => {
    // `fleetInstructSurface.test.tsx` asserts an unmeasured waiters surface does
    // not say "none orphaned". A header that always prints a count would make
    // an absence look like a measurement of nothing.
    const { container } = render(
      <Panel title="Waiters" onClose={() => {}}><p>body</p></Panel>,
    )
    expect(container.querySelector('[role="dialog"]')!.textContent).not.toMatch(/\d/)
  })

  it('closes on a backdrop click and stays open on a click inside', () => {
    const onClose = vi.fn()
    const { container } = render(
      <Panel title="Waiters" onClose={onClose}><p>body</p></Panel>,
    )
    fireEvent.click(container.querySelector('[role="dialog"] > div')!)
    expect(onClose).not.toHaveBeenCalled()
    fireEvent.click(container.querySelector('[role="dialog"]')!)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('carries the markers it is given', () => {
    const { container } = render(
      <Panel title="Modules" onClose={() => {}} data={{ 'data-fleet-install-panel': 'demo' }}>
        <p>body</p>
      </Panel>,
    )
    expect(container.querySelector('[data-fleet-install-panel="demo"]')).toBeTruthy()
  })
})

describe('PanelTable — rows as columns', () => {
  const columns = [
    { key: 'pid', label: 'PID', width: '5rem' },
    { key: 'status', label: 'Status', width: '7rem' },
    { key: 'cwd', label: 'Working directory', width: 'minmax(0,1fr)' },
    { key: 'action', label: 'Action', width: '12rem', align: 'end' as const },
  ]

  it('declares the template once so every row inherits the same one', () => {
    // Two rows that lay themselves out independently are two rows that drift
    // out of alignment with their own heading.
    const { container } = render(
      <PanelTable columns={columns}>
        <PanelRow data={{ 'data-fleet-waiter': '1' }}><span>1</span><span>live</span><span>/a</span><span /></PanelRow>
        <PanelRow data={{ 'data-fleet-waiter': '2' }}><span>2</span><span>orphaned</span><span>/b</span><span /></PanelRow>
      </PanelTable>,
    )
    const table = container.firstElementChild as HTMLElement
    expect(table.style.getPropertyValue('--panel-cols'))
      .toBe('5rem 7rem minmax(0,1fr) 12rem')
    for (const row of container.querySelectorAll('[data-fleet-waiter]')) {
      expect((row as HTMLElement).style.gridTemplateColumns).toBe('var(--panel-cols)')
    }
  })

  it('heads every column, so a field can be found without reading a row', () => {
    const { container } = render(<PanelTable columns={columns}><span /></PanelTable>)
    const heads = [...container.querySelector('[data-fleet-panel-head]')!.children]
      .map(c => c.textContent)
    expect(heads).toEqual(['PID', 'Status', 'Working directory', 'Action'])
  })
})

/**
 * Task 7.6 — the notice that used to own a row.
 *
 * *We could not ask* was a line of its own under the tile header. Measured in a
 * real browser on 2026-09-23, on the running dashboard: that line was
 * 1411 × 13 px, and removing it moved the terminal below it from y=150 to
 * y=133. So a notice ARRIVING pushed 17 px of content the reader was already
 * looking at — which is what `an opened panel never changes the size or
 * position of anything else` forbids in its own words: *a notice arriving does
 * not shift the row*.
 *
 * The fix is not to reserve the row's height — the user asked for the mark to
 * join the icons, which removes the row instead of padding it out:
 * *"The yellow warning triangle icon shouldn'T have a whole line for itself,
 * put it above to the icons too."*
 *
 * **What this file can prove about that, and what it cannot.** jsdom has no
 * layout, so the 17 px is not re-measurable here (see this file's header). What
 * IS structural, and is what these tests hold, is WHERE the mark lives and what
 * kind of thing it is — the two facts that make the shift impossible. The pixels
 * stay a browser measurement, recorded in the task.
 */
describe('task 7.6 — the unasked mark costs no row', () => {
  const tile = (declaredUnasked: boolean) => render(
    <TileControls
      agent={{ pid: 7, name: 'demo-a1', state: 'quiet' } as never}
      logOpen={false}
      onLog={() => {}}
      terminalOpen={false}
      onTerminal={() => {}}
      declaredUnasked={declaredUnasked}
    />,
  )

  it('puts the mark inside the title bar, not in a row of its own', () => {
    const { container } = tile(true)
    const mark = container.querySelector('[data-fleet-declared="unasked"]')
    expect(mark).toBeTruthy()
    // The assertion that carries the requirement: it is a CHILD of the
    // controls row. A mark rendered anywhere else is a mark with a row.
    expect(mark!.closest('[data-tile-controls]')).toBeTruthy()
  })

  it('reports a condition rather than offering an act, so it is not a button', () => {
    // `IconButton` renders a <span> when it has no `onClick`. A <button> here
    // would be a control that does nothing when clicked, which this screen's
    // own rule calls worse than an absent one.
    const { container } = tile(true)
    const mark = container.querySelector('[data-fleet-declared="unasked"]')!
    expect(mark.tagName).toBe('SPAN')
  })

  it('carries ONE description — the browser tooltip, not a second panel', () => {
    // Reported by the user: *"remove it's description, since when I'm hovering
    // it the default description appears"*. It used to have a `title` AND a
    // hover panel of its own, so hovering said the same thing twice.
    const { container } = tile(true)
    const mark = container.querySelector('[data-fleet-declared="unasked"]')!
    expect(mark.getAttribute('title')).toMatch(/could not ask/)
    expect(container.querySelector('[data-fleet-declared-note]')).toBeNull()
  })

  it('is absent while the bus DID answer, so the mark means what it says', () => {
    const { container } = tile(false)
    expect(container.querySelector('[data-fleet-declared="unasked"]')).toBeNull()
  })
})
