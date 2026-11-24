import { describe, expect, it } from 'vitest'

import { hereState, offAgentRows, parseAutoAnswerState } from '../../src/lib/fleetAutoAnswer'

describe('fleet-auto-answer-session-off helpers', () => {
  it('reads the opt-out list and drops anything that is not label:/session:', () => {
    const s = parseAutoAnswerState({ enabled: true, pending: [], off_agents: ['label:planner', 'session:47f1', 'x', 3] })!
    expect(s.off_agents).toEqual(['label:planner', 'session:47f1'])
    expect(parseAutoAnswerState({ enabled: true, pending: [] })!.off_agents).toEqual([])
  })

  it('says off for an opted-out terminal, on otherwise, and machine-off when the switch is off', () => {
    expect(hereState('planner', ['label:planner'], true)).toBe('off')
    expect(hereState('planner', ['label:planner'], false)).toBe('off')
    expect(hereState('other', ['label:planner'], true)).toBe('on')
    expect(hereState('other', [], false)).toBe('machine-off')
    expect(hereState(null, ['label:planner'], true)).toBe('on')
  })

  it('lists entries by what they name', () => {
    expect(offAgentRows(['label:planner', 'session:47f1763f-c5c5'])).toEqual([
      { entry: 'label:planner', name: 'planner', kind: 'terminal' },
      { entry: 'session:47f1763f-c5c5', name: '47f1763f', kind: 'session' },
    ])
  })
})
