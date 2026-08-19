import { describe, expect, it } from 'vitest'

import { capabilityStanding, extraSources, toneOf } from '../../src/lib/fleetCapabilityMarks'

describe('task 7.9 — a project reports what it has wired in, and dim is not absent', () => {
  it('keeps not-connected and unknown apart, because they invite opposite actions', () => {
    const s = capabilityStanding({
      capabilities: [
        { name: 'a', state: 'connected' },
        { name: 'b', state: 'not-connected' },
        { name: 'c', state: 'unknown' },
      ],
    })
    expect(s.kind).toBe('marks')
    if (s.kind !== 'marks') return
    expect(s.marks.map(m => m.tone)).toEqual(['connected', 'not-connected', 'unknown'])
    // Counted separately: "not wired in" invites wiring it in, "unknown" does not,
    // and one number covering both is the collapse the requirement forbids.
    expect(s.notConnected).toBe(1)
    expect(s.unknown).toBe(1)
  })

  it('says NOT MEASURED rather than drawing an empty strip', () => {
    // The failure this guards is a gap rendered as a zero: an absent report and a
    // project with nothing installed both arrive as "nothing to draw", and an
    // empty strip claims the second when it might be the first.
    expect(capabilityStanding(null).kind).toBe('unmeasured')
    expect(capabilityStanding(undefined).kind).toBe('unmeasured')
    expect(capabilityStanding({ unreadable: 'the ledger could not be read' }).kind).toBe('unmeasured')
    expect(capabilityStanding({}).kind).toBe('unmeasured')
  })

  it('distinguishes MEASURED-and-empty from never measured', () => {
    expect(capabilityStanding({ capabilities: [] }).kind).toBe('none')
  })

  it('reads an unrecognised state as unknown, never as connected', () => {
    // The fail direction decides this one. A state this screen does not know,
    // drawn as connected, silently stops offering a capability the project could
    // have — which is exactly the collapse the requirement is about.
    expect(toneOf('half-installed')).toBe('unknown')
    expect(toneOf('')).toBe('unknown')
    expect(toneOf('connected')).toBe('connected')
  })

  it("carries the producer's own reason into the hover sentence", () => {
    const s = capabilityStanding({
      capabilities: [{ name: 'core', state: 'partial', present: 4, total: 10, reason: 'present without an install record' }],
    })
    if (s.kind !== 'marks') throw new Error('expected marks')
    expect(s.marks[0].title).toContain('4/10 file(s)')
    expect(s.marks[0].title).toContain('present without an install record')
  })

  it('does not invent a reason where the producer gave none', () => {
    const s = capabilityStanding({ capabilities: [{ name: 'core', state: 'not-connected', reason: null }] })
    if (s.kind !== 'marks') throw new Error('expected marks')
    expect(s.marks[0].title).toBe('core: not connected')
  })
})

describe('AC-8 — a project known to more than one source names each of them', () => {
  it('names every source when there is more than one', () => {
    expect(extraSources(['registry', 'messaging', 'process']))
      .toEqual(['registry', 'messaging', 'process'])
  })

  it('says nothing when only one source knew about it', () => {
    // The criterion is about MORE THAN ONE, and a badge on every row is noise
    // that hides the rows where the union actually said something.
    expect(extraSources(['registry'])).toEqual([])
    expect(extraSources([])).toEqual([])
    expect(extraSources(undefined)).toEqual([])
  })

  it('does not let a repeated source look like two', () => {
    expect(extraSources(['registry', 'registry'])).toEqual([])
  })
})

describe('the short source names are readable, not sliced', () => {
  it('gives each known source a name a reader can expand', async () => {
    const { shortSource } = await import('../../src/lib/fleetCapabilityMarks')
    expect(shortSource('messaging')).toBe('msg')   // `slice(0,3)` gave `mes`
    expect(shortSource('registry')).toBe('reg')
    expect(shortSource('process')).toBe('live')
  })

  it('still names a source it does not recognise', async () => {
    // Dropping it would hide exactly the case worth seeing: a source this
    // screen has never heard of.
    const { shortSource } = await import('../../src/lib/fleetCapabilityMarks')
    expect(shortSource('something-new')).toBe('some')
  })
})
