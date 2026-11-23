/**
 * The map's control and panel through the rendered component.
 *
 * The graph library needs a real layout engine, which jsdom is not, so it is
 * replaced by a stand-in that renders each node with the REAL node components
 * and each edge as a button. What these tests can therefore hold is everything
 * around the canvas: what the closed control says, what the notices say, and
 * that a detail opens out of the flow with its own way out. Whether a detail
 * moves anything on screen is a MEASUREMENT, and it is taken in the browser
 * (`tests/e2e/fleet-map.spec.ts`), not here.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

vi.mock('@xyflow/react', () => {
  const React = require('react')
  return {
    ReactFlowProvider: ({ children }: any) => children,
    ReactFlow: ({ nodes, edges, nodeTypes, onNodeClick, onEdgeClick }: any) => (
      React.createElement('div', { 'data-stub-flow': true },
        nodes.map((n: any) => React.createElement('div', {
          key: n.id, 'data-stub-node': n.id, onClick: (e: any) => onNodeClick(e, n),
        }, React.createElement(nodeTypes[n.type], { data: n.data }))),
        edges.map((e: any) => React.createElement('button', {
          key: e.id, 'data-stub-edge': e.id, 'data-stub-edge-kind': e.data.kind,
          'data-stub-edge-dash': e.style.strokeDasharray ?? 'solid',
          'data-stub-edge-stroke': e.style.stroke, 'data-stub-edge-path': e.data.path,
          onClick: (ev: any) => onEdgeClick(ev, e),
        }, e.data.label)))
    ),
    BaseEdge: () => null,
    EdgeLabelRenderer: ({ children }: any) => children,
    Background: () => null,
    Controls: () => null,
    Handle: () => null,
    Position: { Left: 'left', Right: 'right' },
    MarkerType: { Arrow: 'arrow', ArrowClosed: 'arrowclosed' },
  }
})

import FleetMap from '../../src/components/FleetMap'
import type { MapPayload } from '../../src/lib/fleetMap'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.localStorage.clear() })

const OK = { inventory: true, mandates: true, bus: true, roles: 'ok' }
const PAYLOAD: MapPayload = {
  projects: [
    { name: 'alpha', archived: false, expanded: true, agents: [
      { pid: 1, label: 'alpha-1200', seat: 'alpha#1', state: 'working', population: 'started-here',
        mandate: { id: 'm-1', kind: 'work', goal: 'ship the importer', delivered: true }, mandate_absent: null },
    ] },
    { name: 'beta', archived: false, expanded: true, agents: [
      { pid: 9, label: 'beta-desk', seat: 'beta#9', state: 'quiet', population: 'started-here',
        mandate: null, mandate_absent: { reason: 'not-declared' } },
    ] },
    { name: 'zeta', archived: false, expanded: false, agents: [] },
  ],
  relations: [
    { type: 'engagement', id: 'e-1', from_seat: 'alpha#1', from_pid: 1, to_project: 'beta', to_seat: 'beta#9',
      to_pid: 9, kind: 'REQUEST', subject: 'the export format', state: 'open', reason: null,
      age_seconds: 4000, waiting: true },
    { type: 'started', from_seat: 'alpha#1', from_pid: 1, to_pid: 9, to_seat: 'beta#9', is_claim: true },
    { type: 'flow', from_project: 'alpha', to_project: 'beta', what: 'a new field', how: null },
  ],
  counts: { no_mandate: 1, waiting: 1, failed: 0 },
  sources: { ...OK },
}

function stub(answer: MapPayload | 'down' | 'garbage') {
  vi.stubGlobal('fetch', vi.fn(async () => {
    if (answer === 'down') return { ok: false, status: 500, json: async () => ({}) } as any
    if (answer === 'garbage') return { ok: true, json: async () => ({}) } as any
    return { ok: true, json: async () => answer } as any
  }))
}

async function found(selector: string): Promise<HTMLElement> {
  return waitFor(() => {
    const el = document.querySelector(selector)
    if (!el) throw new Error(`no ${selector} yet`)
    return el as HTMLElement
  })
}

async function openMap(answer: MapPayload | 'down' | 'garbage' = PAYLOAD) {
  stub(answer)
  render(<FleetMap />)
  const toggle = await found(answer === 'down' || answer === 'garbage'
    ? '[data-fleet-map-read="unread"]' : '[data-fleet-map-read="read"]')
  fireEvent.click(toggle)
  return found('[data-fleet-map-panel]')
}

describe('the closed control', () => {
  it('carries both counts without the map being open', async () => {
    stub(PAYLOAD)
    render(<FleetMap />)
    expect((await found('[data-fleet-map-count="no-mandate"]')).textContent).toBe('1 no mandate')
    expect((await found('[data-fleet-map-count="waiting"]')).textContent).toBe('1 waiting')
    expect(document.querySelector('[data-fleet-map-count="failed"]')).toBeNull()
    expect(document.querySelector('[data-fleet-map-panel]')).toBeNull()
  })

  /** Two zeros are what a calm fleet looks like. A failed read is not calm. */
  it.each(['down', 'garbage'] as const)('says the map is unread when the read is %s', async answer => {
    stub(answer)
    render(<FleetMap />)
    expect((await found('[data-fleet-map-count="unread"]')).textContent).toBe('map ?')
    expect(document.querySelector('[data-fleet-map-count="no-mandate"]')).toBeNull()
  })

  it('marks counts that rest on something unmeasured', async () => {
    stub({ ...PAYLOAD, sources: { ...OK, bus: false } })
    render(<FleetMap />)
    await found('[data-fleet-map-count="unmeasured"]')
  })
})

