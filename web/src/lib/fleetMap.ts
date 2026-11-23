/**
 * The relation map — projects, the agents in them, and what connects them — as
 * a pure function from the payload to things to draw.
 *
 * `GET /api/fleet/map` already decided what is true; this file decides what is
 * DRAWN, and four of those decisions are the content:
 *
 *  - **Three relation kinds, never alike.** An engagement is a request one
 *    agent sent to a project's desk and its state; a start relation is who the
 *    start request SAID was asking (a claim); a flow is a relation somebody
 *    declared between two projects. They differ in `kind`, and the view gives
 *    each kind its own stroke.
 *  - **Compact, and it says what it left out.** A machine has dozens of
 *    registered projects and a handful with anything live. Idle projects are
 *    one node, and a declared flow between two idle projects is counted, not
 *    drawn — a map of every registration would bury the few that matter.
 *  - **What is wrong is marked where it is.** An agent with no mandate is
 *    marked on its node; an engagement that is waiting or failed is marked on
 *    its edge with its age; both counts ride on the control that opens the map.
 *  - **A source that could not be read is unmeasured, not empty.** The notices
 *    say which, in a fixed order, so "no engagements" is never what an
 *    unreadable bus looks like.
 *
 * Nothing here takes the reader's selection as an input. That is deliberate:
 * opening a detail cannot move a node if the layout does not know a detail is
 * open.
 */

import { age } from './fleetAge'
import { mandateDescription, NOT_DECLARED_TITLE, NOT_STARTED_HERE_TITLE, UNMEASURED_TITLE } from './fleetMandate'
import type { FleetMandate, FleetMandateAbsent } from './fleetTypes'

// --------------------------------------------------------------------------- //
// The payload
// --------------------------------------------------------------------------- //

export interface MapAgent {
  pid: number | null
  label: string | null
  seat: string | null
  state: string | null
  population: string | null
  mandate: FleetMandate | null
  mandate_absent: FleetMandateAbsent | null
  /** Optional: a server older than the field sends none, which is not "main". */
  branch?: string | null
  /** Set only when the agent runs OUTSIDE the project's main tree. */
  worktree?: { name: string | null; branch: string | null; unlisted?: boolean } | null
  /** Copied from the listing row: `state` is `measured` only when fill/window exist. */
  context?: { state?: string; fill?: number; band?: string; tokens?: number; window?: number; model?: string } | null
  cache?: { cold?: boolean; rewrite_usd?: number; seconds_remaining?: number } | null
}

export interface MapProject {
  name: string
  archived: boolean
  agents: MapAgent[]
  expanded: boolean
}

export interface EngagementRelation {
  type: 'engagement'
  id: string
  from_seat: string | null
  from_pid: number | null
  to_project: string
  to_seat: string | null
  to_pid: number | null
  kind: string
  subject: string | null
  state: 'resolving' | 'open' | 'failed' | 'unmeasured' | string
  reason: string | null
  age_seconds: number | null
  waiting: boolean
}

export interface StartedRelation {
  type: 'started'
  from_seat: string
  from_pid: number | null
  to_pid: number | null
  to_seat: string | null
  is_claim: boolean
}

export interface FlowRelation {
  type: 'flow'
  from_project: string
  to_project: string
  what: string
  how: string | null
}

export type MapRelation = EngagementRelation | StartedRelation | FlowRelation

export interface MapPayload {
  projects: MapProject[]
  relations: MapRelation[]
  counts: { no_mandate: number; waiting: number; failed: number }
  sources: { inventory: boolean; mandates: boolean; bus: boolean; roles: 'ok' | 'none' | 'unreadable' | string }
  generated_at?: number
}

// --------------------------------------------------------------------------- //
// What is drawn
// --------------------------------------------------------------------------- //

export interface Box { x: number; y: number; w: number; h: number }

