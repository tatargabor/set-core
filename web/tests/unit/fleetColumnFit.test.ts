import { describe, expect, it } from 'vitest'
import { DEFAULT_COLUMNS, fitColumns } from '../../src/lib/fleetViewState'

/*
  The defect this file holds: the column count is a per-project preference that
  outlives the agents that justified it, and the DEFAULT is two. So a project
  with a single tile laid itself out in two columns — one tile, one empty
  column — and the control that would fix it was hidden behind `agents.length
  > 1`. Reported 2026-08-27.
*/
describe('fitting the stored column count to the tiles there are', () => {
  it('one tile is one column, whatever was stored — including the DEFAULT', () => {
    // The default is the case that shipped broken: nobody chose it, so nobody
    // suspected it, and every single-agent project got half a black panel.
    expect(fitColumns(DEFAULT_COLUMNS, 1)).toBe(1)
    for (const stored of [1, 2, 3, 4]) expect(fitColumns(stored, 1)).toBe(1)
  })

  it('a choice the tiles can fill is honoured untouched', () => {
    expect(fitColumns(2, 2)).toBe(2)
    expect(fitColumns(3, 3)).toBe(3)
    expect(fitColumns(4, 4)).toBe(4)
    expect(fitColumns(4, 9)).toBe(4)
    // Fewer columns than tiles is a choice, not a misfit: the rows wrap.
    expect(fitColumns(1, 7)).toBe(1)
    expect(fitColumns(2, 7)).toBe(2)
  })

  it('clamps DOWN to the tile count, never up to it', () => {
    expect(fitColumns(4, 2)).toBe(2)
    expect(fitColumns(3, 2)).toBe(2)
    expect(fitColumns(4, 3)).toBe(3)
  })

  it('does not overwrite the preference — the caller keeps what was stored', () => {
    // Stated as a test because the tempting fix is to write the fitted value
    // back, which would silently destroy a choice nobody changed: a project
    // that grows a second agent must return to two columns on its own.
    const stored = 4
    expect(fitColumns(stored, 1)).toBe(1)
    expect(stored).toBe(4)
    expect(fitColumns(stored, 4)).toBe(4)
  })

  it('with nothing to lay out it answers the stored value, not 1', () => {
    // No tiles is not a one-tile grid. Answering 1 would be a claim about a
    // layout that is not on screen; there is nothing to clamp against.
    expect(fitColumns(3, 0)).toBe(3)
    expect(fitColumns(3, -1)).toBe(3)
    expect(fitColumns(3, Number.NaN)).toBe(3)
  })
})
