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

import { searchText } from '../../src/components/StatusTable'

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