export type MapNode = Box & (
  | { id: string; type: 'project'; name: string; agents: number }
  | {
      id: string
      type: 'agent'
      label: string
      project: string
      state: string | null
      /** `work` / `desk`, or null when there is no mandate to name. */
      badge: string | null
      goal: string | null
      /** Measured: this agent has no mandate. The node carries the marker. */
      noMandate: boolean
      /** The store could not be read — which is not "no mandate". */
      mandateUnmeasured: boolean
      /** The worktree's name when the agent runs outside the main tree; '?' when unlisted. */
      worktree: string | null
      /** Context fill 0..1, only when measured — null is "not measured", never empty. */
      fill: number | null
      band: string | null
      detail: string[]
    }
  /** A project with nothing live, drawn only because a relation ends on it. */
  | { id: string; type: 'collapsed'; name: string; known: boolean }
  /** Every other idle project, as one node. */
  | { id: string; type: 'idle'; names: string[] }
)

export type EdgeMarker = 'waiting' | 'failed' | 'unmeasured' | null

export type Point = [number, number]

export interface MapEdge {
  id: string
  source: string
  target: string
  /**
   * The route, corner by corner. It runs in the gaps BETWEEN boxes — the
   * gutters beside the columns and the corridors between the rows — so it
   * never crosses a project it does not end in.
   */
  points: Point[]
  /** Where the label sits: the middle of the route's longest run. */
  labelAt: Point
  kind: 'engagement' | 'started' | 'flow'
  label: string
  /** Set only on an engagement that needs the reader: the edge is marked. */
  marker: EdgeMarker
  detailTitle: string
  detail: string[]
}

export interface MapNotice { key: string; tone: 'warn' | 'info'; text: string }

export interface MapModel {
  nodes: MapNode[]
  edges: MapEdge[]
  notices: MapNotice[]
  counts: { noMandate: number; waiting: number; failed: number }
  width: number
  height: number
}

// Geometry. One place, so the view and the tests read the same numbers.
export const GROUP_W = 264
export const GROUP_HEAD = 30
export const GROUP_PAD = 10
export const AGENT_H = 46
export const AGENT_GAP = 6
export const GROUP_GAP_X = 120
export const GROUP_GAP_Y = 64
export const GROUPS_PER_ROW = 3
export const SMALL_W = 176
export const SMALL_H = 30
export const SMALL_GAP = 20

export const projectId = (name: string) => `p:${name}`
export const agentId = (pid: number) => `a:${pid}`
const projectOfSeat = (seat: string | null | undefined) => (seat ? seat.split('#')[0] : null)

function kTokens(n: number): string {
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : `${Math.round(n / 1000)}k`
}

/** Where the agent works and what its context holds — one line each, nothing measured here. */
export function workAndUsageLines(agent: MapAgent): string[] {
  const lines: string[] = []
  const wt = agent.worktree
  if (wt) {
    lines.push(wt.unlisted
      ? `worktree: outside the project's main tree, not in its worktree list${wt.branch ? ` · branch ${wt.branch}` : ''}`
      : `worktree: ${wt.name}${wt.branch ? ` · branch ${wt.branch}` : ''}`)
  } else if (agent.branch) {
    lines.push(`branch: ${agent.branch}`)
  }
  const c = agent.context
  if (c?.state === 'measured' && typeof c.fill === 'number' && typeof c.tokens === 'number' && typeof c.window === 'number') {
    lines.push(`context: ${Math.round(c.fill * 100)}% — ${kTokens(c.tokens)} of ${kTokens(c.window)}${c.model ? ` · ${c.model}` : ''}`)
  } else if (c) {
    lines.push('context: not measured')
  }
  const k = agent.cache
  if (k && typeof k.cold === 'boolean') {
    const cost = typeof k.rewrite_usd === 'number' ? ` · rewriting it would cost ~$${k.rewrite_usd.toFixed(2)}` : ''
    lines.push(k.cold ? `cache: cold${cost}` : `cache: warm, ${Math.round((k.seconds_remaining ?? 0) / 60)} min left${cost}`)
  }
  return lines
}

