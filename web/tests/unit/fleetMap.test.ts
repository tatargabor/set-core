/**
 * The relation map as a pure function: what is drawn, what is marked, what is
 * left out and said to be left out, and what an unreadable source looks like.
 */
import { describe, expect, it } from 'vitest'

import {
  GROUPS_PER_ROW, GROUP_W, LANE_STEP, agentId, labelPoint, layoutMap, openerSummary, projectId, routeEdge, routePath,
  type MapAgent, type MapPayload, type MapRelation, type Point,
} from '../../src/lib/fleetMap'

const OK = { inventory: true, mandates: true, bus: true, roles: 'ok' }

function agent(pid: number, over: Partial<MapAgent> = {}): MapAgent {
  return {
    pid, label: `agent-${pid}`, seat: `p#${pid}`, state: 'quiet', population: 'started-here',
    mandate: null, mandate_absent: { reason: 'not-declared' }, ...over,
  }
}

function payload(over: Partial<MapPayload> = {}): MapPayload {
  return {
    projects: [], relations: [], counts: { no_mandate: 0, waiting: 0, failed: 0 },
    sources: { ...OK }, ...over,
  }
}

const mandate = { id: 'm-1', kind: 'work', goal: 'ship the importer', delivered: true }

function engagement(over: Partial<Extract<MapRelation, { type: 'engagement' }>> = {}): MapRelation {
  return {
    type: 'engagement', id: 'e-1', from_seat: 'alpha#1', from_pid: 1, to_project: 'beta',
    to_seat: 'beta#9', to_pid: 9, kind: 'REQUEST', subject: 'the export format',
    state: 'open', reason: null, age_seconds: 120, waiting: false, ...over,
  }
}

const TWO = [
  { name: 'alpha', archived: false, expanded: true, agents: [agent(1, { seat: 'alpha#1', mandate, mandate_absent: null })] },
  { name: 'beta', archived: false, expanded: true, agents: [agent(9, { seat: 'beta#9' })] },
]

describe('nodes', () => {
  it('draws an expanded project with its agents inside it', () => {
    const m = layoutMap(payload({ projects: TWO }))
    const group = m.nodes.find(n => n.id === projectId('alpha'))!
    const node = m.nodes.find(n => n.id === agentId(1))!
    expect(group.type).toBe('project')
    expect(node).toMatchObject({ type: 'agent', badge: 'work', goal: 'ship the importer', noMandate: false })
    // Inside the group's box.
    expect(node.x).toBeGreaterThan(group.x)
    expect(node.x + node.w).toBeLessThan(group.x + group.w)
    expect(node.y + node.h).toBeLessThanOrEqual(group.y + group.h)
  })

  it('marks an agent with no mandate on its node', () => {
    const m = layoutMap(payload({ projects: TWO }))
    expect(m.nodes.find(n => n.id === agentId(9))).toMatchObject({ noMandate: true, mandateUnmeasured: false, badge: null })
  })

  /** The refuted reading: an unreadable store drawn as an agent with no mandate. */
  it('does not mark "no mandate" on an agent whose mandate could not be read', () => {
    const m = layoutMap(payload({
      projects: [{ name: 'alpha', archived: false, expanded: true,
                   agents: [agent(1, { mandate_absent: { reason: 'unmeasured' } })] }],
      sources: { ...OK, mandates: false },
    }))
    expect(m.nodes.find(n => n.id === agentId(1))).toMatchObject({ noMandate: false, mandateUnmeasured: true })
    expect(m.notices.map(n => n.key)).toContain('mandates')
  })

  it('folds every idle project into one node, and names them', () => {
    const m = layoutMap(payload({ projects: [
      ...TWO,
      { name: 'zeta', archived: false, expanded: false, agents: [] },
      { name: 'eta', archived: false, expanded: false, agents: [] },
    ] }))
    const idle = m.nodes.filter(n => n.type === 'idle')
    expect(idle).toHaveLength(1)
    expect(idle[0].type === 'idle' && idle[0].names).toEqual(['eta', 'zeta'])
    expect(m.nodes.some(n => n.id === projectId('zeta'))).toBe(false)
  })

  it('wraps expanded projects into rows', () => {
    const many = Array.from({ length: GROUPS_PER_ROW + 1 }, (_, i) => (
      { name: `p${i}`, archived: false, expanded: true, agents: [agent(100 + i)] }))
    const m = layoutMap(payload({ projects: many }))
    const groups = m.nodes.filter(n => n.type === 'project')
    expect(groups[GROUPS_PER_ROW].x).toBe(0)
    expect(groups[GROUPS_PER_ROW].y).toBeGreaterThan(groups[0].y + groups[0].h)
    // No two boxes of the same kind overlap.
    for (const a of groups) for (const b of groups) {
      if (a === b) continue
      const apart = a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y
      expect(apart).toBe(true)
    }
    expect(m.width).toBeGreaterThanOrEqual(GROUP_W)
  })

  it('gives the same boxes for the same payload', () => {
    const p = payload({ projects: TWO, relations: [engagement()] })
    expect(layoutMap(p)).toEqual(layoutMap(JSON.parse(JSON.stringify(p))))
  })
})

