/**
 * A structured cell participates in search — or a project that improves its data makes the
 * surface worse.
 *
 * The measurement that forced this: `cellText` returned `''` for any object, so a cell holding a
 * structure contributed nothing to the index. The search box then answered "no rows" rather than
 * "this column is not indexed", which is the reassuring direction on the one control a reader
 * uses to decide something is not there.
 */
import { describe, expect, it } from 'vitest'
import { fireEvent, render } from '@testing-library/react'

import { constantColumns, searchText } from '../../src/components/StatusTable'
import StatusValue from '../../src/components/StatusValue'

describe('searchText — every scalar leaf, and nothing else', () => {
  it('reaches a leaf inside an object', () => {
    expect(searchText({ kind: 'meeting', date: '2026-05-06' })).toContain('meeting')
    expect(searchText({ kind: 'meeting', date: '2026-05-06' })).toContain('2026-05-06')
  })

  it('reaches every element of a list — the shape a set of participants arrives in', () => {
    const t = searchText({ participants: ['Anna', 'Peter', 'Gabor'] })
    expect(t).toContain('Anna')
    expect(t).toContain('Gabor')
  })

  it('reaches leaves at any depth, because nesting is not the reader’s problem', () => {
    expect(searchText({ a: { b: { c: ['deep-value'] } } })).toContain('deep-value')
  })

  it('leaves a scalar exactly as the project gave it', () => {
    expect(searchText('meeting/anj-bxay-muy')).toBe('meeting/anj-bxay-muy')
    expect(searchText(49)).toBe('49')
    expect(searchText(false)).toBe('false')
  })

  it('contributes nothing for absent values, rather than the word "null"', () => {
    // A row that matches a search for "null" because a cell is empty is a false match, and it
    // arrives exactly when the reader is looking for something that is not there.
    expect(searchText(null)).toBe('')
    expect(searchText(undefined)).toBe('')
    expect(searchText({ a: null, b: undefined })).toBe('')
  })
})

describe('the refuted approach, held in a test', () => {
  it('searching the serialised object would match a key name — this must not', () => {
    // JSON.stringify is the obvious shortcut and it is wrong in a way that looks right: every row
    // contains the word `date` when `date` is a key, so a search for it matches everything. A
    // control that cannot narrow is what this file's facet bounds already exist to prevent.
    const cell = { date: '2026-05-06', kind: 'meeting' }
    expect(JSON.stringify(cell)).toContain('date')      // the refuted version WOULD match
    expect(searchText(cell)).not.toContain('date')      // …and this one does not
    expect(searchText(cell)).not.toContain('{')
    expect(searchText(cell)).not.toContain('"')
  })

  it('a value that legitimately CONTAINS a key name still matches', () => {
    // The exclusion is of key names, not of the word. A row whose value is literally "date" is
    // still findable — otherwise the fix would have created a second blind spot.
    expect(searchText({ kind: 'date' })).toContain('date')
  })
})

describe('a column whose value never varies', () => {
  const nine = (extra: Record<string, unknown> = {}) =>
    Array.from({ length: 9 }, (_, i) => ({
      change: 'one-and-the-same', model: 'x', effort: null,
      group: String(i), seconds: i * 10, ...extra,
    }))

  it('is lifted out of the table and stated once', () => {
    const lifted = constantColumns(nine(), ['change', 'model', 'effort', 'group', 'seconds'])

    expect(lifted.map(l => l.key)).toEqual(['change', 'model', 'effort'])
    expect(lifted.find(l => l.key === 'change')!.value).toBe('one-and-the-same')
  })

  it('marks a column empty in EVERY row as absent, not as a value', () => {
    // A gap is not a zero. Repeating the same dash nine times is a slow way to say it once,
    // but saying nothing at all would be a different claim.
    const lifted = constantColumns(nine(), ['effort', 'group', 'seconds'])
    expect(lifted).toEqual([{ key: 'effort', value: null, missing: true }])
  })

  it('leaves a column alone the moment one row differs', () => {
    const rows = nine()
    rows[4].model = 'y'
    expect(constantColumns(rows, ['model'])).toEqual([])
  })

  it('lifts nothing from a table too small for the note to pay for itself', () => {
    // With two rows "both the same" is thin evidence about the column, and the note costs
    // more than the column it removes.
    //
    // TWO columns on purpose, one of them varying. With a single column the never-empty guard
    // returns [] regardless of the row count, so the first version of this test passed while
    // measuring the wrong rule — a mutation that lowered the threshold to two did not trip it.
    const two = [{ a: 'same', b: 1 }, { a: 'same', b: 2 }]
    expect(constantColumns(two, ['a', 'b'])).toEqual([])
  })

  it('never compares structures', () => {
    const rows = Array.from({ length: 9 }, () => ({ obj: { deep: 1 } }))
    expect(constantColumns(rows, ['obj'])).toEqual([])
  })

  it('never empties the table, however uniform it is', () => {
    // Lifting every column would leave a header and no data — a tidier screen showing nothing.
    const rows = Array.from({ length: 9 }, () => ({ a: 1, b: 2 }))
    expect(constantColumns(rows, ['a', 'b'])).toEqual([])
  })

  it('renders the lifted value ABOVE the table rather than dropping it', () => {
    // The rule that outranks the compaction: nothing withheld may become invisible. A constant
    // that happens to be a failure ends up MORE prominent after this, not less.
    const { container } = render(<StatusValue value={nine({ gate: 'FAILED' })} />)

    expect(container.textContent).toContain('one-and-the-same')
    expect(container.textContent).toContain('FAILED')
    expect(container.textContent).toContain('all 9 rows')
    expect([...container.querySelectorAll('th')].map(h => h.textContent))
      .not.toContain('change')
  })

  it('still finds a lifted column by SEARCH, because the value is still in every row', () => {
    // Removing it from the index would turn a term matching every row into one matching none,
    // and "no rows" is what a reader takes for "not there".
    const { container } = render(<StatusValue value={nine()} />)
    fireEvent.change(
      container.querySelector('input[aria-label="search rows"]')!,
      { target: { value: 'one-and-the' } },
    )

    expect(container.textContent).toContain('9 of 9 rows shown')
  })
})
