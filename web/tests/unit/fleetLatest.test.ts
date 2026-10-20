/**
 * fleet-latest-mode §2 — which agents the mode shows, and that nothing moves
 * under the reader's hand. Pure functions, so the stability rule is measured
 * without a screen: an `update` that re-sorted would pass every "is the set
 * right" check and still move tile 3 the moment the reader typed into it.
 */
import { describe, expect, it } from 'vitest'

import {
  allAgents, clampCount, initial, LATEST_VIEW_KEY, latestProject, resort, rootOfAgent, update,
} from '../../src/lib/fleetLatest'
import type { FleetAgent, FleetProject } from '../../src/lib/fleetTypes'

function agent(pid: number, recency: number | null, project = 'p'): FleetAgent {
  return {
    pid, name: `a${pid}`, project, branch: null, session_id: null, binding_confirmed: true,
    sources: [], kind: 'interactive', state: 'quiet',
    last_movement_seconds: 1, last_human_input_seconds: recency,
  } as unknown as FleetAgent
}

describe('the selection', () => {
  it('honours N — 5 of 12', () => {
    const agents = Array.from({ length: 12 }, (_, i) => agent(i + 1, i * 10))
    expect(initial(agents, 5)).toEqual([1, 2, 3, 4, 5])
  })

  it('draws no empty slots when fewer agents exist than N', () => {
    expect(initial([agent(1, 5), agent(2, 1)], 10)).toEqual([2, 1])
  })

  it('places unmeasured agents after every measured one', () => {
    const agents = [agent(1, null), agent(2, 9000), agent(3, 5)]
    expect(initial(agents, 10)).toEqual([3, 2, 1])
  })

  it('crosses projects', () => {
    const projects = [
      { name: 'p', root: '/p', sources: [], archived: false, agents: [agent(1, 3, 'p')] },
      { name: 'q', root: '/q', sources: [], archived: false, agents: [agent(2, 1, 'q')] },
      { name: 'r', root: '/r', sources: [], archived: false, agents: [agent(3, 2, 'r')] },
    ] as FleetProject[]
    expect(initial(allAgents(projects), 10)).toEqual([2, 3, 1])
  })
})

describe('the placement is stable', () => {
  const four = [agent(1, 10), agent(2, 20), agent(3, 30), agent(4, 40)]

  it('typing into a shown agent moves nothing', () => {
    const slots = initial(four, 4)
    // Agent 3 is now the most recent of all.
    const after = update(slots, [agent(1, 15), agent(2, 25), agent(3, 0), agent(4, 45)], 4)
    expect(after).toEqual([1, 2, 3, 4])
    // And it is the same array, so state holding it does not re-render.
    expect(after).toBe(slots)
  })

  it('a newcomer takes the slot of the oldest shown agent, and only that one', () => {
    const slots = initial(four, 4)
    const after = update(slots, [...four, agent(9, 0)], 4)
    expect(after).toEqual([1, 2, 3, 9])
  })

  it('the oldest is the one replaced even when it is not last', () => {
    const slots = [4, 1, 2, 3]
    expect(update(slots, [...four, agent(9, 0)], 4)).toEqual([9, 1, 2, 3])
  })

  it('a departed agent frees its slot for the next entrant', () => {
    const slots = initial(four, 3) // [1, 2, 3]
    const after = update(slots, [agent(1, 10), agent(3, 30), agent(4, 40)], 3)
    expect(after).toEqual([1, 4, 3])
  })

  it('a departed agent with nobody to replace it leaves no empty slot', () => {
    expect(update([1, 2], [agent(1, 10)], 5)).toEqual([1])
  })

  it('a smaller count drops the oldest shown agents', () => {
    expect(update([4, 1, 2, 3], four, 2)).toEqual([1, 2])
  })

  it('a larger count lets the next most recent in', () => {
    expect(update([1, 2], four, 3)).toEqual([1, 2, 3])
  })

  it('re-sort orders most recent first', () => {
    const now = [agent(1, 50), agent(2, 5), agent(3, null), agent(4, 1)]
    expect(resort(now, 4)).toEqual([4, 2, 1, 3])
  })
})

describe('the mode as a project', () => {
  it('has no root, so nothing can resolve against a wrong tree', () => {
    const p = latestProject([agent(1, 1)])
    expect(p.root).toBe('')
    expect(p.name).toBe(LATEST_VIEW_KEY)
  })

  it('uses a key no directory name can produce', () => {
    expect(LATEST_VIEW_KEY).toContain('/')
  })

  it("a tile's root is its own agent's", () => {
    const q = { ...agent(2, 1, 'q'), project_root: '/home/x/q' }
    expect(rootOfAgent(q, [])).toBe('/home/x/q')
    const listed = [{ name: 'q', root: '/listed/q', sources: [], archived: false, agents: [agent(2, 1, 'q')] }] as FleetProject[]
    expect(rootOfAgent(agent(2, 1, 'q'), listed)).toBe('/listed/q')
    expect(rootOfAgent(agent(7, 1, 'nowhere'), listed)).toBeNull()
  })

  it('clamps the count and refuses garbage', () => {
    expect(clampCount(0)).toBe(1)
    expect(clampCount(500)).toBe(50)
    expect(clampCount('x')).toBe(10)
    expect(clampCount('7')).toBe(7)
  })
})
