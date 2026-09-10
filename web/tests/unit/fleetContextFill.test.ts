/**
 * What the context strip draws, and — the half that matters — what it refuses to.
 *
 * Two properties carry the weight here. An unmeasured agent must never become a
 * bar, because an empty bar is a confident claim that the agent holds nothing.
 * And the cap must never hide a fuller agent than it shows, because that is
 * exactly the place a filling agent sits while the header looks calm.
 */

import { describe, expect, it } from 'vitest'

import {
  MAX_MARKS, agentLabel, contextStrip, markTitle, overflowTitle, unmeasuredTitle,
  type ContextAgent,
} from '../../src/lib/fleetContextFill'

function agent(pid: number, fill: number | null, extra: Partial<ContextAgent> = {}): ContextAgent {
  return {
    pid,
    name: `agent-${pid}`,
    context: fill === null
      ? { state: 'unmeasured', reason: 'no context record' }
      : {
          state: 'measured', fill, tokens: Math.round(fill * 272000),
          window: 272000, model: 'gpt-6-astra',
          band: fill >= 0.9 ? 'critical' : fill >= 0.7 ? 'warning' : 'normal',
        },
    ...extra,
  }
}

describe('contextStrip — what is drawn', () => {
  it('draws one mark per measured agent', () => {
    const s = contextStrip([agent(1, 0.2), agent(2, 0.5)])
    expect(s.marks).toHaveLength(2)
    expect(s.total).toBe(2)
    expect(s.unmeasured).toBe(0)
  })

  it('draws nothing at all for an empty fleet', () => {
    const s = contextStrip([])
    expect(s.marks).toHaveLength(0)
    expect(s.overflow).toBe(0)
    expect(s.unmeasured).toBe(0)
  })

  it('tolerates null and undefined rather than throwing at the header', () => {
    expect(contextStrip(null).marks).toHaveLength(0)
    expect(contextStrip(undefined).total).toBe(0)
  })
})

describe('contextStrip — unmeasured is never a bar', () => {
  it('counts an unmeasured agent instead of drawing it', () => {
    const s = contextStrip([agent(1, null), agent(2, 0.4)])
    expect(s.unmeasured).toBe(1)
    expect(s.marks).toHaveLength(1)
    expect(s.marks.every(m => m.kind === 'measured')).toBe(true)
  })

  it.each([
    ['no context block at all', undefined],
    ['an explicitly null context', null],
    ['a measured state carrying no fill', { state: 'measured' as const }],
  ])('treats %s as unmeasured, not as zero', (_label, context) => {
    const s = contextStrip([{ pid: 7, name: 'a', context: context as never }])
    expect(s.unmeasured).toBe(1)
    expect(s.marks).toHaveLength(0)
  })

  it('never silently drops an unmeasured agent from the total', () => {
    const s = contextStrip([agent(1, null), agent(2, null), agent(3, 0.1)])
    expect(s.unmeasured + s.marks.length + s.overflow).toBe(s.total)
  })
})

describe('contextStrip — the cap may not hide a fuller agent', () => {
  it('draws the fullest first', () => {
    const s = contextStrip([agent(1, 0.1), agent(2, 0.9), agent(3, 0.5)])
    expect(s.marks.map(m => m.fill)).toEqual([0.9, 0.5, 0.1])
  })

  it('reports the remainder rather than dropping it', () => {
    const many = Array.from({ length: MAX_MARKS + 4 }, (_, i) => agent(i + 1, i / 100))
    const s = contextStrip(many)
    expect(s.marks).toHaveLength(MAX_MARKS)
    expect(s.overflow).toBe(4)
  })

  it('THE PROPERTY: no hidden agent is fuller than any drawn one', () => {
    // Deliberately shuffled and larger than the cap — asserting the invariant
    // over the whole population, not one arranged example.
    const fills = [0.42, 0.99, 0.01, 0.77, 0.5, 0.33, 0.88, 0.12, 0.64, 0.71]
    const all = fills.map((f, i) => agent(i + 1, f))
    const s = contextStrip(all, 4)

    const drawn = s.marks.map(m => m.fill)
    const drawnPids = new Set(s.marks.map(m => m.pid))
    const hidden = all
      .filter(a => !drawnPids.has(a.pid))
      .map(a => a.context!.fill!)

    expect(s.overflow).toBe(hidden.length)
    for (const h of hidden) {
      for (const d of drawn) expect(h).toBeLessThanOrEqual(d)
    }
  })

  it('a cap of zero draws nothing and counts everything', () => {
    const s = contextStrip([agent(1, 0.5), agent(2, 0.2)], 0)
    expect(s.marks).toHaveLength(0)
    expect(s.overflow).toBe(2)
  })
})

describe('contextStrip — over its window', () => {
  it('flags rather than silently clamping, and clamps only the drawn width', () => {
    const s = contextStrip([agent(1, 1.3)])
    expect(s.marks[0]).toMatchObject({ kind: 'measured', over: true })
    expect(s.marks[0].kind === 'measured' && s.marks[0].fill).toBeGreaterThan(1)
    expect(s.marks[0].kind === 'measured' && s.marks[0].drawn).toBe(1)
  })
})

describe('identity and labels', () => {
  it('keys on pid, so two unnamed agents stay two agents', () => {
    const s = contextStrip([
      { pid: 11, name: null, context: agent(1, 0.3).context },
      { pid: 12, name: null, context: agent(2, 0.4).context },
    ])
    expect(s.marks).toHaveLength(2)
    expect(new Set(s.marks.map(m => m.pid)).size).toBe(2)
  })

  it('names an unnamed agent by pid rather than by an empty label', () => {
    expect(agentLabel({ pid: 99, name: null })).toBe('pid 99')
    expect(agentLabel({ pid: 99, name: '   ' })).toBe('pid 99')
    expect(agentLabel({ pid: 99, name: 'worker' })).toBe('worker')
  })
})

describe('the descriptions say what the figure is', () => {
  it('names tokens, window and model, and states it is a proxy', () => {
    const t = markTitle('agent-1', {
      state: 'measured', tokens: 212000, window: 272000, fill: 0.7794,
      model: 'gpt-6-astra', band: 'warning',
    })
    expect(t).toContain('212,000')
    expect(t).toContain('272,000')
    expect(t).toContain('78%')
    expect(t).toContain('gpt-6-astra')
    expect(t).toMatch(/proxy/i)
  })

  it('says why an unmeasured agent has no bar', () => {
    const t = unmeasuredTitle('agent-2', { state: 'unmeasured', reason: 'no cache record' })
    expect(t).toContain('no cache record')
    expect(t).toMatch(/not the same as nothing consumed/i)
  })

  it('the overflow sentence promises the hidden ones are emptier', () => {
    expect(overflowTitle(3)).toMatch(/fullest/i)
    expect(overflowTitle(3)).toMatch(/emptier/i)
  })
})
