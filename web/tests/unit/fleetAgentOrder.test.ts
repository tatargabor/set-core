/**
 * The hand-made agent order — every rule here is one about the reader's
 * arrangement rewriting itself, and every one of them fails silently.
 *
 * Asked for 2026-08-26: *"a tabokat akarom tudni húzva rendezni felül és a
 * sorrendet mentve kialakítani … a gridben is"*. What makes that a feature
 * rather than a sort call is what happens around it: agents restart with new
 * pids, agents stop and come back, new ones appear, and none of that may move
 * what the reader placed.
 */
import { describe, expect, it } from 'vitest'

import { agentKey, moveKey, orderAgents } from '../../src/lib/fleetAgentOrder'

type A = { terminal_label: string | null; name: string | null; pid: number }
const agent = (over: Partial<A>): A => ({ terminal_label: null, name: null, pid: 0, ...over })

describe('what an agent is called in a stored order', () => {
  it('prefers the terminal label — the identity the layout already uses', () => {
    expect(agentKey(agent({ terminal_label: 'proj-one', name: 'other', pid: 7 }))).toBe('proj-one')
  })

  it('falls back to the name, then to a PREFIXED pid', () => {
    expect(agentKey(agent({ name: 'proj-two', pid: 7 }))).toBe('proj-two')
    expect(agentKey(agent({ pid: 7 }))).toBe('pid:7')
  })

  it('cannot collide a pid with a numeric label', () => {
    // Without the prefix these two agents would share a key, and sharing a key
    // silently swaps two agents' places.
    expect(agentKey(agent({ terminal_label: '7', pid: 9 })))
      .not.toBe(agentKey(agent({ pid: 7 })))
  })

  it('treats a blank label or name as absent', () => {
    expect(agentKey(agent({ terminal_label: '  ', name: '', pid: 3 }))).toBe('pid:3')
  })
})

describe('a stored order meeting a live inventory', () => {
  const a = agent({ terminal_label: 'a', pid: 1 })
  const b = agent({ terminal_label: 'b', pid: 2 })
  const c = agent({ terminal_label: 'c', pid: 3 })

  it('puts the named agents in the stored sequence', () => {
    expect(orderAgents([a, b, c], ['c', 'a', 'b']).map(x => x.terminal_label))
      .toEqual(['c', 'a', 'b'])
  })

  it('survives a restart — same keys, new pids', () => {
    // The reason the key is not the pid. These are the same agents, restarted.
    const restarted = [
      agent({ terminal_label: 'a', pid: 101 }),
      agent({ terminal_label: 'b', pid: 102 }),
      agent({ terminal_label: 'c', pid: 103 }),
    ]
    expect(orderAgents(restarted, ['c', 'a', 'b']).map(x => x.terminal_label))
      .toEqual(['c', 'a', 'b'])
  })

  it('shows an agent the order does not name LAST, in discovery order', () => {
    const fresh = agent({ terminal_label: 'new', pid: 4 })
    expect(orderAgents([a, fresh, b, c], ['c', 'a', 'b']).map(x => x.terminal_label))
      .toEqual(['c', 'a', 'b', 'new'])
  })

  it('skips a stored key whose agent is not running', () => {
    expect(orderAgents([a, c], ['c', 'b', 'a']).map(x => x.terminal_label)).toEqual(['c', 'a'])
  })

  it('returns discovery order untouched when there is no stored order', () => {
    expect(orderAgents([a, b, c], undefined).map(x => x.terminal_label)).toEqual(['a', 'b', 'c'])
    expect(orderAgents([a, b, c], []).map(x => x.terminal_label)).toEqual(['a', 'b', 'c'])
  })
})

describe('the stored list after a move', () => {
  const a = agent({ terminal_label: 'a', pid: 1 })
  const b = agent({ terminal_label: 'b', pid: 2 })
  const c = agent({ terminal_label: 'c', pid: 3 })

  it('moves the agent and returns the whole list', () => {
    expect(moveKey([a, b, c], ['a', 'b', 'c'], 0, 2)).toEqual(['b', 'c', 'a'])
    expect(moveKey([a, b, c], ['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b'])
  })

  it('KEEPS a key whose agent is not running, between the same neighbours', () => {
    // The rule the whole store exists for. `gone` sits between `a` and `c`; the
    // reader, who cannot see it, swaps the two agents they can see. `gone` must
    // not be dropped, and must not be pushed to the end.
    expect(moveKey([a, c], ['a', 'gone', 'c'], 0, 1)).toEqual(['c', 'gone', 'a'])
  })

  it('adopts an agent the stored list never knew about', () => {
    const fresh = agent({ terminal_label: 'new', pid: 4 })
    // Rendered order is what the reader sees: the unnamed one is already last.
    expect(moveKey([a, b, fresh], ['a', 'b'], 2, 0)).toEqual(['new', 'a', 'b'])
  })

  it('is a no-op for a move that goes nowhere, but still returns a full list', () => {
    // A press-and-release must not rewrite the arrangement, and an out-of-range
    // index must not either — both used to be the same defect on the project
    // column, where one click moved a row six positions and saved it.
    expect(moveKey([a, b, c], ['a', 'b', 'c'], 1, 1)).toEqual(['a', 'b', 'c'])
    expect(moveKey([a, b, c], ['a', 'b', 'c'], -1, 2)).toEqual(['a', 'b', 'c'])
    expect(moveKey([a, b, c], ['a', 'b', 'c'], 0, 9)).toEqual(['a', 'b', 'c'])
  })

  it('builds a list from nothing when none was stored', () => {
    expect(moveKey([a, b, c], undefined, 2, 0)).toEqual(['c', 'a', 'b'])
  })
})
