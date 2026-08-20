/**
 * Docking geometry — the subtraction, and the three ways it can be wrong while
 * still producing a screen.
 *
 * Everything here is about the fact that a layout failure LOOKS like a layout.
 * A band that is a few pixels off, a grid handed a zero box, a view that
 * silently resizes when it is moved — none of them throw, none of them show up
 * in a structural count, and each one reads as "the screen decided something"
 * rather than as a defect.
 */
import { describe, expect, it } from 'vitest'
import {
  DEFAULT_DOCK_SIZE, bandsOn, dockSplitKey, dockedBands, isDockedView,
  remainingArea, withDock, type DockedView,
} from '../../src/lib/fleetDocks'
import { SPLIT_PROJECTS } from '../../src/lib/fleetSplits'

const right: DockedView = { kind: 'changes', id: 'v1', edge: 'right' }
const bottom: DockedView = { kind: 'changes', id: 'v2', edge: 'bottom' }

describe('what counts as a docked view', () => {
  it('accepts the four edges and nothing else', () => {
    for (const edge of ['left', 'right', 'top', 'bottom']) {
      expect(isDockedView({ kind: 'k', id: 'i', edge })).toBe(true)
    }
    // An unknown edge is not a smaller mistake — placing a view where nobody put
    // it renders, looks deliberate, and is wrong.
    expect(isDockedView({ kind: 'k', id: 'i', edge: 'diagonal' })).toBe(false)
    expect(isDockedView({ kind: 'k', id: 'i' })).toBe(false)
    expect(isDockedView(null)).toBe(false)
  })
})

describe('a docked view keeps the size the user gave it', () => {
  it('is keyed by identity, not by edge', () => {
    // Keyed by edge, moving a view from right to bottom would silently give it
    // whatever the last view on that edge was set to — the screen resizing
    // something the user sized.
    expect(dockSplitKey(right)).toBe('dock:changes:v1')
    expect(dockSplitKey({ ...right, edge: 'bottom' })).toBe(dockSplitKey(right))
  })

  it('uses the default until somebody drags it', () => {
    expect(dockedBands([right], {})[0].size).toBe(DEFAULT_DOCK_SIZE)
  })

  it('uses the stored position once there is one', () => {
    expect(dockedBands([right], { [dockSplitKey(right)]: 420 })[0].size).toBe(420)
  })

  it('drops an entry that is not a docked view rather than guessing an edge', () => {
    expect(dockedBands([right, { kind: 'x', id: 'y', edge: 'nowhere' }, null], {})).toHaveLength(1)
  })
})

describe('the area left for the agent grid', () => {
  const shell = { width: 1600, height: 900 }

  it('subtracts the project column and each band', () => {
    const bands = dockedBands([right], { [SPLIT_PROJECTS]: 300, [dockSplitKey(right)]: 400 })
    expect(remainingArea(shell, bands, { [SPLIT_PROJECTS]: 300, [dockSplitKey(right)]: 400 }))
      .toMatchObject({ width: 900, height: 900 })
  })

  it('subtracts on BOTH axes when two edges are docked', () => {
    const splits = { [SPLIT_PROJECTS]: 300, [dockSplitKey(right)]: 400, [dockSplitKey(bottom)]: 200 }
    const bands = dockedBands([right, bottom], splits)
    expect(remainingArea(shell, bands, splits)).toMatchObject({ width: 900, height: 700 })
  })

  it('treats left and right identically, and top and bottom identically', () => {
    const splits = { [dockSplitKey({ kind: 'changes', id: 'v1' })]: 400 }
    const asRight = remainingArea(shell, dockedBands([right], splits), splits)
    const asLeft = remainingArea(shell, dockedBands([{ ...right, edge: 'left' }], splits), splits)
    expect(asLeft.width).toBe(asRight.width)
  })

  it('never hands the grid a zero or negative box', () => {
    // A zero box is not a smaller box: it is a grid that renders nothing, and a
    // reader looking at an empty panel cannot tell that from "no agents".
    const splits = { [dockSplitKey(right)]: 900 }
    const out = remainingArea({ width: 800, height: 300 }, dockedBands([right], splits), splits)
    expect(out.width).toBeGreaterThan(0)
    expect(out.height).toBeGreaterThan(0)
  })

  it('SAYS that it overflowed rather than only clamping', () => {
    // Clamping alone would make a too-full screen look like a normal one. The
    // flag is what lets the surface say so where the reader is standing.
    const splits = { [dockSplitKey(right)]: 900 }
    expect(remainingArea({ width: 800, height: 300 }, dockedBands([right], splits), splits).overflowed).toBe(true)
    expect(remainingArea({ width: 1600, height: 900 }, [], {}).overflowed).toBe(false)
  })

  it('can be asked to ignore the project column, for a shell that has none', () => {
    expect(remainingArea(shell, [], { [SPLIT_PROJECTS]: 300 }, { projectColumn: false }).width).toBe(1600)
  })
})

describe('docking and undocking', () => {
  it('adds a view at the end of the list', () => {
    expect(withDock([], right, 'right')).toEqual([right])
  })

  it('moving a docked view keeps its position in the list', () => {
    // Sending it to the end would be the screen rearranging something the user
    // did not touch — the other views on that edge would shuffle past it.
    const docks = [right, bottom]
    const moved = withDock(docks, right, 'top')
    expect(moved.map(d => d.id)).toEqual(['v1', 'v2'])
    expect(moved[0].edge).toBe('top')
  })

  it('undocking removes it and returns the space', () => {
    const docks = [right, bottom]
    expect(withDock(docks, right, null).map(d => d.id)).toEqual(['v2'])
  })

  it('undocking something that was not docked changes nothing', () => {
    expect(withDock([bottom], right, null)).toEqual([bottom])
  })

  it('does not mutate the list it was given', () => {
    const docks = [right]
    withDock(docks, bottom, 'left')
    expect(docks).toEqual([right])
  })
})

describe('two views on one edge', () => {
  it('are both kept, in the order they were docked', () => {
    const a: DockedView = { kind: 'changes', id: 'a', edge: 'right' }
    const b: DockedView = { kind: 'changes', id: 'b', edge: 'right' }
    expect(bandsOn(dockedBands([a, b], {}), 'right').map(x => x.id)).toEqual(['a', 'b'])
  })

  it('each subtract their own size', () => {
    const a: DockedView = { kind: 'changes', id: 'a', edge: 'right' }
    const b: DockedView = { kind: 'changes', id: 'b', edge: 'right' }
    const splits = { [dockSplitKey(a)]: 300, [dockSplitKey(b)]: 200 }
    // `projectColumn: false` rather than a stored zero: a zero IS clamped to the
    // minimum, correctly — a pane cannot be stored into invisibility — so a test
    // that used one would be measuring the clamp and calling it "no column".
    expect(remainingArea({ width: 1600, height: 900 }, dockedBands([a, b], splits), splits,
                         { projectColumn: false }).width)
      .toBe(1100)
  })
})
