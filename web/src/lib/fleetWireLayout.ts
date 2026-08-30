/**
 * The wire view's geometry — a ROOM-COLUMN MATRIX.
 *
 * ## The shape, and why it replaced freeform wires
 *
 * Rows are agents (as on the board), columns are rooms, and each membership
 * is a cell where its row crosses its column. The user designed this on the
 * live screen: freeform wires between two seats degenerated into an
 * unreadable sheaf once seats shared several channels, and the hygiene
 * question — WHICH rooms does this seat hold, which are unwanted — is a
 * scanning question, and scanning is what a matrix is for. Room names run
 * VERTICALLY down their column; a room no visible agent belongs to draws no
 * column at all.
 *
 * ## The coordinate space
 *
 * Everything is relative to the gutter container's top-left: the caller
 * hands over row rectangles ALREADY RELATIVE to it, and every y this file
 * returns is directly an SVG coordinate. Column headers sit at a FIXED y at
 * the top (they label the column, not any row); cells move with their rows.
 *
 * ## Direction is the cell, not an arrow
 *
 * A channel's newest write has a sender. The sender's cell renders FILLED
 * and, when the write is fresh, animated; every other member's cell renders
 * a bright ring; an idle membership renders a dim ring. Who-sent-what is
 * readable from which cell is filled — no arrows needed in a grid.
 */

export interface WireNode {
  pid?: number
  sessionId?: string | null
  seat?: string | null
  agent?: string | null
  enrolled?: boolean
  /** Seats sharing this node's project root, when the node itself is
      unjoined — session drift, and the surface says "re-enrol". */
  projectSeatCount?: number
}

export interface WireEdge {
  room?: string
  members?: (string | null)[]
  memberSeats?: (string | null)[]
  from?: string | null
  fromSeat?: string | null
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
  /** Width of the gutter — how far the columns may spread. */
  gutterWidth: number
  /** Fold every `dm-` pair room into ONE column (`+N direct`). Default TRUE:
      pair rooms are private by nature — their value on this screen is "how
      many and how loud", not their per-room traffic — and N of them crowd the
      work rooms out of a 140px gutter. The surface expands them on click. */
  collapseDirect?: boolean
}

export interface WireTerminal {
  pid: number
  y: number
  enrolled: boolean
  seat: string | null
}

export interface RoomColumn {
  room: string
  /** The column's x — where its guide line, header and cells sit. */
  x: number
  recent: boolean
  /** Age of the room's newest write in seconds, when known. */
  lastActivity: number | null
  memberSeats: string[]
  /** The text the label shows, when it is not the room name — the collapsed
      direct-messages column reads `+N direct`. */
  label?: string
  /** This column is the FOLDED group of pair rooms: clicking it expands. */
  isDirectGroup?: boolean
  /** How many pair rooms the fold holds — the N in `+N direct`. */
  directCount?: number
}

export interface RoomCell {
  key: string
  pid: number
  room: string
  x: number
  y: number
  /** sender = this seat made the room's newest write; member = sits in it. */
  role: 'sender' | 'member'
  active: boolean
}

export interface RoomMatrix {
  sourceAvailable: boolean
  /** The width the caller should render at — echoed back by the component's
      two-pass width choice, so the SVG and its container agree. */
  width?: number
  columns: RoomColumn[]
  cells: RoomCell[]
  terminals: WireTerminal[]
  sockets: { pid: number; y: number; projectSeatCount: number | null }[]
}

/** Where the column headers live — a fixed band at the gutter's top. */
export const HEADER_Y = 14

/** The synthetic room name the folded pair-room column carries. Not a real
    room — no sac room is named `dm` — so it can never collide with one. */
export const DIRECT_ROOM = 'dm'