function agentDetail(agent: MapAgent, project: string): string[] {
  const lines = [`project: ${project}`, `state: ${agent.state ?? 'unknown'}`, ...workAndUsageLines(agent)]
  if (agent.seat) lines.push(`bus seat: ${agent.seat}`)
  if (agent.mandate) return [...lines, ...mandateDescription(agent.mandate)]
  const reason = agent.mandate_absent?.reason
  if (reason === 'not-declared') return [...lines, 'no mandate — none declared', NOT_DECLARED_TITLE]
  if (reason === 'not-started-here') return [...lines, 'no mandate — opened by hand', NOT_STARTED_HERE_TITLE]
  return [...lines, 'mandate unmeasured', UNMEASURED_TITLE]
}

/** An end of an edge: the box it touches, the group that box sits in, and
    whether it is one of the small boxes in the bottom row. */
export interface RouteEnd { box: Box; group: Box; small: boolean }

/** How far apart two edges sharing a gutter or a corridor are drawn. */
export const LANE_STEP = 9
export const LANES = 5
/** A run shorter than this holds a label only in its middle. */
export const SHORT_RUN = 200

function simplify(points: Point[]): Point[] {
  const out: Point[] = []
  for (const p of points) {
    const last = out[out.length - 1]
    if (last && last[0] === p[0] && last[1] === p[1]) continue
    const prev = out[out.length - 2]
    // Drop a corner that is not one: three points on one line.
    if (prev && last && ((prev[0] === last[0] && last[0] === p[0]) || (prev[1] === last[1] && last[1] === p[1]))) {
      out[out.length - 1] = p
      continue
    }
    out.push(p)
  }
  return out
}

/**
 * Route one edge through the gaps between boxes.
 *
 * The first build of this drew a curve from box to box, and on the screen it
 * was unreadable: a request from the third column to the first ran straight
 * across the second, on top of an agent's name; two requests to agents in the
 * same row lay exactly on each other; and labels sat on tiles. So an edge now
 * travels only where nothing is drawn — the vertical GUTTER beside a column and
 * the horizontal CORRIDOR between two rows — and `lane` shifts it sideways so
 * edges sharing a gap run beside each other instead of on each other.
 *
 * `rowBottom` is the bottom of the tallest group in the source's row: the
 * corridor under a row starts below the tallest box in it, not below the
 * source's own.
 */
export function routeEdge(s: RouteEnd, t: RouteEnd, lane: number, rowBottom: number): Point[] {
  const off = ((lane % LANES) - Math.floor(LANES / 2)) * LANE_STEP
  // The ends are spread too, by the same lane: two edges touching one box
  // otherwise meet in one point, and the arrowhead of one sits on the start of
  // the other. The spread stays well inside the box's own edge.
  const cy = (b: Box) => b.y + b.h / 2 + Math.max(-b.h / 2 + 6, Math.min(b.h / 2 - 6, off * 0.8))
  const cx = (b: Box) => b.x + b.w / 2 + off * 2
  const rightGutter = (g: Box) => g.x + g.w + GROUP_GAP_X / 2 + off
  const leftGutter = (g: Box) => g.x - GROUP_GAP_X / 2 + off

  // Into a small box: down from the corridor above the small row, onto its top.
  if (t.small) {
    const corridor = t.box.y - GROUP_GAP_Y / 2 + off
    if (s.small) {
      return simplify([[cx(s.box), s.box.y], [cx(s.box), corridor], [cx(t.box), corridor], [cx(t.box), t.box.y]])
    }
    const gx = rightGutter(s.group)
    return simplify([
      [s.box.x + s.box.w, cy(s.box)], [gx, cy(s.box)], [gx, corridor], [cx(t.box), corridor], [cx(t.box), t.box.y],
    ])
  }
  // Out of a small box: up into that corridor, along it, then down a gutter.
  if (s.small) {
    const corridor = s.box.y - GROUP_GAP_Y / 2 + off
    const fromLeft = cx(s.box) < cx(t.group)
    const gx = fromLeft ? leftGutter(t.group) : rightGutter(t.group)
    return simplify([
      [cx(s.box), s.box.y], [cx(s.box), corridor], [gx, corridor], [gx, cy(t.box)],
      [fromLeft ? t.box.x : t.box.x + t.box.w, cy(t.box)],
    ])
  }
  // Same column: a bracket in the gutter to the right of it.
  if (s.group.x === t.group.x) {
    const gx = s.group.x + s.group.w + 12 + (lane % LANES) * LANE_STEP
    return simplify([
      [s.box.x + s.box.w, cy(s.box)], [gx, cy(s.box)], [gx, cy(t.box)], [t.box.x + t.box.w, cy(t.box)],
    ])
  }
  const toRight = t.group.x > s.group.x
  const sx = toRight ? s.box.x + s.box.w : s.box.x
  const tx = toRight ? t.box.x : t.box.x + t.box.w
  const adjacent = Math.abs(t.group.x - s.group.x) === GROUP_W + GROUP_GAP_X
  // Neighbours in one row: straight across the gutter they share.
  if (adjacent && s.group.y === t.group.y) {
    const gx = toRight ? rightGutter(s.group) : leftGutter(s.group)
    return simplify([[sx, cy(s.box)], [gx, cy(s.box)], [gx, cy(t.box)], [tx, cy(t.box)]])
  }
  // Anything further: out to the gutter, along a corridor, in from a gutter.
  const gx1 = toRight ? rightGutter(s.group) : leftGutter(s.group)
  const gx2 = toRight ? leftGutter(t.group) : rightGutter(t.group)
  const corridor = t.group.y < s.group.y
    ? s.group.y - GROUP_GAP_Y / 2 + off
    : rowBottom + GROUP_GAP_Y / 2 + off
  return simplify([[sx, cy(s.box)], [gx1, cy(s.box)], [gx1, corridor], [gx2, corridor], [gx2, cy(t.box)], [tx, cy(t.box)]])
}