describe('relations', () => {
  it('draws an engagement between the asker and the desk, with state and age', () => {
    const m = layoutMap(payload({ projects: TWO, relations: [engagement()] }))
    expect(m.edges).toHaveLength(1)
    expect(m.edges[0]).toMatchObject({
      kind: 'engagement', source: agentId(1), target: agentId(9), label: 'open · 2m', marker: null,
    })
    expect(m.edges[0].detail.join('\n')).toContain('the export format')
    expect(m.edges[0].detail.join('\n')).toContain('on the bus, not here')
  })

  it('marks a waiting engagement and a failed one on the edge, with the age', () => {
    const m = layoutMap(payload({ projects: TWO, relations: [
      engagement({ id: 'e-w', waiting: true, age_seconds: 4000 }),
      engagement({ id: 'e-f', state: 'failed', reason: 'not-on-bus', age_seconds: 30 }),
    ] }))
    expect(m.edges.find(e => e.id === 'e:e-w')).toMatchObject({ marker: 'waiting', label: 'waiting · 67m' })
    const failed = m.edges.find(e => e.id === 'e:e-f')!
    expect(failed).toMatchObject({ marker: 'failed', label: 'failed · 30s' })
    expect(failed.detail.join('\n')).toContain('not-on-bus')
  })

  /** An unreadable bus must not look like an open request, or like a waiting one. */
  it('marks an unmeasured engagement as unmeasured', () => {
    const m = layoutMap(payload({
      projects: TWO, relations: [engagement({ state: 'unmeasured', waiting: false })],
      sources: { ...OK, bus: false },
    }))
    expect(m.edges[0]).toMatchObject({ marker: 'unmeasured' })
    expect(m.edges[0].label).toMatch(/^unmeasured/)
    expect(m.edges[0].detail.join('\n')).toContain('This is not “open”')
    expect(m.notices.find(n => n.key === 'bus')).toMatchObject({ tone: 'warn' })
  })

  it('lands an engagement on the project when the desk is not live, and draws that project small', () => {
    const m = layoutMap(payload({
      projects: [TWO[0], { name: 'beta', archived: false, expanded: false, agents: [] }],
      relations: [engagement({ state: 'failed', to_pid: null, to_seat: null })],
    }))
    expect(m.edges[0]).toMatchObject({ source: agentId(1), target: projectId('beta') })
    expect(m.nodes.find(n => n.id === projectId('beta'))).toMatchObject({ type: 'collapsed', known: true })
    // …and it is not ALSO folded into the idle node.
    expect(m.nodes.some(n => n.type === 'idle')).toBe(false)
  })

  it('still draws a request from an asker that is not on the map', () => {
    const m = layoutMap(payload({
      projects: [TWO[1]],
      relations: [engagement({ from_pid: null, from_seat: 'ghost#77' })],
    }))
    expect(m.edges[0]).toMatchObject({ source: projectId('ghost'), target: agentId(9) })
    expect(m.nodes.find(n => n.id === projectId('ghost'))).toMatchObject({ type: 'collapsed', known: false })
  })

  it('draws a start relation as a claim, and says so in words', () => {
    const m = layoutMap(payload({ projects: TWO, relations: [
      { type: 'started', from_seat: 'alpha#1', from_pid: 1, to_pid: 9, to_seat: 'beta#9', is_claim: true },
    ] }))
    expect(m.edges[0]).toMatchObject({ kind: 'started', source: agentId(1), target: agentId(9), label: 'said to have asked' })
    expect(m.edges[0].detail.join('\n')).toContain('a claim, not a measurement')
  })

  it('draws a declared flow when one end has something live, and counts the rest', () => {
    const m = layoutMap(payload({
      projects: [TWO[0],
        { name: 'beta', archived: false, expanded: false, agents: [] },
        { name: 'gamma', archived: false, expanded: false, agents: [] },
        { name: 'delta', archived: false, expanded: false, agents: [] }],
      relations: [
        { type: 'flow', from_project: 'alpha', to_project: 'beta', what: 'a new field', how: 'over the bus' },
        { type: 'flow', from_project: 'gamma', to_project: 'delta', what: 'a release', how: null },
      ],
    }))
    const flows = m.edges.filter(e => e.kind === 'flow')
    expect(flows).toHaveLength(1)
    expect(flows[0]).toMatchObject({ source: projectId('alpha'), target: projectId('beta'), label: 'a new field' })
    expect(flows[0].detail.join('\n')).toContain('A declaration, not traffic')
    expect(m.notices.find(n => n.key === 'flows-not-drawn')!.text).toBe(
      '1 declared flow between projects with nothing live is not drawn.')
    // gamma and delta stay folded away.
    expect(m.nodes.find(n => n.type === 'idle')).toMatchObject({ names: ['delta', 'gamma'] })
  })

  it('keeps the three kinds apart', () => {
    const m = layoutMap(payload({ projects: TWO, relations: [
      engagement(),
      { type: 'started', from_seat: 'alpha#1', from_pid: 1, to_pid: 9, to_seat: 'beta#9', is_claim: true },
      { type: 'flow', from_project: 'alpha', to_project: 'beta', what: 'a new field', how: null },
    ] }))
    expect(m.edges.map(e => e.kind).sort()).toEqual(['engagement', 'flow', 'started'])
    expect(new Set(m.edges.map(e => e.id)).size).toBe(3)
  })

  it('every edge ends on a node that is drawn', () => {
    const m = layoutMap(payload({
      projects: [TWO[0], { name: 'beta', archived: false, expanded: false, agents: [] }],
      relations: [
        engagement({ to_pid: null }), engagement({ id: 'e-2', from_pid: null, from_seat: 'nowhere#1', to_pid: null }),
        { type: 'started', from_seat: 'gone#5', from_pid: null, to_pid: 1, to_seat: 'alpha#1', is_claim: true },
        { type: 'started', from_seat: 'alpha#1', from_pid: 1, to_pid: 555, to_seat: null, is_claim: true },
        { type: 'flow', from_project: 'alpha', to_project: 'unregistered', what: 'x', how: null },
      ],
    }))
    const ids = new Set(m.nodes.map(n => n.id))
    for (const e of m.edges) {
      expect(ids.has(e.source)).toBe(true)
      expect(ids.has(e.target)).toBe(true)
    }
    // The start relation to an agent that is not on the map is not drawn at all.
    expect(m.edges.some(e => e.target === agentId(555))).toBe(false)
  })
})