/** One human age line, shared by every hover that names a write age. */
export function ageLine(last: number | null, nowSeconds: number): string {
  if (last == null) return 'no recorded write'
  const age = Math.max(0, Math.round(nowSeconds - last))
  return age < 60 ? `${age}s ago`
    : age < 3600 ? `${Math.round(age / 60)}m ago`
    : `${Math.round(age / 3600)}h ago`
}

/** How alive a room is, in three steps instead of the binary recent: a room
    written to seconds ago is a DIFFERENT thing from one written to twenty
    minutes back, and the old two-state view flattened exactly that. */
export const FRESH_SECONDS = 120

export type AgeBucket = 'fresh' | 'warm' | 'idle'

export function ageBucket(
  lastActivity: number | null,
  nowMs: number,
  windowSeconds: number = 1800,
): AgeBucket {
  if (lastActivity == null) return 'idle'
  const age = Math.max(0, nowMs / 1000 - lastActivity)
  if (age < FRESH_SECONDS) return 'fresh'
  if (age < windowSeconds) return 'warm'
  return 'idle'
}

/** The seat name a cell's hover shows, and the prune hint every hover
    carries — the inactive columns exist to be JUDGED and left. */
export function cellTitle(room: string, seats: string[], lastActivity: number | null, nowMs: number): string {
  return `${room} — ${seats.join(', ')} — newest write ${ageLine(lastActivity, nowMs / 1000)} — leave it: sac part ${room}`
}

/** The folded pair-room column's hover line — not one room, so the default
    room title would misdescribe it. Count and newest write, then the act. */
export function directGroupTitle(count: number, lastActivity: number | null, nowMs: number): string {
  return `${count} direct-message rooms — newest write ${ageLine(lastActivity, nowMs / 1000)} — click to expand them`
}

/**
 * Turn a channels payload plus measured rows into the room matrix. Never
 * throws on a malformed payload: an edge naming a session no node carries is
 * dropped, not a crash — the next poll redraws everything.
 */
