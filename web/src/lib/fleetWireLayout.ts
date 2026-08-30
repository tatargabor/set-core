/**
 * The wire view's geometry — pure, testable, component-free.
 *
 * ## Why this is here and not in the component
 *
 * A wire is a claim about two rows and a channel. The component's job is
 * measuring rows and drawing; turning measurements into paths is the part
 * with the rules in it (lane assignment, direction, what happens when a row
 * has vanished), and rules that live in a component are rules nobody can
 * unit test without a DOM.
 *
 * ## The coordinate space
 *
 * Everything is relative to the gutter container's top-left: the caller hands
 * over row rectangles ALREADY RELATIVE to it (viewport rect minus container
 * rect), and every y this file returns is directly an SVG coordinate.
 *
 * ## Direction is path direction
 *
 * Every segment's path is written IN THE FLOW DIRECTION — sender terminal →
 * junction, junction → receiver, sender → receiver for a pair. The CSS
 * animation then needs no direction of its own: dashes moving forward along
 * the path ARE the flow. A segment whose flow starts at the sender carries
 * `flow: 'sender'`; a receiver's carries `flow: 'receiver'` — which only
 * decides where the animation's emphasis sits, never the path.
 */

export interface WireNode {
  pid?: number
  sessionId?: string | null
  seat?: string | null
  agent?: string | null
  enrolled?: boolean
}

export interface WireEdge {
  room?: string
  members?: (string | null)[]
  memberSeats?: (string | null)[]
  from?: string | null
  fromSeat?: string | null
  to?: (string | null)[]
  lastActivity?: number | null
  recent?: boolean
}

export interface ChannelsPayload {
  sourceAvailable?: boolean
  nodes?: WireNode[]
  edges?: WireEdge[]
  activityWindowSeconds?: number
}

/** One live agent row measured on screen, relative to the gutter container. */
export interface RowRect {
  pid: number
  top: number
  bottom: number
}

export interface LayoutInput {
  payload: ChannelsPayload | null
  rows: RowRect[]
  /** Height of the gutter container — the SVG's own height. */
  height: number
  /** Width of the gutter — how far wires may reach into it. */
  gutterWidth: number
}

export interface WireTerminal {
  pid: number
  y: number
  enrolled: boolean
  seat: string | null
}

export interface WireJunction {
  key: string
  x: number
  y: number
  room: string
}

export interface WireSegment {
  key: string
  /** SVG path data, written in the flow direction. */
  path: string
  flow: 'sender' | 'receiver'
  active: boolean
  /** Pair channels animate their one segment both ways; a junction channel's
      receiver segments each carry it. The flag marks junction fan members. */
  kind: 'pair' | 'fan'
  room: string
  memberSeats: string[]
  /** Age of the channel's newest write in seconds, when known. */
  lastActivity: number | null
  /** Where the channel's NAME sits — the wire's midpoint for a pair, above
      the junction for a fan. A channel a reader cannot name is a wire they
      cannot reason about; hover-only identity was measured invisible. */
  label: { x: number; y: number }
}

export interface WireLayout {
  sourceAvailable: boolean
  terminals: WireTerminal[]
  sockets: { pid: number; y: number }[]
  junctions: WireJunction[]
  segments: WireSegment[]
}

const GUTTER_INSET = 4

/** A terminal dot's x — on the gutter's left edge, just inside it. */
export const TERMINAL_X = GUTTER_INSET

/**
 * Turn a channels payload plus measured rows into terminals, junctions and
 * segments. Never throws on a malformed payload: an edge naming a session no
 * node carries is dropped, not a crash — the next poll redraws everything.
 */
