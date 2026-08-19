import { describe, expect, it } from 'vitest'

import { age, stalestSeconds } from '../../src/lib/fleetAge'

describe('age — one formatter, shared rather than copied', () => {
  it('says nothing rather than zero when nothing is known', () => {
    // `—` and `0s` are different claims. A null that formatted as a zero would
    // read as "it moved just now", which is the false-absence direction.
    expect(age(null)).toBe('—')
    expect(age(undefined)).toBe('—')
    expect(age(0)).toBe('0s')
  })

  it('changes unit at the documented boundaries', () => {
    expect(age(89)).toBe('89s')
    expect(age(90)).toBe('2m')
    expect(age(5399)).toBe('90m')
    expect(age(5400)).toBe('2h')
  })
})

describe('stalestSeconds — the project row answers "where has work stopped"', () => {
  const project = (...secs: (number | null)[]) => ({
    name: 'demo', root: '/x', sources: [], archived: false,
    agents: secs.map((s, i) => ({ pid: i, last_movement_seconds: s })),
  })

  it('takes the MAXIMUM, so one busy agent cannot vouch for the rest', () => {
    // A mean would report 30 minutes here and look like data while doing it.
    expect(stalestSeconds(project(5, 3600, 8) as never)).toBe(3600)
  })

  it('is null when nothing reported a movement — not zero', () => {
    expect(stalestSeconds(project() as never)).toBeNull()
    expect(stalestSeconds(project(null, null) as never)).toBeNull()
    expect(stalestSeconds(undefined)).toBeNull()
  })

  it('keeps a real zero', () => {
    // Something that moved this second is a fact; it must not fall into the
    // same bucket as "we do not know".
    expect(stalestSeconds(project(0) as never)).toBe(0)
  })
})