export function computeRoomMatrix(input: LayoutInput): RoomMatrix {
  const { payload, rows, height, gutterWidth } = input
  if (!payload || payload.sourceAvailable === false) {
    return { sourceAvailable: false, columns: [], cells: [], terminals: [], sockets: [] }
  }

  const nodeByPid = new Map<number, WireNode>()
  const pidBySession = new Map<string, number>()
  for (const node of payload.nodes ?? []) {
    if (typeof node.pid !== 'number') continue
    nodeByPid.set(node.pid, node)
    if (node.sessionId) pidBySession.set(node.sessionId, node.pid)
  }

  // A row scrolled out of the gutter keeps its CELLS clamped to the edge it
  // exited through — scrolling must never make drawn data vanish (measured
  // live when this was a wire view). Only the row's own terminal dot is
  // suppressed: a dot at the edge points at nothing.
  const clampY = (y: number) => Math.max(2, Math.min(height - 2, y))
  const yByPid = new Map<number, { y: number; onScreen: boolean }>()
  for (const row of rows) {
    const mid = (row.top + row.bottom) / 2
    yByPid.set(row.pid, { y: clampY(mid), onScreen: row.bottom > 0 && row.top < height })
  }

  const terminals: WireTerminal[] = []
  const sockets: RoomMatrix['sockets'] = []
  for (const [pid, pos] of yByPid) {
    if (!pos.onScreen) continue
    const node = nodeByPid.get(pid)
    if (node?.enrolled) {
      terminals.push({ pid, y: pos.y, enrolled: true, seat: node.seat ?? null })
    } else {
      sockets.push({ pid, y: pos.y, projectSeatCount: node?.projectSeatCount ?? null })
    }
  }
  terminals.sort((a, b) => a.y - b.y)

  // The columns: every room at least one VISIBLE enrolled agent sits in. A
  // room whose members are all off-screen or unenrolled draws nothing — the
  // user's own rule: rooms of non-showing projects are not visualized.
  const seatToPid = new Map<string, number>()
  for (const node of payload.nodes ?? []) {
    if (node.enrolled && node.seat && typeof node.pid === 'number') seatToPid.set(node.seat, node.pid)
  }
  const byRoom = new Map<string, {
    seats: string[]; visibleSeats: string[]; recent: boolean; last: number | null; senderSeat: string | null
  }>()
  for (const edge of payload.edges ?? []) {
    const room = edge.room
    if (typeof room !== 'string') continue
    const seats = (edge.memberSeats ?? []).filter((s): s is string => typeof s === 'string')
    const visible = seats.filter(s => {
      const pid = seatToPid.get(s)
      return pid != null && yByPid.get(pid)?.onScreen === true
    })
    if (visible.length === 0) continue
    byRoom.set(room, {
      seats: visible,
      visibleSeats: visible,
      recent: edge.recent === true,
      last: typeof edge.lastActivity === 'number' ? edge.lastActivity : null,
      senderSeat: edge.fromSeat ?? null,
    })
  }

  // Recent rooms lead — the active conversation is the leftmost column, the
  // ones to prune trail to the right. Ties break by name so the order does
  // not jitter between polls. Pair rooms fold into ONE entry first, so the
  // folded column takes the newest write among them and sits by it.
  type RoomInfo = { seats: string[]; visibleSeats: string[]; recent: boolean
                    last: number | null; senderSeat: string | null; roomCount?: number }
  const isDirect = (room: string) => room.startsWith('dm-')
  let entries = [...byRoom.entries()] as [string, RoomInfo][]
  if (input.collapseDirect !== false) {
    const direct = entries.filter(([room]) => isDirect(room))
    if (direct.length > 1) {
      const seatOrder: string[] = []
      for (const [, info] of direct) {
        for (const seat of info.seats) if (!seatOrder.includes(seat)) seatOrder.push(seat)
      }
      const folded: RoomInfo = {
        seats: seatOrder,
        visibleSeats: seatOrder,
        recent: direct.some(([, info]) => info.recent),
        last: direct.reduce<number | null>((acc, [, info]) =>
          info.last != null && (acc == null || info.last > acc) ? info.last : acc, null),
        senderSeat: null, // a fold has no single sender — cells stay member rings
        roomCount: direct.length,
      }
      entries = [[DIRECT_ROOM, folded] as [string, RoomInfo],
                 ...entries.filter(([room]) => !isDirect(room))]
    }
  }
  const rooms = entries.sort((a, b) => {
    if (a[1].recent !== b[1].recent) return a[1].recent ? -1 : 1
    // Same recency class: the genuinely newer write leads, and only an exact
    // tie (or two rooms with no writes at all) falls back to the name.
    const al = a[1].last ?? -1
    const bl = b[1].last ?? -1
    if (al !== bl) return bl - al
    return a[0].localeCompare(b[0])
  })
  const columns: RoomColumn[] = rooms.map(([room, info], i) => ({
    room,
    x: Math.round(((i + 1) / (rooms.length + 1)) * (gutterWidth - 24) + 12),
    recent: info.recent,
    lastActivity: info.last,
    memberSeats: info.seats,
    ...(info.roomCount != null && room === DIRECT_ROOM ? {
      label: `+${info.roomCount} direct`,
      isDirectGroup: true,
      directCount: info.roomCount,
    } : {}),
  }))
  const colX = new Map(columns.map(c => [c.room, c.x]))

  const cells: RoomCell[] = []
  for (const [room, info] of rooms) {
    const x = colX.get(room) as number
    for (const seat of info.visibleSeats) {
      const pid = seatToPid.get(seat)
      if (pid == null) continue
      const pos = yByPid.get(pid)
      if (!pos) continue
      cells.push({
        key: `${room}:${pid}`,
        pid, room, x, y: pos.y,
        role: info.senderSeat === seat ? 'sender' : 'member',
        active: info.recent,
      })
    }
  }

  return {
    sourceAvailable: true,
    columns,
    cells,
    terminals,
    sockets,
  }
}
