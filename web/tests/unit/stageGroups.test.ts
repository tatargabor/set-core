/**
 * A declared process keeps its shape, and what falls outside it stays visible.
 *
 * The two tests that matter most here are the ones that look like they are about nothing: the
 * empty declared stage, and the stage whose every row fell past the cap. Both are the same
 * failure — a stage that exists reporting as absent — and both are invisible on screen, because
 * a missing column looks exactly like a process that never had one.
 */

import { describe, expect, it } from 'vitest'

import { hasStageOrder, stageGroups, unmatchedCount } from '../../src/lib/stageGroups'

const ORDER = ['planned', 'specified', 'in-progress', 'implemented', 'demoed', 'done']

/** A tiny row model: index → stage value. */
function from(values: (string | null)[]) {
  return {
    indices: values.map((_, i) => i),
    valueAt: (i: number) => values[i],
  }
}

describe('the declared order is read, never derived', () => {
  it('keeps every declared stage even when nothing matched it', () => {
    const { indices, valueAt } = from(['planned', 'planned'])
    const groups = stageGroups(indices, valueAt, ORDER)

    expect(groups.map(g => g.stage)).toEqual(ORDER)
    // The five nobody matched are present, in position, and honest about being empty.
    expect(groups.filter(g => g.count === 0).map(g => g.stage))
      .toEqual(['specified', 'in-progress', 'implemented', 'demoed', 'done'])
  })

  it('yields the identical order for two answers with disjoint values', () => {
    const a = from(['planned', 'planned'])
    const b = from(['done'])

    const ga = stageGroups(a.indices, a.valueAt, ORDER).map(g => g.stage)
    const gb = stageGroups(b.indices, b.valueAt, ORDER).map(g => g.stage)

    // The property a `Set` of present stages would break, and the reason the order is static:
    // two readers filtering differently must not see two different processes.
    expect(ga).toEqual(gb)
  })

  it('renders the whole order even when no row matches anything', () => {
    const { indices, valueAt } = from(['tesztelés'])
    const groups = stageGroups(indices, valueAt, ORDER)
    expect(groups.filter(g => g.declared).map(g => g.stage)).toEqual(ORDER)
  })

  it('produces every declared stage from an empty row set', () => {
    const groups = stageGroups([], () => null, ORDER)
    expect(groups.map(g => g.stage)).toEqual(ORDER)
    expect(groups.every(g => g.count === 0)).toBe(true)
  })
})

describe('a value outside the order stays visible and marked', () => {
  it('keeps the unmatched row rather than dropping it', () => {
    const { indices, valueAt } = from(['planned', 'tesztelés'])
    const groups = stageGroups(indices, valueAt, ORDER)

    const stray = groups.find(g => g.stage === 'tesztelés')
    expect(stray).toBeDefined()
    expect(stray!.indices).toEqual([1])
  })

  it('marks it as outside the declared process', () => {
    const { indices, valueAt } = from(['tesztelés'])
    const groups = stageGroups(indices, valueAt, ORDER)

    expect(groups.find(g => g.stage === 'tesztelés')!.declared).toBe(false)
    expect(groups.filter(g => g.declared).every(g => ORDER.includes(g.stage as string))).toBe(true)
  })

  it('never lets an unmatched value pass for the end of the process', () => {
    const { indices, valueAt } = from(['planned', 'done', 'tesztelés'])
    const groups = stageGroups(indices, valueAt, ORDER)

    const last = groups[groups.length - 1]
    // It IS last — position is not the defect. The mark is what stops it reading as a stage.
    expect(last.stage).toBe('tesztelés')
    expect(last.declared).toBe(false)
    // And the real final stage is still there, still declared, still distinguishable from it.
    expect(groups.find(g => g.stage === 'done')!.declared).toBe(true)
  })

  it('never extends the declared order with a value it did not contain', () => {
    const { indices, valueAt } = from(['tesztelés', 'planned'])
    const groups = stageGroups(indices, valueAt, ORDER)

    expect(groups.filter(g => g.declared).map(g => g.stage)).toEqual(ORDER)
    expect(groups.filter(g => g.declared).map(g => g.stage)).not.toContain('tesztelés')
  })

  it('groups rows carrying no value at all, marked, rather than losing them', () => {
    const { indices, valueAt } = from(['planned', null, null])
    const groups = stageGroups(indices, valueAt, ORDER)

    const none = groups.find(g => g.stage === null)
    expect(none).toBeDefined()
    expect(none!.declared).toBe(false)
    expect(none!.count).toBe(2)
  })

  it('keeps several unmatched values apart, in first-appearance order', () => {
    const { indices, valueAt } = from(['zeta', 'alpha', 'zeta'])
    const groups = stageGroups(indices, valueAt, ORDER).filter(g => !g.declared)
    expect(groups.map(g => g.stage)).toEqual(['zeta', 'alpha'])
    expect(groups[0].count).toBe(2)
  })

  it('reports how many rows sit outside the process', () => {
    const { indices, valueAt } = from(['planned', 'tesztelés', 'zeta', null])
    expect(unmatchedCount(stageGroups(indices, valueAt, ORDER))).toBe(3)
  })
})

describe('counts come from the full set, never the rendered slice', () => {
  it('reports the TRUE count for a stage holding more rows than the cap', () => {
    const values = Array.from({ length: 60 }, () => 'planned')
    const { indices, valueAt } = from(values)
    const groups = stageGroups(indices, valueAt, ORDER)

    expect(groups.find(g => g.stage === 'planned')!.count).toBe(60)
  })

  it('does NOT report a stage as empty when its every row fell past the cap', () => {
    // 30 `planned` then 1 `done`. Hand the model a 25-row slice — the mistake this guards —
    // and `done` reports as empty while genuinely holding a row.
    const values = [...Array.from({ length: 30 }, () => 'planned'), 'done']
    const { indices, valueAt } = from(values)

    const honest = stageGroups(indices, valueAt, ORDER)
    expect(honest.find(g => g.stage === 'done')!.count).toBe(1)

    const fromSlice = stageGroups(indices.slice(0, 25), valueAt, ORDER)
    expect(fromSlice.find(g => g.stage === 'done')!.count).toBe(0)
    // Stated as an assertion so the difference is the test's subject, not a comment about it:
    // the two disagree, and only the first one is allowed on screen.
    expect(honest.find(g => g.stage === 'done')!.count)
      .not.toBe(fromSlice.find(g => g.stage === 'done')!.count)
  })
})

describe('nothing changes for a consumer that declares nothing', () => {
  it('does not group without a declaration', () => {
    expect(hasStageOrder(null)).toBe(false)
    expect(hasStageOrder(undefined)).toBe(false)
    expect(hasStageOrder([])).toBe(false)
    expect(hasStageOrder(['planned'])).toBe(true)
  })

  it('preserves the incoming row order inside a stage', () => {
    const { indices, valueAt } = from(['planned', 'done', 'planned'])
    const groups = stageGroups(indices, valueAt, ORDER)
    expect(groups.find(g => g.stage === 'planned')!.indices).toEqual([0, 2])
  })

  it('loses no row: every index lands in exactly one group', () => {
    const { indices, valueAt } = from(['planned', 'tesztelés', null, 'done', 'planned'])
    const groups = stageGroups(indices, valueAt, ORDER)

    const landed = groups.flatMap(g => g.indices).sort((a, b) => a - b)
    expect(landed).toEqual([0, 1, 2, 3, 4])
    expect(groups.reduce((n, g) => n + g.count, 0)).toBe(5)
  })
})
