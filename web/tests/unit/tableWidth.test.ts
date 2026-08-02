/**
 * The width estimate that decides whether a block sits beside a neighbour or takes the row.
 *
 * It exists because the first version of that decision counted TOP-LEVEL KEYS, and the tests
 * below are shaped around that specific mistake rather than around the happy path. A `review`
 * object holding four keys is one key and four columns; counting the key put a seven-column
 * table into a half-width slot and clipped its last header off the right edge. The direction is
 * what made it expensive — the estimate came out too SMALL, so the layout looked confident and
 * lost data, rather than looking wrong and losing nothing.
 */
import { describe, expect, it } from 'vitest'
import {
  CELL_CLIP_CHARS, CELL_CLIP_PX, cellClipPxFor, charBudgetFor, tableCharWidth, tablePxWidth,
} from '../../src/components/statusShape'

/** Two rows agreeing on a nested shape — the case the table flattens into columns. */
const NESTED = [
  { name: 'alpha', tasksTotal: 81, tasksDone: 36, review: { exists: 'yes', criticalOpen: 0, severityFromSection: 'high', blocksApply: 'no' } },
  { name: 'beta', tasksTotal: 88, tasksDone: 87, review: { exists: 'no', criticalOpen: 4, severityFromSection: 'low', blocksApply: 'yes' } },
]

/** The chrome the table spends before any data — kept in step with `needsFullWidth`. */
const CHROME = 11

describe('tableCharWidth', () => {
  it('measures the columns a nested object becomes, not the one key it is', () => {
    // `review.severityFromSection` alone is 25 characters, so any estimate that treated `review`
    // as a single column could not reach this figure however generous its per-column guess.
    const w = tableCharWidth(NESTED)
    expect(w).toBeGreaterThan('review.severityFromSection'.length)

    // Stated as the difference it makes to the DECISION, not only to the number: this table does
    // not fit a half-width slot, and the buggy version said it did.
    expect(w).toBeGreaterThan(charBudgetFor(825) - CHROME)
  })

  it('a bare count of top-level keys would NOT have caught it', () => {
    // Held as a test rather than a comment, so a later "simplification" back to counting keys
    // fails here instead of looking equivalent and quietly clipping a column again.
    const topLevelKeys = new Set(NESTED.flatMap(r => Object.keys(r))).size
    expect(topLevelKeys).toBe(4)
    expect(topLevelKeys).toBeLessThan(charBudgetFor(825) - CHROME)
  })

  it('a genuinely narrow table fits beside a neighbour', () => {
    const narrow = [
      { version: '1.20.0', date: '2026-07-22', status: 'released', hasTag: 'yes' },
      { version: '1.19.0', date: '2026-07-19', status: 'released', hasTag: 'yes' },
    ]
    expect(tableCharWidth(narrow)).toBeLessThan(charBudgetFor(825) - CHROME)
  })

  it('counts a long value only as far as the cell will show it', () => {
    // The cell clips, so budgeting for the untruncated string would send every table carrying one
    // long sentence to full width — the opposite failure, and a much more common shape.
    const long = [{ id: 'a', note: 'x'.repeat(400) }]
    expect(tableCharWidth(long)).toBeLessThan(CELL_CLIP_CHARS * 2 + 20)
  })

  it('ignores rows that are not objects rather than throwing on them', () => {
    expect(tableCharWidth([])).toBe(0)
  })
})

/**
 * The clip the cell actually uses, which is the half of the width rule that shows.
 *
 * The estimate above only decides how many copies of a table fit. What the reader SEES clipped is
 * this number, and until it was derived from the leftover width it was a Tailwind literal that no
 * rename could reach: a table that fitted the panel once kept a 42-character clip and left the
 * rest of the panel empty beside the sentence it was cutting.
 */
describe('cellClipPxFor', () => {
  /** Two rows whose last column is a long human sentence — the shape that made this visible. */
  const WAITING = [
    { change: 'planning-surface', group: '2', task: '2.6', text: `2.6 [confirm] ${'x'.repeat(200)}` },
    { change: 'planning-surface', group: '7', task: '7.7', text: `7.7 [confirm] ${'y'.repeat(300)}` },
  ]

  it('spends the width the table left over on the clip', () => {
    // The load-bearing test: with the old fixed clip this is an equality, not a gain.
    const clip = cellClipPxFor(WAITING, 1150, 1)
    expect(clip).toBeGreaterThan(CELL_CLIP_PX)
    expect(clip).toBeCloseTo(CELL_CLIP_PX + (1150 - tablePxWidth(WAITING)), 5)
  })

  it('a fixed clip would NOT have caught it', () => {
    // Held as a test rather than a comment: a later "simplify" back to the constant fails here
    // instead of looking equivalent and quietly re-clipping at 42 characters.
    expect(CELL_CLIP_PX).toBeLessThan(cellClipPxFor(WAITING, 1150, 1))
  })

  it('leaves a table that already fills its panel alone', () => {
    // No spare width means no widening — and never a NEGATIVE clip, which is what a bare
    // subtraction would produce and would render as a cell one character wide.
    const clip = cellClipPxFor(WAITING, 120, 1)
    expect(clip).toBe(CELL_CLIP_PX)
  })

  it('leaves a table that flowed into groups alone', () => {
    // Flowing already spends the width. Widening the clip on top of it would push each group
    // past its share and re-introduce the sideways scroll the flow exists to avoid.
    expect(cellClipPxFor(WAITING, 1600, 2)).toBe(CELL_CLIP_PX)
    expect(cellClipPxFor(WAITING, 1600, 3)).toBe(CELL_CLIP_PX)
  })

  it('treats an unmeasured panel as no information rather than as zero width', () => {
    // The first render sees 0 before the ResizeObserver reports. Zero is not "no room" — it is
    // "not known yet", and subtracting from it would clip every cell to nothing for one frame.
    expect(cellClipPxFor(WAITING, 0, 1)).toBe(CELL_CLIP_PX)
  })
})