describe('where an edge runs', () => {
  type Seg = [Point, Point]
  const segments = (points: Point[]): Seg[] => points.slice(1).map((p, i) => [points[i], p])
  /** Does an axis-aligned segment pass through the INSIDE of a box? */
  const crosses = ([[ax, ay], [bx, by]]: Seg, b: { x: number; y: number; w: number; h: number }) => {
    const [x0, x1] = [Math.min(ax, bx), Math.max(ax, bx)]
    const [y0, y1] = [Math.min(ay, by), Math.max(ay, by)]
    return x0 < b.x + b.w && x1 > b.x && y0 < b.y + b.h && y1 > b.y
  }

  /** Nine projects in three rows, two idle ones a request ends on, and edges of every shape. */
  const WIDE = payload({
    projects: [
      ...Array.from({ length: 9 }, (_, i) => ({
        name: `p${i}`, archived: false, expanded: true,
        agents: Array.from({ length: 1 + (i % 3) }, (_, j) => agent(i * 10 + j, { seat: `p${i}#${j}` })),
      })),
      { name: 'idle-a', archived: false, expanded: false, agents: [] },
      { name: 'idle-b', archived: false, expanded: false, agents: [] },
    ],
    relations: [
      engagement({ id: 'near', from_pid: 0, from_seat: 'p0#0', to_project: 'p1', to_pid: 10 }),       // neighbours
      engagement({ id: 'far', from_pid: 20, from_seat: 'p2#0', to_project: 'p0', to_pid: 0 }),        // across a column
      engagement({ id: 'far2', from_pid: 20, from_seat: 'p2#0', to_project: 'p1', to_pid: 10 }),      // same source
      engagement({ id: 'down', from_pid: 0, from_seat: 'p0#0', to_project: 'p8', to_pid: 80 }),       // two rows down
      engagement({ id: 'up', from_pid: 81, from_seat: 'p8#1', to_project: 'p1', to_pid: 11 }),        // two rows up
      engagement({ id: 'up2', from_pid: 81, from_seat: 'p8#1', to_project: 'p0', to_pid: 0 }),        // up AND across a column
      engagement({ id: 'down2', from_pid: 0, from_seat: 'p0#0', to_project: 'p7', to_pid: 70 }),      // shares a gutter with `down`
      engagement({ id: 'dead', from_pid: 40, from_seat: 'p4#0', to_project: 'idle-a', to_pid: null }),// onto a small box
      engagement({ id: 'ghost', from_pid: null, from_seat: 'idle-b#1', to_project: 'p5', to_pid: 50 }),// out of one
      { type: 'started', from_seat: 'p5#0', from_pid: 50, to_pid: 52, to_seat: 'p5#2', is_claim: true }, // one column
      { type: 'flow', from_project: 'p3', to_project: 'p5', what: 'x', how: null },                   // group to group
    ],
  })

  /**
   * The defect this routing replaced, held as a test: a request from the third
   * column to the first ran straight across the second, over an agent's name.
   */
  it('never crosses a box it does not end in', () => {
    const m = layoutMap(WIDE)
    expect(m.edges).toHaveLength(11)
    const byId = new Map(m.nodes.map(n => [n.id, n]))
    const groupOf = (id: string) => {
      const n = byId.get(id)!
      return n.type === 'agent' ? projectId(n.project) : id
    }
    for (const e of m.edges) {
      const own = new Set([e.source, e.target, groupOf(e.source), groupOf(e.target)])
      for (const seg of segments(e.points)) {
        for (const n of m.nodes) {
          if (own.has(n.id)) continue
          expect(crosses(seg, n), `${e.id} crosses ${n.id}`).toBe(false)
        }
      }
    }
  })

  it('starts on the source box and ends on the target box', () => {
    const m = layoutMap(WIDE)
    const byId = new Map(m.nodes.map(n => [n.id, n]))
    const onEdgeOf = ([x, y]: Point, b: { x: number; y: number; w: number; h: number }) =>
      ((x === b.x || x === b.x + b.w) && y >= b.y && y <= b.y + b.h)
      || ((y === b.y || y === b.y + b.h) && x >= b.x && x <= b.x + b.w)
    for (const e of m.edges) {
      expect(onEdgeOf(e.points[0], byId.get(e.source)!), `${e.id} start`).toBe(true)
      expect(onEdgeOf(e.points[e.points.length - 1], byId.get(e.target)!), `${e.id} end`).toBe(true)
    }
  })

  it('makes only right-angle turns', () => {
    for (const e of layoutMap(WIDE).edges) {
      for (const [[ax, ay], [bx, by]] of segments(e.points)) expect(ax === bx || ay === by, e.id).toBe(true)
    }
  })

  /** Seen on the screen: two requests from one agent lay exactly on each other. */
  it('runs two edges that share a gutter beside each other, not on each other', () => {
    const m = layoutMap(WIDE)
    const down = m.edges.find(e => e.id === 'e:down')!
    const down2 = m.edges.find(e => e.id === 'e:down2')!
    // Both leave the same box on the same side and turn down the same gutter…
    expect(down.points[0][0]).toBe(down2.points[0][0])
    // …from different points of that side, so one arrowhead is not on the other's start…
    expect(down.points[0][1]).not.toBe(down2.points[0][1])
    // …and at different x, so the two vertical runs are two lines and not one.
    expect(down.points[1][0]).not.toBe(down2.points[1][0])
    expect(Math.abs(down.points[1][0] - down2.points[1][0])).toBeGreaterThanOrEqual(LANE_STEP)
  })

  it('brackets two agents of one project beside their column', () => {
    const m = layoutMap(WIDE)
    const e = m.edges.find(x => x.kind === 'started')!
    const group = m.nodes.find(n => n.id === projectId('p5'))!
    expect(e.points).toHaveLength(4)
    expect(e.points[1][0]).toBeGreaterThan(group.x + group.w)
    expect(e.points[1][0]).toBe(e.points[2][0])
  })

  it('puts the label on the route', () => {
    for (const e of layoutMap(WIDE).edges) {
      const on = segments(e.points).some(([[ax, ay], [bx, by]]) =>
        e.labelAt[0] >= Math.min(ax, bx) && e.labelAt[0] <= Math.max(ax, bx)
        && e.labelAt[1] >= Math.min(ay, by) && e.labelAt[1] <= Math.max(ay, by))
      expect(on, e.id).toBe(true)
    }
    expect(labelPoint([[0, 0], [10, 0], [10, 100]])).toEqual([10, 50])
    // Labels of edges in one corridor take different places along it.
    expect(labelPoint([[0, 0], [400, 0]], 0.2)).toEqual([80, 0])
    // …except on a short run, where off-centre means on top of a box.
    expect(labelPoint([[0, 0], [140, 0]], 0.2)).toEqual([70, 0])
    const m = layoutMap(WIDE)
    const at = m.edges.map(e => e.labelAt.join(','))
    expect(new Set(at).size).toBe(at.length)
  })

  it('draws the route as one path from the first point to the last', () => {
    const path = routePath([[0, 0], [40, 0], [40, 30], [90, 30]])
    expect(path.startsWith('M 0 0')).toBe(true)
    expect(path.endsWith('L 90 30')).toBe(true)
    expect((path.match(/Q/g) ?? []).length).toBe(2)
    expect(routePath([[0, 0]])).toBe('')
  })

  it('routes one edge the same way whatever else is drawn', () => {
    const s = { box: { x: 10, y: 30, w: 244, h: 46 }, group: { x: 0, y: 0, w: 264, h: 92 }, small: false }
    const t = { box: { x: 394, y: 30, w: 244, h: 46 }, group: { x: 384, y: 0, w: 264, h: 92 }, small: false }
    // Neighbours in one row on the middle lane: straight across.
    expect(routeEdge(s, t, 2, 92)).toEqual([[254, 53], [394, 53]])
    // Another lane: the same shape, a step apart, with its ends still on the boxes.
    const other = routeEdge(s, t, 3, 92)
    expect(other[0][0]).toBe(254)
    expect(other[other.length - 1][0]).toBe(394)
    expect(other[0][1]).not.toBe(53)
  })
})

