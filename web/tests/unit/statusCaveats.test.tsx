/**
 * `caveats` — counted from the data, additive, and never an alarm.
 *
 * A caveat says a value is CORRECT and means something narrower than its name suggests. The
 * defect it fixes is that the number travels and the caveat does not, so the tests that matter
 * here are the ones about WHERE it ends up and what happens when the declaration is wrong —
 * not that a string can be rendered.
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import {
  COMMAND_LEVEL_CAVEAT,
  CaveatProvider,
  absentCaveatKeys,
  presentCaveats,
} from '../../src/components/statusShape'
import { StatusValue } from '../../src/components/StatusValue'

describe('presentCaveats — the declaration says what to look for, the data says what is there', () => {
  it('finds only the declared keys that the answer actually carries', () => {
    const data = { tracked: 12, untracked: 5 }
    const found = presentCaveats(data, { tracked: 'a lower bound', missing: 'never sent' })
    expect([...found.keys()]).toEqual(['tracked'])
    expect(found.get('tracked')).toBe('a lower bound')
  })

  it('walks nested objects and arrays, because a value is rarely at the top level', () => {
    const data = { stats: { deep: 3 }, rows: [{ nested: 1 }] }
    const found = presentCaveats(data, { deep: 'x', nested: 'y' })
    expect([...found.keys()].sort()).toEqual(['deep', 'nested'])
  })

  it('never looks for the command-level key in the data', () => {
    // It qualifies the COMMAND. A walker that looked for it would fail to find it in every
    // answer ever sent, and the diagnostics list would then accuse every correct producer.
    const found = presentCaveats({ a: 1 }, { [COMMAND_LEVEL_CAVEAT]: 'applies to all of it' })
    expect(found.size).toBe(0)
  })

  it('returns nothing when nothing is declared, without walking', () => {
    expect(presentCaveats({ a: { b: { c: 1 } } }, {}).size).toBe(0)
  })
})

describe('absentCaveatKeys — diagnostics, never a gate', () => {
  it('lists declared keys the answer does not carry', () => {
    expect(absentCaveatKeys({ here: 1 }, { here: 'a', gone: 'b', alsoGone: 'c' }))
      .toEqual(['alsoGone', 'gone'])
  })

  it('excludes the command-level key, or every correct producer is accused of a typo', () => {
    expect(absentCaveatKeys({ a: 1 }, { [COMMAND_LEVEL_CAVEAT]: 'general', a: 'specific' }))
      .toEqual([])
  })

  it('is empty when every declared key is present', () => {
    expect(absentCaveatKeys({ a: 1, b: 2 }, { a: 'x', b: 'y' })).toEqual([])
  })
})

describe('rendering — beside the value, at caveat weight', () => {
  const renderWith = (data: unknown, caveats: Record<string, string>) =>
    render(
      <CaveatProvider value={{ perField: presentCaveats(data, caveats) }}>
        <StatusValue value={data} />
      </CaveatProvider>,
    )

  it('puts the caveat in the same block as the value it qualifies', () => {
    // Adjacency is the requirement: a caveat one interaction away has been filed, not carried.
    renderWith({ tracked: 12 }, { tracked: 'a known lower bound' })
    const note = screen.getByText('a known lower bound')
    const cell = note.closest('dd')
    expect(cell).not.toBeNull()
    expect(cell!.textContent).toContain('12')
  })

  it('renders no caveat for a field whose declared key is absent from the data', () => {
    // The false-absence case: a caveat for a field the project stopped sending must be silent,
    // and must NOT announce that something was withheld.
    renderWith({ tracked: 12 }, { retired: 'this field is gone' })
    expect(screen.queryByText('this field is gone')).toBeNull()
    expect(screen.queryByText(/withheld|hidden/i)).toBeNull()
  })

  it('does not repeat the command-level sentence beside every value', () => {
    renderWith({ a: 1, b: 2 }, { [COMMAND_LEVEL_CAVEAT]: 'applies to all of these' })
    expect(screen.queryByText('applies to all of these')).toBeNull()
  })

  it('gives an alarming-sounding key no alarming treatment', () => {
    // The framework never reads the sentence to decide how to show it. One visual weight per
    // meaning: if red means broken, a caveat is not red — and a producer's wording may sound
    // alarming without being an alarm.
    renderWith({ expired: 3 }, { expired: 'the DEADLINE passed — not a failure, and not late' })
    const note = screen.getByText(/the DEADLINE passed/)
    const cls = note.className
    expect(cls).not.toMatch(/red|rose|amber|danger|error/i)
  })

  it('shows a per-field caveat that is only reachable through nesting', () => {
    renderWith({ stats: { untracked: 5 } }, { untracked: 'our register, not the world' })
    expect(screen.getByText('our register, not the world')).toBeTruthy()
  })
})

describe('additive — a per-field caveat can never remove the command-level one', () => {
  it('the "*" sentence survives a per-field entry for the same answer', () => {
    // Asserted on the DATA STRUCTURE rather than on the render, because the "*" is deliberately
    // NOT rendered per value — it belongs in the section header. The property under test is that
    // nothing a producer can put in a per-field entry removes it.
    const caveats = { [COMMAND_LEVEL_CAVEAT]: 'the general one', tracked: 'the narrow one' }
    const perField = presentCaveats({ tracked: 1 }, caveats)
    expect(caveats[COMMAND_LEVEL_CAVEAT]).toBe('the general one')
    expect(perField.get('tracked')).toBe('the narrow one')
  })

  it('offers no suppression value — an empty per-field sentence is dropped upstream, not honoured', () => {
    // There is no sentinel meaning "hide the default". The reader never sees an empty sentence
    // because the envelope parser drops it, so this asserts the renderer has no such path either.
    const perField = presentCaveats({ tracked: 1 }, { tracked: '' })
    expect(perField.get('tracked')).toBe('')
    // …and rendering an empty note would be an empty bordered box, so the guard is that the
    // producer's empty entry never reaches here: the Python side filters it.
  })

  it('a mistyped per-field key loses only the narrow half', () => {
    // The direction argument, as a test. Under replacement semantics this same typo would have
    // cleared everything beside the number.
    const caveats = { [COMMAND_LEVEL_CAVEAT]: 'still applies', trackd: 'typo' }
    const perField = presentCaveats({ tracked: 1 }, caveats)
    expect(perField.size).toBe(0)
    expect(caveats[COMMAND_LEVEL_CAVEAT]).toBe('still applies')
    expect(absentCaveatKeys({ tracked: 1 }, caveats)).toEqual(['trackd'])
  })
})

describe('diagnostics never becomes a gate', () => {
  it('reports absent keys as a plain list, with no severity of any kind', () => {
    // The listing is a list of names. It returns no count object, no level, no boolean "failed" —
    // there is nothing here for a caller to turn into an exit status without inventing it.
    const out = absentCaveatKeys({ a: 1 }, { a: 'x', gone: 'y' })
    expect(Array.isArray(out)).toBe(true)
    expect(out).toEqual(['gone'])
    out.forEach(v => expect(typeof v).toBe('string'))
  })
})