export function computeWireLayout(input: LayoutInput): WireLayout {
  const { payload, rows, height, gutterWidth } = input
  if (!payload || payload.sourceAvailable === false) {
    return { sourceAvailable: payload?.sourceAvailable !== false && payload != null, terminals: [], sockets: [], junctions: [], segments: [] }
  }

  // pid → node, session → pid. The join the whole view rests on: edges speak
  // sessions, the screen speaks pids.
  const nodeByPid = new Map<number, WireNode>()
  const pidBySession = new Map<string, number>()
  for (const node of payload.nodes ?? []) {
    if (typeof node.pid !== 'number') continue
    nodeByPid.set(node.pid, node)
    if (node.sessionId) pidBySession.set(node.sessionId, node.pid)
  }
  const yByPid = new Map<number, number>()
  for (const row of rows) {
    if (row.bottom <= 0 || row.top >= height) continue
    yByPid.set(row.pid, (row.top + row.bottom) / 2)
  }

  const terminals: WireTerminal[] = []
  const sockets: { pid: number; y: number }[] = []
  for (const [pid, y] of yByPid) {
    const node = nodeByPid.get(pid)
    if (node?.enrolled) {
      terminals.push({ pid, y, enrolled: true, seat: node.seat ?? null })
    } else {
      // A live row with no seat — the socket, never a wired node. Note the
      // case this cannot happen in: `sourceAvailable: false` already
      // returned above, so `enrolled: false` here is a measurement (the bus
      // was asked and does not know this session), not a guess.
      sockets.push({ pid, y })
    }
  }
  terminals.sort((a, b) => a.y - b.y)

  const clampY = (y: number) => Math.max(2, Math.min(height - 2, y))
  const tx = TERMINAL_X

  // One lane per channel across the gutter, so two channels' wires share the
  // strip instead of overprinting each other.
  const edges = (payload.edges ?? []).filter(e => {
    const members = (e.members ?? []).filter((s): s is string => typeof s === 'string')
    const live = members.filter(s => yByPid.has(pidBySession.get(s) ?? -1))
    // A channel that NEVER had a write draws nothing. Two enrolled seats
    // typically share a dozen dead rooms — measured live: eleven channels,
    // one with a write in the last hour. Drawing all of them buries the one
    // conversation the screen exists to show, which is the same
    // "compacting must not hide a failure" failure in the opposite direction:
    // drawing everything hides what matters.
    return live.length >= 2 && typeof e.room === 'string' && e.lastActivity != null
  })
  const laneX = (index: number) =>
    Math.round(((index + 1) / (edges.length + 1)) * (gutterWidth - tx) + tx)

  const junctions: WireJunction[] = []
  const segments: WireSegment[] = []

  edges.forEach((edge, index) => {
    const room = edge.room as string
    const members = (edge.members ?? []).filter((s): s is string => typeof s === 'string')
    const memberPids = members
      .map(s => pidBySession.get(s))
      .filter((p): p is number => typeof p === 'number' && yByPid.has(p))
    const seats = (edge.memberSeats ?? []).filter((s): s is string => typeof s === 'string')
    const active = edge.recent === true
    const last = typeof edge.lastActivity === 'number' ? edge.lastActivity : null
    const meta = { room, memberSeats: seats, lastActivity: last }

    const lx = laneX(index)
    const ys = memberPids.map(pid => ({ pid, y: clampY(yByPid.get(pid) as number) }))
    const senderPid = edge.from ? pidBySession.get(edge.from) : undefined
    const sender = ys.find(e => e.pid === senderPid) ?? null
    // A sender the screen cannot see (its row is scrolled away or the write
    // came from a non-live seat) degrades to broadcast: every member animates
    // as a receiver from the junction, and nothing claims a direction nobody
    // can see.
    const addressees = new Set(
      (edge.to ?? []).filter((s): s is string => typeof s === 'string')
        .map(s => pidBySession.get(s)))

    if (ys.length === 2) {
      // Pair channel: one wire, bulging into the gutter, drawn from the
      // sender to the receiver. With no visible sender the path direction is
      // top-to-bottom — still motion, never a claim about who sent.
      const [a, b] = ys
      const forward = sender ? sender.pid === a.pid : true
      const [from, to] = forward ? [a, b] : [b, a]
      const bulge = Math.max(lx, tx + 12)
      segments.push({
        key: `${room}:${from.pid}:${to.pid}`,
        path: `M ${tx} ${from.y} C ${bulge} ${from.y}, ${bulge} ${to.y}, ${tx} ${to.y}`,
        flow: sender ? 'sender' : 'receiver',
        active,
        kind: 'pair',
        // Labels live in ONE right-aligned column (see the pair-group
        // staggering below) — a legend column, not text floating on curves.
        label: { x: gutterWidth - 6, y: Math.round((from.y + to.y) / 2) },
        ...meta,
      })
      return
    }

    // Multi-member: a junction in the lane, each member wired to it.
    const junctionY = clampY(ys.reduce((s, e) => s + e.y, 0) / ys.length)
    junctions.push({ key: room, x: lx, y: junctionY, room })
    for (const member of ys) {
      const isSender = sender != null && member.pid === sender.pid
      const flow: 'sender' | 'receiver' = isSender ? 'sender' : 'receiver'
      const emphasize = isSender || addressees.has(member.pid)
      segments.push({
        key: `${room}:${member.pid}`,
        // Written in the flow direction: sender runs terminal → junction,
        // every receiver runs junction → terminal, so forward dashes move
        // outward everywhere.
        path: isSender
          ? `M ${tx} ${member.y} C ${lx} ${member.y}, ${lx} ${junctionY}, ${lx} ${junctionY}`
          : `M ${lx} ${junctionY} C ${lx} ${member.y}, ${lx} ${member.y}, ${tx} ${member.y}`,
        flow,
        active: active && (emphasize || sender == null || addressees.size === 0),
        kind: 'fan',
        // Same label for every fan member — the component renders it once,
        // in the label column, level with the junction.
        label: { x: gutterWidth - 6, y: junctionY - 10 },
        ...meta,
      })
    }
  })

  // Pair channels between the SAME two rows share a midpoint, so their labels
  // would overprint (measured live: `dm-set-core-ff8…` on top of `wpc-board`).
  // Stagger each group's labels vertically around the shared midpoint, ordered
  // by lane so the label column reads in the same order as the wires.
  const pairGroups = new Map<string, WireSegment[]>()
  for (const seg of segments) {
    if (seg.kind !== 'pair') continue
    const key = `${seg.label.y}`
    const group = pairGroups.get(key)
    if (group) group.push(seg)
    else pairGroups.set(key, [seg])
  }
  for (const group of pairGroups.values()) {
    if (group.length < 2) continue
    group.sort((a, b) => a.label.x - b.label.x)
    group.forEach((seg, i) => {
      seg.label = { ...seg.label, y: seg.label.y + (i - (group.length - 1) / 2) * 11 }
    })
  }

  return {
    sourceAvailable: true,
    terminals,
    sockets,
    junctions,
    segments,
  }
}

/** How much room name a 140px gutter can carry at label size. The full name
    rides the hover; a truncated name that FITS beats a full name that
    overprints its neighbours. */
export function labelFor(room: string): string {
  return room.length <= 16 ? room : `${room.slice(0, 15)}…`
}

/** Human sentence for a segment's hover — identity and recency, never content. */
export function segmentTitle(segment: WireSegment, nowMs: number): string {
  const seats = segment.memberSeats.join(', ')
  const age = segment.lastActivity != null
    ? Math.max(0, Math.round((nowMs / 1000) - segment.lastActivity))
    : null
  const when = age == null
    ? 'no recorded write'
    : age < 60
      ? `newest write ${age}s ago`
      : age < 3600
        ? `newest write ${Math.round(age / 60)}m ago`
        : `newest write ${Math.round(age / 3600)}h ago`
  return `${segment.room} — ${seats} — ${when}`
}