/**
 * A point on the longest run of a route — where a label has most room.
 *
 * `fraction` is how far along that run. Edges sharing a corridor are a lane
 * apart, which is less than a label is tall, so labels at the same fraction
 * would sit on each other: each lane takes its own.
 */
export function labelPoint(points: Point[], fraction = 0.5): Point {
  let best: Point = points[0] ?? [0, 0]
  let longest = -1
  for (let i = 1; i < points.length; i += 1) {
    const [ax, ay] = points[i - 1]
    const [bx, by] = points[i]
    const length = Math.abs(bx - ax) + Math.abs(by - ay)
    if (length > longest) {
      longest = length
      // A short run — one gutter between two neighbours — has room for a label
      // only in its middle: off-centre it lands on the box at one end.
      const at = length < SHORT_RUN ? 0.5 : fraction
      best = [ax + (bx - ax) * at, ay + (by - ay) * at]
    }
  }
  return best
}

/** The route as an SVG path, with its corners rounded. */
export function routePath(points: Point[], radius = 7): string {
  if (points.length < 2) return ''
  let d = `M ${points[0][0]} ${points[0][1]}`
  for (let i = 1; i < points.length; i += 1) {
    const [x, y] = points[i]
    const next = points[i + 1]
    if (!next) { d += ` L ${x} ${y}`; break }
    const [px, py] = points[i - 1]
    const r = Math.min(radius, (Math.abs(x - px) + Math.abs(y - py)) / 2, (Math.abs(next[0] - x) + Math.abs(next[1] - y)) / 2)
    const inX = x - Math.sign(x - px) * r
    const inY = y - Math.sign(y - py) * r
    const outX = x + Math.sign(next[0] - x) * r
    const outY = y + Math.sign(next[1] - y) * r
    d += ` L ${inX} ${inY} Q ${x} ${y} ${outX} ${outY}`
  }
  return d
}

type RawEdge = Omit<MapEdge, 'points' | 'labelAt'>