describe('the open map', () => {
  it('draws the agents with their mandate, and marks the one that has none', async () => {
    const panel = await openMap()
    const held = panel.querySelector('[data-fleet-map-agent="alpha-1200"]')!
    const none = panel.querySelector('[data-fleet-map-agent="beta-desk"]')!
    expect(held.textContent).toContain('work')
    expect(held.textContent).toContain('ship the importer')
    expect(held.getAttribute('data-fleet-map-no-mandate')).toBeNull()
    expect(none.getAttribute('data-fleet-map-no-mandate')).toBe('yes')
    expect(none.textContent).toContain('no mandate')
    expect(panel.querySelector('[data-fleet-map-small="idle"]')!.textContent).toBe('1 idle project')
  })

  it('gives each relation kind its own stroke', async () => {
    const panel = await openMap()
    const dash = (kind: string) =>
      panel.querySelector(`[data-stub-edge-kind="${kind}"]`)!.getAttribute('data-stub-edge-dash')
    expect(new Set([dash('engagement'), dash('started'), dash('flow')]).size).toBe(3)
    expect(panel.querySelector('[data-fleet-map-legend]')!.textContent).toMatch(/request.*said to have asked.*declared flow/)
  })

  it('marks a waiting request on its edge, with its age', async () => {
    const panel = await openMap()
    const edge = panel.querySelector('[data-stub-edge="e:e-1"]')!
    expect(edge.textContent).toBe('⚠ waiting · 67m')
    expect(edge.getAttribute('data-stub-edge-stroke')).toBe('#fbbf24')
  })

  it('says which source could not be read', async () => {
    const panel = await openMap({ ...PAYLOAD, sources: { inventory: true, mandates: true, bus: false, roles: 'none' } })
    expect(panel.querySelector('[data-fleet-map-notice="bus"]')!.textContent).toContain('unmeasured')
    expect(panel.querySelector('[data-fleet-map-notice="roles"]')!.textContent).toContain('no role file')
  })

  it('says so when the read failed and there is nothing to draw', async () => {
    const panel = await openMap('down')
    expect(panel.querySelector('[data-fleet-map-notice="stale"]')!.textContent).toContain('no map has been read yet')
    expect(panel.querySelector('[data-stub-flow]')).toBeNull()
  })

  it('closes on its own control', async () => {
    const panel = await openMap()
    fireEvent.click(panel.querySelector('[data-fleet-map-close]')!)
    await waitFor(() => expect(document.querySelector('[data-fleet-map-panel]')).toBeNull())
  })

  it('remembers which edge it is held against', async () => {
    const panel = await openMap()
    expect(panel.getAttribute('data-fleet-map-panel')).toBe('right')
    fireEvent.click(panel.querySelector('[data-fleet-map-dock="bottom"]')!)
    await waitFor(() => expect(document.querySelector('[data-fleet-map-panel]')!.getAttribute('data-fleet-map-panel')).toBe('bottom'))
    expect(window.localStorage.getItem('fleet-map-dock')).toBe('bottom')
  })

  it('floats: the panel is fixed and takes no room from the page', async () => {
    const panel = await openMap()
    expect(panel.className).toMatch(/\bfixed\b/)
  })
})

describe('a detail', () => {
  it('opens for an agent with its mandate, out of the flow, and closes on its own control', async () => {
    const panel = await openMap()
    fireEvent.click(panel.querySelector('[data-stub-node="a:1"]')!)
    const detail = await found('[data-fleet-map-detail]')
    expect(detail.className).toMatch(/\babsolute\b/)
    expect(detail.textContent).toContain('ship the importer')
    expect(detail.textContent).toContain('Instructed to decline')
    // It is a sibling OVER the canvas, not a child that the canvas lays out.
    expect(detail.parentElement!.hasAttribute('data-fleet-map-canvas')).toBe(true)
    fireEvent.click(detail.querySelector('[data-fleet-map-detail-close]')!)
    await waitFor(() => expect(document.querySelector('[data-fleet-map-detail]')).toBeNull())
    expect(document.querySelector('[data-fleet-map-panel]')).toBeTruthy()
  })

  it('opens for a request without showing its text', async () => {
    const panel = await openMap()
    fireEvent.click(panel.querySelector('[data-stub-edge="e:e-1"]')!)
    const detail = await found('[data-fleet-map-detail]')
    expect(detail.textContent).toContain('the export format')
    expect(detail.textContent).toContain('on the bus, not here')
  })

  it('says a start relation is a claim', async () => {
    const panel = await openMap()
    fireEvent.click(panel.querySelector('[data-stub-edge-kind="started"]')!)
    expect((await found('[data-fleet-map-detail]')).textContent).toContain('a claim, not a measurement')
  })

  it('Escape closes the detail first, and the map second', async () => {
    const panel = await openMap()
    fireEvent.click(panel.querySelector('[data-stub-node="a:1"]')!)
    await found('[data-fleet-map-detail]')
    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => expect(document.querySelector('[data-fleet-map-detail]')).toBeNull())
    expect(document.querySelector('[data-fleet-map-panel]')).toBeTruthy()
    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => expect(document.querySelector('[data-fleet-map-panel]')).toBeNull())
  })

  it('a project box opens nothing', async () => {
    const panel = await openMap()
    fireEvent.click(panel.querySelector('[data-stub-node="p:alpha"]')!)
    await new Promise(r => setTimeout(r, 20))
    expect(document.querySelector('[data-fleet-map-detail]')).toBeNull()
  })
})
