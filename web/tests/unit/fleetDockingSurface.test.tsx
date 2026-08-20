/**
 * Docking, on the real screen, driven by clicking the control a person clicks.
 *
 * The geometry module and the band component each have their own tests. What
 * neither can show is the claim that actually matters here — that docking MOVES
 * a panel rather than copying it, and that the space comes back when it is
 * undocked. Both are properties of the page, and both fail in the reassuring
 * direction: a duplicated panel looks like a working feature until you notice
 * the two copies disagree, and space that never returns looks like a layout.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function agent(pid: number, name: string, over: Json = {}): Json {
  return {
    pid, name, project: 'demo', branch: 'main', session_id: 'abc',
    binding_confirmed: true, sources: ['process'], kind: 'interactive',
    state: 'quiet', tool: null, tool_elapsed_seconds: null, other_tools: [],
    last_movement_seconds: 12, unknown_reason: null,
    population: 'started-here', terminal_label: `t-${pid}`, ...over,
  }
}

const body = {
  agents: 2, working: 0, unknown: 0,
  owner_reachable: true,
  projects: [{
    name: 'demo', root: '/home/x/demo', sources: ['process'], archived: false,
    agents: [agent(1, 'one'), agent(2, 'two')],
  }],
  quiet_means: 'x',
}

/** Layout answers, and every write recorded so the test can inspect them. */
function installFetch(layout: Json = {}) {
  const writes: { url: string; body: Json }[] = []
  let current: Json = {
    version: 1, groups: [], parked: [], ungrouped: ['demo'], missing: [],
    splits: {}, docks: [], ...layout,
  }
  const stub = vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout/docks') && init?.method === 'PUT') {
      const sent = JSON.parse(String(init.body)) as Json
      writes.push({ url: u, body: sent })
      current = { ...current, docks: sent.docks }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(sent) } as unknown as Response)
    }
    if (u.includes('/api/fleet/layout/splits') && init?.method === 'PUT') {
      const sent = JSON.parse(String(init.body)) as Json
      writes.push({ url: u, body: sent })
      return Promise.resolve({ ok: true, json: () => Promise.resolve(sent) } as unknown as Response)
    }
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(current) } as unknown as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({
        ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }),
      } as unknown as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response)
  })
  vi.stubGlobal('fetch', stub)
  return { writes }
}

beforeEach(() => {
  vi.useRealTimers()
  try { localStorage.clear() } catch { /* no storage here */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

async function ready(container: HTMLElement) {
  await screen.findByText('demo')
  await waitFor(() => {
    if (!container.querySelector('[data-tile-dock]')) throw new Error('no dock control yet')
  })
}

describe('sending a panel to an edge', () => {
  it('offers one control per edge, so the reader picks and the screen does not', async () => {
    installFetch()
    const { container } = render(<Fleet />)
    await ready(container)
    const controls = container.querySelector('[data-tile-dock]') as HTMLElement
    for (const edge of ['left', 'right', 'top', 'bottom']) {
      expect(controls.querySelector(`[data-tile-control="dock-${edge}"]`)).not.toBeNull()
    }
  })

  it('persists the docking to its own route, not to the version-guarded PUT', async () => {
    const { writes } = installFetch()
    const { container } = render(<Fleet />)
    await ready(container)
    ;(container.querySelector('[data-tile-control="dock-right"]') as HTMLElement).click()
    await waitFor(() => expect(writes.length).toBeGreaterThan(0))
    expect(writes[0].url).toContain('/api/fleet/layout/docks')
    expect(writes[0].body).toEqual({ docks: [{ kind: 'agent', id: 't-1', edge: 'right' }] })
  })

  it('MOVES the panel — it does not leave a copy in the grid', async () => {
    // The claim neither module test can make. A duplicated panel looks like a
    // working feature until the two copies disagree, and the one nobody is
    // watching is the one that goes stale.
    installFetch({ docks: [{ kind: 'agent', id: 't-1', edge: 'right' }] })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    await waitFor(() => {
      if (!container.querySelector('[data-fleet-dock]')) throw new Error('not docked yet')
    })
    const tiles = container.querySelectorAll('[data-tile-controls]')
    // Two agents, one docked: exactly two tiles in total, not three.
    expect(tiles.length).toBe(2)
    expect(container.querySelectorAll('[data-fleet-dock]').length).toBe(1)
  })

  it('renders the band on the edge it was docked to', async () => {
    installFetch({ docks: [{ kind: 'agent', id: 't-2', edge: 'bottom' }] })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const band = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock]')
      if (!el) throw new Error('no band')
      return el
    })
    expect(band.getAttribute('data-fleet-dock-edge')).toBe('bottom')
    expect(band.getAttribute('data-fleet-dock')).toBe('t-2')
  })
})

describe('bringing it back', () => {
  it('undocks by pressing the edge it is already on, so the control is never a dead end', async () => {
    const { writes } = installFetch({ docks: [{ kind: 'agent', id: 't-1', edge: 'right' }] })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const band = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock]')
      if (!el) throw new Error('no band')
      return el as HTMLElement
    })
    // The docked panel's own tile carries the control, showing the edge as active.
    const active = band.querySelector('[data-tile-control="dock-right"][data-tile-control-active="on"]')
    expect(active).not.toBeNull()
    ;(active as HTMLElement).click()
    await waitFor(() => expect(writes.length).toBeGreaterThan(0))
    expect(writes[writes.length - 1].body).toEqual({ docks: [] })
  })

  it('returns the space — the band is gone and the agent is back in the grid', async () => {
    installFetch({ docks: [{ kind: 'agent', id: 't-1', edge: 'right' }] })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const band = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock]')
      if (!el) throw new Error('no band')
      return el as HTMLElement
    })
    ;(band.querySelector('[data-tile-control="dock-right"]') as HTMLElement).click()
    await waitFor(() => {
      if (container.querySelector('[data-fleet-dock]')) throw new Error('still docked')
    })
    expect(container.querySelectorAll('[data-tile-controls]').length).toBe(2)
  })
})

describe('two edges at once', () => {
  it('renders a band on each and leaves the grid what is left', async () => {
    installFetch({
      docks: [
        { kind: 'agent', id: 't-1', edge: 'right' },
        { kind: 'agent', id: 't-2', edge: 'top' },
      ],
    })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    await waitFor(() => {
      if (container.querySelectorAll('[data-fleet-dock]').length !== 2) throw new Error('not both')
    })
    const edges = [...container.querySelectorAll('[data-fleet-dock]')]
      .map(el => el.getAttribute('data-fleet-dock-edge'))
    expect(new Set(edges)).toEqual(new Set(['right', 'top']))
  })
})

describe('a docked panel whose agent is gone', () => {
  it('says the panel was kept rather than rendering an empty band', async () => {
    // A blank band is indistinguishable from a broken one, and the reader would
    // conclude the screen lost something.
    installFetch({ docks: [{ kind: 'agent', id: 't-999', edge: 'right' }] })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const band = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock]')
      if (!el) throw new Error('no band')
      return el as HTMLElement
    })
    expect(band.textContent).toMatch(/kept, not closed/i)
  })

  it('reports its failing count as UNKNOWN, not as zero', async () => {
    // There is no agent to ask, so "nothing is wrong" would be a claim of calm
    // nobody measured — the false-absence class.
    installFetch({ docks: [{ kind: 'agent', id: 't-999', edge: 'right' }] })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const marker = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock-marker]')
      if (!el) throw new Error('no marker')
      return el
    })
    expect(marker.getAttribute('data-fleet-dock-failing')).toBe('unknown')
  })
})