function engagementEdge(rel: EngagementRelation, source: string, target: string): RawEdge {
  const marker: EdgeMarker = rel.state === 'failed' ? 'failed'
    : rel.state === 'unmeasured' ? 'unmeasured'
      : rel.waiting ? 'waiting' : null
  const ageText = rel.age_seconds === null || rel.age_seconds === undefined ? 'age unknown' : age(rel.age_seconds)
  const word = marker === 'waiting' ? 'waiting' : rel.state
  const detail = [
    `${rel.from_seat ?? 'an unnamed asker'} → ${rel.to_project}${rel.to_seat ? ` (desk ${rel.to_seat})` : ''}`,
    `${rel.kind}${rel.subject ? ` — ${rel.subject}` : ''}`,
    `state: ${rel.state}${rel.reason ? ` (${rel.reason})` : ''}`,
    `age: ${ageText}`,
  ]
  if (marker === 'waiting') detail.push('No linked reply has arrived within the waiting bound.')
  if (marker === 'unmeasured') {
    detail.push('The bus could not be read, so nobody checked for a reply. This is not “open”.')
  }
  detail.push('The text of the request is on the bus, not here.')
  return {
    id: `e:${rel.id}`, source, target, kind: 'engagement',
    label: `${word} · ${ageText}`, marker,
    detailTitle: `Request ${rel.id}`, detail,
  }
}

/**
 * Lay the payload out. Deterministic: the same payload gives the same boxes,
 * whatever is selected, hovered or open.
 */
