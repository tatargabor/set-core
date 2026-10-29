/** `/?agent=<session id>` — the Now card's Go there lands on the fleet (fleet-now-card 4.4). */
import { describe, expect, it } from 'vitest'
import { agentHref, agentParam, stripAgentParam } from '../../src/lib/fleetFocusParam'

describe('agent focus parameter', () => {
  it('reads the session id, and nothing when absent or blank', () => {
    expect(agentParam('?agent=abc-123')).toBe('abc-123')
    expect(agentParam('?x=1')).toBeNull()
    expect(agentParam('?agent=%20')).toBeNull()
  })

  it('is removed after use, keeping every other parameter', () => {
    expect(stripAgentParam('http://h:7400/?agent=abc&x=1#t')).toBe('/?x=1#t')
    expect(stripAgentParam('http://h:7400/?agent=abc')).toBe('/')
  })

  it('round-trips through the href the card builds', () => {
    expect(agentParam(agentHref('a b')!.slice(1))).toBe('a b')
  })
})
