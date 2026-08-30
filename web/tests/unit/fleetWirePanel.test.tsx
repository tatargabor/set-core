/**
 * The wire gutter, on screen.
 *
 * The guarantees under test are the honesty ones: a live row without a seat
 * renders a socket and never a wire; a source that could not be asked renders
 * the source-down sentence and never an all-socket board; terminals follow
 * the rows they measured. Pair-vs-junction rendering is the layout lib's
 * contract (see fleetWireLayout.test.ts); here it is asserted once each as a
 * render smoke check.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render } from '@testing-library/react'

import FleetWirePanel from '../../src/components/FleetWirePanel'
import type { ChannelsPayload } from '../../src/lib/fleetWireLayout'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

const PAYLOAD: ChannelsPayload = {
  sourceAvailable: true,
  nodes: [
    { pid: 11, sessionId: 'sess-a', seat: 'alpha#111111', agent: 'alpha', enrolled: true },
    { pid: 12, sessionId: 'sess-b', seat: 'bravo#222222', agent: 'bravo', enrolled: true },
    { pid: 13, sessionId: 'sess-c', seat: null, enrolled: false },
  ],
  edges: [{
    room: 'dm-a-b', members: ['sess-a', 'sess-b'],
    memberSeats: ['alpha#111111', 'bravo#222222'],
    from: 'sess-a', fromSeat: 'alpha#111111', to: ['sess-b'],
    lastActivity: Date.now() / 1000 - 30, recent: true,
  }],
}

/** Two live agent rows in the document, as the column's tree renders them.
    jsdom does no layout, so rect measurement is stubbed: each row is 30px
    tall, stacked at 40px pitch — the geometry the assertions below read. */
function mountRows() {
  const proto = Element.prototype as Element & {
    getBoundingClientRect: () => DOMRect
  }
  proto.getBoundingClientRect = function () {
    const el = this as HTMLElement
    if (el.getAttribute?.('data-fleet-wire-gutter') !== null) {
      return { x: 0, y: 0, width: 140, height: 400, top: 0, left: 0, right: 140, bottom: 400, toJSON: () => ({}) } as DOMRect
    }
    const pid = Number(el.getAttribute?.('data-fleet-agent-row'))
    const top = Number.isFinite(pid) ? (pid % 10) * 40 : 0
    return {
      x: 0, y: top, width: 200, height: 30, top, left: 0, right: 200, bottom: top + 30,
      toJSON: () => ({}),
    } as DOMRect
  }
  for (const pid of [11, 12, 13]) {
    const row = document.createElement('button')
    row.setAttribute('data-fleet-agent-row', String(pid))
    document.body.appendChild(row)
  }
}

function renderPanel(payload: ChannelsPayload | null) {
  return render(
    <div style={{ position: 'relative', height: 400 }}>
      <FleetWirePanel payload={payload} />
    </div>,
  )
}

describe('FleetWirePanel', () => {
  it('renders terminals for enrolled rows and a socket for the unenrolled one', () => {
    mountRows()
    const { container } = renderPanel(PAYLOAD)
    const terminals = container.querySelectorAll('[data-fleet-wire-terminal]')
    expect(terminals.length).toBe(2)
    const sockets = container.querySelectorAll('[data-fleet-wire-socket]')
    expect(sockets.length).toBe(1)
    expect(sockets[0].getAttribute('data-fleet-wire-socket')).toBe('13')
    // The enrolled pair's channel drew its wire.
    expect(container.querySelectorAll('[data-fleet-wire-segment]').length).toBe(1)
    expect(container.querySelector('[data-fleet-wire-segment="dm-a-b"]')).not.toBeNull()
  })

  it('marks an animated wire as active and sender-flowed', () => {
    mountRows()
    const { container } = renderPanel(PAYLOAD)
    const seg = container.querySelector('[data-fleet-wire-segment]')
    expect(seg?.getAttribute('data-fleet-wire-active')).toBe('true')
    expect(seg?.getAttribute('data-fleet-wire-flow')).toBe('sender')
  })

  it('renders the source-down note and no sockets when the source is unreachable', () => {
    mountRows()
    const { container } = renderPanel({ sourceAvailable: false, nodes: [], edges: [] })
    expect(container.querySelector('[data-fleet-wire-source-down]')).not.toBeNull()
    // Never an all-socket board: without a measurement, no enrolment claim.
    expect(container.querySelectorAll('[data-fleet-wire-socket]').length).toBe(0)
    expect(container.querySelectorAll('[data-fleet-wire-terminal]').length).toBe(0)
  })

  it('renders a junction for a multi-member channel', () => {
    mountRows()
    const p: ChannelsPayload = {
      sourceAvailable: true,
      nodes: PAYLOAD.nodes,
      edges: [{
        room: 'war-room', members: ['sess-a', 'sess-b'], memberSeats: ['alpha#111111', 'bravo#222222'],
        from: 'sess-a', to: [], lastActivity: null, recent: false,
      }],
    }
    // Two visible members only — still renders through the junction path? No:
    // two visible members is a pair. A third row is needed for a junction.
    const third = document.createElement('button')
    third.setAttribute('data-fleet-agent-row', '99')
    document.body.appendChild(third)
    const withThird: ChannelsPayload = {
      ...p,
      nodes: [...(p.nodes ?? []), { pid: 99, sessionId: 'sess-x', seat: 'x#abc123', enrolled: true }],
      edges: [{ ...p.edges![0], members: ['sess-a', 'sess-b', 'sess-x'] }],
    }
    const { container } = renderPanel(withThird)
    expect(container.querySelector('[data-fleet-wire-junction="war-room"]')).not.toBeNull()
    expect(container.querySelectorAll('[data-fleet-wire-segment]').length).toBe(3)
  })
})
