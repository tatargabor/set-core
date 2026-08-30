import { describe, expect, it } from 'vitest'

import {
  computeWireLayout, segmentTitle,
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
      { pid: 4, sessionId: 'sess-d', seat: null, enrolled: false },
    ],
    edges: [],
    ...over,
  }
}

function rows(...pids: number[]): RowRect[] {
  return pids.map((pid, i) => ({ pid, top: i * 40, bottom: i * 40 + 30 }))
}

describe('computeWireLayout', () => {
  it('gives every enrolled live row a terminal and an unenrolled row a socket', () => {
    const layout = computeWireLayout({ payload: payload(), rows: rows(1, 2, 4), height: H, gutterWidth: W })
    expect(layout.terminals.map(t => t.pid).sort()).toEqual([1, 2])
    expect(layout.sockets).toEqual([{ pid: 4, y: 80 + 15 }])
    expect(layout.sourceAvailable).toBe(true)
  })

  it('renders nothing but the source-down state when the source is unavailable', () => {
    const layout = computeWireLayout({
      payload: payload({ sourceAvailable: false }),
      rows: rows(1, 2), height: H, gutterWidth: W,
    })
    expect(layout.sourceAvailable).toBe(false)
    expect(layout.terminals).toEqual([])
    expect(layout.segments).toEqual([])
  })

  it('wires a pair channel with one sender-directed segment', () => {
    const p = payload({
      edges: [{
        room: 'dm-a-b', members: ['sess-a', 'sess-b'], memberSeats: ['alpha#111111', 'bravo#222222'],
        from: 'sess-a', fromSeat: 'alpha#111111', to: ['sess-b'],
        lastActivity: 1_000, recent: true,
      }],
    })
    const layout = computeWireLayout({ payload: p, rows: rows(2, 1), height: H, gutterWidth: W })
    expect(layout.segments).toHaveLength(1)
    const seg = layout.segments[0]
    expect(seg.kind).toBe('pair')
    expect(seg.flow).toBe('sender')
    expect(seg.active).toBe(true)
    // Written FROM the sender: starts at alpha's row (pid 1, second row → y 55),
    // even though bravo was measured first. Path direction IS flow direction.
    expect(seg.path.startsWith('M 4 55')).toBe(true)
    expect(seg.path.endsWith('55')).toBe(false)
  })

  it('draws a junction with one fan segment per member for a 3-member channel', () => {
    const p = payload({
      edges: [{
        room: 'war-room', members: ['sess-a', 'sess-b', 'sess-c'],
        memberSeats: ['alpha#111111', 'bravo#222222', 'charlie#333333'],
        from: 'sess-b', fromSeat: 'bravo#222222', to: [],
        lastActivity: 1_000, recent: true,
      }],
    })
    const layout = computeWireLayout({ payload: p, rows: rows(1, 2, 3), height: H, gutterWidth: W })
    expect(layout.junctions).toHaveLength(1)
    expect(layout.segments).toHaveLength(3)
    expect(layout.segments.filter(s => s.flow === 'sender')).toHaveLength(1)
    expect(layout.segments.filter(s => s.flow === 'receiver')).toHaveLength(2)
    // Broadcast (`to` is empty): every receiver segment animates.
    expect(layout.segments.filter(s => s.flow === 'receiver' && s.active).length).toBe(2)
    // Receiver segments are written junction → terminal: they START at the
    // junction x, not at the terminal x — forward dashes move outward.
    for (const seg of layout.segments.filter(s => s.flow === 'receiver')) {
      expect(seg.path.startsWith(`M ${layout.junctions[0].x} `)).toBe(true)
    }
  })

  it('draws a memberless-other channel as a stub to the visible member only', () => {
    const p = payload({
      edges: [{
        room: 'ghost', members: ['sess-a', 'sess-zzz'], memberSeats: ['alpha#111111'],
        from: 'sess-a', to: ['sess-zzz'], lastActivity: null, recent: false,
      }],
    })
    // sess-zzz has no node — the wire must never reach for it. The room still
    // exists and alpha is in it, so one stub wire to alpha renders (the
    // hygiene view), and nothing points at the member nobody carries.
    const layout = computeWireLayout({ payload: p, rows: rows(1), height: H, gutterWidth: W })
    expect(layout.segments).toHaveLength(1)
    expect(layout.segments[0].path.startsWith('M')).toBe(true)
    expect(layout.junctions).toHaveLength(1)
  })

  it('keeps a channel whose endpoint row scrolled out, clamped to the edge', () => {
    const p = payload({
      edges: [{
        room: 'dm-a-b', members: ['sess-a', 'sess-b'], memberSeats: ['alpha#111111', 'bravo#222222'],
        from: 'sess-a', to: ['sess-b'], lastActivity: 1_000, recent: true,
      }],
    })
    // pid 2's row is BELOW the visible gutter (top beyond height). The
    // channel must survive, clamped to the bottom edge — scrolling must not
    // make drawn channels vanish; it only hides the terminal dot.
    const layout = computeWireLayout({
      payload: p,
      rows: [...rows(1), { pid: 2, top: H + 50, bottom: H + 80 }],
      height: H, gutterWidth: W,
    })
    expect(layout.segments).toHaveLength(1)
    expect(layout.segments[0].path.endsWith(` ${H - 2}`)).toBe(true)
    // The off-screen row draws no terminal dot (it would point at nothing).
    expect(layout.terminals.map(t => t.pid)).toEqual([1])
  })

  it('mutes an idle channel', () => {
    const p = payload({
      edges: [{
        room: 'dm-a-b', members: ['sess-a', 'sess-b'], memberSeats: ['alpha#111111', 'bravo#222222'],
        from: 'sess-a', to: ['sess-b'], lastActivity: 1_000, recent: false,
      }],
    })
    const layout = computeWireLayout({ payload: p, rows: rows(1, 2), height: H, gutterWidth: W })
    expect(layout.segments[0].active).toBe(false)
  })

  it('assigns distinct lanes to distinct channels', () => {
    const p = payload({
      edges: [
        {
          room: 'dm-a-b', members: ['sess-a', 'sess-b'], memberSeats: ['alpha#111111', 'bravo#222222'],
          from: 'sess-a', to: ['sess-b'], lastActivity: 1_000, recent: false,
        },
        {
          room: 'dm-b-c', members: ['sess-b', 'sess-c'], memberSeats: ['bravo#222222', 'charlie#333333'],
          from: 'sess-c', to: ['sess-b'], lastActivity: 1_000, recent: false,
        },
      ],
    })
    const layout = computeWireLayout({ payload: p, rows: rows(1, 2, 3), height: H, gutterWidth: W })
    expect(layout.segments).toHaveLength(2)
    const bulgeOf = (d: string) => Number(d.split('C ')[1].split(' ')[0])
    expect(bulgeOf(layout.segments[0].path)).not.toEqual(bulgeOf(layout.segments[1].path))
  })

  it('treats a null payload as an unavailable source, not a crash', () => {
    const layout = computeWireLayout({ payload: null, rows: rows(1), height: H, gutterWidth: W })
    expect(layout.segments).toEqual([])
    expect(layout.terminals).toEqual([])
  })
})

describe('segmentTitle', () => {
  const seg = {
    key: 'k', path: 'M 0 0', flow: 'sender' as const, active: true, kind: 'pair' as const,
    room: 'war-room', memberSeats: ['alpha#111111', 'bravo#222222'], lastActivity: 5_000_000,
    label: { x: 10, y: 10 },
  }
  it('names the channel, members and write age — never message content', () => {
    const title = segmentTitle(seg, 5_000_045_000)
    expect(title).toContain('war-room')
    expect(title).toContain('alpha#111111')
    expect(title).toContain('45s ago')
    expect(title).toContain('sac part war-room')
  })

  it('says when nothing was ever written', () => {
    const title = segmentTitle({ ...seg, lastActivity: null }, 5_000_000_000)
    expect(title).toContain('no recorded write')
  })
})
