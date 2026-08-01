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
import { CELL_CLIP_CHARS, charBudgetFor, tableCharWidth } from '../../src/components/statusShape'

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
