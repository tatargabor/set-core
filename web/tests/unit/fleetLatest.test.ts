/**
 * fleet-latest-mode §2 — which agents the mode shows, and in what order. Pure
 * functions, so the ranking is measured without a screen: an `update` that
 * kept the first order would pass every "is the set right" check and still
 * show the tabs in the order they were first opened.
 */
import { describe, expect, it } from 'vitest'

import {
  allAgents, clampCount, initial, LATEST_VIEW_KEY, latestProject, rootOfAgent, update, stepTab, tabSwitchDirection,
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

describe('the order follows recency', () => {
  // The user reversed stable slots on 2026-10-23: the order is re-ranked on
  // every poll. What keeps a click safe is the page's pointer hold, measured in
  // fleetLatestMode.test.tsx — not this function.
  const four = [agent(1, 10), agent(2, 20), agent(3, 30), agent(4, 40)]

  it('typing into a shown agent moves it first', () => {
    const slots = initial(four, 4)
    // Agent 3 is now the most recent of all.
    expect(update(slots, [agent(1, 15), agent(2, 25), agent(3, 0), agent(4, 45)], 4)).toEqual([3, 1, 2, 4])
  })

  it('an unchanged order is the same array, so state holding it does not re-render', () => {
    const slots = initial(four, 4)
    expect(update(slots, [agent(1, 11), agent(2, 21), agent(3, 31), agent(4, 41)], 4)).toBe(slots)
  })

  it('a newcomer enters at its rank and the least recent leaves', () => {
    expect(update(initial(four, 4), [...four, agent(9, 0)], 4)).toEqual([9, 1, 2, 3])
  })

  it('a departed agent is replaced by the next most recent', () => {
    const slots = initial(four, 3) // [1, 2, 3]
    expect(update(slots, [agent(1, 10), agent(3, 30), agent(4, 40)], 3)).toEqual([1, 3, 4])
  })

  it('a departed agent with nobody to replace it leaves no empty slot', () => {
    expect(update([1, 2], [agent(1, 10)], 5)).toEqual([1])
  })

  it('a smaller count keeps the most recent', () => {
    expect(update([4, 1, 2, 3], four, 2)).toEqual([1, 2])
  })

  it('a larger count lets the next most recent in', () => {
    expect(update([1, 2], four, 3)).toEqual([1, 2, 3])
  })

  it('unmeasured agents come after every measured one', () => {
    const now = [agent(1, 50), agent(2, 5), agent(3, null), agent(4, 1)]
    expect(update([], now, 4)).toEqual([4, 2, 1, 3])
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

describe('the Ctrl+←/→ tab switch', () => {
  const k = (over: Partial<KeyboardEvent>) =>
    ({ key: 'x', ctrlKey: false, altKey: false, shiftKey: false, metaKey: false, ...over }) as KeyboardEvent

  it('is plain Ctrl with an arrow, and nothing else', () => {
    expect(tabSwitchDirection(k({ ctrlKey: true, key: 'ArrowLeft' }))).toBe(-1)
    expect(tabSwitchDirection(k({ ctrlKey: true, key: 'ArrowRight' }))).toBe(1)
    expect(tabSwitchDirection(k({ key: 'ArrowRight' }))).toBe(0)
    expect(tabSwitchDirection(k({ ctrlKey: true, shiftKey: true, key: 'ArrowRight' }))).toBe(0)
    expect(tabSwitchDirection(k({ ctrlKey: true, altKey: true, key: 'ArrowRight' }))).toBe(0)
    expect(tabSwitchDirection(k({ ctrlKey: true, metaKey: true, key: 'ArrowRight' }))).toBe(0)
    expect(tabSwitchDirection(k({ ctrlKey: true, key: 'ArrowUp' }))).toBe(0)
  })

  it('steps to the neighbour and wraps at both ends', () => {
    const at = (i: number, n = 3) => Array.from({ length: n }, (_, j) => ({ active: j === i }))
    expect(stepTab(at(0), 1)).toBe(1)
    expect(stepTab(at(2), 1)).toBe(0)
    expect(stepTab(at(0), -1)).toBe(2)
    expect(stepTab(at(1), -1)).toBe(0)
  })

  it('with no active tab takes the first or the last; with nothing to switch to, nothing', () => {
    const none = [{ active: false }, { active: false }, { active: false }]
    expect(stepTab(none, 1)).toBe(0)
    expect(stepTab(none, -1)).toBe(2)
    expect(stepTab([], 1)).toBeNull()
    expect(stepTab([{ active: true }], 1)).toBeNull()
  })
})