describe('what could not be read', () => {
  it('says which source failed, in a fixed order', () => {
    const m = layoutMap(payload({ sources: { inventory: false, mandates: false, bus: false, roles: 'unreadable' } }))
    expect(m.notices.map(n => n.key)).toEqual(['inventory', 'mandates', 'bus', 'roles'])
    expect(m.notices.every(n => n.tone === 'warn')).toBe(true)
    expect(m.notices[0].text).toContain('unmeasured, not absent')
  })

  it('tells a missing role file from one with no flows from one that could not be read', () => {
    const none = layoutMap(payload({ sources: { ...OK, roles: 'none' } })).notices.find(n => n.key === 'roles')!
    const empty = layoutMap(payload()).notices.find(n => n.key === 'roles')!
    const broken = layoutMap(payload({ sources: { ...OK, roles: 'unreadable' } })).notices.find(n => n.key === 'roles')!
    expect(none).toMatchObject({ tone: 'info', text: 'No flows are declared: this machine has no role file.' })
    expect(empty).toMatchObject({ tone: 'info', text: 'No flows are declared in the role file.' })
    expect(broken.tone).toBe('warn')
    expect(new Set([none.text, empty.text, broken.text]).size).toBe(3)
  })

  it('says nothing when everything was read and a flow is declared', () => {
    const m = layoutMap(payload({ projects: TWO, relations: [
      { type: 'flow', from_project: 'alpha', to_project: 'beta', what: 'x', how: null }] }))
    expect(m.notices).toEqual([])
  })
})

describe('the opener', () => {
  it('carries both counts while the map is closed', () => {
    const s = openerSummary(payload({ counts: { no_mandate: 1, waiting: 1, failed: 2 } }), false)
    expect(s).toMatchObject({ kind: 'read', noMandate: 1, waiting: 1, failed: 2, unmeasured: false })
    expect(s.kind === 'read' && s.title).toContain('1 agent with no mandate')
    expect(s.kind === 'read' && s.title).toContain('1 request waiting')
  })

  it('says when the counts rest on something unmeasured', () => {
    const s = openerSummary(payload({ sources: { ...OK, bus: false } }), false)
    expect(s).toMatchObject({ kind: 'read', unmeasured: true })
  })

  /** A failed read must not render as "0 · 0", which is what calm looks like. */
  it('reports a failed read as unread, never as zero', () => {
    expect(openerSummary(null, true).kind).toBe('unread')
    expect(openerSummary(payload(), true).kind).toBe('unread')
    expect(openerSummary(null, false).kind).toBe('asking')
    expect(openerSummary(undefined, false).kind).toBe('asking')
  })
})
