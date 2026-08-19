import { describe, expect, it } from 'vitest'
import { EMPTY_TALLY, firstAwaiting, tally } from '../../src/lib/fleetAttention'
import type { AttentionProject } from '../../src/lib/fleetAttention'

const P = (name: string, awaiting?: unknown, agents: unknown[] = []): AttentionProject =>
  ({ name, agents, awaiting } as AttentionProject)

describe('az emberre váró munka számolása', () => {
  it('egy agent nélküli projekt is számít — ez az egész taszk lényege', () => {
    const t = tally([P('a', { total: 2, source_missing: false })])
    expect(t.agents).toBe(0)
    expect(t.awaiting).toBe(2)
  })

  it('NEM keveredik össze a válaszra váró agentekkel', () => {
    // Kettő külön kérdés: az egyik egy ÉLŐ agent, aki kérdezett; a másik olyan
    // munka, amin senki nem áll. Aki az egyiket kergeti, mást csinál, mint aki
    // a másikat — az összeadás mindkét számot használhatatlanná tenné.
    const t = tally([P('a', { total: 3 }, [{ pid: 1, state: 'waiting' }])])
    expect(t.waiting).toBe(1)
    expect(t.awaiting).toBe(3)
  })

  it('a nem mért projekt nem nulla, hanem külön szám', () => {
    const t = tally([P('a', { total: 0, source_missing: true }), P('b', { total: 1 })])
    expect(t.awaiting).toBe(1)
    expect(t.unmeasured).toBe(1)
  })

  it('a hiányzó kulcs sem nulla és sem nem mért — a producer nem küldte', () => {
    // Egy régebbi szerver egyáltalán nem küld `awaiting`-et. Az nem ugyanaz,
    // mint hogy megnéztük és nem találtunk állapotfájlt.
    const t = tally([P('a', undefined)])
    expect(t.awaiting).toBe(0)
    expect(t.unmeasured).toBe(0)
  })

  it('az üres összesítés hordozza a két új mezőt', () => {
    expect(EMPTY_TALLY.awaiting).toBe(0)
    expect(EMPTY_TALLY.unmeasured).toBe(0)
  })
})

describe('az ugrás célja', () => {
  const byName = new Map<string, AttentionProject>([
    ['a', P('a', { total: 0 })],
    ['b', P('b', { total: 0, source_missing: true })],
    ['c', P('c', { total: 2 })],
  ])

  it('az OLVASÁSI sorrend első emberre váró projektjére ugrik', () => {
    expect(firstAwaiting(['a', 'b', 'c'], byName)).toBe('c')
  })

  it('agent nélküli projektet is megtalál — az agent-alapú kereső ezt kihagyná', () => {
    // Ez a függvény azért létezik külön: a `firstMatching` AGENTET keres, és
    // ezeknek a projekteknek jellemzően nincs egy sem.
    expect(byName.get('c')!.agents.length).toBe(0)
    expect(firstAwaiting(['c'], byName)).toBe('c')
  })

  it('nincs találat esetén NULL, nem az első projekt', () => {
    // Egy irreleváns helyre ugrás megtanítja az olvasót, hogy a jelzés zaj.
    expect(firstAwaiting(['a', 'b'], byName)).toBeNull()
  })

  it('a meg nem mért projekt nem ugrási cél', () => {
    expect(firstAwaiting(['b'], byName)).toBeNull()
  })
})
