import { describe, expect, it } from 'vitest'

import {
  computeRoomMatrix, cellTitle,
  type ChannelsPayload, type RowRect,
} from '../../src/lib/fleetWireLayout'

const H = 600
const W = 140

function payload(over: Partial<ChannelsPayload> = {}): ChannelsPayload {
  return {
    sourceAvailable: true,
    nodes: [
      { pid: 1, sessionId: 'sess-a', seat: 'alpha#111111', agent: 'alpha', enrolled: true },
      { pid: 2, sessionId: 'sess-b', seat: 'bravo#222222', agent: 'bravo', enrolled: true },
      { pid: 3, sessionId: 'sess-c', seat: 'charlie#333333', agent: 'charlie', enrolled: true },
      { pid: 4, sessionId: 'sess-d', seat: null, enrolled: false, projectSeatCount: 2 },
    ],
    edges: [],
    ...over,
  }
}

function rows(...pids: number[]): RowRect[] {
  return pids.map((pid, i) => ({ pid, top: i * 40, bottom: i * 40 + 30 }))
}

describe('computeRoomMatrix', () => {
  it('gives every enrolled live row a terminal and an unenrolled row a socket', () => {
    const m = computeRoomMatrix({ payload: payload(), rows: rows(1, 2, 4), height: H, gutterWidth: W })
    expect(m.terminals.map(t => t.pid).sort()).toEqual([1, 2])
    expect(m.sockets).toEqual([{ pid: 4, y: 95, projectSeatCount: 2 }])
    expect(m.sourceAvailable).toBe(true)
  })

  it('renders nothing but the source-down state when the source is unavailable', () => {
    const m = computeRoomMatrix({
      payload: payload({ sourceAvailable: false }),
      rows: rows(1, 2), height: H, gutterWidth: W,
    })
    expect(m.sourceAvailable).toBe(false)
    expect(m.columns).toEqual([])
    expect(m.cells).toEqual([])
  })

  it('builds one column per room with members on screen, recent rooms first', () => {
    const p = payload({
      edges: [
        { room: 'wpc-board', members: ['sess-a', 'sess-b'], memberSeats: ['alpha#111111', 'bravo#222222'],
          from: 'sess-b', fromSeat: 'bravo#222222', lastActivity: 5_000, recent: true },
        { room: 'set-glm', members: ['sess-a', 'sess-b'], memberSeats: ['alpha#111111', 'bravo#222222'],
          from: 'sess-a', fromSeat: 'alpha#111111', lastActivity: 5_000_000, recent: false },
      ],
    })
    const m = computeRoomMatrix({ payload: p, rows: rows(1, 2), height: H, gutterWidth: W })
    expect(m.columns.map(c => c.room)).toEqual(['wpc-board', 'set-glm'])
    expect(m.columns[0].x).not.toEqual(m.columns[1].x)
  })

  it('marks the sender cell filled and member cells as members', () => {
    const p = payload({
      edges: [{
        room: 'wpc-board', members: ['sess-a', 'sess-b'], memberSeats: ['alpha#111111', 'bravo#222222'],
        from: 'sess-b', fromSeat: 'bravo#222222', lastActivity: 1_000, recent: true,
      }],
    })
    const m = computeRoomMatrix({ payload: p, rows: rows(1, 2), height: H, gutterWidth: W })
    expect(m.cells).toHaveLength(2)
    const sender = m.cells.find(c => c.role === 'sender')
    expect(sender?.pid).toBe(2)
    expect(sender?.active).toBe(true)
    expect(m.cells.filter(c => c.role === 'member')).toHaveLength(1)
  })

  it('draws a single-member room as one stub cell — the hygiene view', () => {
    const p = payload({
      edges: [{
        room: 'probe-fresh', members: ['sess-a'], memberSeats: ['alpha#111111'],
        fromSeat: null, lastActivity: null, recent: false,
      }],
    })
    const m = computeRoomMatrix({ payload: p, rows: rows(1, 4), height: H, gutterWidth: W })
    expect(m.columns.map(c => c.room)).toEqual(['probe-fresh'])
    expect(m.cells).toHaveLength(1)
    expect(m.cells[0].pid).toBe(1)
    expect(m.cells[0].active).toBe(false)
  })

  it('draws no column for a room whose members are all off-screen', () => {
    const p = payload({
      edges: [{
        room: 'offscreen', members: ['sess-z'], memberSeats: ['z#000000'],
        lastActivity: 1_000, recent: true,
      }],
    })
    const m = computeRoomMatrix({ payload: p, rows: rows(1), height: H, gutterWidth: W })
    expect(m.columns).toEqual([])
    expect(m.cells).toEqual([])
  })

  it('keeps the column when a member row scrolls out, but draws only on-screen cells', () => {
    const p = payload({
      edges: [{
        room: 'wpc-board', members: ['sess-a', 'sess-b'], memberSeats: ['alpha#111111', 'bravo#222222'],
        from: 'sess-a', fromSeat: 'alpha#111111', lastActivity: 1_000, recent: true,
      }],
    })
    const m = computeRoomMatrix({
      payload: p,
      rows: [...rows(1), { pid: 2, top: H + 50, bottom: H + 80 }],
      height: H, gutterWidth: W,
    })
    // The room is still on screen through alpha, so its column persists —
    // scrolling must not erase channels. But a cell floating at the edge
    // with no row under it would be noise: bravo simply has no cell while
    // its row is off-screen, and no terminal dot either.
    expect(m.columns.map(c => c.room)).toEqual(['wpc-board'])
    expect(m.cells.map(c => c.pid)).toEqual([1])
    expect(m.terminals.map(t => t.pid)).toEqual([1])
  })

  it('treats a null payload as an unavailable source, not a crash', () => {
    const m = computeRoomMatrix({ payload: null, rows: rows(1), height: H, gutterWidth: W })
    expect(m.columns).toEqual([])
    expect(m.terminals).toEqual([])
  })
})

describe('cellTitle', () => {
  it('names the room, members and write age, and carries the prune hint', () => {
    const title = cellTitle('war-room', ['alpha#111111', 'bravo#222222'], 5_000_000, 5_000_045_000)
    expect(title).toContain('war-room')
    expect(title).toContain('45s ago')
    expect(title).toContain('sac part war-room')
  })

  it('says when nothing was ever written', () => {
    const title = cellTitle('ghost', ['alpha#111111'], null, 5_000_000_000)
    expect(title).toContain('no recorded write')
  })
})
