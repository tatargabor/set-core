/**
 * The declared process, on screen.
 *
 * `stageGroups.test.ts` proves the model; this file proves the model REACHES the DOM. The two
 * are separate on purpose, because the defect this whole change exists to close is a value
 * that is computed correctly and then silently dropped on the way out — twice, at two different
 * layers. A green model test beside a renderer that never renders it is exactly that failure
 * wearing a passing suite.
 *
 * So every assertion here is about something being PRESENT: the empty stage, the marked stray,
 * the honest count. An assertion that nothing threw would pass against the unfixed renderer.
 */

import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import StatusValue from '../../src/components/StatusValue'
import { RoleProvider } from '../../src/components/statusShape'
import { ROW_CAP } from '../../src/components/StatusTable'

afterEach(() => { cleanup() })

const ORDER = ['planned', 'specified', 'in-progress', 'implemented', 'demoed', 'done']
const DECLARED = { lane: { stageOrder: ORDER } }

function show(rows: unknown[], display: Record<string, unknown> = DECLARED) {
  return render(
    <RoleProvider value={display}>
      <StatusValue value={rows} />
    </RoleProvider>,
  )
}

/** The strip's chips, as `[stage, declared, count]`. Read from the DOM, not from the model. */
function chips() {
  const strip = screen.queryByTestId('stage-strip')
  if (!strip) return null
  return Array.from(strip.querySelectorAll('[data-stage]')).map(el => [
    el.getAttribute('data-stage'),
    el.getAttribute('data-declared'),
    Number(el.getAttribute('data-count')),
  ])
}

const row = (lane: string | null, i: number) => ({ id: `r${i}`, lane, note: `n${i}` })

describe('the declared process is drawn', () => {
  it('draws every declared stage, in the declared order', () => {
    show([row('planned', 1), row('done', 2)])
    expect(chips()!.map(c => c[0])).toEqual(ORDER)
  })

  it('draws a declared stage that holds nothing, and says it holds nothing', () => {
    // The guarantee a table cannot express by itself: no rows means no row to render, so
    // without the strip the stage is simply absent — indistinguishable from a process that
    // never had one.
    show([row('planned', 1), row('planned', 2)])
    const empties = chips()!.filter(c => c[2] === 0).map(c => c[0])
    expect(empties).toEqual(['specified', 'in-progress', 'implemented', 'demoed', 'done'])
    expect(screen.getByTestId('stage-strip').textContent).toContain('done 0')
  })

  it('draws the whole order even when nothing matches any stage', () => {
    show([row('tesztelés', 1)])
    expect(chips()!.filter(c => c[1] === 'true').map(c => c[0])).toEqual(ORDER)
  })
})

describe('a value outside the declared order is visible and marked', () => {
  it('shows it, marked as undeclared', () => {
    show([row('planned', 1), row('tesztelés', 2)])
    const stray = chips()!.find(c => c[0] === 'tesztelés')
    expect(stray).toBeDefined()
    expect(stray![1]).toBe('false')
    expect(stray![2]).toBe(1)
  })

  it('states how many rows sit outside the process, where the reader is standing', () => {
    show([row('planned', 1), row('tesztelés', 2), row('zeta', 3)])
    expect(screen.getByTestId('stage-strip-unmatched').textContent)
      .toContain('2 rows outside the declared order')
  })

  it('marks it structurally, not only by colour', () => {
    // A colour is a restyle away from gone. `data-declared` is the mark that survives one.
    show([row('tesztelés', 1)])
    const stray = screen.getByTestId('stage-strip').querySelector('[data-stage="tesztelés"]')
    expect(stray!.getAttribute('data-declared')).toBe('false')
  })

  it('never lets the stray pass for the final declared stage', () => {
    show([row('planned', 1), row('done', 2), row('tesztelés', 3)])
    const all = chips()!
    const last = all[all.length - 1]
    expect(last[0]).toBe('tesztelés')
    // It is last, and position is not the defect — the mark is. `done` is still there, still
    // declared, and still distinguishable from it.
    expect(last[1]).toBe('false')
    expect(all.find(c => c[0] === 'done')![1]).toBe('true')
  })

  it('keeps rows carrying no value at all, marked rather than lost', () => {
    show([row('planned', 1), row(null, 2)])
    const none = chips()!.find(c => c[0] === '')
    expect(none).toBeDefined()
    expect(none![1]).toBe('false')
  })
})

describe('the counts do not lie when the cap bites', () => {
  it('reports the TRUE count for a stage larger than the cap', () => {
    const rows = Array.from({ length: ROW_CAP + 20 }, (_, i) => row('planned', i))
    show(rows)
    expect(chips()!.find(c => c[0] === 'planned')![2]).toBe(ROW_CAP + 20)
  })

  it('does NOT report a stage as empty when its every row fell past the cap', () => {
    // The trap this guards, and the one worth having a test for: ROW_CAP rows of `planned`
    // then a single `done`. Count from the rendered slice and `done` reads as 0 while
    // genuinely holding a row — an honest cap turned into a false absence.
    const rows = [
      ...Array.from({ length: ROW_CAP + 5 }, (_, i) => row('planned', i)),
      row('done', 999),
    ]
    show(rows)
    expect(chips()!.find(c => c[0] === 'done')![2]).toBe(1)
  })
})

describe('nothing changes for a consumer that declares nothing', () => {
  it('draws no strip without a declaration', () => {
    show([row('planned', 1), row('done', 2)], {})
    expect(chips()).toBeNull()
  })

  it('draws no strip when the declared order is malformed', () => {
    show([row('planned', 1)], { lane: { stageOrder: ['planned', 3] } })
    expect(chips()).toBeNull()
  })

  it('draws no strip when the declared field is absent from every row', () => {
    // The shipped presence rule: a declaration alone must never conjure a process onto screen.
    show([{ id: 'r1', other: 1 }, { id: 'r2', other: 2 }], DECLARED)
    expect(chips()).toBeNull()
  })
})
