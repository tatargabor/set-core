import { describe, expect, it } from 'vitest'

import { age, ageKey, freshestSeconds, stalestSeconds } from '../../src/lib/fleetAge'

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

describe('freshestSeconds — the other question: where am I working right now', () => {
  const project = (...secs: (number | null)[]) => ({
    name: 'demo', root: '/x', sources: [], archived: false,
    agents: secs.map((s, i) => ({ pid: i, last_movement_seconds: s })),
  })

  it('takes the MINIMUM — the opposite end from stalestSeconds', () => {
    // The same project, both numbers: one agent moved 5s ago, another has been
    // still for an hour. Neither number is the other's approximation, which is
    // why the recency order renders both when they differ.
    expect(freshestSeconds(project(5, 3600, 8) as never)).toBe(5)
    expect(stalestSeconds(project(5, 3600, 8) as never)).toBe(3600)
  })

  it('is null when nothing reported a movement — not zero', () => {
    // A zero here would sort the project to the very top of a freshest-first
    // list, claiming it moved this second. Nobody looked.
    expect(freshestSeconds(project() as never)).toBeNull()
    expect(freshestSeconds(project(null, null) as never)).toBeNull()
    expect(freshestSeconds(undefined)).toBeNull()
  })

  it('keeps a real zero', () => {
    expect(freshestSeconds(project(0, 60) as never)).toBe(0)
  })
})

describe('ageKey — the sort key IS the displayed value', () => {
  // The whole contract in two properties, checked across the range rather than
  // at hand-picked points: a bucket that drifts from `age` puts a row above one
  // showing a smaller number, and nothing in a screenshot would explain why.
  const samples = [0, 0.4, 1.001, 1.002, 5, 32, 59.4, 59.6, 60, 89, 89.4, 89.6,
    90, 91, 100, 125, 130, 149, 150, 600, 3599, 5399, 5400, 5401, 7200, 12000, 86400]

  it('gives equal keys to exactly the rows that read the same', () => {
    for (const a of samples) {
      for (const b of samples) {
        expect(ageKey(a) === ageKey(b)).toBe(age(a) === age(b))
      }
    }
  })

  it('never sorts a row above one that displays a smaller age', () => {
    const sorted = [...samples].sort((x, y) => x - y)
    for (let i = 1; i < sorted.length; i++) {
      expect(ageKey(sorted[i])).toBeGreaterThanOrEqual(ageKey(sorted[i - 1]))
    }
  })
})
