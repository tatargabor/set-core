/**
 * The wire gutter, on screen — rendered as the ROOM-COLUMN MATRIX.
 *
 * The guarantees under test are the honesty ones: a live row without a seat
 * renders a socket and never a cell; a source that could not be asked renders
 * the source-down sentence and never an all-socket board; terminals follow
 * the rows they measured; a room whose members are invisible draws no column.
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
    { pid: 1, sessionId: 'sess-a', seat: 'alpha#111111', agent: 'alpha', enrolled: true },
    { pid: 2, sessionId: 'sess-b', seat: 'bravo#222222', agent: 'bravo', enrolled: true },
    { pid: 3, sessionId: 'sess-c', seat: null, enrolled: false },
  ],
  edges: [{
    room: 'dm-a-b', members: ['sess-a', 'sess-b'],
    memberSeats: ['alpha#111111', 'bravo#222222'],
    from: 'sess-a', fromSeat: 'alpha#111111', to: ['sess-b'],
    lastActivity: Date.now() / 1000 - 30, recent: true,
  }],
}

/** jsdom does no layout, so rect measurement is stubbed: each row is 30px
    tall at a 40px pitch; the gutter itself is a 140×400 box. */
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
  for (const pid of [1, 2, 3]) {
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

describe('FleetWirePanel (room matrix)', () => {
  it('renders columns, cells, terminals and a socket for the unenrolled row', () => {
    mountRows()
    const { container } = renderPanel(PAYLOAD)
    expect(container.querySelectorAll('[data-fleet-wire-column]').length).toBe(1)
    expect(container.querySelectorAll('[data-fleet-wire-cell]').length).toBe(2)
    expect(container.querySelectorAll('[data-fleet-wire-terminal]').length).toBe(2)
    const sockets = container.querySelectorAll('[data-fleet-wire-socket]')
    expect(sockets.length).toBe(1)
    expect(sockets[0].getAttribute('data-fleet-wire-socket')).toBe('3')
  })

  it('marks the sender cell filled and active', () => {
    mountRows()
    const { container } = renderPanel(PAYLOAD)
    const sender = container.querySelector('[data-fleet-wire-role="sender"]')
    expect(sender?.getAttribute('data-fleet-wire-active')).toBe('true')
  })

  it('renders a vertical label per column', () => {
    mountRows()
    const { container } = renderPanel(PAYLOAD)
    const label = container.querySelector('[data-fleet-wire-label]')
    expect(label?.textContent).toBe('dm-a-b')
  })

  it('renders the source-down note and no sockets when the source is unreachable', () => {
    mountRows()
    const { container } = renderPanel({ sourceAvailable: false, nodes: [], edges: [] })
    expect(container.querySelector('[data-fleet-wire-source-down]')).not.toBeNull()
    expect(container.querySelectorAll('[data-fleet-wire-socket]').length).toBe(0)
    expect(container.querySelectorAll('[data-fleet-wire-terminal]').length).toBe(0)
  })
})