export function layoutMap(payload: MapPayload): MapModel {
  const nodes: MapNode[] = []
  const raw: RawEdge[] = []
  const byName = new Map(payload.projects.map(p => [p.name, p]))
  const drawnAgents = new Set<number>()

  // 1. Expanded projects, in rows.
  const expanded = payload.projects.filter(p => p.expanded && p.agents.length > 0)
  let x = 0
  let y = 0
  let rowH = 0
  let width = 0
  expanded.forEach((project, i) => {
    if (i > 0 && i % GROUPS_PER_ROW === 0) {
      x = 0
      y += rowH + GROUP_GAP_Y
      rowH = 0
    }
    const h = GROUP_HEAD + GROUP_PAD + project.agents.length * (AGENT_H + AGENT_GAP)
    nodes.push({ id: projectId(project.name), type: 'project', name: project.name, agents: project.agents.length,
                 x, y, w: GROUP_W, h })
    project.agents.forEach((agent, j) => {
      if (agent.pid === null) return
      drawnAgents.add(agent.pid)
      const reason = agent.mandate_absent?.reason
      const unmeasured = !agent.mandate && reason !== 'not-declared' && reason !== 'not-started-here'
      nodes.push({
        id: agentId(agent.pid), type: 'agent',
        label: agent.label ?? `pid ${agent.pid}`, project: project.name, state: agent.state,
        badge: agent.mandate ? String(agent.mandate.kind) : null,
        goal: agent.mandate ? agent.mandate.goal : null,
        noMandate: !agent.mandate && !unmeasured,
        mandateUnmeasured: unmeasured,
        worktree: agent.worktree ? (agent.worktree.name ?? '?') : null,
        fill: agent.context?.state === 'measured' && typeof agent.context.fill === 'number' ? agent.context.fill : null,
        band: agent.context?.state === 'measured' ? agent.context.band ?? null : null,
        detail: agentDetail(agent, project.name),
        x: x + GROUP_PAD, y: y + GROUP_HEAD + j * (AGENT_H + AGENT_GAP),
        w: GROUP_W - 2 * GROUP_PAD, h: AGENT_H,
      })
    })
    rowH = Math.max(rowH, h)
    width = Math.max(width, x + GROUP_W)
    x += GROUP_W + GROUP_GAP_X
  })
  const expandedNames = new Set(expanded.map(p => p.name))

  // 2. Which relation ends need a small node of their own.
  const small = new Map<string, boolean>() // name -> is it a registered project
  const need = (name: string | null) => {
    if (!name || expandedNames.has(name) || small.has(name)) return
    small.set(name, byName.has(name))
  }
  const endpoint = (pid: number | null, project: string | null): string | null => {
    if (pid !== null && drawnAgents.has(pid)) return agentId(pid)
    return project ? projectId(project) : null
  }
  let flowsNotDrawn = 0
  let flows = 0
  for (const rel of payload.relations) {
    if (rel.type === 'engagement') {
      if (!(rel.from_pid !== null && drawnAgents.has(rel.from_pid))) need(projectOfSeat(rel.from_seat) ?? rel.from_seat)
      if (!(rel.to_pid !== null && drawnAgents.has(rel.to_pid))) need(rel.to_project)
    } else if (rel.type === 'started') {
      if (rel.to_pid === null || !drawnAgents.has(rel.to_pid)) continue
      if (!(rel.from_pid !== null && drawnAgents.has(rel.from_pid))) need(projectOfSeat(rel.from_seat))
    } else {
      flows += 1
      const a = expandedNames.has(rel.from_project)
      const b = expandedNames.has(rel.to_project)
      if (!a && !b) { flowsNotDrawn += 1; continue }
      need(rel.from_project)
      need(rel.to_project)
    }
  }

  // 3. The small row: relation ends first, then everything idle as one node.
  const smallY = expanded.length ? y + rowH + GROUP_GAP_Y : 0
  let sx = 0
  let sy = smallY
  const rowWidth = Math.max(width, GROUPS_PER_ROW * GROUP_W + (GROUPS_PER_ROW - 1) * GROUP_GAP_X)
  const place = (): Box => {
    if (sx > 0 && sx + SMALL_W > rowWidth) { sx = 0; sy += SMALL_H + SMALL_GAP }
    const box = { x: sx, y: sy, w: SMALL_W, h: SMALL_H }
    sx += SMALL_W + SMALL_GAP
    return box
  }
  for (const [name, known] of [...small.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    nodes.push({ id: projectId(name), type: 'collapsed', name, known, ...place() })
  }
  const idle = payload.projects
    .filter(p => !expandedNames.has(p.name) && !small.has(p.name))
    .map(p => p.name)
    .sort((a, b) => a.localeCompare(b))
  if (idle.length) nodes.push({ id: 'idle', type: 'idle', names: idle, ...place() })
  const hasSmall = small.size > 0 || idle.length > 0
  const height = hasSmall ? sy + SMALL_H : (expanded.length ? y + rowH : 0)
  width = Math.max(width, hasSmall ? Math.min(rowWidth, Math.max(sx - SMALL_GAP, SMALL_W)) : 0)

  // 4. Edges, now that every end has somewhere to land.
  payload.relations.forEach((rel, i) => {
    if (rel.type === 'engagement') {
      const source = endpoint(rel.from_pid, projectOfSeat(rel.from_seat) ?? rel.from_seat)
      const target = endpoint(rel.to_pid, rel.to_project)
      if (source && target) raw.push(engagementEdge(rel, source, target))
    } else if (rel.type === 'started') {
      if (rel.to_pid === null || !drawnAgents.has(rel.to_pid)) return
      const source = endpoint(rel.from_pid, projectOfSeat(rel.from_seat))
      if (!source) return
      raw.push({
        id: `s:${rel.to_pid}`, source, target: agentId(rel.to_pid), kind: 'started',
        label: 'said to have asked', marker: null,
        detailTitle: 'Who asked for this agent',
        detail: [
          `${rel.from_seat} is recorded as having asked for ${rel.to_seat ?? `pid ${rel.to_pid}`} to be started.`,
          'That is what the start request said. Nothing verified it — a claim, not a measurement.',
        ],
      })
    } else {
      const a = expandedNames.has(rel.from_project)
      const b = expandedNames.has(rel.to_project)
      if (!a && !b) return
      raw.push({
        id: `f:${i}`, source: projectId(rel.from_project), target: projectId(rel.to_project), kind: 'flow',
        label: rel.what, marker: null,
        detailTitle: `${rel.from_project} → ${rel.to_project}`,
        detail: [
          `Declared in the machine's role file: for ${rel.what}, ${rel.from_project} asks ${rel.to_project}${rel.how ? ` (${rel.how})` : ''}.`,
          'A declaration, not traffic: it says who should be asked, not that anyone was.',
        ],
      })
    }
  })

  const byId = new Map(nodes.map(n => [n.id, n]))
  const groups = nodes.filter(n => n.type === 'project')
  const end = (id: string): RouteEnd | null => {
    const node = byId.get(id)
    if (!node) return null
    if (node.type === 'agent') return { box: node, group: byId.get(projectId(node.project)) ?? node, small: false }
    return { box: node, group: node, small: node.type !== 'project' }
  }
  const bottomOfRow = (group: Box) =>
    Math.max(group.y + group.h, ...groups.filter(g => g.y === group.y).map(g => g.y + g.h))
  const edges: MapEdge[] = []
  raw.forEach(e => {
    const s = end(e.source)
    const t = end(e.target)
    if (!s || !t) return
    // The lane is the edge's own position among those drawn, so two edges that
    // share a gutter are next to each other rather than on each other.
    const lane = edges.length
    const points = routeEdge(s, t, lane, bottomOfRow(s.group))
    edges.push({ ...e, points, labelAt: labelPoint(points, 0.2 + 0.15 * (lane % LANES)) })
  })

  // 5. What could not be read, in a fixed order.
  const notices: MapNotice[] = []
  const s = payload.sources
  if (!s.inventory) {
    notices.push({ key: 'inventory', tone: 'warn', text: 'The fleet inventory could not be read: agents are unmeasured, not absent.' })
  }
  if (!s.mandates) {
    notices.push({ key: 'mandates', tone: 'warn', text: 'The mandate store could not be read: an agent drawn without a mandate may have one.' })
  }
  if (!s.bus) {
    notices.push({ key: 'bus', tone: 'warn', text: 'The bus could not be read: engagement states are unmeasured — not open, not answered.' })
  }
  if (s.roles === 'none') {
    notices.push({ key: 'roles', tone: 'info', text: 'No flows are declared: this machine has no role file.' })
  } else if (s.roles !== 'ok') {
    notices.push({ key: 'roles', tone: 'warn', text: 'The role file could not be read: declared flows are unmeasured.' })
  } else if (flows === 0) {
    notices.push({ key: 'roles', tone: 'info', text: 'No flows are declared in the role file.' })
  }
  if (flowsNotDrawn > 0) {
    notices.push({
      key: 'flows-not-drawn', tone: 'info',
      text: `${flowsNotDrawn} declared flow${flowsNotDrawn === 1 ? '' : 's'} between projects with nothing live ${flowsNotDrawn === 1 ? 'is' : 'are'} not drawn.`,
    })
  }

  return {
    nodes, edges, notices,
    counts: { noMandate: payload.counts.no_mandate, waiting: payload.counts.waiting, failed: payload.counts.failed },
    width, height,
  }
}

// --------------------------------------------------------------------------- //
// The opener — what the closed map still has to say
// --------------------------------------------------------------------------- //

export type OpenerSummary =
  /** Not answered yet. Nothing is claimed. */
  | { kind: 'asking' }
  /** The map could not be read. NOT "nothing to report". */
  | { kind: 'unread'; title: string }
  | { kind: 'read'; noMandate: number; waiting: number; failed: number; unmeasured: boolean; title: string }

export function openerSummary(payload: MapPayload | null | undefined, failed: boolean): OpenerSummary {
  if (failed) {
    return { kind: 'unread', title: 'The relation map could not be read. This is not the same as nothing to report.' }
  }
  if (!payload) return { kind: 'asking' }
  const c = payload.counts
  const s = payload.sources
  const unmeasured = !s.inventory || !s.mandates || !s.bus
  const parts = [
    `${c.no_mandate} agent${c.no_mandate === 1 ? '' : 's'} with no mandate`,
    `${c.waiting} request${c.waiting === 1 ? '' : 's'} waiting for a reply`,
    `${c.failed} request${c.failed === 1 ? '' : 's'} that could not be delivered`,
  ]
  if (unmeasured) parts.push('some of this could not be measured — open the map to see which')
  return {
    kind: 'read', noMandate: c.no_mandate, waiting: c.waiting, failed: c.failed, unmeasured,
    title: `Relation map — who exists for what, and who is asking whom. ${parts.join(' · ')}.`,
  }
}
